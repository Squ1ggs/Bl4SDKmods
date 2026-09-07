"""Install the bundled deterministic supplemental loot pools before game boot."""

from __future__ import annotations

import hashlib
import os
import pkgutil
import sys
from dataclasses import dataclass
from pathlib import Path


COMPANION_PAK_NAME = "pakchunk991-SQBT-PearlPools-Windows_991_P.pak"
COMPANION_PAK_SHA256 = "e60402cf54d226cc22bf552d7add7fd9b605d2c562cc4d34cc828a63070aa356"
LEGACY_FULL_PATCH_NAME = "pakchunk99-windows_99_P.pak"


@dataclass(frozen=True, slots=True)
class CompanionPakStatus:
    ok: bool
    restart_required: bool
    detail: str
    target: str = ""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().lower()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def _bundled_pak_bytes() -> bytes:
    package = __package__ or __name__.rpartition(".")[0]
    try:
        blob = pkgutil.get_data(package, f"assets/{COMPANION_PAK_NAME}")
        if blob:
            return blob
    except Exception:
        pass
    loose = Path(__file__).resolve().parent / "assets" / COMPANION_PAK_NAME
    if loose.is_file():
        return loose.read_bytes()
    raise FileNotFoundError(COMPANION_PAK_NAME)


def _candidate_roots() -> list[Path]:
    seeds: list[Path] = [Path.cwd()]
    try:
        seeds.append(Path(sys.executable).resolve().parent)
    except Exception:
        pass
    try:
        seeds.append(Path(__file__).resolve().parent)
    except Exception:
        pass

    out: list[Path] = []
    seen: set[str] = set()
    for seed in seeds:
        for candidate in (seed, *seed.parents):
            key = str(candidate).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(candidate)
    return out


def _game_paks_dir() -> Path | None:
    for root in _candidate_roots():
        candidate = root / "OakGame" / "Content" / "Paks"
        if candidate.is_dir():
            return candidate
    return None


def ensure_companion_pak() -> CompanionPakStatus:
    """Install/update the mod-owned pool patch; never touch unrelated PAKs."""
    try:
        payload = _bundled_pak_bytes()
    except Exception as exc:  # noqa: BLE001
        return CompanionPakStatus(False, False, f"bundled loot-pool data unavailable: {exc}")

    payload_hash = _sha256_bytes(payload)
    if payload_hash != COMPANION_PAK_SHA256:
        return CompanionPakStatus(
            False,
            False,
            "bundled loot-pool data failed its integrity check",
        )

    paks_dir = _game_paks_dir()
    if paks_dir is None:
        return CompanionPakStatus(False, False, "could not locate OakGame/Content/Paks")

    target = paks_dir / COMPANION_PAK_NAME
    legacy = paks_dir / LEGACY_FULL_PATCH_NAME
    legacy_warning = (
        f" Remove the incompatible {LEGACY_FULL_PATCH_NAME}." if legacy.exists() else ""
    )
    try:
        if target.is_file() and _sha256_file(target) == COMPANION_PAK_SHA256:
            return CompanionPakStatus(
                True,
                False,
                "companion loot pools are installed and ready." + legacy_warning,
                str(target),
            )
    except OSError:
        pass

    temporary = target.with_name(target.name + ".sqbt.tmp")
    try:
        temporary.write_bytes(payload)
        if _sha256_file(temporary) != COMPANION_PAK_SHA256:
            raise OSError("temporary file failed integrity verification")
        os.replace(temporary, target)
        if _sha256_file(target) != COMPANION_PAK_SHA256:
            raise OSError("installed file failed integrity verification")
    except Exception as exc:  # noqa: BLE001
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return CompanionPakStatus(
            False,
            False,
            f"could not install companion loot pools: {exc}",
            str(target),
        )

    return CompanionPakStatus(
        True,
        True,
        "companion loot pools installed; fully restart Borderlands 4 once."
        + legacy_warning,
        str(target),
    )
