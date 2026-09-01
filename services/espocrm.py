from __future__ import annotations

from typing import Any

import requests


class EspoCRMError(RuntimeError):
    pass


class EspoCRMClient:
    """Cliente mínimo para EspoCRM. v0.2 sigue siendo read-only."""

    def __init__(self, base_url: str, api_key: str, timeout: int = 20):
        self.base_url = base_url.rstrip("/")
        self.api_root = f"{self.base_url}/api/v1"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-Api-Key": api_key,
                "Accept": "application/json",
            }
        )

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.api_root}/{path.lstrip('/')}"
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise EspoCRMError(f"No se pudo conectar con EspoCRM: {exc}") from exc

        if response.status_code >= 400:
            body = response.text[:500]
            raise EspoCRMError(
                f"EspoCRM respondió HTTP {response.status_code} en {path}: {body}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise EspoCRMError(f"EspoCRM no devolvió JSON válido en {path}.") from exc

    def health(self) -> dict[str, Any]:
        return self._get("App/user")

    def get_lead(self, lead_id: str) -> dict[str, Any]:
        return self._get(f"Lead/{lead_id}")

    def list_leads(self, max_size: int = 200) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        page_size = min(100, max_size)

        while len(rows) < max_size:
            payload = self._get(
                "Lead",
                {
                    "maxSize": page_size,
                    "offset": offset,
                    "orderBy": "modifiedAt",
                    "order": "desc",
                },
            )
            batch = payload.get("list", [])
            if not batch:
                break

            rows.extend(batch)
            offset += len(batch)

            total = payload.get("total")
            if total is not None and offset >= int(total):
                break
            if len(batch) < page_size:
                break

        return rows[:max_size]

    def related(
        self,
        entity_type: str,
        entity_id: str,
        link: str,
        max_size: int = 100,
        order_by: str = "createdAt",
        order: str = "desc",
    ) -> list[dict[str, Any]]:
        payload = self._get(
            f"{entity_type}/{entity_id}/{link}",
            {
                "maxSize": max_size,
                "orderBy": order_by,
                "order": order,
            },
        )
        return payload.get("list", [])

    def lead_emails(self, lead_id: str, link: str = "emails") -> list[dict[str, Any]]:
        return self.related("Lead", lead_id, link, max_size=100)

    def lead_tasks(self, lead_id: str, link: str = "tasks") -> list[dict[str, Any]]:
        return self.related("Lead", lead_id, link, max_size=100)
