# NMDA Sales Assistant v0.4

## Qué cambia

La v0.4 usa **Ollama para redactar únicamente el First Email**.

La lógica de seguimiento sigue siendo determinista:

```text
0 emails → First Email
1 email  → Follow-up #1
2 emails → Follow-up #2
3+       → Recycled
respuesta → revisión humana
```

Cuando la acción es `First Email`, aparece:

```text
Generar First Email con IA
```

El botón:

1. Lee el Lead real de EspoCRM.
2. Construye contexto con los datos disponibles.
3. Envía ese contexto a Ollama.
4. Pide un correo natural y personalizado.
5. Devuelve `subject` + `body`.
6. Lo muestra editable.
7. Tú copias, revisas y envías manualmente.

**No guarda ni envía el correo.**

## Por qué Ollama solo en First Email

El First Email necesita interpretar información de la empresa y sintetizarla de forma humana.

Los follow-ups son más repetitivos y siguen usando plantillas locales simples.

La separación queda:

```text
Código decide QUÉ toca.
Ollama redacta CÓMO decir el First Email.
Jimmy decide QUÉ se envía.
```

## Configuración

Tu `.env` debe incluir:

```env
ESPOCRM_API_KEY=TU_API_KEY
OUR_EMAIL=contact@nmdasolutions.com

OLLAMA_MODEL=qwen2.5:7b
OLLAMA_TIMEOUT=180
```

En Docker no necesitas poner `OLLAMA_URL`: `docker-compose.yml` usa automáticamente:

```text
http://host.docker.internal:11434
```

porque Ollama corre en la máquina host y el Sales Assistant dentro del contenedor.

## Confirmar Ollama

En la máquina host:

```bash
ollama list
```

Debes tener descargado el modelo configurado.

Por ejemplo:

```bash
ollama pull qwen2.5:7b
```

## Actualizar Docker

Conserva tu `.env`.

```bash
docker compose down
docker compose up -d --build
```

Luego abre:

```text
http://localhost:8090
```

## Si el botón falla

Ver logs:

```bash
docker compose logs -f
```

Los errores de conexión o modelo aparecerán en la interfaz y en logs.

## Reglas del prompt

Ollama recibe instrucciones para:

- escribir en español;
- sonar profesional y humano;
- usar solo 1–2 observaciones relevantes;
- no copiar listas crudas de servicios;
- no inventar dolores o tecnología;
- no asumir que la empresa carece de plataforma;
- plantear complemento cuando ya existe tecnología;
- CTA de demo de 15–20 minutos;
- devolver JSON estructurado.

## No automatizado todavía

La v0.4 todavía NO:

- envía correos;
- crea Tasks;
- completa Tasks;
- cambia status;
- mueve leads a Recycled.

Eso queda para una siguiente versión una vez que validemos bien los First Emails con IA.
