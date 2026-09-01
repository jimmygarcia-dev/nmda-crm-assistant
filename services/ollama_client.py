from __future__ import annotations

import json
import re
from typing import Any

import requests


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    """Cliente pequeño para Ollama /api/generate."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: int = 180,
        temperature: float = 0.25,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature

    def generate_json(self, prompt: str) -> dict[str, Any]:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.temperature,
            },
        }

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise OllamaError(f"No se pudo conectar con Ollama: {exc}") from exc

        if response.status_code >= 400:
            body = response.text[:700]
            raise OllamaError(
                f"Ollama respondió HTTP {response.status_code}: {body}"
            )

        try:
            outer = response.json()
        except ValueError as exc:
            raise OllamaError("Ollama no devolvió JSON válido.") from exc

        raw = outer.get("response")
        if not raw:
            raise OllamaError("Ollama devolvió una respuesta vacía.")

        parsed = self._parse_json_object(raw)
        if not isinstance(parsed, dict):
            raise OllamaError("La respuesta de Ollama no contiene un objeto JSON.")

        return parsed

    def _parse_json_object(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw

        text = str(raw).strip()

        # Tolera fences aunque usemos format=json.
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Último intento: extraer el primer objeto JSON.
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise OllamaError("No se pudo localizar JSON en la respuesta de Ollama.")

        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise OllamaError(
                "Ollama respondió texto, pero el JSON generado no se pudo interpretar."
            ) from exc
