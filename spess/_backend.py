from __future__ import annotations

import asyncio
import datetime as dt
import sys
import time
import typing

import requests
import rich.progress

import spess._json
import spess.models
import spess._model_bases
import spess._paged
import spess._rate_limit

#: Set to False to turn off interactive waits.
_wait_interactive: bool = True

def _wait(*expirations: dt.datetime | None, message: str | None = None) -> None:
    """Backend for model wait methods."""
    if message is None:
        message = 'waiting'
    expiration = max(e for e in expirations if e is not None)
    start = dt.datetime.now(dt.UTC)
    expiration += dt.timedelta(seconds=1)
    amt = (expiration - start).total_seconds()

    if amt < 0:
        return

    if not _wait_interactive:
        time.sleep(amt)
        return

    prog = rich.progress.Progress(
        rich.progress.SpinnerColumn(),
        rich.progress.TextColumn('[progress.description]{task.description}'),
        rich.progress.TimeRemainingColumn(),
    )

    with prog:
        task = prog.add_task(message if message else 'waiting', total=amt)
        while True:
            now = dt.datetime.now(dt.UTC)
            elapsed = (now - start).total_seconds()
            prog.update(task, completed=elapsed)
            if now > expiration:
                return
            time.sleep(1)

async def _await(*expirations: dt.datetime | None) -> None:
    """Backend for model __await__ methods."""
    expiration = max(e for e in expirations if e is not None)
    start = dt.datetime.now(dt.UTC)
    expiration += dt.timedelta(seconds=1)
    amt = (expiration - start).total_seconds()
    await asyncio.sleep(amt)

class Error(Exception):
    """Base error class thrown by :class:`spess.client.Client`."""

    #: The error code reported by the server, if any.
    code: int | None

    def __init__(self, code: int | None = None, message: str | None = None):
        m = ''
        if code is not None and message is not None:
            m = f'(code {code}) {message}'
        elif code is not None:
            m = f'code {code}'
        elif message is not None:
            m = message
        else:
            m = 'unknown'

        super().__init__(m)
        self.code = code

class ParseError(Error):
    """ParseError indicates that the server provided a response, but
    it was not in the expected form and could not be parsed."""

class ClientError(Error):
    """ClientError indicates the server received the message but can't
    act on it, either because that action is not possible right now or
    because the message was not understood.
    """

class ServerError(Error):
    """ServerError indicates the server received the message but
    encountered an internal error.
    """

class NoContentError(Error):
    """NoContentError indicates an HTTP 204 response, which some
    commands interpret specially. This is handled internally when
    appropriate.
    """

