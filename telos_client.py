"""HTTP client for telos-core search/write APIs.

Reads TELOS_CORE_URL from the environment. No external config dependency.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_RATE_LIMIT_SLEEP = 60.0
_MAX_RETRIES = 5


class TelosClient:
    def __init__(self, base_url: str, monad_id: str, timeout: float = 30.0) -> None:
        self._base_url = base_url
        self._monad_id = monad_id
        self._client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
            headers={"Content-Type": "application/json"},
        )

    @classmethod
    def from_env(cls, monad_id: str, timeout: float = 30.0) -> "TelosClient":
        """Convenience constructor that reads TELOS_CORE_URL from the environment."""
        base_url = os.environ["TELOS_CORE_URL"]
        return cls(base_url=base_url, monad_id=monad_id, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def _request_json(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any],
    ) -> httpx.Response | None:
        """Send a request, retrying on 429. Returns None on network error."""
        attempt = 0
        while True:
            try:
                resp = self._client.request(method, path, json=json_body)
            except httpx.RequestError as exc:
                logger.error("telos network error [%s %s]: %s", method, path, exc)
                return None

            if resp.status_code == 429 and attempt < _MAX_RETRIES:
                attempt += 1
                logger.warning(
                    "telos-core 429; sleeping %ss (retry %s/%s)",
                    _RATE_LIMIT_SLEEP,
                    attempt,
                    _MAX_RETRIES,
                )
                time.sleep(_RATE_LIMIT_SLEEP)
                continue

            return resp

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """POST /api/v1/search — returns list of result dicts, or [] on error."""
        body = {
            "monad_id": self._monad_id,
            "query": query,
            "limit": limit,
        }
        resp = self._request_json("POST", "/api/v1/search", body)
        if resp is None:
            return []

        if resp.status_code == 429:
            logger.error("telos search still rate-limited after %s retries", _MAX_RETRIES)
            return []
        if resp.status_code >= 500:
            logger.error("telos search server error %s: %s", resp.status_code, resp.text[:500])
            return []
        if not (200 <= resp.status_code < 300):
            logger.error("telos search unexpected %s: %s", resp.status_code, resp.text[:500])
            return []

        data = resp.json()
        return data.get("results") or []

    def write(self, content: str, parent_ids: list[str] = []) -> str | None:
        """POST /api/v1/write — returns node id string on success, None on failure."""
        body = {
            "monad_id": self._monad_id,
            "content": content,
            "parent_ids": parent_ids,
        }
        resp = self._request_json("POST", "/api/v1/write", body)
        if resp is None:
            return None

        if resp.status_code == 413:
            logger.error("telos write 413: content too large")
            return None
        if resp.status_code == 429:
            logger.error("telos write still rate-limited after %s retries", _MAX_RETRIES)
            return None
        if resp.status_code >= 500:
            logger.error("telos write server error %s: %s", resp.status_code, resp.text[:500])
            return None
        if not (200 <= resp.status_code < 300):
            logger.error("telos write unexpected %s: %s", resp.status_code, resp.text[:500])
            return None

        data = resp.json()
        node_id = str(data.get("id", ""))
        return node_id or None
