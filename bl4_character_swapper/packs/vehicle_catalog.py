"""Registry-backed imported vehicle choices; also usable by the offline app."""
from pathlib import Path
import json

HOST_VEHICLE_CHOICES = (
    ('PV_Base', 'Base', 'base'),
    ('PV_Borg', 'Borg', 'base'),
    ('PV_Grazer', 'Grazer', 'base'),
    ('PV_DarkSiren', 'Dark Siren [DarkSiren]', 'character'),
    ('PV_DarkSiren_Proto', 'Dark Siren (Proto) [DarkSiren_Proto]', 'character'),
    ('PV_ExoSoldier', 'Exo Soldier [ExoSoldier]', 'character'),
    ('PV_ExoSoldier_Proto', 'Exo Soldier (Proto) [ExoSoldier_Proto]', 'character'),
    ('PV_Gravitar', 'Gravitar [Gravitar]', 'character'),
    ('PV_Gravitar_Proto', 'Gravitar (Proto) [Gravitar_Proto]', 'character'),
    ('PV_Paladin', 'Paladin [Paladin]', 'character'),
    ('PV_Paladin_Proto', 'Paladin (Proto) [Paladin_Proto]', 'character'),
    ('PV_Mountain', 'Mountain (Vault Card) [Mountain]', 'dlc'),
    ('PV_City', 'City', 'promo'),
    ('PV_CityOrder', 'City Order [CityOrder]', 'promo'),
    ('PV_shatterlandV1', 'Shatterland V1 [shatterlandV1]', 'promo'),
)

def picker_rows(rows=None):
    if rows is None:
        path=Path(__file__).parent/'data/imported_vehicles.json'
        rows=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    return {key:row for key,row in rows.items() if row.get('picker_visible', True)}


def display_name(key, row):
    return str(row.get('display_name') or row.get('name') or key)
