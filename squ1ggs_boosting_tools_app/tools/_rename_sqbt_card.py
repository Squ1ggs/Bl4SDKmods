"""Rename msbt-card → sqbt-card (keep msbt-card as silent alias)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(r"C:\Users\picto\Documents\New folder (4)\squ1ggs_boosting_tools_app")


def _replace_all(text: str, pairs: list[tuple[str, str]], label: str) -> str:
    for old, new in pairs:
        if old not in text:
            print(f"  MISS {label}: {old[:70]!r}")
        else:
            count = text.count(old)
            text = text.replace(old, new)
            print(f"  OK {label} x{count}: {old[:50]!r}")
    return text


def patch_protocol() -> None:
    path = ROOT / "native_card_protocol.js"
    text = path.read_text(encoding="utf-8")
    text = _replace_all(
        text,
        [
            (
                'const schemes = ["coui", "common", "msbt-card", "sqbt-asset"];',
                'const schemes = ["coui", "common", "sqbt-card", "msbt-card", "sqbt-asset"];',
            ),
            ("type:'msbt-card-size'", "type:'sqbt-card-size'"),
            ("type:'msbt-card-rendered'", "type:'sqbt-card-rendered'"),
            ("type:'msbt-card-error'", "type:'sqbt-card-error'"),
            ("type:'msbt-card-ready'", "type:'sqbt-card-ready'"),
        ],
        "protocol",
    )
    # Accept both model message types in the injected listener.
    old_listen = "event.data?.type!=='msbt-card-model'"
    new_listen = (
        "event.data?.type!=='sqbt-card-model'&&event.data?.type!=='msbt-card-model'"
    )
    if old_listen in text:
        text = text.replace(old_listen, new_listen)
        print("  OK protocol listen dual-model")
    else:
        print("  MISS protocol listen")

    # Dual-register protocol handlers.
    old_handle = 'protocol.handle("msbt-card", (request) => {'
    if old_handle in text and 'protocol.handle("sqbt-card"' not in text:
        # Find the handler function body end — the handle call closes with });
        idx = text.find(old_handle)
        # Replace opening with named handler + both registrations at the end.
        # Simpler: register sqbt-card with same callback by duplicating the call.
        rest = text[idx + len(old_handle) :]
        # Find matching close of this arrow function — look for "\n  });\n" after handle
        close = rest.find("\n  });")
        if close < 0:
            raise SystemExit("could not find protocol.handle close")
        body = rest[:close]
        after = rest[close + len("\n  });") :]
        text = (
            text[:idx]
            + "const handleNativeCardRequest = (request) => {"
            + body
            + "\n  };\n"
            + '  protocol.handle("sqbt-card", handleNativeCardRequest);\n'
            + '  protocol.handle("msbt-card", handleNativeCardRequest);'  # silent alias
            + after
        )
        print("  OK protocol dual handle")
    else:
        print("  SKIP protocol dual handle (already done or missing)")

    path.write_text(text, encoding="utf-8")
    print("wrote", path.name)


def patch_item_card(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = _replace_all(
        text,
        [
            (
                "Loads msbt-card://inventory/card.html via privileged protocols registered in main.js.",
                "Loads sqbt-card://inventory/card.html via privileged protocols registered in main.js.",
            ),
            (
                "const modelApi = root.MSBTNativeCard || root.SQBTNativeCard;",
                "const modelApi = root.SQBTNativeCard || root.MSBTNativeCard;",
            ),
            ('type: "msbt-card-model"', 'type: "sqbt-card-model"'),
            (
                'frame.src = "msbt-card://inventory/card.html?v=1623";',
                'frame.src = "sqbt-card://inventory/card.html?v=1623";',
            ),
            ('data.type === "msbt-card-ready"', 'data.type === "sqbt-card-ready" || data.type === "msbt-card-ready"'),
            ('type: "msbt-card-model"', 'type: "sqbt-card-model"'),  # second occurrence in ready handler
            ('data.type === "msbt-card-size"', 'data.type === "sqbt-card-size" || data.type === "msbt-card-size"'),
            (
                'data.type === "msbt-card-rendered"',
                'data.type === "sqbt-card-rendered" || data.type === "msbt-card-rendered"',
            ),
            (
                'data.type === "msbt-card-error"',
                'data.type === "sqbt-card-error" || data.type === "msbt-card-error"',
            ),
        ],
        path.name,
    )
    path.write_text(text, encoding="utf-8")
    print("wrote", path)


def patch_model(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = _replace_all(
        text,
        [
            (
                "else root.MSBTNativeCard = { toNativeCardModel, compact };",
                "else root.SQBTNativeCard = root.MSBTNativeCard = { toNativeCardModel, compact };",
            ),
        ],
        path.name,
    )
    path.write_text(text, encoding="utf-8")
    print("wrote", path)


def patch_index_html() -> None:
    path = ROOT / "renderer" / "index.html"
    text = path.read_text(encoding="utf-8")
    text = text.replace("msbt-card:", "sqbt-card:")
    if "msbt-card" in text:
        print("  WARN index.html still has msbt-card")
    else:
        print("  OK index.html CSP → sqbt-card")
    path.write_text(text, encoding="utf-8")


def patch_smoke() -> None:
    for name in ("smoke_native_card.js", "smoke_native_card_assets.js"):
        path = ROOT / "tools" / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        text = text.replace("msbt-card:", "sqbt-card:")
        path.write_text(text, encoding="utf-8")
        print("wrote", path)


def patch_provenance() -> None:
    path = ROOT / "NATIVE_CARD_PROVENANCE.md"
    if not path.is_file():
        return
    path.write_text(
        """# Native item-card UI provenance

`native_card_ui/` contains extracted Borderlands 4 Cohtml item-card resources
(HTML, CSS, JS, fonts, icons) from an installed game build. These assets are
Gearbox / 2K game UI artwork and code — they are **not** MIT-licensed SQBT
originals and are not relicensed by this project.

Host glue (`native_card_protocol.js`, `native_card_adapter.js`,
`native_card_model.js`, `native_card_compat.css`, `renderer/native_item_card.js`)
adapts those templates for Chromium/Electron inside Squ1ggs Boosting Tools
(`sqbt-card://` privileged protocol).

Per-file hashes for the extracted tree are recorded in
`native_card_ui/manifest.json`.
""",
        encoding="utf-8",
    )
    print("wrote provenance")


def main() -> None:
    patch_protocol()
    patch_item_card(ROOT / "native_item_card.js")
    patch_item_card(ROOT / "renderer" / "native_item_card.js")
    patch_model(ROOT / "native_card_model.js")
    patch_model(ROOT / "renderer" / "native_card_model.js")
    patch_index_html()
    patch_smoke()
    patch_provenance()
    # Verify primary call sites
    leftovers = []
    for p in [
        ROOT / "native_card_protocol.js",
        ROOT / "native_item_card.js",
        ROOT / "renderer" / "native_item_card.js",
        ROOT / "native_card_model.js",
        ROOT / "renderer" / "native_card_model.js",
        ROOT / "renderer" / "index.html",
    ]:
        t = p.read_text(encoding="utf-8")
        # Allowed leftovers: alias scheme + alias message accept + MSBTNativeCard alias assign
        for line_no, line in enumerate(t.splitlines(), 1):
            if "msbt-card://" in line and "sqbt-card://" not in line:
                leftovers.append(f"{p.name}:{line_no}: {line.strip()}")
            if 'src = "msbt-card' in line:
                leftovers.append(f"{p.name}:{line_no}: {line.strip()}")
    print("leftover primary URLs:", leftovers or "none")


if __name__ == "__main__":
    main()
