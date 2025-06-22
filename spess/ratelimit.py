from __future__ import annotations

import time
import threading
import typing

Timer: typing.TypeAlias = typing.Callable[[], float]

class Limiter:
    """Base class for rate limit helpers."""

    def reset(self) -> None:
        """Reset the limiter state."""
        raise NotImplementedError

    # this should not mutate the limiter
    @property
    def wait_time(self) -> float | None:
        """Return number of seconds until next allowed request, or
        None for immediate."""
        raise NotImplementedError

    # *this* mutates the limiter, at the instant of use
    # careful: calling this in a tight loop should not cause
    # wait_time to grow unbounded. grow only to the largest time
    # you would see if the user obeyed wait_time
    def use(self) -> None:
        """Register a request with the limiter."""
        raise NotImplementedError

    #
    # Handy Methods
    #

    def limit(self) -> None:
        """Block until the next allowed request, register it, and return."""
        wait = self.wait_time
        if wait is not None:
            time.sleep(wait)
        self.use()

    def limit_iter[T](self, it: typing.Iterable[T]) -> typing.Iterable[T]:
        """Transform an iterator to yield objects at a limited rate."""
        for x in it:
            self.limit()
            yield x

    def __iter__(self) -> typing.Iterator[None]:
        """Yield None at a limited rate."""
        return self

    def __next__(self) -> None:
        """Yield None at a limited rate."""
        self.limit()

    #
    # Convenience Combinators
    #

    def synced(self) -> Limiter:
        """Guard this limiter inside a threading.Lock."""
        if isinstance(self, Synced):
            return self
        return Synced(self)

    def __or__(self, other: Limiter) -> Limiter:
        """Allow requests if either self or other allows it."""
        if isinstance(self, Any) and isinstance(other, Any):
            return Any(*self._children, *other._children)
        elif isinstance(self, Any):
            return Any(*self._children, other)
        elif isinstance(other, Any):
            return Any(self, *other._children)
        else:
            return Any(self, other)

class Unlimited(Limiter):
    """Dummy limiter that imposes no limit."""
    def reset(self) -> None:
        pass

    @property
    def wait_time(self) -> float | None:
        return None

    def use(self) -> None:
        pass

class ConstantRate(Limiter):
    """If a request comes in before 1/`rate` has elapsed from the last
    request, wait."""

    def __init__(self, rate: float, margin: float = 0,
                 timer: Timer = time.monotonic) -> None:
        self._delay = (1.0 + margin) / rate
        self._timer = timer
        self.reset()

    def reset(self) -> None:
        self._last_t = self._timer() - self._delay

    @property
    def wait_time(self) -> float | None:
        now = self._timer()
        wait = self._last_t + self._delay - now
        if wait > 0:
            return wait
        return None

    def use(self) -> None:
        self._last_t = self._timer()

class LeakyBucket(Limiter):
    """The bucket drains at a fixed `rate` and holds at most
    `burst`. If there is no room in the bucket for a new request, wait
    until there is."""

    def __init__(self, rate: float, burst: float, margin: float = 0,
                 timer: Timer = time.monotonic) -> None:
        self._rate = rate * (1.0 - margin)
        self._burst = burst * (1.0 - margin)
        self._timer = timer
        self.reset()

    def reset(self) -> None:
        self._last_v = 0.0
        self._last_t = self._timer()

    def _current(self, now: float) -> float:
        return max(0, self._last_v - self._rate * (now - self._last_t))

    @property
    def wait_time(self) -> float | None:
        now = self._timer()
        over = self._current(now) + 1 - self._burst
        if over >= 0:
            wait = over / self._rate
            return wait
        return None

    def use(self) -> None:
        now = self._timer()
        self._last_v = min(self._current(now) + 1, self._burst)
        self._last_t = now

class Windowed(Limiter):
    """Each request either adds to an existing window (if it's valid)
    or opens a new window of length `window` seconds. Each window can
    hold up to `max` requests. If there is no room left, wait until
    the current window expires and open a new one."""

    def __init__(self, max: int, window: float, margin: float = 0,
                 timer: Timer = time.monotonic) -> None:
        self._max = max
        self._window = window * (1 + margin)
        self._timer = timer
        self.reset()

    def reset(self) -> None:
        self._window_end = self._timer()
        self._window_count = 0

    @property
    def wait_time(self) -> float | None:
        now = self._timer()
        wait = self._window_end - now

        if wait > 0 and self._window_count >= self._max:
            return wait
        return None

    def use(self) -> None:
        now = self._timer()
        if now >= self._window_end:
            self._window_end = now + self._window
            self._window_count = 1
        else:
            self._window_count += 1

class Any(Limiter):
    """A request goes through if any child limiter allows it. If
    waiting is required, wait the minimum time."""

    def __init__(self, *children: Limiter) -> None:
        self._children = children

    def reset(self) -> None:
        for child in self._children:
            child.reset()

    @property
    def wait_time(self) -> float | None:
        wait = float('inf')
        for child in self._children:
            cwait = child.wait_time
            if cwait is None:
                return None
            elif cwait < wait:
                wait = cwait
        return wait

    def use(self) -> None:
        for child in self._children:
            child.use()

class Synced(Limiter):
    """A thread-safe wrapper for a limiter."""

    def __init__(self, inner: Limiter) -> None:
        self._inner = inner
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._inner.reset()

    @property
    def wait_time(self) -> float | None:
        return self._inner.wait_time

    def use(self) -> None:
        with self._lock:
            self._inner.use()
