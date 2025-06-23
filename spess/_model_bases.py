import datetime as dt
import enum
import typing

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
