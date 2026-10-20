"""Opt-in native-rig seat clips from separately validated local archives."""
from pathlib import Path
import hashlib
import json


def _path(value):
    if value is None:return ''
    method = getattr(value, '_path_name', None)
    if callable(method):return str(method())
    value = str(value)
    return value.split("'")[1] if "'" in value else value


def definition(mesh, state):
    if 'native_seat_definition' in state:return state['native_seat_definition']
    state['native_seat_definition'] = None
    root = Path(__file__).parent.parent
    config = root/'data/native_seat_animations.json'
    if not config.is_file():return None
    try:
        skeleton = _path(mesh.GetSkinnedAsset().Skeleton)
        rows = json.loads(config.read_text(encoding='utf-8'))
        for row in rows.values():
            if row.get('enabled') is not True or row.get('mesh_skeleton') != skeleton:continue
            archives = row.get('archives',{})
            if len(archives)!=3 or {Path(n).suffix for n in archives}!={'.pak','.utoc','.ucas'}:continue
            folder = root/'assets/native_character_animations'
            if any(Path(name).name!=name or not (folder/name).is_file() or
                   hashlib.sha256((folder/name).read_bytes()).hexdigest()!=digest for name,digest in archives.items()):continue
            path = row.get('animation','')
            if not path.startswith('/Game/ImportedCharacters/NativeAmaraSeat/') or '..' in path:continue
            state['native_seat_definition'] = row
            return row
    except Exception as exc:
        state['native_seat_error'] = str(exc)
    return None


def restore(state):
    saved = state.pop('native_seat_clip',None)
    if saved is None:return
    mesh = saved['mesh']()
    if mesh is None:return
    owned = saved.get('instance')
    current = mesh.GetAnimInstance()
    lost = current is None and int(mesh.GetAnimationMode()) == 1
    if owned is not None and str(current)!=str(owned()) and not lost:return
    original = saved['class']() if saved['class'] else None
    if original is not None:mesh.SetAnimInstanceClass(original)
    mesh.SetAnimationMode(saved['mode'], True)


def load_clip(path):
    """Load through UE's reflected asset API; SDK LoadPackage misses this build."""
    import unrealsdk
    try:asset = unrealsdk.find_object('AnimSequence',path)
    except ValueError:asset = None
    if asset is not None:return asset
    package,name = path.rsplit('.',1)
    asset_class = unrealsdk.make_struct('TopLevelAssetPath',PackageName='/Script/Engine',AssetName='AnimSequence')
    data = unrealsdk.make_struct('AssetData',PackageName=package,
        PackagePath=package.rsplit('/',1)[0],AssetName=name,AssetClassPath=asset_class)
    library = unrealsdk.find_class('AssetRegistryHelpers').ClassDefaultObject
    # SDK wraps this call's return and out parameters in a tuple. Resolve the
    # exact UObject after the engine has loaded it instead of trusting shape.
    library.GetAsset(data)
    asset = unrealsdk.find_object('AnimSequence',path)
    if asset is None:raise ValueError('Engine asset API could not load seat clip: '+path)
    return asset


def update(state, mesh, driving):
    if not driving:state['native_seat_recoveries'] = 0
    saved = state.get('native_seat_clip')
    if saved is not None:
        owned = saved.get('instance')
        current = mesh.GetAnimInstance()
        same_mesh = str(saved['mesh']())==str(mesh)
        if driving and same_mesh and current is not None and owned is not None and str(current)==str(owned()):
            return 'source_seated'
        lost = driving and same_mesh and current is None and int(mesh.GetAnimationMode()) == 1
        restore(state)
        if lost:
            attempts = state.get('native_seat_recoveries',0) + 1
            state['native_seat_recoveries'] = attempts
            if attempts > 3:
                state['native_seat_error'] = 'Engine repeatedly cleared the seat animation instance'
                return None
        elif driving:
            # Respect a foreign animation change until the next apply.
            state['native_seat_definition'] = None
            return None
    if not driving:return None
    row = definition(mesh,state)
    if row is None or state.get('native_seat_error'):return None
    import unrealsdk
    from unrealsdk.unreal import WeakPointer
    try:
        asset = load_clip(row['animation'])
        if asset is None or _path(asset.Skeleton)!=_path(mesh.GetSkinnedAsset().Skeleton):
            raise ValueError('Seat animation does not match this native skeleton')
        original = mesh.AnimClass
        saved = {'mesh':WeakPointer(mesh),'class':WeakPointer(original) if original is not None else None,
                 'mode':int(mesh.GetAnimationMode()),'instance':None}
        state['native_seat_clip'] = saved
        mesh.PlayAnimation(asset,True)
        instance = mesh.GetAnimInstance()
        if instance is None:raise ValueError('Seat animation did not create an instance')
        saved['instance'] = WeakPointer(instance)
        return 'source_seated'
    except Exception as exc:
        restore(state)
        state['native_seat_error'] = str(exc)
        return None
