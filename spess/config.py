from __future__ import annotations

import contextlib
import dataclasses
import datetime as dt
import io
import os
import pathlib
import typing

import jwt
import platformdirs

import spess.models

__all__ = ['Config', 'Tokens']

@dataclasses.dataclass
class Config:
    """Configuration info for :class:`spess.client.Client`.

    This class will load configuration preferentially from the
    environment, and then from values overridden by
    :func:`with_values`, then finally by loading configuration files.
    """

    @dataclasses.dataclass
    class File:
        #: The path to this configuration file.
        path: pathlib.Path
        #: Should `spess` be allowed to write to this file?
        write: bool

        def _read_file(self) -> typing.ContextManager[typing.TextIO]:
            return open(self.path)

        @contextlib.contextmanager
        def _replace_file(self) -> typing.Iterator[typing.TextIO]:
            if not self.write:
                yield io.StringIO()

            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + '.new')
            try:
                with open(tmp, 'w') as f:
                    yield f
            except Exception:
                raise
            else:
                tmp.replace(self.path)
            finally:
                tmp.unlink(missing_ok=True)

    #: The tokens, stored by default in `${config}/spess/tokens.txt`.
    tokens: Tokens

    #: The base url to use to access `spacetraders.io`.
    url: str | None = None

    #: The account token to use, or the account name to load, or ``None``.
    #:
    #: If a string is given, this will either load the token itself
    #: from the string, or search `tokens.txt` for an account token
    #: matching this identifier. If ``None``, the most recent account token
    #: in `tokens.txt` will be used.
    account_token: spess.models.Token | str | None = None

    #: The agent token to use, or the agent name to load, or ``None``.
    #:
    #: If a string is given, this will either load the token itself
    #: from the string, or search `tokens.txt` for an agent token
    #: matching this identifier. If ``None``, the most recent agent token
    #: in `tokens.txt` will be used.
    agent_token: spess.models.Token | str | None = None

    @classmethod
    def default(cls) -> typing.Self:
        """Use the default paths and configuration."""
        return cls.with_values()

    @classmethod
    def with_values(
            cls,
            tokens_path: str | pathlib.Path | None = None,
            tokens_write: bool | None = None,
            url: str | None = None,
            account_token: spess.models.Token | str | None = None,
            agent_token: spess.models.Token | str | None = None,
    ) -> typing.Self:
        """Use the default paths and configuration, but override
        certain values.
        """
        dirs = platformdirs.PlatformDirs(__package__)

        tokens = Tokens(
            path = cls._get_path('TOKENS', tokens_path, dirs.user_config_dir, 'tokens.txt'),
            write = cls._get_bool('TOKENS_WRITE', tokens_write, True),
        )

        url = cls._get_env('URL', str, url, None)
        account_token = cls._get_token('ACCOUNT_TOKEN', account_token)
        agent_token = cls._get_token('AGENT_TOKEN', agent_token)

        return cls(
            tokens = tokens,
            url = url,
            account_token = account_token,
            agent_token = agent_token,
        )

    @classmethod
    def _get_bool(cls, env: str, arg: bool | None, default: bool) -> bool:
        def parse_bool(s):
            if b.lower() == 'false' or b.strip('0') == '':
                return False
            return True
        return cls._get_env(env, parse_bool, arg, default)

    @classmethod
    def _get_path(cls, env: str, arg: str | pathlib.Path | None, base: str, leaf: str) -> pathlib.Path:
        default = pathlib.Path(base) / leaf
        path = cls._get_env(env, pathlib.Path, pathlib.Path(arg) if arg else None, default)
        return path.expanduser().resolve()

    @classmethod
    def _get_token(cls, env: str, arg: spess.models.Token | str | None) -> spess.models.Token | str | None:
        name: str | None = cls._get_env(env, str, None, None)
        if name is not None:
            return name
        return arg

    @classmethod
    def _get_env[T](cls, env: str, f: typing.Callable[[str], T], arg: T | None, default: T) -> T:
        env = f'{__package__.upper()}_{env}'
        try:
            return f(os.environ[env])
        except KeyError:
            return arg if arg is not None else default

@dataclasses.dataclass
class Tokens(Config.File):
    """Tokens loaded from `tokens.txt`."""

    #: Account Tokens
    account: list[spess.models.Token] = dataclasses.field(default_factory=list)
    #: Agent Tokens
    agent: list[spess.models.Token] = dataclasses.field(default_factory=list)

    def _resolve_token(self, tokens: list[spess.models.Token], tok: spess.models.Token | str | None) -> typing.Iterator[spess.models.Token]:
        if isinstance(tok, spess.models.Token):
            yield tok
            return
        if isinstance(tok, str) and spess.models.Token.is_token(tok):
            yield spess.models.Token.from_str(tok)
            return
        for token in tokens:
            if tok is None or tok == token.identifier:
                yield token

    def get_account(self, tok: spess.models.Token | str | None = None) -> spess.models.Token:
        """Get an account token, directly or by identifier. If ``None``,
        choose the most recent account token.
        """
        for token in self._resolve_token(self.account, tok):
            return token
        if self.account:
            raise ValueError(f'account token for {tok!r} not found')
        raise RuntimeError('no account tokens available')

    def get_agent(self, reset_date: dt.date, tok: spess.models.Token | str | None = None) -> spess.models.Token:
        """Get an agent token, directly or by identifier. If ``None``,
        choose the most recent valid agent token.

        This will only return tokens valid for the given ``reset_date``.
        """
        for token in self._resolve_token(self.agent, tok):
            if token.reset_date == reset_date:
                return token
        if isinstance(tok, spess.models.Token):
            raise ValueError(f'agent token expired: has reset {tok.reset_date}, expected {reset_date}')
        if self.account:
            raise ValueError(f'agent token for {tok!r} with reset date {reset_date} not found')
        raise RuntimeError('no agent tokens available')

    def __post_init__(self) -> None:
        self._read()

    def _read(self) -> None:
        try:
            with self._read_file() as f:
                lines = f.readlines()
        except IOError:
            lines = []

        for i, line in enumerate(lines):
            line = line.split('#', 1)[0].strip()
            if not line:
                continue

            try:
                tok = spess.models.Token.from_str(line)
            except Exception:
                raise ValueError(f'could not parse token on line {i+1} of {self.path}')
            match tok.sub:
                case 'account-token':
                    self.account.append(tok)
                case 'agent-token':
                    self.agent.append(tok)
                case v:
                    raise ValueError(f'unknown token type {v!r}')

        self.account.sort(key=lambda t: t.iat, reverse=True)
        self.agent.sort(key=lambda t: t.iat, reverse=True)

if __name__ == '__main__':
    from rich import print
    print(Config.default())
