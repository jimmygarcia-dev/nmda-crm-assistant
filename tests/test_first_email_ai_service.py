from services.first_email_ai_service import FirstEmailAIService
from services.ollama_client import OllamaClient


class FakeOllama(OllamaClient):
    def __init__(self):
        self.model = "fake-model"

    def generate_json(self, prompt):
        assert "CS Congress Services" in prompt
        assert "NO copies listas crudas" in prompt or "NO copies listas crudas".lower() in prompt.lower()
        return {
            "subject": "Una idea para sus congresos",
            "body": (
                "Hola equipo de CS Congress Services,\n\n"
                "Estuve revisando su trabajo en congresos y eventos médicos y científicos.\n\n"
                "Me gustaría conocer cómo gestionan actualmente la operación de asistentes.\n\n"
                "Saludos,\nJimmy García"
            ),
        }


def test_ai_first_email():
    service = FirstEmailAIService(FakeOllama())
    lead = {
        "accountName": "CS Congress Services",
        "cServices": "Event planning | Medical events | Scientific events | Conventions",
    }
    draft = service.generate(lead)
    assert draft.action == "FIRST_EMAIL"
    assert draft.model == "fake-model"
    assert "CS Congress Services" in draft.body
    assert "|" not in draft.body
