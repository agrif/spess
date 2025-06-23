import sys
import time
import typing

import requests

import spess._json
import spess.models
import spess._paged
import spess._rate_limit

# any sort of error
class Error(Exception):
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

# we did something wrong
class ClientError(Error):
    pass

# they did something wrong
class ServerError(Error):
    pass

# HTTP 204 no content, sometimes signals empty
class NoContentError(Error):
    pass

class Backend:
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

    def _debug(self, *args, **kwargs):
        if self.debug:
            print(*args, file=sys.stderr, **kwargs)

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
            raise

        self._debug('<<<', r.status_code, json)

        if 200 <= r.status_code < 300:
            return json

        # otherwise, an error
        err = json.get('error', {})
        try:
            msg = str(err.get('message'))
        except Exception:
            msg = None
        try:
            code = int(err.get('code'))
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
            if isinstance(json, dict):
                json = json['data']
            else:
                raise TypeError(type(json))
        return spess._json.from_json(ty, json)

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
            if not isinstance(json, dict):
                raise TypeError(type(json))

            meta = spess.models.Meta.from_json(json['meta'])
            data = spess._json.from_json(list[ty], json['data']) # type: ignore

            return (meta, data)

        return spess._paged.Paged(get_page)
