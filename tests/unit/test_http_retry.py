"""Unit tests for geofrea.core.http_retry.

All network calls are mocked via monkeypatch on requests.request — no
real HTTP traffic in this test file.
"""

from unittest.mock import Mock

import pytest
import requests

from geofrea.core.http_retry import get_with_retry, request_with_retry


def _ok_response(content: bytes = b"ok") -> Mock:
    resp = Mock()
    resp.status_code = 200
    resp.content = content
    resp.raise_for_status = Mock()
    return resp


@pytest.mark.unit
def test_request_with_retry_returns_response_on_first_success(monkeypatch):
    monkeypatch.setattr(requests, "request", Mock(return_value=_ok_response(b"hello")))

    resp = request_with_retry("GET", "https://example.test/x")

    assert resp.content == b"hello"


@pytest.mark.unit
def test_get_with_retry_calls_request_with_retry_get(monkeypatch):
    mock_request = Mock(return_value=_ok_response())
    monkeypatch.setattr(requests, "request", mock_request)

    get_with_retry("https://example.test/x", timeout=30)

    mock_request.assert_called_once()
    assert mock_request.call_args.args[0] == "GET"
    assert mock_request.call_args.args[1] == "https://example.test/x"


@pytest.mark.unit
def test_request_with_retry_retries_on_429_then_succeeds(monkeypatch):
    rate_limited = Mock(status_code=429, headers={})
    monkeypatch.setattr(requests, "request", Mock(side_effect=[rate_limited, _ok_response()]))
    monkeypatch.setattr("time.sleep", Mock())

    resp = request_with_retry("GET", "https://example.test/x", max_retries=3, backoff_base_s=0.01)

    assert resp.status_code == 200


@pytest.mark.unit
def test_request_with_retry_honors_retry_after_header(monkeypatch):
    rate_limited = Mock(status_code=429, headers={"Retry-After": "7"})
    monkeypatch.setattr(requests, "request", Mock(side_effect=[rate_limited, _ok_response()]))
    sleep_mock = Mock()
    monkeypatch.setattr("time.sleep", sleep_mock)

    request_with_retry("GET", "https://example.test/x", max_retries=3)

    sleep_mock.assert_called_once_with(7)


@pytest.mark.unit
def test_request_with_retry_retries_on_connection_error_then_succeeds(monkeypatch):
    monkeypatch.setattr(
        requests,
        "request",
        Mock(side_effect=[requests.ConnectionError("boom"), _ok_response()]),
    )
    monkeypatch.setattr("time.sleep", Mock())

    resp = request_with_retry("GET", "https://example.test/x", max_retries=3, backoff_base_s=0.01)

    assert resp.status_code == 200


@pytest.mark.unit
def test_request_with_retry_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(
        requests, "request", Mock(side_effect=requests.ConnectionError("still down"))
    )
    monkeypatch.setattr("time.sleep", Mock())

    with pytest.raises(requests.ConnectionError):
        request_with_retry("GET", "https://example.test/x", max_retries=2, backoff_base_s=0.01)


@pytest.mark.unit
def test_request_with_retry_raises_on_http_error_status(monkeypatch):
    error_resp = Mock(status_code=500, headers={})
    error_resp.raise_for_status = Mock(side_effect=requests.HTTPError("500"))
    monkeypatch.setattr(requests, "request", Mock(return_value=error_resp))
    monkeypatch.setattr("time.sleep", Mock())

    with pytest.raises(requests.HTTPError):
        request_with_retry("GET", "https://example.test/x", max_retries=1)
