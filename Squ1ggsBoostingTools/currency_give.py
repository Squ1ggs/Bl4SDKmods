"""CurrencyManager slot reads/writes and GiveCurrency helpers for Boosting Tools."""

from __future__ import annotations

import re
from typing import Any

_INT32_MAX = 2_147_483_647

_CURRENCY_NEEDLE_TO_TOKEN: dict[str, str] = {
    "cash": "Cash",
    "money": "Cash",
    "eridium": "eridium",
    "premium": "eridium",
    "vaultcard01": "VaultCard01_Tokens",
    "vaultcard02": "VaultCard02_Tokens",
    "vaultcard03": "VaultCard03_Tokens",
    "vaultcard04": "VaultCard04_Tokens",
    "vaultcard1": "VaultCard01_Tokens",
    "vaultcard2": "VaultCard02_Tokens",
    "vaultcard3": "VaultCard03_Tokens",
    "vaultcard4": "VaultCard04_Tokens",
    "vaultcard_1": "VaultCard01_Tokens",
    "vaultcard_2": "VaultCard02_Tokens",
    "vaultcard_3": "VaultCard03_Tokens",
    "vaultcard_4": "VaultCard04_Tokens",
    "vault card 01": "VaultCard01_Tokens",
    "vault card 02": "VaultCard02_Tokens",
    "vault card 03": "VaultCard03_Tokens",
    "vault card 04": "VaultCard04_Tokens",
    "vc1": "VaultCard01_Tokens",
    "vc2": "VaultCard02_Tokens",
    "vc3": "VaultCard03_Tokens",
    "vc4": "VaultCard04_Tokens",
}

_CURRENCY_DEF_SCRIPT_PATHS = (
    "/Script/GbxGame.GbxCurrencyDef",
    "/Script/OakGame.GbxCurrencyDef",
)


def _needle_to_token(needle: str) -> str | None:
    n = needle.strip().lower()
    if not n:
        return None
    if n in _CURRENCY_NEEDLE_TO_TOKEN:
        return _CURRENCY_NEEDLE_TO_TOKEN[n]
    for key, token in _CURRENCY_NEEDLE_TO_TOKEN.items():
        if key in n or n in key:
            return token
    return None


def _assign_fgbx_def_ptr_fields(ptr: Any, name: str, ref: Any) -> bool:
    for name_attr, ref_attr in (("name", "ref"), ("_experimental_name", "_experimental_ref")):
        try:
            setattr(ptr, name_attr, name)
            setattr(ptr, ref_attr, ref)
            return True
        except Exception:
            continue
    return False


def fgbx_def_ptr_api_ok() -> bool:
    """True when unrealsdk exposes a real FGbxDefPtr (Oak2 SDK 0.3+)."""
    try:
        from unrealsdk.unreal import FGbxDefPtr  # pyright: ignore[reportMissingImports]
    except Exception:
        return False
    # Empty ctor fails on some builds that still have a working named ctor.
    for factory in (
        lambda: FGbxDefPtr(),
        lambda: FGbxDefPtr("Cash"),
        lambda: FGbxDefPtr("Cash", type="GbxCurrencyDef"),
        lambda: FGbxDefPtr("Cash", type=None),
    ):
        try:
            sample = factory()
        except Exception:
            continue
        if sample is None:
            continue
        try:
            if isinstance(sample, FGbxDefPtr):
                return True
        except Exception:
            pass
        if type(sample).__name__ == "FGbxDefPtr":
            return True
    return False


def _is_real_fgbx_def_ptr(obj: Any) -> bool:
    if obj is None:
        return False
    try:
        from unrealsdk.unreal import FGbxDefPtr  # pyright: ignore[reportMissingImports]

        return isinstance(obj, FGbxDefPtr)
    except Exception:
        return type(obj).__name__ == "FGbxDefPtr"


def _token_from_currency_ptr(raw: Any) -> str:
    if raw is None:
        return ""
    for attr in ("name", "Name", "_experimental_name"):
        try:
            value = getattr(raw, attr, None)
        except Exception:
            value = None
        if value:
            text = str(value).strip()
            if text:
                return text.split("/")[-1]
    return ""


def _coerce_currency_def_ptr(raw: Any, currency_token: str) -> Any | None:
    """Never pass a WrappedStruct into GiveCurrency — rebuild a real FGbxDefPtr."""
    if _is_real_fgbx_def_ptr(raw):
        return raw
    token = (currency_token or "").strip() or _token_from_currency_ptr(raw)
    if not token:
        return None
    return _make_currency_def_ptr(token)


