# Native item-card UI provenance


ative_card_ui/ contains extracted Borderlands 4 Cohtml item-card resources
(HTML, CSS, JS, fonts, icons) from an installed game build. These assets are
Gearbox / 2K game UI artwork and code — they are **not** MIT-licensed SQBT
originals and are not relicensed by this project.

Host glue (
ative_card_protocol.js, 
ative_card_adapter.js,

ative_card_model.js, 
ative_card_compat.css, 
enderer/native_item_card.js)
adapts those templates for Chromium/Electron inside Squ1ggs Boosting Tools
(sqbt-card:// privileged protocol).

Per-file hashes for the extracted tree are recorded in

ative_card_ui/manifest.json.
