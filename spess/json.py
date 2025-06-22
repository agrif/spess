from __future__ import annotations

import datetime as dt
import enum
import types
import typing

JsonInner = typing.TypeVar('JsonInner')
JsonLayer: typing.TypeAlias = typing.Mapping[str, JsonInner] | typing.Sequence[JsonInner] | bool | float | int | str | None
Json: typing.TypeAlias = JsonLayer['Json']

@typing.runtime_checkable
class JsonFormat(typing.Protocol):
    def to_json(self) -> Json:
        raise NotImplementedError

    @classmethod
    def from_json(cls, v: Json) -> typing.Self:
        raise NotImplementedError

ToJson: typing.TypeAlias = JsonFormat | dt.datetime | JsonLayer['ToJson']

def to_json(v: ToJson) -> Json:
    if isinstance(v, JsonFormat):
        return v.to_json()
    elif isinstance(v, dt.datetime):
        s = v.astimezone(dt.UTC).isoformat()
        if s.endswith('+00:00'):
            s = s[:-len('+00:00')] + 'Z'
        return s
    elif isinstance(v, dict):
        return {str(k): to_json(val) for k, val in v.items()}
    elif isinstance(v, list):
        return [to_json(val) for val in v]
    elif isinstance(v, (bool, float, int, str, types.NoneType)):
        return v
    else:
        raise TypeError(type(v))

FromJson: typing.TypeAlias = JsonFormat | dt.datetime | JsonLayer['FromJson']

def from_json[T: FromJson](cls: type[T], v: Json) -> T:
    args = typing.get_args(cls)
    origin = typing.get_origin(cls)
    if origin is not None:
        cls = origin

    # lots of casts to help checker know that cls(...) has type T

    if issubclass(cls, JsonFormat):
        return typing.cast(T, cls.from_json(v))
    elif issubclass(cls, dt.datetime):
        if isinstance(v, str):
            return typing.cast(T, cls.fromisoformat(v).astimezone())
        else:
            raise TypeError('expected str')
    elif issubclass(cls, dict) and len(args) == 2 and issubclass(args[0], str):
        if isinstance(v, dict):
            return typing.cast(T, cls({k: from_json(args[1], val) for k, val in v.items()}))
        else:
            raise TypeError('expected dict')
    elif issubclass(cls, list) and len(args) == 1:
        if isinstance(v, list):
            return typing.cast(T, cls([from_json(args[0], val) for val in v]))
        else:
            raise TypeError('expected list')
    elif issubclass(cls, bool):
        if isinstance(v, bool):
            return typing.cast(T, cls(v))
        else:
            raise TypeError('expected bool')
    elif issubclass(cls, float):
        if isinstance(v, (int, float)):
            return typing.cast(T, cls(v))
        else:
            raise TypeError('expected float')
    elif issubclass(cls, int):
        if isinstance(v, int):
            return typing.cast(T, cls(v))
        else:
            raise TypeError('expected int')
    elif issubclass(cls, str):
        if isinstance(v, str):
            return typing.cast(T, cls(v))
        else:
            raise TypeError('expected str')
    elif cls == types.NoneType:
        # NoneType can't be subclassed
        if v == None:
            return typing.cast(T, None)
        else:
            raise TypeError('expected None')
    else:
        raise TypeError(cls)

# for custom repr and str
class Enum(enum.Enum):
    def __repr__(self) -> str:
        return f'{self.__class__.__name__}.{self.name}'

    def __str__(self) -> str:
        return str(self.value)

# for custom repr
class datetime(dt.datetime):
    def __repr__(self) -> str:
        return f'<{self:%Y-%m-%d %H:%M:%S UTC%:z}>'
