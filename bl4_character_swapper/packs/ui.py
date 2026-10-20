"""Cached optional-car choices; ImGui only queues work for the shared tick."""
from . import manager
_car = ''


def draw(imgui):
    global _car
    state = manager.status()
    if state['errors']:
        imgui.text_wrapped(f"{len(state['errors'])} pack(s) could not be loaded. Use asw_packs for details.")
    rows = manager.vehicle_catalog()['rows']
    if not rows:
        return
    imgui.separator()
    imgui.text('Installed car packs')
    if not any(row['code'] == _car for row in rows):
        _car = rows[0]['code']
    current = next(row['display_name'] for row in rows if row['code'] == _car)
    if imgui.begin_combo('Car', current):
        for row in rows:
            selected, _ = imgui.selectable(row['display_name'] + '##car:' + row['code'], _car == row['code'])
            if selected:
                _car = row['code']
        imgui.end_combo()
    for verb, label in (('preview', 'Preview car'), ('summon', 'Summon car'), ('use', 'Use on my vehicle'), ('restore', 'Restore vehicle')):
        if imgui.button(label):
            manager.request_vehicle({'verb': verb, 'codes': [_car]})
    imgui.text_wrapped(state['message'])
    imgui.text_disabled('Visual shells retain native hover driving; wheels are static.')
