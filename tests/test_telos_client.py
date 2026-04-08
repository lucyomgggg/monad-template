# Feature: monad-template, Property 5: TelosClientは429に対して最大5回リトライする
"""
Property 5 tests: TelosClient retries on 429 responses, max 5 times,
with a 60-second sleep before each retry.

Validates: Requirements 4.2
"""

from __future__ import annotations

import sys
import os
from unittest.mock import patch, call

import httpx
import pytest
import respx

# Ensure the monad-template package root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from telos_client import TelosClient, _MAX_RETRIES, _RATE_LIMIT_SLEEP


BASE_URL = "http://telos-test.local"


def make_client() -> TelosClient:
    return TelosClient(base_url=BASE_URL, monad_id="test-monad")


# ---------------------------------------------------------------------------
# Helper: build a list of N 429 responses followed by an optional final one
# ---------------------------------------------------------------------------

def _429() -> httpx.Response:
    return httpx.Response(429, json={"detail": "rate limited"})


def _200_search() -> httpx.Response:
    return httpx.Response(200, json={"results": [{"id": "x", "content": "c", "score": 0.9}]})


def _200_write() -> httpx.Response:
    return httpx.Response(200, json={"id": "node-abc"})


# ===========================================================================
# Property 5 – search(): 429 retry behaviour
# ===========================================================================

class TestSearch429Retry:
    """search() retries on 429 up to _MAX_RETRIES (5) times."""

    @respx.mock
    def test_search_retries_exactly_5_times_then_returns_empty(self):
        """When telos-core returns 429 continuously, search() retries 5 times
        and then returns []."""
        # 6 total calls: initial + 5 retries, all 429
        route = respx.post(f"{BASE_URL}/api/v1/search").mock(
            side_effect=[_429()] * (_MAX_RETRIES + 1)
        )

        client = make_client()
        with patch("telos_client.time.sleep") as mock_sleep:
            result = client.search("test query")

        assert result == []
        # 5 retries → 5 sleeps of 60 seconds each
        assert mock_sleep.call_count == _MAX_RETRIES
        mock_sleep.assert_called_with(_RATE_LIMIT_SLEEP)
        # Total HTTP calls: 1 initial + 5 retries = 6
        assert route.call_count == _MAX_RETRIES + 1

    @respx.mock
    def test_search_does_not_exceed_5_retries(self):
        """Even if the server keeps returning 429, search() stops after 5 retries."""
        # Provide more 429s than the max retry count
        route = respx.post(f"{BASE_URL}/api/v1/search").mock(
            side_effect=[_429()] * 20
        )

        client = make_client()
        with patch("telos_client.time.sleep") as mock_sleep:
            result = client.search("query")

        assert result == []
        assert mock_sleep.call_count == _MAX_RETRIES
        assert route.call_count == _MAX_RETRIES + 1

    @respx.mock
    def test_search_succeeds_after_fewer_than_5_retries(self):
        """search() succeeds if telos-core stops returning 429 before the limit."""
        # 3 x 429, then success
        route = respx.post(f"{BASE_URL}/api/v1/search").mock(
            side_effect=[_429(), _429(), _429(), _200_search()]
        )

        client = make_client()
        with patch("telos_client.time.sleep") as mock_sleep:
            result = client.search("query")

        assert result == [{"id": "x", "content": "c", "score": 0.9}]
        assert mock_sleep.call_count == 3
        assert route.call_count == 4

    @respx.mock
    def test_search_sleep_duration_is_60_seconds(self):
        """Each retry sleep is exactly 60 seconds."""
        respx.post(f"{BASE_URL}/api/v1/search").mock(
            side_effect=[_429()] * (_MAX_RETRIES + 1)
        )

        client = make_client()
        with patch("telos_client.time.sleep") as mock_sleep:
            client.search("query")

        expected_calls = [call(_RATE_LIMIT_SLEEP)] * _MAX_RETRIES
        assert mock_sleep.call_args_list == expected_calls

    @respx.mock
    def test_search_no_retry_on_first_success(self):
        """search() does not sleep at all when the first request succeeds."""
        respx.post(f"{BASE_URL}/api/v1/search").mock(return_value=_200_search())

        client = make_client()
        with patch("telos_client.time.sleep") as mock_sleep:
            result = client.search("query")

        assert result != []
        mock_sleep.assert_not_called()


