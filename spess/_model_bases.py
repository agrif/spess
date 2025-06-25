from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import functools
import typing

import spess.client
from spess._json import Json

# for custom repr
class date(dt.date):
    def __repr__(self) -> str:
        return f'<{self:%Y-%m-%d}>'

# for custom repr
class datetime(dt.datetime):
    def __repr__(self) -> str:
        return f'<{self:%Y-%m-%d %H:%M:%S UTC%:z}>'

# for custom repr and str, common json impl
class Enum(enum.Enum):
    def __repr__(self) -> str:
        return f'{self.__class__.__name__}.{self.name}'

    def __str__(self) -> str:
        return str(self.value)

    def to_json(self) -> Json:
        return self.value

    @classmethod
    def from_json(cls, v: Json) -> typing.Self:
        if not isinstance(v, str):
            raise TypeError(type(v))
        return cls(v)

class LocalClient:
    _client: spess.client.Client | None

    def _set_client(self, client: spess.client.Client):
        self._client = client
        if dataclasses.is_dataclass(self):
            for field in dataclasses.fields(self):
                child = getattr(self, field.name, None)
                if isinstance(child, LocalClient):
                    child._set_client(client)

    @property
    def _c(self) -> spess.client.Client:
        if getattr(self, '_client', None) is None or self._client is None:
            raise RuntimeError('model has no reference to client')
        return self._client

class Synced:
    _class_key: typing.ClassVar[str]

    def _update(self, other: typing.Self) -> typing.Self:
        if dataclasses.is_dataclass(other):
            for field in dataclasses.fields(other):
                setattr(self, field.name, getattr(other, field.name))
            return self
        return other

@functools.total_ordering
class Keyed[SelfKey](Synced):
    @classmethod
    def _resolve(cls, other: str | SelfKey) -> str:
        if isinstance(other, str):
            return other
        return getattr(other, cls._class_key)

    def _compare_keys(self, other: object) -> tuple[str, str] | None:
        if isinstance(other, Keyed):
            if type(self) == type(other):
                # compare keys
                return (getattr(self, self._class_key), getattr(other, other._class_key))
            else:
                # flat refuse to compare to another keyed that isn't us
                return None

        # if the other is a string, compare to that
        if isinstance(other, str):
            return (getattr(self, self._class_key), other)

        # ok, try to compare keys
        try:
            return (getattr(self, self._class_key), getattr(other, self._class_key))
        except AttributeError:
            return None

    def __eq__(self, other: object) -> bool:
        keys = self._compare_keys(other)
        if keys is None:
            return NotImplemented
        else:
            return keys[0] == keys[1]

    def __lt__(self, other: object) -> bool:
        keys = self._compare_keys(other)
        if keys is None:
            return NotImplemented
        else:
            return keys[0] < keys[1]
