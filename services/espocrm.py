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
        self._cached_user_id: str | None = None

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

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.api_root}/{path.lstrip('/')}"
        try:
            response = self.session.post(url, json=body, timeout=self.timeout)
        except requests.RequestException as exc:
            raise EspoCRMError(f"No se pudo conectar con EspoCRM: {exc}") from exc

        if response.status_code >= 400:
            payload = response.text[:500]
            raise EspoCRMError(
                f"EspoCRM respondió HTTP {response.status_code} al crear "
                f"{path}: {payload}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise EspoCRMError(f"EspoCRM no devolvió JSON válido al crear {path}.") from exc

    def health(self) -> dict[str, Any]:
        return self._get("App/user")

    def get_current_user_id(self) -> str | None:
        """Obtiene el ID del usuario autenticado por la API key (cacheado)."""
        if self._cached_user_id:
            return self._cached_user_id
        try:
            data = self._get("App/user")
            user = data.get("user") if isinstance(data.get("user"), dict) else None
            if user and user.get("id"):
                self._cached_user_id = str(user["id"])
                return self._cached_user_id
        except EspoCRMError:
            pass
        return None

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

    def create_task(
        self,
        *,
        name: str,
        date_start: str | None = None,
        date_end: str | None = None,
        status: str = "Not Started",
        description: str | None = None,
        parent_type: str = "Lead",
        parent_id: str | None = None,
        assigned_user_id: str | None = None,
    ) -> dict[str, Any]:
        """Crea una tarea en EspoCRM (primera operación de escritura del cliente).

        date_start/date_end se reciben en formato "YYYY-MM-DD HH:MM:SS".
        Si no se provee assigned_user_id, intenta usar el usuario de la API key.
        """
        body: dict[str, Any] = {
            "name": name,
            "status": status,
            "parentType": parent_type,
            "parentId": parent_id,
        }
        if date_start:
            body["dateStart"] = date_start
        if date_end:
            body["dateEnd"] = date_end
        if description:
            body["description"] = description

        # EspoCRM exige assignedUserId obligatorio.
        resolved_user = assigned_user_id or self.get_current_user_id()
        if resolved_user:
            body["assignedUserId"] = resolved_user
        else:
            raise EspoCRMError(
                "No se pudo resolver assignedUserId: provee ESPOCRM_ASSIGNED_USER "
                "en .env o asegúrate de que /api/v1/App/user devuelva el usuario."
            )

        return self._post("Task", body)
