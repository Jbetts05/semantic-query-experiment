from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, cast


@dataclass(frozen=True)
class SearchRestClient:
    """Minimal REST client for Azure AI Search index management and ingestion."""

    endpoint: str
    api_key: str
    api_version: str

    def get_index(self, index_name: str) -> dict[str, object]:
        return self._request("GET", f"/indexes/{index_name}", None)

    def put_index(self, index_name: str, schema: dict[str, object]) -> dict[str, object]:
        return self._request("PUT", f"/indexes/{index_name}", schema)

    def upload_documents(
        self,
        index_name: str,
        documents: list[dict[str, object]],
    ) -> dict[str, object]:
        actions = [{"@search.action": "mergeOrUpload", **document} for document in documents]
        return self._request("POST", f"/indexes/{index_name}/docs/index", {"value": actions})

    def search_documents(self, index_name: str, payload: dict[str, object]) -> dict[str, object]:
        return self._request("POST", f"/indexes/{index_name}/docs/search", payload)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None,
    ) -> dict[str, object]:
        base = self.endpoint.rstrip("/")
        url = f"{base}{path}?api-version={self.api_version}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Content-Type": "application/json",
                "api-key": self.api_key,
            },
        )
        response_body = ""
        for attempt in range(5):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    response_body = response.read().decode("utf-8")
                    break
            except urllib.error.HTTPError as error:
                if error.code not in {429, 500, 502, 503, 504} or attempt == 4:
                    detail = error.read().decode("utf-8", errors="replace")
                    raise RuntimeError(f"Search request failed: {error.code} {detail}") from error
                retry_after = error.headers.get("Retry-After")
                delay = int(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                time.sleep(delay)
        parsed: Any = json.loads(response_body) if response_body else {}
        return cast(dict[str, object], parsed) if isinstance(parsed, dict) else {}
