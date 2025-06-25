"""This module exports all the models used in ``spess``. It is also
available under the alias ``spess.m``.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import typing

import jwt

import spess._json
import spess._model_bases as bases

# re-export generated code
import spess._generated.models
from spess._generated.models import *
__all__ = spess._generated.models.__all__

# but also we have a few custom definitions
__all__ += ['Token']
__all__.sort()

@dataclasses.dataclass
class Token:
    """`spacetraders.io` Account or Agent Token"""

    #: The token string, as shown on the website.
    token: str = dataclasses.field(repr=False)

    #: The name of the account or agent associated with this token.
    identifier: str
    #: The version of `spacetraders.io` that created this token.
    version: str
    #: The reset date for an Agent token.
    reset_date: dt.date | None
    #: When was this token created?
    iat: dt.datetime
    #: The token type, either ``'account-token'`` or ``'agent-token'``.
    sub: str

    #: Any other data the token contains that is not parsed elsewhere.
    extra: dict[str, typing.Any]

    def to_json(self) -> spess._json.Json:
        return self.token

    @classmethod
    def from_json(cls, v: spess._json.Json) -> typing.Self:
        if not isinstance(v, str):
            raise TypeError(v)
        return cls.from_str(v)

    @classmethod
    def is_token(cls, token: str) -> bool:
        """Returns ``True`` if this string looks like a token string."""
        try:
            jwt.decode(token, options={'verify_signature': False})
            return True
        except Exception:
            return False

    @classmethod
    def from_str(cls, token: str) -> typing.Self:
        """Parse a token string into a ``Token``."""
        info = jwt.decode(token, options={'verify_signature': False})
        from_json = spess._json.from_json

        try:
            reset_date_val = info.pop('reset_date')
        except KeyError:
            reset_date = None
        else:
            reset_date = bases.date.fromisoformat(from_json(str, reset_date_val))

        return cls(
            token = from_json(str, token),
            identifier = from_json(str, info.pop('identifier')),
            version = from_json(str, info.pop('version')),
            reset_date = reset_date,
            iat = bases.datetime.fromtimestamp(
                from_json(int, info.pop('iat')), dt.UTC).astimezone(),
            sub = from_json(str, info.pop('sub')),
            extra = info,
        )