def _find_currency_def_struct() -> Any | None:
    try:
        from unrealsdk import find_all, find_object  # pyright: ignore[reportMissingImports]
    except Exception:
        return None
    for class_name in ("ScriptStruct", "Object"):
        for object_path in _CURRENCY_DEF_SCRIPT_PATHS:
            try:
                resolved = find_object(class_name, object_path)
            except Exception:
                resolved = None
            if resolved is not None:
                return resolved
    try:
        for candidate in find_all("ScriptStruct", False) or []:
            if getattr(candidate, "Name", None) == "GbxCurrencyDef":
                return candidate
    except Exception:
        pass
    return None


def _make_currency_def_ptr(token_tail: str) -> Any | None:
    """Build the FGbxDefPtr required by GiveCurrency."""
    try:
        from unrealsdk.unreal import FGbxDefPtr  # pyright: ignore[reportMissingImports]
    except Exception:
        return None
    struct_u = _find_currency_def_struct()
    if struct_u is None:
        return None
    tail = (token_tail or "").strip().split("/")[-1]
    if not tail:
        return None
    try:
        ptr = FGbxDefPtr()
    except Exception:
        return None
    return ptr if _assign_fgbx_def_ptr_fields(ptr, tail, struct_u) else None


def _get_currency_function_library() -> Any | None:
    try:
        from unrealsdk import find_all, find_class, find_object  # pyright: ignore[reportMissingImports]
    except Exception:
        return None
    try:
        cls = find_class("GbxCurrencyFunctionLibrary")
        if cls is not None:
            cdo = getattr(cls, "ClassDefaultObject", None)
            if cdo is not None:
                return cdo
    except Exception:
        pass
    for path in (
        "/Script/GbxGame.GbxCurrencyFunctionLibrary",
        "/Script/OakGame.GbxCurrencyFunctionLibrary",
    ):
        try:
            lib = find_object("Class", path)
            if lib is not None:
                return lib
        except Exception:
            continue
    try:
        objs = find_all("GbxCurrencyFunctionLibrary", False) or []
        if objs:
            return objs[-1]
    except Exception:
        pass
    return None


def find_currency_manager(pc: Any) -> Any | None:
    if pc is None:
        return None
    for attr in ("CurrencyManager", "GbxCurrencyManager"):
        cm = getattr(pc, attr, None)
        if cm is not None:
            return cm
    for ps_attr in ("OakPlayerState", "PlayerState"):
        ps = getattr(pc, ps_attr, None)
        if ps is None:
            continue
        for attr in ("CurrencyManager", "GbxCurrencyManager"):
            cm = getattr(ps, attr, None)
            if cm is not None:
                return cm
    return None


def currency_slot_name(slot: Any) -> str:
    """Read SToken.Name / FGbxDefPtr name from GbxCurrency.type."""
    try:
        slot_type = getattr(slot, "type", None)
        if slot_type is None:
            return "<unnamed>"
        for attr in ("Name", "name", "_experimental_name"):
            name = getattr(slot_type, attr, None)
            if name is not None:
                text = str(name).strip()
                if text and text.lower() != "none":
                    return text
    except Exception:
        pass
    return "<unnamed>"


def iter_currency_slots(pc: Any) -> list[tuple[int, Any, str, int]]:
    cm = find_currency_manager(pc)
    if cm is None:
        return []
    try:
        currencies = getattr(cm, "currencies", None)
        count = len(currencies) if currencies is not None else 0
    except Exception:
        return []
    out: list[tuple[int, Any, str, int]] = []
    for index in range(count):
        try:
            slot = currencies[index]
        except Exception:
            continue
        try:
            raw = getattr(slot, "Amount", 0)
            amount = int(raw) if raw is not None else 0
        except Exception:
            amount = 0
        out.append((index, slot, currency_slot_name(slot), amount))
    return out


