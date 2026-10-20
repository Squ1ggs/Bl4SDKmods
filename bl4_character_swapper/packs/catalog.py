"""Stable display groups, independent of how character packs are downloaded."""
GAME_FILTERS = ('All games', 'Borderlands 4', 'Borderlands 1', 'Borderlands 2',
                'The Pre-Sequel', 'Borderlands 3', 'Other games')
SOURCE_NAMES = {'bl1': 'Borderlands 1', 'bl2': 'Borderlands 2', 'tps': 'The Pre-Sequel',
                'bl3': 'Borderlands 3', 'halo_mcc': 'Halo MCC', 'kh2': 'Kingdom Hearts II',
                'kh3': 'Kingdom Hearts III', 'spiderman2': 'Spider-Man 2'}
HUNTERS = frozenset(('bl1:soldier', 'bl1:siren', 'bl1:hunter', 'bl1:berserker',
                     'bl2:soldier', 'bl2:siren', 'bl2:mercenary', 'bl2:assassin', 'bl2:mechromancer', 'bl2:psycho',
                     'tps:gladiator', 'tps:enforcer', 'tps:lawbringer', 'tps:fragtrap', 'tps:doppelganger', 'tps:baroness',
                     'bl3:siren', 'bl3:beastmaster', 'bl3:gunner', 'bl3:operative'))


def character_role(catalog_id):
    return 'Vault Hunter' if catalog_id in HUNTERS else 'Character'


def source_name(source):
    value = str(source or '').strip()
    return SOURCE_NAMES.get(value.casefold(), value or 'Other games')


def game_family(source):
    name = source_name(source)
    return name if name in GAME_FILTERS[1:-1] else 'Other games'


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
    """Short picker label; provenance remains in the unchanged pack metadata."""
    import re
    text = str(value).strip()
    text = re.sub(r"\s*[·|]\s*(?:[A-Z]{2,}_[A-Za-z0-9_]+|(?:source|original|converted|static)\b.*)$", "", text, flags=re.I)
    def bracket(match):
        parts = [part.strip() for part in match.group(1).split(',')]
        keep = [part for part in parts if not re.search(
            r"kingdom hearts|\bKH[23]\b|spider-man 2|halo [0-9]|halo reach|halo mcc|borderlands|pre-sequel|\b(?:BL[123]|TPS)\b|static|tex1|flame hidden|preview|original sword", part, re.I)]
        return ' (' + ', '.join(keep) + ')' if keep else ''
    return re.sub(r"\s*\(([^()]*)\)", bracket, text).strip()
