# -*- coding: utf-8 -*-
"""3.11.23: freecam IO sync + faster grab drip + shorter join quiet."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _patch_io_freecam_async() -> None:
    path = ROOT / "embedded_bms" / "controller.py"
    t = path.read_text(encoding="utf-8")
    old = '''            def _do_ai_only() -> tuple[bool, str]:
                try:
                    # Always async-fire like mob spawner. Dual world pass waits on
                    # later ticks via find_object — never block PlayerTick with polls.
                    with self._with_spawn_anchor():
                        ok, msg = spawn_actor_def(
                            short,
                            count=1,
                            distance=float(self.ui.spawn_distance),
                            spacing=float(self.ui.spawn_spacing),
                            allow_summon_fallback=False,
                            fast_path=True,
                            async_fire=True,
                        )'''
    new = '''            def _do_ai_only() -> tuple[bool, str]:
                try:
                    # Freecam: sync fire — async + DCC queue stall = action ok, nothing at cam.
                    freecam_on = False
                    try:
                        from Squ1ggsBoostingTools.dev_tools import is_debug_cam_active

                        freecam_on = bool(is_debug_cam_active())
                    except Exception:
                        freecam_on = False
                    with self._with_spawn_anchor():
                        ok, msg = spawn_actor_def(
                            short,
                            count=1,
                            distance=float(self.ui.spawn_distance),
                            spacing=float(self.ui.spawn_spacing),
                            allow_summon_fallback=False,
                            fast_path=True,
                            async_fire=not freecam_on,
                        )'''
    if old not in t:
        raise SystemExit("io _do_ai_only missing")
    t = t.replace(old, new, 1)

    old2 = '''                    else:
                        # One Oak Spawner fire only. spawn_actor_def often returns False when the prop
                        # has not appeared in the 0.05–0.28s poll yet; the old run_oak_line
                        # fallback ResetSpawner'd again and duplicated IO_AscensionBeam etc.
                        with self._with_spawn_anchor():
                            ok, msg = spawn_actor_def(
                                short,
                                count=1,
                                distance=float(self.ui.spawn_distance),
                                spacing=float(self.ui.spawn_spacing),
                                allow_summon_fallback=False,
                                fast_path=True,
                                async_fire=True,
                            )'''
    new2 = '''                    else:
                        # One Oak Spawner fire only. spawn_actor_def often returns False when the prop
                        # has not appeared in the 0.05–0.28s poll yet; the old run_oak_line
                        # fallback ResetSpawner'd again and duplicated IO_AscensionBeam etc.
                        freecam_on = False
                        try:
                            from Squ1ggsBoostingTools.dev_tools import is_debug_cam_active

                            freecam_on = bool(is_debug_cam_active())
                        except Exception:
                            freecam_on = False
                        with self._with_spawn_anchor():
                            ok, msg = spawn_actor_def(
                                short,
                                count=1,
                                distance=float(self.ui.spawn_distance),
                                spacing=float(self.ui.spawn_spacing),
                                allow_summon_fallback=False,
                                fast_path=True,
                                async_fire=not freecam_on,
                            )'''
    if old2 not in t:
        raise SystemExit("io _do_io async missing")
    path.write_text(t.replace(old2, new2, 1), encoding="utf-8")
    print("ok io freecam sync")


def _patch_grab_pace() -> None:
    path = ROOT / "loot_shapes.py"
    t = path.read_text(encoding="utf-8")
    old = '''    elif keep_freeze and heavy_3d:
        # Was 1/@0.72s — third shape never finished ForceNet before Use/mail pauses.
        publish_budget = 3 if n > 60 else 4
        unlock_budget = 4
        retry_gap = 0.22 if n > 80 else 0.16
    elif keep_freeze and flat_2d:
        # Grids + Drop All silhouettes: net+unlock fast so guests grab sooner
        # (was ~0.28s × N/2 — lobby waited a long time after Auto backpack→shape).
        publish_budget = 4 if n > 60 else 5
        unlock_budget = 6
        retry_gap = 0.14 if n > 80 else 0.10'''
    new = '''    elif keep_freeze and heavy_3d:
        # ULM: 119-pin globe took ~35s — denser drip so Use-stamped pins are also visible.
        publish_budget = 6 if n > 60 else 7
        unlock_budget = 8
        retry_gap = 0.10 if n > 80 else 0.08
    elif keep_freeze and flat_2d:
        # Grids + Drop All silhouettes: net+unlock fast so guests grab sooner.
        publish_budget = 6 if n > 60 else 7
        unlock_budget = 8
        retry_gap = 0.08 if n > 80 else 0.06'''
    if old not in t:
        raise SystemExit("publish pace missing")
    t = t.replace(old, new, 1)

    old_q = '''        quiet = 14.0 if pin_n >= 80 else (10.0 if pin_n >= 30 else 8.0)
        if hold:
            # Console join + held silhouette: long quiet so character load finishes
            # before any ForceNet drip (early publish hitch-locks join).
            # Was 32/26/22 — lobby waited forever after join before Use worked.
            quiet = max(quiet, 12.0 if pin_n >= 80 else (10.0 if pin_n >= 30 else 8.0))'''
    new_q = '''        quiet = 8.0 if pin_n >= 80 else (6.0 if pin_n >= 30 else 4.0)
        if hold:
            # Keep quiet short — Use-stamped at arm; long mute was "can't grab after join".
            quiet = max(quiet, 8.0 if pin_n >= 80 else (6.0 if pin_n >= 30 else 4.0))'''
    if old_q not in t:
        raise SystemExit("join quiet missing")
    path.write_text(t.replace(old_q, new_q, 1), encoding="utf-8")
    print("ok grab pace + join quiet")


def _bump() -> None:
    mv = ROOT / "_mod_version.py"
    mv.write_text(
        '"""Single source of truth for the live Squ1ggsBoostingTools mod version."""\n'
        '__version__: str = "3.11.23"\n',
        encoding="utf-8",
    )
    cl = ROOT / "CHANGELOG.md"
    text = cl.read_text(encoding="utf-8")
    entry = (
        "## 3.11.23 / EXE 1.4.23\n"
        "- **Freecam spawn (queue stall):** fire mob/IO immediately while freecam is on "
        "(PlayerTick drain never ran under DebugCamera — action ok, nothing at cam); "
        "IO also sync Oak at look-at.\n"
        "- **Faster grab after spawn/join:** stamp Useable when publish arms; denser "
        "ForceNet drip; join quiet 4–8s (was 8–14); blank-@U re-grab uses native Attract.\n"
        "\n"
    )
    if "## 3.11.23" not in text:
        text = text.replace("# Changelog\n\n", "# Changelog\n\n" + entry, 1)
        cl.write_text(text, encoding="utf-8")
    print("ok bump 3.11.23")


if __name__ == "__main__":
    _patch_io_freecam_async()
    _patch_grab_pace()
    _bump()
    print("done")