# ===========================================================================
# Property 5 – write(): 429 retry behaviour
# ===========================================================================

class TestWrite429Retry:
    """write() retries on 429 up to _MAX_RETRIES (5) times."""

    @respx.mock
    def test_write_retries_exactly_5_times_then_returns_none(self):
        """When telos-core returns 429 continuously, write() retries 5 times
        and then returns None."""
        route = respx.post(f"{BASE_URL}/api/v1/write").mock(
            side_effect=[_429()] * (_MAX_RETRIES + 1)
        )

        client = make_client()
        with patch("telos_client.time.sleep") as mock_sleep:
            result = client.write("some content")

        assert result is None
        assert mock_sleep.call_count == _MAX_RETRIES
        mock_sleep.assert_called_with(_RATE_LIMIT_SLEEP)
        assert route.call_count == _MAX_RETRIES + 1

    @respx.mock
    def test_write_does_not_exceed_5_retries(self):
        """Even if the server keeps returning 429, write() stops after 5 retries."""
        route = respx.post(f"{BASE_URL}/api/v1/write").mock(
            side_effect=[_429()] * 20
        )

        client = make_client()
        with patch("telos_client.time.sleep") as mock_sleep:
            result = client.write("content")

        assert result is None
        assert mock_sleep.call_count == _MAX_RETRIES
        assert route.call_count == _MAX_RETRIES + 1

    @respx.mock
    def test_write_succeeds_after_fewer_than_5_retries(self):
        """write() succeeds if telos-core stops returning 429 before the limit."""
        route = respx.post(f"{BASE_URL}/api/v1/write").mock(
            side_effect=[_429(), _429(), _200_write()]
        )

        client = make_client()
        with patch("telos_client.time.sleep") as mock_sleep:
            result = client.write("content")

        assert result == "node-abc"
        assert mock_sleep.call_count == 2
        assert route.call_count == 3

    @respx.mock
    def test_write_sleep_duration_is_60_seconds(self):
        """Each retry sleep is exactly 60 seconds."""
        respx.post(f"{BASE_URL}/api/v1/write").mock(
            side_effect=[_429()] * (_MAX_RETRIES + 1)
        )

        client = make_client()
        with patch("telos_client.time.sleep") as mock_sleep:
            client.write("content")

        expected_calls = [call(_RATE_LIMIT_SLEEP)] * _MAX_RETRIES
        assert mock_sleep.call_args_list == expected_calls

    @respx.mock
    def test_write_no_retry_on_first_success(self):
        """write() does not sleep at all when the first request succeeds."""
        respx.post(f"{BASE_URL}/api/v1/write").mock(return_value=_200_write())

        client = make_client()
        with patch("telos_client.time.sleep") as mock_sleep:
            result = client.write("content")

        assert result == "node-abc"
        mock_sleep.assert_not_called()


# ===========================================================================
# Parametrized concrete cases (100+ iterations equivalent)
# ===========================================================================

@pytest.mark.parametrize("num_429s", list(range(1, _MAX_RETRIES + 1)))
@respx.mock
def test_search_partial_429_then_success(num_429s: int):
    """search() handles 1..5 leading 429s followed by a success."""
    respx.post(f"{BASE_URL}/api/v1/search").mock(
        side_effect=[_429()] * num_429s + [_200_search()]
    )
    client = make_client()
    with patch("telos_client.time.sleep") as mock_sleep:
        result = client.search("q")
    assert result != []
    assert mock_sleep.call_count == num_429s


