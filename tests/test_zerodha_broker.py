"""Tests for ZerodhaBroker token handling via SessionManager."""

import pytest
from unittest.mock import MagicMock, patch

from brokers.zerodha_broker import ZerodhaBroker
from core.session_manager import SessionManager


class TestZerodhaBrokerTokenHandling:
    """Test ZerodhaBroker token retrieval via SessionManager."""

    def test_zerodha_broker_gets_token_from_session_manager(self):
        """Test that ZerodhaBroker retrieves token via SessionManager when session_context is set."""
        mock_session_manager = MagicMock(spec=SessionManager)
        mock_session_manager.get_access_token.return_value = "db_access_token_123"

        broker = ZerodhaBroker(user_id="test_user", api_key="test_api_key")
        broker.set_session_context(session_manager=mock_session_manager, connection_id=42)

        token = broker._get_access_token()

        assert token == "db_access_token_123"
        mock_session_manager.get_access_token.assert_called_once_with("zerodha", connection_id=42)

    def test_zerodha_broker_fallback_to_constructor_token(self):
        """Test fallback to access_token passed in constructor when no session_manager."""
        broker = ZerodhaBroker(user_id="test_user", api_key="test_api_key", access_token="constructor_token")

        token = broker._get_access_token()

        assert token == "constructor_token"

    def test_zerodha_broker_raises_error_when_no_token(self):
        """Test that ZerodhaBroker raises error when no token available."""
        mock_session_manager = MagicMock(spec=SessionManager)
        mock_session_manager.get_access_token.return_value = None

        broker = ZerodhaBroker(user_id="test_user", api_key="test_api_key")
        broker.set_session_context(session_manager=mock_session_manager, connection_id=42)

        with pytest.raises(RuntimeError) as exc_info:
            broker._get_access_token()

        assert "Zerodha session expired" in str(exc_info.value)

    @patch("brokers.zerodha_broker.KiteConnect")
    def test_zerodha_broker_login_success(self, mock_kite_class):
        """Test successful login with valid token."""
        mock_kite = MagicMock()
        mock_kite.profile.return_value = {"user_name": "Test User"}
        mock_kite_class.return_value = mock_kite

        mock_session_manager = MagicMock(spec=SessionManager)
        mock_session_manager.get_access_token.return_value = "valid_token"

        broker = ZerodhaBroker(user_id="test_user", api_key="test_api_key")
        broker.set_session_context(session_manager=mock_session_manager, connection_id=42)

        broker.login()

        mock_kite.set_access_token.assert_called_once_with("valid_token")
        mock_kite.profile.assert_called_once()

    @patch("brokers.zerodha_broker.KiteConnect")
    def test_zerodha_broker_login_token_error(self, mock_kite_class):
        """Test login failure with expired/invalid token."""
        mock_kite = MagicMock()
        mock_kite.profile.side_effect = Exception("401 Unauthorized - Access token is invalid")
        mock_kite_class.return_value = mock_kite

        mock_session_manager = MagicMock(spec=SessionManager)
        mock_session_manager.get_access_token.return_value = "invalid_token"

        broker = ZerodhaBroker(user_id="test_user", api_key="test_api_key")
        broker.set_session_context(session_manager=mock_session_manager, connection_id=42)

        with pytest.raises(RuntimeError) as exc_info:
            broker.login()

        assert "Zerodha session expired" in str(exc_info.value)

    @patch("brokers.zerodha_broker.KiteConnect")
    def test_zerodha_broker_get_holdings_normalizes_output(self, mock_kite_class):
        """Test that get_holdings normalizes output to expected format."""
        mock_kite = MagicMock()
        mock_kite.holdings.return_value = [
            {
                'tradingsymbol': 'RELIANCE',
                'exchange': 'NSE',
                'instrument_token': 288975,
                'quantity': 10,
                'average_price': 2200.0,
                'last_price': 2250.0,
                'pnl': 500.0,
            }
        ]
        mock_kite_class.return_value = mock_kite

        mock_session_manager = MagicMock(spec=SessionManager)
        mock_session_manager.get_access_token.return_value = "valid_token"

        broker = ZerodhaBroker(user_id="test_user", api_key="test_api_key")
        broker.set_session_context(session_manager=mock_session_manager, connection_id=42)
        broker.kite = mock_kite

        holdings = broker.get_holdings()

        assert len(holdings) == 1
        assert holdings[0]['tradingsymbol'] == 'RELIANCE'
        assert holdings[0]['quantity'] == 10
        assert holdings[0]['average_price'] == 2200.0
        assert holdings[0]['last_price'] == 2250.0

    @patch("brokers.zerodha_broker.KiteConnect")
    def test_zerodha_broker_get_holdings_token_error(self, mock_kite_class):
        """Test that get_holdings raises token error on 401."""
        mock_kite = MagicMock()
        mock_kite.holdings.side_effect = Exception("401 Access token is invalid")
        mock_kite_class.return_value = mock_kite

        mock_session_manager = MagicMock(spec=SessionManager)
        mock_session_manager.get_access_token.return_value = "expired_token"

        broker = ZerodhaBroker(user_id="test_user", api_key="test_api_key")
        broker.set_session_context(session_manager=mock_session_manager, connection_id=42)
        broker.kite = mock_kite

        # Should raise RuntimeError on token error
        with pytest.raises(RuntimeError) as exc_info:
            broker.get_holdings()

        assert "Zerodha session expired" in str(exc_info.value)
        assert broker.kite is None

    @patch("brokers.zerodha_broker.KiteConnect")
    def test_zerodha_broker_ensure_kite_recreates_on_error(self, mock_kite_class):
        """Test that _ensure_kite recreates the Kite client after token error."""
        mock_kite = MagicMock()
        mock_kite_class.return_value = mock_kite

        mock_session_manager = MagicMock(spec=SessionManager)
        mock_session_manager.get_access_token.return_value = "valid_token"

        broker = ZerodhaBroker(user_id="test_user", api_key="test_api_key")
        broker.set_session_context(session_manager=mock_session_manager, connection_id=42)
        broker.kite = mock_kite

        kite1 = broker._ensure_kite()
        assert kite1 == mock_kite

        broker.kite = None
        kite2 = broker._ensure_kite()
        assert kite2 == mock_kite
        mock_kite.set_access_token.assert_called()
