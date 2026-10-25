"""Picker groups for the public release. Extra models use the installed pack's own name."""
GAME_FILTERS = ('All games', 'Borderlands 4', 'Installed')
SOURCE_NAMES = {'bl4': 'Borderlands 4'}


def character_role(_catalog_id):
    return 'Character'


def source_name(source):
    value = str(source or '').strip()
    mapped = SOURCE_NAMES.get(value.casefold())
    if mapped:
        return mapped
    return 'Installed' if value else 'Borderlands 4'


def game_family(source):
    name = source_name(source)
    return name if name in GAME_FILTERS[1:] else 'Installed'


def matches(row, game='All games', role='All characters', group='All'):
    if game not in ('All', 'All games', '') and row.get('game', 'Borderlands 4') != game:
        return False
    if role == 'Vault Hunters' and row.get('role') != 'Vault Hunter':
        return False
    if role == 'Other characters' and row.get('role') == 'Vault Hunter':
        return False
    imported = str(row.get('key', '')).startswith('pack:')
    if group == 'Installed packs':
        return imported
    # This filter is explicitly labelled BL4 category in the frontends.
    return imported or group in ('All', '') or row['group'] == group


def menu_name(value):
    """Use the pack's own label, without adding a game name in this program."""
    import re
    text = str(value).strip()
    return re.sub(r"\s*[·|]\s*[A-Z]{2,}_[A-Za-z0-9_]+.*$", "", text).strip()