@pytest.mark.parametrize("num_429s", list(range(1, _MAX_RETRIES + 1)))
@respx.mock
def test_write_partial_429_then_success(num_429s: int):
    """write() handles 1..5 leading 429s followed by a success."""
    respx.post(f"{BASE_URL}/api/v1/write").mock(
        side_effect=[_429()] * num_429s + [_200_write()]
    )
    client = make_client()
    with patch("telos_client.time.sleep") as mock_sleep:
        result = client.write("content")
    assert result == "node-abc"
    assert mock_sleep.call_count == num_429s


@pytest.mark.parametrize("extra_429s", list(range(0, 10)))
@respx.mock
def test_search_always_caps_at_5_retries(extra_429s: int):
    """search() never retries more than 5 times regardless of how many 429s follow."""
    total = _MAX_RETRIES + 1 + extra_429s
    respx.post(f"{BASE_URL}/api/v1/search").mock(
        side_effect=[_429()] * total
    )
    client = make_client()
    with patch("telos_client.time.sleep") as mock_sleep:
        result = client.search("q")
    assert result == []
    assert mock_sleep.call_count == _MAX_RETRIES


@pytest.mark.parametrize("extra_429s", list(range(0, 10)))
@respx.mock
def test_write_always_caps_at_5_retries(extra_429s: int):
    """write() never retries more than 5 times regardless of how many 429s follow."""
    total = _MAX_RETRIES + 1 + extra_429s
    respx.post(f"{BASE_URL}/api/v1/write").mock(
        side_effect=[_429()] * total
    )
    client = make_client()
    with patch("telos_client.time.sleep") as mock_sleep:
        result = client.write("content")
    assert result is None
    assert mock_sleep.call_count == _MAX_RETRIES


# Feature: monad-template, Property 6: TelosClientは5xxエラーで例外を伝播させない
"""
Property 6 tests: For any HTTP 5xx status code (500-599), TelosClient.write()
returns None and TelosClient.search() returns [], without propagating exceptions.

Validates: Requirements 4.3
"""

from hypothesis import given, settings
from hypothesis import strategies as st


def _5xx(status_code: int) -> httpx.Response:
    return httpx.Response(status_code, json={"detail": "server error"})


# ===========================================================================
# Property 6 – write(): 5xx does not raise, returns None
# ===========================================================================

@settings(max_examples=100)
@given(status_code=st.integers(min_value=500, max_value=599))
def test_write_returns_none_on_5xx(status_code: int):
    """write() returns None for any 5xx status code without raising an exception."""
    with respx.mock:
        respx.post(f"{BASE_URL}/api/v1/write").mock(return_value=_5xx(status_code))
        client = make_client()
        result = client.write("some content")
    assert result is None


@settings(max_examples=100)
@given(status_code=st.integers(min_value=500, max_value=599))
def test_write_does_not_raise_on_5xx(status_code: int):
    """write() does not propagate any exception for any 5xx status code."""
    with respx.mock:
        respx.post(f"{BASE_URL}/api/v1/write").mock(return_value=_5xx(status_code))
        client = make_client()
        try:
            client.write("some content")
        except Exception as exc:
            pytest.fail(f"write() raised an exception on {status_code}: {exc}")


# ===========================================================================
# Property 6 – search(): 5xx does not raise, returns []
# ===========================================================================

@settings(max_examples=100)
@given(status_code=st.integers(min_value=500, max_value=599))
def test_search_returns_empty_list_on_5xx(status_code: int):
    """search() returns [] for any 5xx status code without raising an exception."""
    with respx.mock:
        respx.post(f"{BASE_URL}/api/v1/search").mock(return_value=_5xx(status_code))
        client = make_client()
        result = client.search("test query")
    assert result == []


@settings(max_examples=100)
@given(status_code=st.integers(min_value=500, max_value=599))
def test_search_does_not_raise_on_5xx(status_code: int):
    """search() does not propagate any exception for any 5xx status code."""
    with respx.mock:
        respx.post(f"{BASE_URL}/api/v1/search").mock(return_value=_5xx(status_code))
        client = make_client()
        try:
            client.search("test query")
        except Exception as exc:
            pytest.fail(f"search() raised an exception on {status_code}: {exc}")


