"""Validate installer-issued namespace receipts without importing the SDK."""
import re

_NAMESPACE = re.compile(r'/Game/ImportedCharacters/[A-Za-z][A-Za-z0-9_]{0,79}/\Z')
_HASH = re.compile(r'[0-9a-f]{64}\Z')


def valid_record(record, row):
    if not isinstance(record, dict) or not isinstance(row, dict):
        return False
    namespace = record.get('namespace', '')
    if not isinstance(namespace, str) or not _NAMESPACE.fullmatch(namespace):
        return False
    if any(record.get(key) != row.get(key) for key in ('pak', 'sha256', 'containers')):
        return False
    archives = {row.get('pak', ''): row.get('sha256', ''), **row.get('containers', {})}
    if len(archives) != 3 or {name.rsplit('.', 1)[-1] for name in archives} != {'pak', 'utoc', 'ucas'}:
        return False
    if any(not isinstance(name, str) or '/' in name or '\\' in name or '..' in name
           or not isinstance(value, str) or not _HASH.fullmatch(value) for name, value in archives.items()):
        return False
    paths = [row.get('actor_class', ''), row.get('mesh', ''),
             *row.get('slot_textures', {}).values()]
    # Shared animation assets have separate receipts; this record grants only
    # its own namespace and must not be invalidated by a seated-clip reference.
    animations=list(row.get('animations', {}).values())
    if any(not isinstance(path,str) or not path.startswith('/Game/ImportedCharacters/')
           or '..' in path or '\\' in path or ':' in path for path in animations):
        return False
    if row.get('skeleton'):
        paths.append(row['skeleton'])
    return bool(paths) and all(isinstance(path, str) and path.startswith(namespace)
                              and '..' not in path and '\\' not in path for path in paths)
