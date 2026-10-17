"""One-shot patch: finish 3.10.5 auto_lobby follow-up + cfg helpers on Steam live mod."""
from __future__ import annotations

from pathlib import Path

STEAM = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Borderlands 4\sdk_mods\Squ1ggsBoostingTools"
)
path = STEAM / "auto_lobby.py"
text = path.read_text(encoding="utf-8")
start = text.index("def _tick_drip_followup(now: float) -> None:")
end = text.index("\ndef _clamp_kick_sec(")
new_fn = '''def _tick_drip_followup(now: float) -> None:
    """After mail+open finishes, spill host backpack (retry until empty / capped)."""
    global _drip_phase, _drip_drop_at, _session_dropped_items, _drip_drop_rounds
    global _drip_last_remaining, _drip_stalled_rounds, _next_drip_at
    global _drip_pending_guest_mail, _drip_guest_mail_started
    if _drip_phase not in ("wait_mail", "drop"):
        return
    if _lobby_join_quiet():
        if _drip_phase == "drop" or (_drip_phase == "wait_mail" and not _serial_delivery_busy()):
            _drip_drop_at = max(float(_drip_drop_at or 0.0), now + 1.5)
            _set_msg(
                "Auto-drop: pausing backpack drop while a guest joins/leaves — "
                "will resume after lobby settles."
            )
        return
    if _drip_phase == "wait_mail":
        if _serial_delivery_busy():
            return
        if _drip_pending_guest_mail and not _drip_guest_mail_started:
            _drip_guest_mail_started = True
            try:
                from .bridge_actions_extended import deliver_serials

                guest_res = deliver_serials(
                    {
                        "serials": list(_drip_pending_guest_mail),
                        "count": 1,
                        "level_override": "yes",
                        "level": int(_cfg.get("item_drip_level") or 50),
                        "mode": "nonhost",
                        "open_rewards": False,
                    }
                )
                g_ok = bool(guest_res.get("ok", True))
                g_msg = str(guest_res.get("message") or "")
                if g_ok:
                    _set_msg(
                        f"Auto-drop: mailed {len(_drip_pending_guest_mail)} to guests "
                        f"(Item list “{_cfg.get('item_drip_mail_pack') or ''}”). "
                        "Dropping host backpack next…"
                    )
                else:
                    _set_msg(
                        f"Auto-drop: guest mail skipped ({g_msg or 'failed'}); "
                        "still dropping host backpack."
                    )
            except Exception as exc:
                _set_msg(f"Auto-drop: guest mail error ({exc!r}); still dropping host backpack.")
            _drip_pending_guest_mail = []
            return
        if _serial_delivery_busy():
            return
        if _drip_drop_at <= 0:
            settle = max(2.5, min(40.0, 2.0 + float(_drip_last_count) * 0.12))
            _drip_drop_at = now + settle
            _set_msg(
                f"Auto-drop: mail/open done ({_drip_last_count}) — "
                f"dropping backpack in {int(settle)}s…"
            )
            return
        if now < _drip_drop_at:
            return
        _drip_phase = "drop"
        _drip_drop_rounds = 0
    if _drip_phase != "drop":
        return
    if _drip_drop_at > 0 and now < _drip_drop_at:
        return
    from .bridge_actions_extended import faafo_drop_backpack

    host_idx = _host_player_index()
    shape = _normalize_drip_shape(_cfg.get("item_drip_shape"))
    settle = _drip_shape_settle(shape)
    try:
        payload: dict[str, Any] = {
            "player_index": host_idx,
            "shape": shape,
            "settle": settle,
            "land_profile": "shiny",
            "soft_lobby": True,
            "soft_lobby_spread": shape == "none",
        }
        if shape != "none":
            payload["stay_in_air"] = "yes"
            payload["spawn_then_shape"] = "no"
            payload["fill_until_complete"] = "no"
            payload["radius"] = 200
            payload["spacing"] = 72
            payload["drop_height"] = 440 if shape == "skyfall" else 120
            payload["z_bias"] = 18
        result = faafo_drop_backpack(payload)
        ok = bool(result.get("ok", True))
        msg = str(result.get("message") or "Backpack drop finished.")
    except Exception as exc:
        ok = False
        msg = f"Backpack drop failed: {exc!r}"
    _drip_drop_rounds += 1
    lower = msg.lower()
    still_full = "partial" in lower or "remaining=" in lower
    remaining = 0
    if "remaining=" in lower:
        try:
            remaining = int(lower.split("remaining=", 1)[1].split()[0].strip(".,;"))
        except Exception:
            remaining = 1 if still_full else 0
    if remaining > 0:
        if remaining == _drip_last_remaining:
            _drip_stalled_rounds += 1
        else:
            _drip_stalled_rounds = 0
        _drip_last_remaining = remaining
    if ok and (not still_full or remaining <= 0):
        _drip_phase = ""
        _drip_drop_at = 0.0
        _drip_drop_rounds = 0
        _drip_last_remaining = -1
        _drip_stalled_rounds = 0
        _drip_pending_guest_mail = []
        _drip_guest_mail_started = False
        gap = max(_MIN_DRIP_SEC, float(_cfg.get("item_drip_interval_sec") or 120))
        _next_drip_at = now + gap
        _session_dropped_items = True
        _set_msg(
            f"Auto-drop complete: mailed {_drip_last_count} → host pack → "
            f"{'shape' if _normalize_drip_shape(_cfg.get('item_drip_shape')) != 'none' else 'ground'}. "
            f"Next drop in {int(gap)}s (loops while Auto Lobby is on)."
        )
        return
    if _drip_drop_rounds >= _MAX_DRIP_DROP_ROUNDS or _drip_stalled_rounds >= 2:
        _drip_phase = ""
        _drip_drop_at = 0.0
        _drip_last_remaining = -1
        _drip_stalled_rounds = 0
        _drip_pending_guest_mail = []
        _drip_guest_mail_started = False
        gap = max(_MIN_DRIP_SEC, float(_cfg.get("item_drip_interval_sec") or 120))
        _next_drip_at = now + gap
        _set_msg(
            f"Auto-drop pause: backpack drop stalled after {_drip_drop_rounds} pass(es). "
            f"Next drop in {int(gap)}s (still looping)."
        )
        return
    _drip_drop_at = now + 2.2
    _set_msg(
        f"Auto-drop: dropping backpack pass {_drip_drop_rounds}/{_MAX_DRIP_DROP_ROUNDS}…"
    )


'''
text = text[:start] + new_fn + text[end:]
if 'merged["item_drip_mail_pack"]' not in text:
    text = text.replace(
        'merged["item_drip_pack"] = str(merged.get("item_drip_pack") or "").strip()\n',
        'merged["item_drip_pack"] = str(merged.get("item_drip_pack") or "").strip()\n'
        '    merged["item_drip_mail_pack"] = str(merged.get("item_drip_mail_pack") or "").strip()\n',
        1,
    )