# ===========================================================================
# Unit tests: correct endpoints and from_env() – Requirements 4.1, 4.4
# ===========================================================================

class TestCorrectEndpoints:
    """search() and write() call the correct HTTP endpoints."""

    @respx.mock
    def test_search_calls_post_api_v1_search(self):
        """search() sends a POST request to /api/v1/search."""
        route = respx.post(f"{BASE_URL}/api/v1/search").mock(return_value=_200_search())
        client = make_client()
        client.search("test query")
        assert route.called

    @respx.mock
    def test_search_does_not_call_write_endpoint(self):
        """search() does not call /api/v1/write."""
        search_route = respx.post(f"{BASE_URL}/api/v1/search").mock(return_value=_200_search())
        write_route = respx.post(f"{BASE_URL}/api/v1/write").mock(return_value=_200_write())
        client = make_client()
        client.search("test query")
        assert search_route.called
        assert not write_route.called

    @respx.mock
    def test_write_calls_post_api_v1_write(self):
        """write() sends a POST request to /api/v1/write."""
        route = respx.post(f"{BASE_URL}/api/v1/write").mock(return_value=_200_write())
        client = make_client()
        client.write("some content")
        assert route.called

    @respx.mock
    def test_write_does_not_call_search_endpoint(self):
        """write() does not call /api/v1/search."""
        search_route = respx.post(f"{BASE_URL}/api/v1/search").mock(return_value=_200_search())
        write_route = respx.post(f"{BASE_URL}/api/v1/write").mock(return_value=_200_write())
        client = make_client()
        client.write("some content")
        assert write_route.called
        assert not search_route.called

    @respx.mock
    def test_search_uses_post_method(self):
        """search() uses the POST HTTP method, not GET or PUT."""
        route = respx.post(f"{BASE_URL}/api/v1/search").mock(return_value=_200_search())
        client = make_client()
        client.search("query")
        assert route.called
        assert route.calls[0].request.method == "POST"

    @respx.mock
    def test_write_uses_post_method(self):
        """write() uses the POST HTTP method, not GET or PUT."""
        route = respx.post(f"{BASE_URL}/api/v1/write").mock(return_value=_200_write())
        client = make_client()
        client.write("content")
        assert route.called
        assert route.calls[0].request.method == "POST"


class TestFromEnv:
    """TelosClient.from_env() reads TELOS_CORE_URL from the environment."""

    @respx.mock
    def test_from_env_reads_telos_core_url(self):
        """from_env() uses TELOS_CORE_URL as the base URL."""
        env_url = "http://env-telos.local"
        route = respx.post(f"{env_url}/api/v1/search").mock(return_value=_200_search())
        with patch.dict(os.environ, {"TELOS_CORE_URL": env_url}):
            client = TelosClient.from_env(monad_id="test-monad")
            client.search("query")
        assert route.called

    def test_from_env_raises_if_telos_core_url_missing(self):
        """from_env() raises KeyError when TELOS_CORE_URL is not set."""
        env = {k: v for k, v in os.environ.items() if k != "TELOS_CORE_URL"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(KeyError):
                TelosClient.from_env(monad_id="test-monad")

    @respx.mock
    def test_from_env_different_urls_reach_correct_host(self):
        """from_env() correctly uses whatever URL is in TELOS_CORE_URL."""
        url_a = "http://host-a.local"
        url_b = "http://host-b.local"
        route_a = respx.post(f"{url_a}/api/v1/write").mock(return_value=_200_write())
        route_b = respx.post(f"{url_b}/api/v1/write").mock(return_value=_200_write())

        with patch.dict(os.environ, {"TELOS_CORE_URL": url_a}):
            TelosClient.from_env(monad_id="m").write("content")
        with patch.dict(os.environ, {"TELOS_CORE_URL": url_b}):
            TelosClient.from_env(monad_id="m").write("content")

        assert route_a.called
        assert route_b.called
