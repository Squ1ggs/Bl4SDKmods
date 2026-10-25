# Source credits

BL4 Character Swapper is developed and integrated by **RDPSqu1ggs**.
The attachment implementation is extracted from SQBT; `provenance.json`
records the exact source functions and hashes.

## External dependencies and game assets

The BL4 Python SDK is required. BLImGui is optional; when installed, its
authors' credits and licences apply. No game meshes, textures or archive packs
are bundled in this standalone SDK mod. Optional imported-character packs
retain their source owners' rights and require separate release decisions.

## Native camera investigation

The post-update camera interception point and its calling convention were
identified using the public BL4 camera investigation at
https://github.com/cnrenil/Borderlands4_Enhanced . The SQBT implementation is
independent, uses SDK-reflected camera properties instead of fixed camera
structure offsets, and accepts only the locally audited executable hash and
entry bytes. No third-party hook implementation is bundled.
