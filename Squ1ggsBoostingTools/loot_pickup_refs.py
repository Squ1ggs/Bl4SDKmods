"""A pickup address map that never returns expired Unreal actor wrappers."""
from collections.abc import MutableMapping
from typing import Any
from unrealsdk.unreal import WeakPointer


class WeakPickupMap(MutableMapping):
    def __init__(self, values=None):
        self._references = {}
        if values:
            self.update(values)

    def __getitem__(self, key):
        reference = self._references[key]
        return reference()

    def __setitem__(self, key, value):
        if value is None:
            self._references.pop(key, None)
        else:
            self._references[key] = WeakPointer(value)

    def __delitem__(self, key):
        del self._references[key]

    def __iter__(self):
        return iter(tuple(self._references))

    def __len__(self):
        return len(self._references)

    def __contains__(self, key):
        reference = self._references.get(key)
        return reference is not None and reference() is not None

    def reference(self, key) -> Any:
        return self._references.get(key)
