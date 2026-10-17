# -*- coding: utf-8 -*-
from pathlib import Path

ls = Path(__file__).with_name("loot_shapes.py")
t = ls.read_text(encoding="utf-8")
old = '''    mode = "soft late-join stamp" if soft_late_join else "full pose publish"
    _log(
        f"Co-op pickup-safe publish queued ({len(_pinned_slots)} pin(s), {mode}); "
        "shape held — Use an item to collect into backpack."
    )'''
new = '''    # Stamp Useable now — do not wait for ForceNet drip (join/spawn grab lag).
    stamped = 0
    for row in _pinned_slots:
        if row.get("prior_hold"):
            continue
        inv = _resolve_pin_inv(row, fresh=False)
        if inv is None or not _live(inv):
            continue
        try:
            _stamp_guest_grab_ready(inv)
            row["client_motion_unlocked"] = True
            stamped += 1
        except Exception:
            continue
    mode = "soft late-join stamp" if soft_late_join else "full pose publish"
    _log(
        f"Co-op pickup-safe publish queued ({len(_pinned_slots)} pin(s), {mode}, "
        f"{stamped} Use-stamped); shape held — Use an item to collect into backpack."
    )
    _log_dev(
        f"pickup-safe publish queued ({len(_pinned_slots)} pin(s), {mode}, "
        f"{stamped} Use-stamped)"
    )'''
if old not in t:
    raise SystemExit("arm log missing")
ls.write_text(t.replace(old, new, 1), encoding="utf-8")
print("ok arm stamp")
