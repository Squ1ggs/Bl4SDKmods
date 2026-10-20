"""Locate already-installed optional assets; never install or delete game files."""
def _game_paks_dir():
    from .registry import game_root
    root = game_root()
    return root / 'OakGame/Content/Paks' if root is not None else None
