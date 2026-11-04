"""Operation-local request admission for automatic interface concurrency."""
import math
import threading
import time
from collections import deque


MAX_AUTO_CONCURRENCY = 64
INITIAL_LATENCY = 5.0
HEADROOM = 0.9


def validate_rpm(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError("接口 RPM 必须是大于 0 的有限数字")
    return value


def initial_concurrency(rpm):
    return max(1, min(8, math.ceil(validate_rpm(rpm) / 60 * INITIAL_LATENCY * HEADROOM)))


class AutoConcurrency:
    """Pace starts by RPM and adapt in-flight requests using successful latency.

    Only network execution is sampled: queueing, prompt preparation and response
    validation must not inflate the estimate. Each task owns its controller;
    no mutable statistics or credentials are written to application settings.
    """

    def __init__(self, rpm, request_timeout, *, fixed_limit=None, clock=time.monotonic):
        self.rpm = validate_rpm(rpm)
        if (isinstance(request_timeout, bool) or not isinstance(request_timeout, (int, float))
                or not math.isfinite(request_timeout) or request_timeout <= 0):
            raise ValueError("请求超时必须是大于 0 的有限数字")
        self.request_timeout = request_timeout
        self.fixed_limit = fixed_limit
        if fixed_limit is not None:
            if type(fixed_limit) is not int or not 1 <= fixed_limit <= MAX_AUTO_CONCURRENCY:
                raise ValueError("自动并发槽位数无效")
            self.initial_limit = self.max_concurrency = fixed_limit
        else:
            # Reserve room for slower replies without creating an unbounded pool.
            self.max_concurrency = max(1, math.ceil(min(MAX_AUTO_CONCURRENCY,
                self.rpm / 60 * min(request_timeout, 120) * HEADROOM)))
            self.initial_limit = min(initial_concurrency(self.rpm), self.max_concurrency)
        self._clock = clock
        self._condition = threading.Condition()
        self._waiting = deque()
        self._limit = self.initial_limit
        self._active = 0
        self._next_start = float("-inf")
        self._cooldown_until = float("-inf")
        self._adjust_after = clock() + 5
        self._latency = None
        self._successes = 0
        self._failures = 0

    @property
    def limit(self):
        with self._condition:
            return self._limit

    def fresh(self):
        return AutoConcurrency(self.rpm, self.request_timeout, fixed_limit=self.fixed_limit)

    def acquire(self, is_cancelled=None):
        """Return the actual start time, or None when cancelled/queue timeout."""
        deadline = self._clock() + self.request_timeout
        with self._condition:
            ticket = object()
            self._waiting.append(ticket)
            try:
                while True:
                    if callable(is_cancelled) and is_cancelled():
                        return None
                    now = self._clock()
                    if now >= deadline:
                        return None
                    ready_at = max(self._next_start, self._cooldown_until)
                    if self._waiting[0] is ticket and self._active < self._limit and now >= ready_at:
                        self._active += 1
                        # No accumulated burst after idle time or a cooldown.
                        self._next_start = now + 60 / self.rpm
                        return now
                    delay = max(0.001, ready_at - now) if now < ready_at else 0.1
                    self._condition.wait(min(0.1, delay, deadline - now))
            finally:
                self._waiting.remove(ticket)
                self._condition.notify_all()

    def finish(self, started, *, success, cancelled=False):
        with self._condition:
            self._active -= 1
            try:
                if cancelled:
                    return
                now = self._clock()
                if not success:
                    self._failures += 1
                    self._successes = 0
                    # A single bad reply is not evidence of overloaded capacity.
                    # Coalesce simultaneous failures into one reduction/cooldown.
                    if self._failures >= 2 and now >= self._cooldown_until:
                        self._limit = max(1, self._limit // 2)
                        self._cooldown_until = now + 5
                        self._adjust_after = now + 10
                        self._failures = 0
                    return
                self._failures = 0
                latency = max(0.01, now - started)
                self._latency = latency if self._latency is None else self._latency * 0.8 + latency * 0.2
                self._successes += 1
                if now < self._adjust_after or self._successes < max(3, self._limit):
                    return
                target = (self.fixed_limit if self.fixed_limit is not None else
                          max(1, math.ceil(min(self.max_concurrency, self.rpm / 60 * self._latency * HEADROOM))))
                # Grow gradually; avoid keeping idle workers after faster replies.
                if target > self._limit:
                    self._limit = min(target, self._limit + max(1, math.ceil(self._limit / 4)))
                elif target < self._limit:
                    self._limit = max(target, math.floor(self._limit * 0.75))
                self._successes = 0
                self._adjust_after = now + 5
            finally:
                self._condition.notify_all()
