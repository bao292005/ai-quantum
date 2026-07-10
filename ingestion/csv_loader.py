"""Historical fixture CSV ingestion (Track 1D).

Maps backtest fixture CSV rows (`fixtures/backtest/*.csv[.gz]`) into normalized
tick-data ``dict``s conforming to ``contracts/tick_data.schema.json`` — the same
contract the realtime path (Track 1A/1B) and the ring buffer (Track 1C) use.

- ``map_csv_row``    (1D.1): one DictReader row -> validated schema dict.
- ``iter_csv_events``(1D.1): sync generator over a whole CSV(.gz), bad rows logged.
"""

from __future__ import annotations

import asyncio
import csv
import gzip
import json
import logging
import math
from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from pathlib import Path

import jsonschema

from core.ring_buffer import RingBufferProtocol

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "contracts" / "tick_data.schema.json"
_INT_FIELDS = ("block_number", "log_index")
_STR_FIELDS = (
    "block_timestamp", "protocol", "event_type", "pool_address",
    "token0", "token1", "amount0", "amount1", "tx_hash",
)
_validator: jsonschema.protocols.Validator | None = None


class CsvRowError(ValueError):
    """Raised when a CSV row cannot be mapped to a valid tick-data dict."""


def _get_validator() -> jsonschema.protocols.Validator:
    """Build the tick-data validator once and reuse it.

    ``jsonschema.validate()`` recompiles the schema on every call, which is
    pathologically slow when validating tens of thousands of rows. Caching a
    compiled validator instance keeps per-row validation cheap.
    """
    global _validator
    if _validator is None:
        with open(_SCHEMA_PATH) as f:
            schema = json.load(f)
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)
        _validator = cls(schema)
    return _validator


def map_csv_row(raw: dict[str, str], *, validate: bool = True) -> dict:
    """Map one CSV ``DictReader`` row to a tick_data.schema.json-conformant dict.

    ``block_number`` and ``log_index`` are coerced to ``int``; every other field
    (including ``amount0``/``amount1``) stays a ``str`` to preserve wei precision.

    Raises ``CsvRowError`` if a required column is missing, an int field is
    non-numeric, or (when ``validate=True``) the row violates the schema.
    """
    try:
        event: dict = {f: int(raw[f]) for f in _INT_FIELDS}
        for f in _STR_FIELDS:
            event[f] = raw[f]  # KeyError if column missing
    except KeyError as e:
        raise CsvRowError(f"missing column {e}") from e
    except (ValueError, TypeError) as e:
        raise CsvRowError(f"bad integer field: {e}") from e

    if validate:
        try:
            _get_validator().validate(event)
        except jsonschema.ValidationError as e:
            raise CsvRowError(f"schema violation: {e.message}") from e
    return event


def _open_text(path: str | Path):
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, mode="rt", encoding="utf-8", newline="")
    return open(path, mode="rt", encoding="utf-8", newline="")


def iter_csv_events(
    path: str | Path,
    *,
    error_log: str | Path = "csv_errors.log",
    validate: bool = True,
) -> Iterator[dict]:
    """Yield schema-conformant tick-data dicts from a fixture CSV(.gz).

    Malformed rows are written as one JSON line to ``error_log`` and skipped —
    the iterator never raises on a bad row.
    """
    with _open_text(path) as fh:
        reader = csv.DictReader(fh)
        err_fh = None
        try:
            for lineno, raw in enumerate(reader, start=2):  # line 1 = header
                try:
                    yield map_csv_row(raw, validate=validate)
                except CsvRowError as e:
                    if err_fh is None:
                        err_fh = open(error_log, "a", encoding="utf-8")
                    err_fh.write(json.dumps(
                        {"event": "csv_row_error", "line": lineno,
                         "reason": str(e), "row": raw}
                    ) + "\n")
                    logger.warning("csv_row_error line=%d: %s", lineno, e)
                    continue
        finally:
            if err_fh is not None:
                err_fh.close()


_YIELD_EVERY = 1000  # cooperatively yield to the event loop every N events


async def stream_csv(
    path: str | Path,
    *,
    error_log: str | Path = "csv_errors.log",
    validate: bool = True,
) -> AsyncIterator[dict]:
    """Async-yield tick-data dicts from a fixture CSV(.gz) in block order.

    Thin async wrapper over the synchronous ``iter_csv_events`` (Story 1D.1).
    Assumes the fixture is pre-sorted by ``block_number`` (Epic 0 fixtures are);
    verifies non-decreasing order and logs a WARN on violation but never drops
    or buffers rows — memory stays O(1) per row.
    """
    prev_block = -1
    for i, event in enumerate(
        iter_csv_events(path, error_log=error_log, validate=validate)
    ):
        block = event["block_number"]
        if block < prev_block:
            logger.warning(json.dumps({
                "event": "csv_out_of_order",
                "block_number": block,
                "prev_block_number": prev_block,
            }))
        prev_block = block
        yield event
        if i % _YIELD_EVERY == 0:
            await asyncio.sleep(0)  # cooperative yield to the event loop


def _parse_rate(rate: str | float) -> float:
    """Return replay speed factor. 'asap' -> inf; '100x'/'1x'/number -> float."""
    if isinstance(rate, bool):  # bool is a subclass of int — reject explicitly
        raise ValueError(f"invalid rate: {rate!r}")
    if isinstance(rate, (int, float)):
        speed = float(rate)
    elif isinstance(rate, str):
        r = rate.strip().lower()
        if r == "asap":
            return math.inf
        r = r[:-1] if r.endswith("x") else r
        try:
            speed = float(r)
        except ValueError as e:
            raise ValueError(f"invalid rate: {rate!r}") from e
    else:
        raise ValueError(f"invalid rate type: {type(rate).__name__}")
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError(f"rate must be a finite number > 0, got {rate!r}")
    return speed


class ReplayDriver:
    """Replay a fixture CSV into a ring buffer paced by event timestamps (1D.3)."""

    def __init__(self, buffer: RingBufferProtocol, *, rate: str | float = "1x") -> None:
        self._buffer = buffer
        self._speed = _parse_rate(rate)

    async def run(self, path: str | Path, *, error_log: str | Path = "csv_errors.log") -> int:
        """Stream ``path`` into the buffer with timestamp pacing. Returns count.

        Between consecutive events the driver sleeps ``gap_seconds / speed``
        where ``gap_seconds`` is the ``block_timestamp`` delta. ``asap`` (speed
        = inf) and same-block events (gap 0) incur no sleep.
        """
        prev_ts: datetime | None = None
        count = 0
        async for event in stream_csv(path, error_log=error_log):
            ts = datetime.fromisoformat(event["block_timestamp"])
            if prev_ts is not None and not math.isinf(self._speed):
                delay = (ts - prev_ts).total_seconds() / self._speed
                if delay > 0:
                    await asyncio.sleep(delay)
            prev_ts = ts
            self._buffer.write(event)
            count += 1
        return count
