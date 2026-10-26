"""A holder for the API key that cannot leak through repr, str, format, pickling or logging."""

from __future__ import annotations


class Secret:
    """Wraps a secret string. ``repr``/``str``/``format`` always give ``'***'``; only ``reveal()``
    returns the value, and only the transport calls it, at the moment a request is sent."""

    __slots__ = ("_v",)

    def __init__(self, value: str):
        object.__setattr__(self, "_v", value)

    def reveal(self) -> str:
        return self._v

    def __repr__(self) -> str:
        return "Secret('***')"

    __str__ = __repr__

    def __format__(self, spec: str) -> str:  # f"{secret}" must not leak either
        return "***"

    def __bool__(self) -> bool:
        return bool(self._v)

    def __reduce__(self):  # pragma: no cover - refuse to be pickled with the value
        raise TypeError("Secret cannot be pickled")

    def __setattr__(self, name, value):  # immutable
        raise AttributeError("Secret is immutable")
