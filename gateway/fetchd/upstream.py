"""HTTP calls from the gateway to Radarr and Sonarr on the same machine."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

MAX_RESPONSE_BYTES = 20 * 1024 * 1024
TIMEOUT_SECONDS = 30


class UpstreamError(Exception):
    """Radarr or Sonarr could not be reached, or refused a call."""

    def __init__(self, service: str, message: str, status: int = 0, detail: str = "") -> None:
        super().__init__(f"{service}: {message}" + (f" ({detail})" if detail else ""))
        self.service = service
        self.status = status
        self.detail = detail


@dataclass(frozen=True)
class Upstream:
    """One Radarr, Sonarr or Plex, reached over localhost with its API key or token."""

    name: str
    base_url: str
    api_key: str
    key_header: str = "X-Api-Key"

    @classmethod
    def from_config_xml(cls, name: str, config_path: Path) -> Upstream:
        """Reads the port, URL base and API key from the app's own config.xml, so the key is never copied."""
        root = ElementTree.parse(config_path).getroot()
        port = _required(root, "Port", config_path)
        api_key = _required(root, "ApiKey", config_path)
        url_base = (root.findtext("UrlBase") or "").strip().rstrip("/")
        if url_base and not url_base.startswith("/"):
            url_base = "/" + url_base
        return cls(name, f"http://127.0.0.1:{port}{url_base}", api_key)

    def get(self, path: str, **query: Any) -> Any:
        return self._request("GET", path, query, None)

    def post(self, path: str, body: dict) -> Any:
        return self._request("POST", path, {}, body)

    def put(self, path: str, body: dict) -> Any:
        return self._request("PUT", path, {}, body)

    def delete(self, path: str, **query: Any) -> None:
        self._request("DELETE", path, query, None)

    def _request(self, method: str, path: str, query: dict, body: dict | None) -> Any:
        request = urllib.request.Request(self._url(path, query), method=method, headers=self._headers(body))
        if body is not None:
            request.data = json.dumps(body).encode("utf-8")
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return _decode(self.name, response.read(MAX_RESPONSE_BYTES + 1))
        except urllib.error.HTTPError as error:
            raise UpstreamError(self.name, f"HTTP {error.code}", error.code, _error_detail(error)) from error
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            raise UpstreamError(self.name, "unreachable", 0, str(getattr(error, "reason", error))) from error

    def _url(self, path: str, query: dict) -> str:
        pairs = {key: _query_value(value) for key, value in query.items()}
        return self.base_url + path + ("?" + urllib.parse.urlencode(pairs) if pairs else "")

    def _headers(self, body: dict | None) -> dict:
        headers = {self.key_header: self.api_key, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        return headers


def _required(root: ElementTree.Element, tag: str, config_path: Path) -> str:
    value = (root.findtext(tag) or "").strip()
    if not value:
        raise ValueError(f"{config_path} has no <{tag}>")
    return value


def _query_value(value: Any) -> str:
    return str(value).lower() if isinstance(value, bool) else str(value)


def _decode(service: str, raw: bytes) -> Any:
    if len(raw) > MAX_RESPONSE_BYTES:
        raise UpstreamError(service, "reply too large")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError as error:
        raise UpstreamError(service, "reply is not JSON") from error


def _error_detail(error: urllib.error.HTTPError) -> str:
    """The first validation message Sonarr or Radarr put in a 4xx reply, if any."""
    try:
        payload = json.loads(error.read(65536) or b"null")
    except ValueError:
        return ""
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return str(payload[0].get("errorMessage", ""))[:300]
    if isinstance(payload, dict):
        return str(payload.get("message", ""))[:300]
    return ""
