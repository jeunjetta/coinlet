"""Protocol definitions for data sources.

The canonical streaming interface is `Source` from `coinlet.data.interfaces`
(PR #1 scaffold). Historical fetch (`fetch_historical` + `source_name`) is a
convention on the same classes, not a competing protocol.

`PriceSource` is an alias of `Source` so older imports keep working.
"""

from collections.abc import AsyncIterator, Iterator
from typing import Protocol, runtime_checkable

from coinlet.data.interfaces import Source
from coinlet.data.types import Bar, Tick

PriceSource = Source


@runtime_checkable
class LiveSource(Protocol):
    """Async live tick stream (complements the sync Source protocol)."""

    @property
    def source_name(self) -> str: ...

    def stream_ticks(self, symbols: list[str]) -> AsyncIterator[Tick]: ...


class SyncLiveSource(Protocol):
    """Synchronous live source for simpler use cases."""

    @property
    def source_name(self) -> str: ...

    def stream_ticks_sync(self, symbols: list[str]) -> Iterator[Tick]: ...


class BarAggregator(Protocol):
    """Protocol for aggregating ticks into bars."""

    def add_tick(self, tick: Tick) -> Bar | None: ...

    def get_current_bar(self) -> Bar | None: ...

    def flush(self) -> Bar | None: ...
