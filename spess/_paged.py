from __future__ import annotations

import typing

import spess.models

__all__ = ['Paged']

class GetPage[T](typing.Protocol):
    def __call__(self, page: int = 1, limit: int = 10) -> tuple[spess.models.Meta, list[T]]: ...

class Paged[T]:
    def __init__(self, get_page: GetPage[T]) -> None:
        self._get_page = get_page

        self.bound_low = 0
        self.bound_high: int | None = None
        self.pagesize = 10

        self.firstpage = None

    def first(self) -> T:
        for v in self:
            return v
        raise ValueError('no items')

    def limit(self, amt: int) -> typing.Self:
        self.bound_high = self.bound_low + amt
        return self

    def all(self) -> list[T]:
        return list(self)

    def __iter__(self) -> typing.Iterator[T]:
        i = self.bound_low
        while self.bound_high is None or i < self.bound_high:
            page = (i // self.pagesize)
            pageoffset = i - page * self.pagesize
            if self.bound_high is not None:
                pagemax = self.bound_high - page * self.pagesize
            else:
                pagemax = self.pagesize
            _, data = self._get_page(page=page + 1, limit=self.pagesize)
            yield from data[pageoffset:pagemax]
            i += min(len(data), pagemax) - pageoffset
            if len(data) < self.pagesize:
                break
