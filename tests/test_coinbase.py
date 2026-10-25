"""Tests for Coinbase data source."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from coinlet.data.coinbase import CoinbaseHistorical
from coinlet.data.types import Granularity


class TestCoinbaseHistorical:
    """Tests for CoinbaseHistorical class."""

    def test_source_name(self):
        """Test source name property."""
        source = CoinbaseHistorical()
        assert source.source_name == "coinbase"

    def test_fetch_historical_single_page(self, sample_coinbase_response):
        """Test fetching a small date range (single page)."""
        source = CoinbaseHistorical(rate_limit_delay=0)

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_coinbase_response
        mock_session.get.return_value = mock_response
        source._session = mock_session

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 4, tzinfo=timezone.utc)

        df = source.fetch_historical("BTC-USD", Granularity.ONE_DAY, start, end)

        assert len(df) == 3
        assert "open" in df.columns
        assert "close" in df.columns
        assert df.index.tzinfo is not None

    def test_fetch_historical_pagination(self):
        """Test fetching a large date range requiring pagination."""
        source = CoinbaseHistorical(rate_limit_delay=0)

        mock_session = MagicMock()
        page1 = [[1704067200 + i * 86400, 99, 102, 100, 101, 1000] for i in range(300)]
        page2 = [[1704067200 + (300 + i) * 86400, 99, 102, 100, 101, 1000] for i in range(100)]

        mock_session.get.side_effect = [
            MagicMock(status_code=200, json=MagicMock(return_value=page1)),
            MagicMock(status_code=200, json=MagicMock(return_value=page2)),
        ]
        source._session = mock_session

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 2, 1, tzinfo=timezone.utc)

        df = source.fetch_historical("BTC-USD", Granularity.ONE_DAY, start, end)

        assert len(df) == 400
        assert mock_session.get.call_count == 2

    def test_fetch_historical_404(self):
        """Test handling of 404 response."""
        source = CoinbaseHistorical(rate_limit_delay=0)

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_session.get.return_value = mock_response
        source._session = mock_session

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 4, tzinfo=timezone.utc)

        df = source.fetch_historical("INVALID-USD", Granularity.ONE_DAY, start, end)

        assert len(df) == 0

    def test_fetch_historical_rate_limit_retry(self):
        """Test retry on rate limit (429)."""
        source = CoinbaseHistorical(rate_limit_delay=0)

        mock_session = MagicMock()
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = [[1704067200, 99, 102, 100, 101, 1000]]

        mock_session.get.side_effect = [rate_limit_response, success_response]
        source._session = mock_session

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        with patch("coinlet.data.coinbase.time.sleep"):
            df = source.fetch_historical("BTC-USD", Granularity.ONE_DAY, start, end)

        assert len(df) == 1
        assert mock_session.get.call_count == 2

    def test_close_session(self):
        """Test session cleanup."""
        source = CoinbaseHistorical()
        source._session = MagicMock()
        source.close()
        assert source._session is None


@pytest.mark.integration
class TestCoinbaseIntegration:
    """Integration tests hitting real Coinbase API.

    Run with: pytest -m integration
    """

    def test_fetch_btc_recent(self):
        """Test fetching recent BTC data from real API."""
        source = CoinbaseHistorical()

        from datetime import timedelta
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=5)

        df = source.fetch_historical("BTC-USD", Granularity.ONE_DAY, start, end)

        assert len(df) > 0
        assert df.index.tzinfo is not None
        assert all(col in df.columns for col in ["open", "high", "low", "close", "volume"])

        source.close()
