"""Command-line interface for coinlet data operations."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime

import click

from coinlet.data.types import Granularity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def main(verbose: bool):
    """Coinlet: Wavelet transforms for crypto price analysis."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@main.command()
@click.argument("symbol")
@click.option(
    "--granularity",
    "-g",
    type=click.Choice(["1m", "5m", "15m", "1h", "6h", "1d"]),
    default="1d",
    help="Candle granularity",
)
@click.option(
    "--since",
    type=click.DateTime(),
    default="2015-01-01",
    help="Start date (YYYY-MM-DD)",
)
@click.option(
    "--until",
    type=click.DateTime(),
    default=None,
    help="End date (YYYY-MM-DD), defaults to now",
)
@click.option(
    "--source",
    "-s",
    type=click.Choice(["coinbase", "yahoo"]),
    default="coinbase",
    help="Data source",
)
@click.option(
    "--export-parquet",
    is_flag=True,
    help="Export to Parquet file in data/ directory",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output file path (CSV or Parquet based on extension)",
)
def fetch(
    symbol: str,
    granularity: str,
    since: datetime,
    until: datetime | None,
    source: str,
    export_parquet: bool,
    output: str | None,
):
    """Fetch historical OHLCV data.

    Example:
        coinlet fetch BTC-USD --granularity 1d --since 2015-01-01
        coinlet fetch ETH-USD -g 1h --since 2022-01-01 --export-parquet
    """
    from coinlet.data.cache import PriceCache, fetch_with_cache
    from coinlet.data.coinbase import CoinbaseHistorical
    from coinlet.data.yahoo import YahooFinanceSource

    gran = Granularity(granularity)

    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    if until is None:
        until = datetime.now(UTC)
    elif until.tzinfo is None:
        until = until.replace(tzinfo=UTC)

    if source == "coinbase":
        data_source = CoinbaseHistorical()
    else:
        data_source = YahooFinanceSource()

    cache = PriceCache()

    try:
        click.echo(f"Fetching {symbol} {granularity} from {source}...")
        click.echo(f"Date range: {since.date()} to {until.date()}")

        df = fetch_with_cache(cache, data_source, symbol, gran, since, until)

        if df.empty:
            click.echo("No data retrieved.", err=True)
            sys.exit(1)

        click.echo(f"Retrieved {len(df)} candles")
        click.echo(f"Date range: {df.index.min()} to {df.index.max()}")
        click.echo(f"Close price range: {df['close'].min():.2f} to {df['close'].max():.2f}")

        if export_parquet:
            path = cache.export_to_parquet(data_source.source_name, symbol, gran)
            size_mb = path.stat().st_size / (1024 * 1024)
            click.echo(f"Exported to {path} ({size_mb:.2f} MB)")

        if output:
            from pathlib import Path

            out_path = Path(output)
            if out_path.suffix == ".parquet":
                df.reset_index().to_parquet(out_path, index=False)
            else:
                df.to_csv(out_path)
            click.echo(f"Saved to {output}")

    finally:
        cache.close()
        if hasattr(data_source, "close"):
            data_source.close()


@main.command()
@click.argument("symbols", nargs=-1, required=True)
@click.option(
    "--granularity",
    "-g",
    type=click.Choice(["1m", "5m", "15m", "1h"]),
    default="1m",
    help="Bar aggregation granularity",
)
@click.option(
    "--duration",
    "-d",
    type=int,
    default=60,
    help="Duration in seconds (default: 60)",
)
def stream(symbols: tuple[str, ...], granularity: str, duration: int):
    """Stream live ticks and print aggregated bars.

    Example:
        coinlet stream BTC-USD ETH-USD --granularity 1m --duration 60
    """
    import time

    from coinlet.data.coinbase import CoinbaseLive
    from coinlet.data.live import RollingBarWindow
    from coinlet.data.types import Granularity

    gran = Granularity(granularity)

    windows = {sym: RollingBarWindow(granularity=gran, max_bars=100) for sym in symbols}

    source = CoinbaseLive()

    click.echo(f"Streaming {', '.join(symbols)} for {duration} seconds...")
    click.echo(f"Bar granularity: {granularity}")
    click.echo("-" * 60)

    start_time = time.time()
    tick_count = 0

    async def run():
        nonlocal tick_count

        async for tick in source.stream_ticks(list(symbols)):
            if time.time() - start_time > duration:
                break

            tick_count += 1

            if tick.product_id in windows:
                completed = windows[tick.product_id].add_tick(tick)
                if completed:
                    click.echo(
                        f"{completed.timestamp} | {tick.product_id:8} | "
                        f"O:{completed.open:10.2f} H:{completed.high:10.2f} "
                        f"L:{completed.low:10.2f} C:{completed.close:10.2f} "
                        f"V:{completed.volume:12.4f} ({completed.tick_count} ticks)"
                    )

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass

    click.echo("-" * 60)
    click.echo(f"Received {tick_count} ticks in {time.time() - start_time:.1f} seconds")

    for sym, window in windows.items():
        click.echo(f"{sym}: {window.bar_count} completed bars")


@main.command()
@click.option(
    "--source",
    "-s",
    type=click.Choice(["coinbase", "yahoo"]),
    default="coinbase",
)
def list_cached(source: str):
    """List cached data in DuckDB."""
    from coinlet.data.cache import PriceCache

    cache = PriceCache()
    conn = cache._get_conn()

    result = conn.execute(
        """
        SELECT source, symbol, granularity,
               MIN(timestamp) as first,
               MAX(timestamp) as last,
               COUNT(*) as rows
        FROM ohlcv
        WHERE source = ?
        GROUP BY source, symbol, granularity
        ORDER BY symbol, granularity
    """,
        [source],
    ).fetchall()

    if not result:
        click.echo(f"No cached data for source: {source}")
        return

    click.echo(f"Cached data for {source}:")
    click.echo("-" * 80)
    for row in result:
        click.echo(f"{row[1]:12} {row[2]:4} | {row[3]} to {row[4]} | {row[5]:,} rows")

    cache.close()


@main.command()
@click.argument("parquet_file", type=click.Path(exists=True))
@click.argument("symbol")
@click.option(
    "--granularity",
    "-g",
    type=click.Choice(["1m", "5m", "15m", "1h", "6h", "1d"]),
    required=True,
)
@click.option(
    "--source",
    "-s",
    default="imported",
    help="Source name for caching",
)
def import_parquet(parquet_file: str, symbol: str, granularity: str, source: str):
    """Import Parquet file into cache.

    Example:
        coinlet import-parquet data/btc_usd_1d.parquet BTC-USD -g 1d
    """
    from coinlet.data.cache import PriceCache
    from coinlet.data.types import Granularity

    gran = Granularity(granularity)
    cache = PriceCache()

    try:
        df = cache.import_from_parquet(parquet_file, source, symbol, gran)
        click.echo(f"Imported {len(df)} rows from {parquet_file}")
        click.echo(f"Date range: {df.index.min()} to {df.index.max()}")
    finally:
        cache.close()


if __name__ == "__main__":
    main()
