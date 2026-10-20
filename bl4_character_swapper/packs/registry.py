"""Read installed, data-only pack manifests. Does not import the game SDK."""
from pathlib import Path
import hashlib
import json
import re
import sys
import math
import base64

SCHEMA = 'squ1ggs.appearance_pack.v1'
_packs = {}
_errors = []
_hashes = {}
_root = None
_ID = re.compile(r'[a-z][a-z0-9_]{0,79}\Z')
_HASH = re.compile(r'[a-f0-9]{64}\Z')


def game_root():
    global _root
    if _root is not None:
        return _root
    seeds = [Path(__file__), Path.cwd(), Path(sys.executable)]
    try:
        from mods_base import SETTINGS_DIR
        seeds.insert(0, Path(SETTINGS_DIR))
    except ImportError:
        pass
    for seed in seeds:
        for candidate in (seed, *seed.parents):
            if (candidate / 'OakGame/Content/Paks').is_dir() and (candidate / 'sdk_mods').is_dir():
                _root = candidate.resolve()
                return _root
    return None


def state_path():
    from mods_base import SETTINGS_DIR
    folder = Path(SETTINGS_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / 'bl4_appearance_vehicle.json'


def file_matches(path, expected):
    if not path.is_file():
        return False
    stat = path.stat()
    stamp = (stat.st_size, stat.st_mtime_ns)
    cached = _hashes.get(str(path))
    if cached is None or cached[:2] != stamp:
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        cached = _hashes[str(path)] = (*stamp, actual)
    return cached[2] == expected


def archives(model):
    result = {}
    for row in (model, *model.get('animation_extensions', [])):
        files = {row.get('pak', ''): row.get('sha256', ''), **row.get('containers', {})}
        if len(files) != 3 or {Path(name).suffix for name in files} != {'.pak', '.utoc', '.ucas'}:
            raise ValueError('Each asset container needs its pak, utoc and ucas hashes')
        stem = Path(row['pak']).stem
        for name, digest in files.items():
            if Path(name).name != name or '/' in name or '\\' in name or ':' in name or '..' in name:
                raise ValueError('Invalid archive filename')
            if Path(name).stem != stem or not isinstance(digest, str) or not _HASH.fullmatch(digest):
                raise ValueError('Invalid asset container receipt')
            if name in result and result[name] != digest:
                raise ValueError('Conflicting asset container receipts')
            result[name] = digest
    return result


def validate(data, folder, root, *, verify=True):
    def finite_metadata(value, depth=0):
        if depth > 24:
            raise ValueError('Pack metadata is too deeply nested')
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('Pack metadata contains a non-finite number')
        if isinstance(value, dict):
            for item in value.values(): finite_metadata(item, depth + 1)
        elif isinstance(value, list):
            for item in value: finite_metadata(item, depth + 1)
    finite_metadata(data)
    if not isinstance(data, dict) or data.get('schema') != SCHEMA or data.get('kind') not in ('character', 'vehicle'):
        raise ValueError('Unsupported pack manifest')
    pack_id = data.get('id', '')
    if not isinstance(pack_id, str) or not _ID.fullmatch(pack_id) or folder.name != pack_id:
        raise ValueError('Pack ID must match its folder')
    for key in ('name', 'author', 'version', 'source_game'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError('Missing pack ' + key)
    model = data.get('model')
    if not isinstance(model, dict) or not isinstance(model.get('name'), str):
        raise ValueError('Missing model metadata')
    for key in ('mesh_yaw_degrees', 'mesh_pitch_degrees', 'mesh_roll_degrees', 'mesh_z_offset_cm', 'preview_ground_z_cm', 'visual_scale'):
        if key in model and (type(model[key]) not in (int, float) or abs(model[key]) > 10000):
            raise ValueError('Invalid model numeric field: ' + key)
    if 'visual_scale' in model and model['visual_scale'] <= 0:
        raise ValueError('Visual scale must be positive')
    for key, limit in (('attach_offset_cm', 2000), ('driver_visual_offset_cm', 200)):
        if key in model:
            values = model[key]
            if not isinstance(values, list) or len(values) != 3 or any(type(v) not in (int, float) or abs(v) > limit for v in values):
                raise ValueError('Invalid model offset: ' + key)
    namespace = data.get('namespace', '')
    category = 'ImportedCharacters' if data['kind'] == 'character' else 'ImportedVehicles'
    if not isinstance(namespace, str) or not re.fullmatch(r'/Game/' + category + r'/[A-Za-z][A-Za-z0-9_]{0,79}/', namespace):
        raise ValueError('Invalid asset namespace')
    paths = [model.get('actor_class', ''), model.get('mesh', ''), *model.get('animations', {}).values()]
    for key in ('slot_textures', 'slot_normals', 'slot_packed'):
        paths.extend(model.get(key, {}).values())
    for extension in model.get('animation_extensions', []):
        paths.extend(extension.get('animations', {}).values())
    if model.get('skeleton'):
        paths.append(model['skeleton'])
    if any(not isinstance(p, str) or not p.startswith(namespace) or '..' in p or '\\' in p or ':' in p for p in paths):
        raise ValueError('Asset paths escape the pack namespace')
    files = archives(model)
    for name, digest in files.items():
        path = root / 'OakGame/Content/Paks' / name
        if verify and not file_matches(path, digest):
            raise ValueError('Missing or changed asset: ' + name)
    textures = data.get('textures', {})
    if not isinstance(textures, dict):
        raise ValueError('Invalid texture receipt')
    texture_root = (folder / 'textures').resolve()
    for name, digest in textures.items():
        if not isinstance(name, str) or not name or '\\' in name or ':' in name or '..' in name or Path(name).is_absolute():
            raise ValueError('Invalid texture filename')
        path = (texture_root / name).resolve()
        if not path.is_relative_to(texture_root) or path.suffix.lower() != '.png' or not isinstance(digest, str) or not _HASH.fullmatch(digest):
            raise ValueError('Invalid texture receipt')
        if verify and not file_matches(path, digest):
            raise ValueError('Missing or changed texture: ' + name)
    if any(name not in textures for name in model.get('runtime_texture_files', {}).values()):
        raise ValueError('A runtime texture is missing its file receipt')
    if type(data.get('apply_enabled')) is not bool:
        raise ValueError('Pack must explicitly declare apply readiness')
    # Internal runtime rows are built after validation; manifests cannot supply paths.
    preview = data.get('preview', {})
    if not isinstance(preview, dict):
        raise ValueError('Invalid pack preview')
    preview_fields = {}
    if preview:
        image = preview.get('preview_data', '')
        kind = preview.get('preview_kind', '')
        if not isinstance(image, str) or len(image) >= 400000 or not re.fullmatch(r'data:image/(?:png|jpeg);base64,[A-Za-z0-9+/=]+', image):
            raise ValueError('Invalid pack preview image')
        raw = base64.b64decode(image.split(',', 1)[1], validate=True)
        if not (raw.startswith(b'\x89PNG\r\n\x1a\n') or raw.startswith(b'\xff\xd8\xff')):
            raise ValueError('Invalid pack preview image signature')
        if kind not in ('Converted preview', 'Source reference', 'Stock assembly', 'Prepared preview'):
            raise ValueError('Pack preview must identify its origin')
        preview_fields = {'preview_data': image, 'preview_kind': kind}
    model = {**model, **preview_fields, 'namespace': namespace, '_texture_root': str(texture_root), '_pack_id': pack_id}
    return {**data, 'model': model}


def discover(root=None):
    global _packs, _errors
    root = Path(root) if root is not None else game_root()
    found, errors, claims = {}, [], {}
    if root is not None:
        for path in sorted((root / 'sdk_mods/appearance_packs').glob('*/pack.json')):
            try:
                if path.stat().st_size > 2_000_000:
                    raise ValueError('Pack manifest is too large')
                pack = validate(json.loads(path.read_text(encoding='utf-8')), path.parent, root)
                # Reject both conflicting packs rather than choosing by scan order.
                chunk_ids = {re.match(r'pakchunk(\d+)', name).group(1)
                             for name in archives(pack['model']) if re.match(r'pakchunk(\d+)', name)}
                keys = {pack['namespace'], *('chunk:' + n for n in chunk_ids)}
                conflict = {claims[key] for key in keys if key in claims}
                for key in keys:
                    claims.setdefault(key, pack['id'])
                if conflict:
                    for other in conflict:
                        found.pop(other, None)
                    raise ValueError('Conflicting pack namespace or chunk: ' + ', '.join(sorted(conflict)))
                found[pack['id']] = pack
            except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
                errors.append({'pack': path.parent.name, 'message': str(exc)})
    _packs, _errors = found, errors
    return list(found.values())


def character_models():
    return {key: row['model'] for key, row in _packs.items() if row['kind'] == 'character'}


def vehicle_models():
    return {key: row['model'] for key, row in _packs.items() if row['kind'] == 'vehicle'}


def namespace_records():
    return {key: {**row['model'], 'namespace': row['namespace']} for key, row in _packs.items() if row['kind'] == 'character'}


def texture_root(model_id):
    return Path(character_models()[model_id]['_texture_root'])


def snapshot():
    return {'installed': [{k: row[k] for k in ('id', 'kind', 'name', 'author', 'version', 'source_game', 'apply_enabled')}
                          for row in _packs.values()], 'errors': list(_errors)}
