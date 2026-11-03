"""Wait for legacy document responses without exhausting HTTP query workers."""
from functools import partial

import anyio


# These old endpoints still return the completed project. Give their waiters a
# separate budget so status/config/cancel never compete for the same 40 slots.
_waiters = anyio.CapacityLimiter(8)


async def wait_document_call(function, *args, **kwargs):
    return await anyio.to_thread.run_sync(partial(function, *args, **kwargs), limiter=_waiters)