def resolve_currency_slot_idx(pc: Any, needle: str) -> tuple[int | None, str]:
    rows = iter_currency_slots(pc)
    if not rows:
        return None, "no currency slots readable on this PlayerController"
    raw = (needle or "").strip()
    if not raw:
        return None, "empty currency query"

    # Prefer canonical token (VaultCard04_Tokens) so vaultcard_4 / vc4 resolve correctly.
    # Important: "vaultcard4" is NOT a substring of "vaultcard04_tokens".
    token = _needle_to_token(raw) or raw
    want = token.lower().replace(" ", "").replace("-", "_")
    stem = want.replace("_tokens", "")

    for index, _slot, name, _amount in rows:
        n = name.lower().replace(" ", "").replace("-", "_")
        if n == want or n == stem or n == f"{stem}_tokens":
            return index, name

    # Vault card soft match: VaultCard04 / VaultCard4 / …_Tokens
    m = re.fullmatch(r"vaultcard0*([1-4])(?:_tokens)?", stem)
    if m:
        num = m.group(1)
        accept = {
            f"vaultcard0{num}",
            f"vaultcard{num}",
            f"vaultcard0{num}_tokens",
            f"vaultcard{num}_tokens",
        }
        for index, _slot, name, _amount in rows:
            n = name.lower().replace(" ", "").replace("-", "_")
            if n in accept:
                return index, name

    available = ", ".join(f"[{i}] {name}" for i, _slot, name, _amount in rows)
    return None, f"no slot matched '{needle}' (token={token}). available: {available}"


def read_currency_amount(pc: Any, slot_idx: int) -> int | None:
    for index, _slot, _name, amount in iter_currency_slots(pc):
        if index == slot_idx:
            return int(amount)
    return None


def write_currency_slot_amount(pc: Any, slot_idx: int, amount: int) -> tuple[bool, str]:
    cm = find_currency_manager(pc)
    if cm is None:
        return False, "No CurrencyManager on this controller."
    try:
        currencies = getattr(cm, "currencies", None)
    except Exception as ex:  # noqa: BLE001
        return False, f"currencies read failed: {ex}"
    if currencies is None:
        return False, "CurrencyManager.currencies is None."
    try:
        count = len(currencies)
    except Exception:
        count = 0
    if count <= 0:
        return False, "CurrencyManager.currencies is empty."
    if slot_idx < 0 or slot_idx >= count:
        return False, f"slot_index {slot_idx} out of range [0..{count - 1}]."
    try:
        slot = currencies[slot_idx]
    except Exception as ex:  # noqa: BLE001
        return False, f"currencies[{slot_idx}] read failed: {ex}"
    before = getattr(slot, "Amount", None)
    try:
        slot.Amount = int(amount)
    except Exception as ex:  # noqa: BLE001
        return False, f"setattr Amount failed: {ex}"
    try:
        on_rep = getattr(cm, "OnRep_Currencies", None)
        if callable(on_rep):
            on_rep()
    except Exception:
        pass
    after = read_currency_amount(pc, slot_idx)
    return True, f"slot[{slot_idx}].Amount: {before} -> {after}"


def give_currency_on_pc(target_pc: Any, currency_token: str, amount: int) -> tuple[bool, str]:
    """Call GbxCurrencyFunctionLibrary.GiveCurrency (additive)."""
    lib = _get_currency_function_library()
    if lib is None:
        return False, "GbxCurrencyFunctionLibrary not found"
    give = getattr(lib, "GiveCurrency", None)
    if not callable(give):
        return False, "GiveCurrency not callable"
    # Use the live wallet's definition when it is a real FGbxDefPtr. Older SDKs
    # expose slot.type as WrappedStruct, which GiveCurrency cannot cast.
    ptr = None
    slot_idx, slot_name = resolve_currency_slot_idx(target_pc, currency_token)
    if slot_idx is not None:
        for index, slot, _name, _value in iter_currency_slots(target_pc):
            if index == slot_idx:
                ptr = _coerce_currency_def_ptr(getattr(slot, "type", None), currency_token)
                break
    if ptr is None:
        ptr = _make_currency_def_ptr(currency_token)
    if not _is_real_fgbx_def_ptr(ptr):
        if not fgbx_def_ptr_api_ok():
            return (
                False,
                "GiveCurrency needs Oak2 SDK 0.3+ (FGbxDefPtr). "
                "In Squ1ggs Boosting Tools → Setup → Update base SDK, then fully restart BL4.",
            )
        hint = ""
        low = (currency_token or "").lower()
        if "vaultcard04" in low or "vaultcard4" in low:
            hint = (
                " — Vault Card 4 (Desert Dreams) wallet slot missing on this save. "
                "Open/activate that vault card once in-game, then retry."
            )
        return False, f"FGbxDefPtr currency def failed for {currency_token!r}{hint}"
    mgr = getattr(target_pc, "CurrencyManager", None)
    trials: list[tuple[str, tuple[Any, ...]]] = [("pc", (target_pc, ptr, int(amount)))]
    if mgr is not None:
        trials.append(("mgr", (mgr, ptr, int(amount))))
    last_error = ""
    for label, args in trials:
        try:
            give(*args)
            return True, f"GiveCurrency({currency_token}, {amount}) via {label}" + (
                f" slot={slot_name}" if slot_idx is not None else " (fabricated def)"
            )
        except TypeError as ex:
            last_error = f"{label} TypeError: {ex}"
        except Exception as ex:  # noqa: BLE001
            err = f"{label}: {type(ex).__name__}: {ex}"
            if "FGbxDefPtr" in err or "WrappedStruct" in err:
                return (
                    False,
                    f"{err} — usually means Oak2 SDK is older than 0.3. "
                    "Setup → Update base SDK, fully restart BL4, and use the latest Squ1ggs EXE.",
                )
            return False, err
    return False, last_error or "GiveCurrency failed"


