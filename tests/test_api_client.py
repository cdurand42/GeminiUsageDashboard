"""Tests for API client resilience and configuration validation."""

from unittest.mock import MagicMock, patch
import pytest
import requests

from app import format_currency, make_api_request, main


class StopExecution(Exception):
    """Exception used to simulate st.stop()."""


def test_monitor_api_url_absent():
    """Missing MONITOR_API_URL returns a clean error without crashing."""
    data, err = make_api_request("", "/summary")
    assert data is None
    assert err is not None
    assert "MONITOR_API_URL n'est pas configuré" in err


@patch("app.st.stop", side_effect=StopExecution)
@patch("app.st.error")
@patch("app.st.sidebar")
@patch("app.st.session_state", {"authenticated": True})
@patch("app.get_config")
def test_authenticated_missing_api_url_clean_error(mock_get_config, mock_sidebar, mock_error, mock_stop):
    """When authenticated but MONITOR_API_URL is missing, app stops cleanly with error."""
    mock_get_config.side_effect = lambda key, default="": {
        "DASHBOARD_PASSWORD": "pass",
        "MONITOR_API_URL": "",
        "MONITOR_READ_TOKEN": "token",
    }.get(key, default)

    with pytest.raises(StopExecution):
        main()

    mock_error.assert_called_with("Configuration manquante : MONITOR_API_URL n'est pas configuré.")
    mock_stop.assert_called_once()


@patch("app.st.stop", side_effect=StopExecution)
@patch("app.st.error")
@patch("app.st.sidebar")
@patch("app.st.session_state", {"authenticated": True})
@patch("app.get_config")
def test_authenticated_missing_read_token_clean_error(mock_get_config, mock_sidebar, mock_error, mock_stop):
    """When authenticated but MONITOR_READ_TOKEN is missing, app stops cleanly with error."""
    mock_get_config.side_effect = lambda key, default="": {
        "DASHBOARD_PASSWORD": "pass",
        "MONITOR_API_URL": "https://backend.example.com",
        "MONITOR_READ_TOKEN": "",
    }.get(key, default)

    with pytest.raises(StopExecution):
        main()

    mock_error.assert_called_with("Configuration manquante : MONITOR_READ_TOKEN n'est pas configuré.")
    mock_stop.assert_called_once()


@patch("app.requests.get")
def test_read_token_sent_in_header(mock_requests_get):
    """Verify read token is transmitted in X-Monitor-Read-Token header."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok"}
    mock_requests_get.return_value = mock_resp

    data, err = make_api_request(
        "https://backend.example.com",
        "/summary",
        read_token="secret-read-token-xyz",
        params={"project": "test-project"},
    )

    assert err is None
    assert data == {"status": "ok"}
    mock_requests_get.assert_called_once_with(
        "https://backend.example.com/summary",
        params={"project": "test-project"},
        headers={"X-Monitor-Read-Token": "secret-read-token-xyz"},
        timeout=10,
    )


@patch("app.requests.get")
def test_api_401_clean_error(mock_requests_get):
    """401 Unauthorized returns a user-friendly error without leaking secrets."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_requests_get.return_value = mock_resp

    data, err = make_api_request("https://backend.example.com", "/summary", read_token="my-token")
    assert data is None
    assert err is not None
    assert "401" in err
    # Ensure token is never in the error message
    assert "my-token" not in err


@patch("app.requests.get")
def test_api_403_clean_error(mock_requests_get):
    """403 Forbidden returns a clean error."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_requests_get.return_value = mock_resp

    data, err = make_api_request("https://backend.example.com", "/summary")
    assert data is None
    assert "403" in err


@patch("app.requests.get")
def test_api_404_clean_error(mock_requests_get):
    """404 Not Found returns a clean error."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_requests_get.return_value = mock_resp

    data, err = make_api_request("https://backend.example.com", "/not-found")
    assert data is None
    assert "404" in err


@patch("app.requests.get")
def test_api_500_clean_error(mock_requests_get):
    """500 Internal Server Error returns a clean error without traceback."""
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_requests_get.return_value = mock_resp

    data, err = make_api_request("https://backend.example.com", "/summary")
    assert data is None
    assert err is not None
    assert "500" in err
    assert "Erreur interne du serveur" in err


@patch("app.requests.get")
def test_api_connection_error_handling(mock_requests_get):
    """Connection failure returns clean indisponible message without crashing."""
    mock_requests_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

    data, err = make_api_request("https://backend.example.com", "/health")
    assert data is None
    assert err is not None
    assert "indisponible" in err.lower()


@patch("app.requests.get")
def test_api_timeout_handling(mock_requests_get):
    """Timeout returns clean message without unhandled exception."""
    mock_requests_get.side_effect = requests.exceptions.Timeout("Request timed out")

    data, err = make_api_request("https://backend.example.com", "/health")
    assert data is None
    assert err is not None
    assert "délai d'attente dépassé" in err.lower()


@patch("app.requests.get")
def test_api_invalid_json_handling(mock_requests_get):
    """Invalid JSON response returns clean format error."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.side_effect = ValueError("No JSON object could be decoded")
    mock_requests_get.return_value = mock_resp

    data, err = make_api_request("https://backend.example.com", "/health")
    assert data is None
    assert err is not None
    assert "format json attendu" in err.lower()


@patch("app.st.stop", side_effect=StopExecution)
@patch("app.st.error")
@patch("app.st.sidebar")
@patch("app.st.session_state", {"authenticated": True})
@patch("app.get_config")
@patch("app.make_api_request")
def test_unreachable_backend_in_main_does_not_crash(mock_request, mock_get_config, mock_sidebar, mock_error, mock_stop):
    """When the backend is unreachable during health check, main stops gracefully with an error."""
    mock_get_config.side_effect = lambda key, default="": {
        "DASHBOARD_PASSWORD": "pass",
        "MONITOR_API_URL": "https://backend.example.com",
        "MONITOR_READ_TOKEN": "token",
    }.get(key, default)
    mock_request.return_value = (None, "Backend GeminiUsageMonitor indisponible (connexion impossible).")

    with pytest.raises(StopExecution):
        main()

    mock_error.assert_called_with("Backend GeminiUsageMonitor indisponible.")
    mock_stop.assert_called_once()


def test_format_currency():
    """Verify currency formatting edge cases."""
    assert format_currency(None) == "Non chiffré"
    assert format_currency("invalid") == "Non chiffré"
    assert format_currency(0) == "$ 0.0000"
    assert format_currency("0.000045") == "$ 0.000045"
    assert format_currency("1.2543") == "$ 1.2543"
