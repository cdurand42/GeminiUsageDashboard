"""Tests for password gate and authentication workflow."""

from unittest.mock import MagicMock, patch
import pytest

from app import get_config, main, verify_password


class StopExecution(Exception):
    """Exception used to simulate st.stop()."""


def test_verify_password_correct():
    """Valid password matches using constant-time comparison."""
    assert verify_password("SuperSecretPass123", "SuperSecretPass123") is True


def test_verify_password_incorrect():
    """Invalid password is rejected."""
    assert verify_password("WrongPassword", "SuperSecretPass123") is False
    assert verify_password("supersecretpass123", "SuperSecretPass123") is False


def test_verify_password_absent_or_empty():
    """Empty or missing passwords fail closed."""
    assert verify_password("", "SuperSecretPass123") is False
    assert verify_password("SuperSecretPass123", "") is False
    assert verify_password("", "") is False


@patch("app.st.stop", side_effect=StopExecution)
@patch("app.st.error")
@patch("app.st.title")
@patch("app.get_config")
def test_password_absent_gate_fails_closed(mock_get_config, mock_title, mock_error, mock_stop):
    """When DASHBOARD_PASSWORD is not configured, the app must halt with a clean error."""
    mock_get_config.return_value = ""

    with pytest.raises(StopExecution):
        main()

    mock_title.assert_called_with("Gemini Usage Monitor")
    mock_error.assert_called_with("Configuration d'accès manquante.")
    mock_stop.assert_called_once()


@patch("app.requests.get")
@patch("app.st.stop", side_effect=StopExecution)
@patch("app.render_login")
@patch("app.st.session_state", {})
@patch("app.get_config")
def test_no_api_calls_before_authentication(mock_get_config, mock_render_login, mock_stop, mock_requests_get):
    """Verify strictly ZERO API requests are performed when user is unauthenticated."""
    # Password exists but user session is not authenticated
    mock_get_config.side_effect = lambda key, default="": "secret" if key == "DASHBOARD_PASSWORD" else "https://api.test"

    with pytest.raises(StopExecution):
        main()

    mock_render_login.assert_called_once_with("secret")
    mock_stop.assert_called_once()
    mock_requests_get.assert_not_called()