def give_currency_by_needle(pc: Any, needle: str, amount: int) -> tuple[bool, str]:
    """Map cash/eridium/vault-card names to chunked GiveCurrency calls."""
    token = _needle_to_token(needle)
    if token is None:
        return False, f"unknown currency needle {needle!r}"
    value = int(amount)
    if value == 0:
        return False, "amount is zero"
    if value < 0:
        return give_currency_on_pc(pc, token, value)
    remaining = value
    chunks = 0
    while remaining > 0:
        chunk = min(remaining, _INT32_MAX)
        ok, message = give_currency_on_pc(pc, token, chunk)
        if not ok:
            return False, f"chunk {chunks + 1}: {message}"
        remaining -= chunk
        chunks += 1
    if chunks > 1:
        return True, f"GiveCurrency({token}) total {value} in {chunks} chunks"
    return True, f"GiveCurrency({token}, {value})"


def set_currency_to_target(pc: Any, needle: str, target: int) -> tuple[bool, str]:
    """Set a wallet to an absolute amount (raise or lower) via slot write, then GiveCurrency if needed."""
    target_value = max(0, min(_INT32_MAX, int(target)))
    index, slot_name = resolve_currency_slot_idx(pc, needle)
    current = read_currency_amount(pc, index) if index is not None else None
    if current is not None and current == target_value:
        return True, f"{slot_name}[{index}] already {current}"

    # Direct slot write first — supports lowering vault-card tokens / wallets.
    # GiveCurrency is additive-only, so decreases must succeed on the slot path.
    slot_detail = ""
    if index is not None:
        slot_ok, slot_detail = write_currency_slot_amount(pc, index, target_value)
        after = read_currency_amount(pc, index)
        if slot_ok and after is not None and after == target_value:
            return True, f"slot[{index}] {slot_name}: {slot_detail}"
        if after is not None and after == target_value:
            return True, f"slot[{index}] {slot_name}: set to {after}"
        # Raised some but not enough — keep going with GiveCurrency delta.
        if after is not None and current is not None and after > current:
            current = after
        # Lowering failed — do not pretend success when still above target.
        if (
            current is not None
            and target_value < current
            and (after is None or after > target_value)
        ):
            return False, (
                f"could not lower {slot_name}[{index}] from {current} to {target_value} "
                f"(slot: {slot_detail or 'write failed'})"
            )

    token = _needle_to_token(needle)
    base_before_write = int(current) if current is not None else 0
    if token is not None and target_value > base_before_write:
        delta = target_value - base_before_write
        api_ok, api_detail = give_currency_by_needle(pc, needle, delta)
        if api_ok:
            final = read_currency_amount(pc, index) if index is not None else None
            return True, f"authoritative GiveCurrency +{delta} -> {final} ({api_detail})"
        if index is not None:
            return False, f"slot ({slot_detail}); GiveCurrency: {api_detail}"
        return False, api_detail

    if token is None:
        if index is not None:
            return False, f"slot write did not reach target ({slot_detail})"
        return False, f"unknown currency {needle!r}"

    base = int(current) if current is not None else 0
    if base == target_value:
        return True, f"{needle} at {base} after slot attempt"
    return False, f"could not reach {needle} target {target_value} (slot: {slot_detail or 'n/a'})"