class Backend:
    #: The default base url to use for requests.
    SERVER_URL: str

    def __init__(self, token: str, url: str | None = None, debug: bool = False):
        self.debug = debug

        self._base_url = self.SERVER_URL
        if url is not None:
            self._base_url = url
        self._base_url = self._base_url.lstrip('/')

        self._session = requests.Session()
        self._session.headers.update({'Authorization': f'Bearer {token}'})

        # spacetrader limits to 2 per second, 30 in 60s
        # put a 5% margin on it to be safe
        self._limit = spess._rate_limit.Any(
            spess._rate_limit.ConstantRate(2, margin=0.05),
            spess._rate_limit.Windowed(30, 60.0, margin=0.05),
        ).synced()

        self._aliases: dict[tuple[type[spess._model_bases.Keyed], str], str] = {}

    def _debug(self, *args, **kwargs):
        if self.debug:
            print(*args, file=sys.stderr, **kwargs)

    #
    # Requests
    #

    def _call_json(
            self,
            method: typing.Literal['get', 'post', 'patch'],
            path: str,
            query_args: dict[str, str | None] = {},
            body: spess._json.Json = None,
    ) -> spess._json.Json:
        # resolve the url
        url = self._base_url + path

        self._debug('>>>', url, query_args, body)

        # wrap the whole request here so we can retry later
        def do_request() -> requests.Response:
            self._limit.limit()
            return self._session.request(method, url, params=query_args, json=body)

        r = do_request()

        # rate limit failure
        if r.status_code == 429:
            # attempt to parse the retry-after header as seconds
            # spacetraders always seems to use seconds, not http dates
            retrystr = r.headers.get('retry-after', '2')
            try:
                retry = float(retrystr)
            except Exception:
                # use a conservative guess
                retry = 2

            # wait a reasonable amount of time for HTTP and try *once* more
            time.sleep(retry)
            r = do_request()

        # 204 no content is an exception, to force dealing with it
        if r.status_code == 204:
            self._debug('<<<', r.status_code)
            raise NoContentError(message='no content')

        try:
            json = r.json()
        except Exception:
            self._debug('<<<', r.status_code, repr(r.content))
            raise ParseError(message='response is not JSON')

        self._debug('<<<', r.status_code, json)

        if 200 <= r.status_code < 300:
            return json

        # otherwise, an error
        try:
            msg = str(json['error']['message'])
        except Exception:
            msg = None
        try:
            code = int(json['error']['code'])
        except Exception:
            code = None

        if 400 <= r.status_code < 500:
            raise ClientError(code, msg)
        raise ServerError(code, msg)

    def _call[T: spess._json.FromJson](
            self,
            ty: type[T],
            method: typing.Literal['get', 'post', 'patch'],
            path: str,
            path_args: dict[str, str | None] = {},
            query_args: dict[str, str | None] = {},
            body: spess._json.Json = None,
            adhoc: bool = False,
    ) -> T:
        # filter out Nones from values, which indicate absent optionals
        path_args = {k: v for k, v in path_args.items() if v is not None}
        query_args = {k: v for k, v in query_args.items() if v is not None}
        if isinstance(body, dict):
            body = {k: v for k, v in body.items() if v is not None}

        path = path.format(**path_args)
        json = self._call_json(method, path, query_args, body)

        # parse json
        if not adhoc:
            try:
                assert isinstance(json, dict)
                json = json['data']
            except Exception:
                raise ParseError(message=f'response has no {"data"!r} key')
        try:
            data = spess._json.from_json(ty, json)
        except Exception:
            raise ParseError(message=f'response is not {ty!r}')

        return self._merge(data)

    def _call_paginated[T](
            self,
            ty: type[T],
            method: typing.Literal['get', 'post', 'patch'],
            path: str,
            path_args: dict[str, str | None] = {},
            query_args: dict[str, str | None] = {},
            body: spess._json.Json = None,
    ) -> spess._paged.Paged[T]:
        # filter out Nones from values, which indicate absent optionals
        path_args = {k: v for k, v in path_args.items() if v is not None}
        query_args = {k: v for k, v in query_args.items() if v is not None}
        if isinstance(body, dict):
            body = {k: v for k, v in body.items() if v is not None}

        path = path.format(**path_args)

        def get_page(page: int = 1, limit: int = 10) -> tuple[spess.models.Meta, list[T]]:
            page_query_args = query_args.copy()
            page_query_args['page'] = str(page)
            page_query_args['limit'] = str(limit)

            json = self._call_json(method, path, page_query_args, body)

            try:
                assert isinstance(json, dict)
                meta_j = json['meta']
                data_j = json['data']
            except Exception:
                raise ParseError(message=f'paged response missing {"meta"!r} or {"data"!r} key')

            try:
                meta = spess.models.Meta.from_json(meta_j)
            except Exception:
                raise ParseError(message='paged response has bad meta')
            try:
                data = spess._json.from_json(list[ty], data_j) # type: ignore
            except Exception:
                raise ParseError(message=f'paged response data is not {ty!r}')

            return (meta, [self._merge(x) for x in data])

        return spess._paged.Paged(get_page)

    #
    # Aliases and Keys
    #

    def _resolve[T](self, ty: type[spess._model_bases.Keyed[T]], key: str | T) -> str:
        if isinstance(key, str):
            try:
                return self._aliases[(ty, key)]
            except KeyError:
                pass
        return ty._resolve(key)

    def _waypoint_to_system(self, waypoint: str | spess.models.WaypointLike) -> str:
        # try it as a system first (but strings are always waypoints)
        if not isinstance(waypoint, str):
            try:
                return self._resolve(spess.models.System, waypoint)
            except AttributeError:
                pass

        # fall back to a waypoint or waypoint alias
        waypoint = self._resolve(spess.models.Waypoint, waypoint)
        if not '-' in waypoint:
            raise ValueError(f'bad waypoint: {waypoint}')
        return waypoint.rsplit('-', 1)[0]

    def add_alias[T](self, ty: type[spess._model_bases.Keyed[T]], name: str, value: str | T) -> None:
        """Add an alias for the given type. This alias will be
        accepted as a valid name for this object in API calls. For
        example,

        .. code-block::

           ship = c.ship('NAME-2')
           c.add_alias(spess.models.Ship, 'hauler', ship)
           c.add_alias(spess.models.Ship, 'also-hauler', 'NAME-2')

           assert c.ship('hauler').symbol == 'NAME-2'
           assert c.ship('also-hauler').symbol == 'NAME-2'
        """
        self._aliases[(ty, name)] = self._resolve(ty, value)

    def remove_alias(self, ty: type[spess._model_bases.Keyed], name: str) -> str:
        """Removes an alias. See :func:`add_alias` for more info."""
        return self._aliases.pop((ty, name))

    @property
    def aliases(self) -> typing.Iterable[tuple[type[spess._model_bases.Keyed], str, str]]:
        """Iterate over the defined aliases. See :func:`add_alias`
        for more info.
        """
        for (ty, name), value in self._aliases.items():
            yield ty, name, value

    #
    # Model Manipulation
    #

    def _merge[T](self, obj: T) -> T:
        if isinstance(obj, spess._model_bases.Keyed):
            obj._client = self # type: ignore
        return obj