old_reset = '''def _reset_session_runtime() -> None:
    global _kick_at, _kick_armed_indices, _session_dropped_items, _cycle_finished_once, _next_drip_at
    global _drip_phase, _drip_drop_at, _drip_last_count, _drip_drop_rounds
    global _drip_last_remaining, _drip_stalled_rounds
    _kick_at.clear()
    _kick_armed_indices.clear()
    _session_dropped_items = False
    _cycle_finished_once = False
    _next_drip_at = 0.0
    _drip_phase = ""
    _drip_drop_at = 0.0
    _drip_last_count = 0
    _drip_drop_rounds = 0
    _drip_last_remaining = -1
    _drip_stalled_rounds = 0
'''
new_reset = '''def _reset_session_runtime() -> None:
    global _kick_at, _kick_armed_indices, _session_dropped_items, _cycle_finished_once, _next_drip_at
    global _drip_phase, _drip_drop_at, _drip_last_count, _drip_drop_rounds
    global _drip_last_remaining, _drip_stalled_rounds
    global _drip_pending_guest_mail, _drip_guest_mail_started
    _kick_at.clear()
    _kick_armed_indices.clear()
    _session_dropped_items = False
    _cycle_finished_once = False
    _next_drip_at = 0.0
    _drip_phase = ""
    _drip_drop_at = 0.0
    _drip_last_count = 0
    _drip_drop_rounds = 0
    _drip_last_remaining = -1
    _drip_stalled_rounds = 0
    _drip_pending_guest_mail = []
    _drip_guest_mail_started = False
'''
if old_reset in text:
    text = text.replace(old_reset, new_reset, 1)
old_nudge = '''            if _serial_delivery_busy() or _drip_phase:
                _next_drip_at = now + max(_MIN_DRIP_SEC, 20.0)
'''
new_nudge = '''            if _serial_delivery_busy() or _drip_phase:
                _next_drip_at = now + max(15.0, min(_MIN_DRIP_SEC, 30.0))
'''
if old_nudge in text:
    text = text.replace(old_nudge, new_nudge, 1)
path.write_text(text, encoding="utf-8")
print("auto_lobby patched:", "loops while" in text, "item_drip_mail_pack" in text)
