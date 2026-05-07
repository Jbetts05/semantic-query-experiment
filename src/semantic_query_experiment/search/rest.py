from __future__ import annotations

import json
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

    def put_index(self, index_name: str, schema: dict[str, object]) -> dict[str, object]:
        return self._request("PUT", f"/indexes/{index_name}", schema)

    def upload_documents(
        self,
        index_name: str,
        documents: list[dict[str, object]],
    ) -> dict[str, object]:
        actions = [{"@search.action": "mergeOrUpload", **document} for document in documents]
        return self._request("POST", f"/indexes/{index_name}/docs/index", {"value": actions})

    def _request(self, method: str, path: str, payload: dict[str, object]) -> dict[str, object]:
        base = self.endpoint.rstrip("/")
        url = f"{base}{path}?api-version={self.api_version}"
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Content-Type": "application/json",
                "api-key": self.api_key,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Search request failed: {error.code} {detail}") from error
        parsed: Any = json.loads(response_body) if response_body else {}
        return cast(dict[str, object], parsed) if isinstance(parsed, dict) else {}
