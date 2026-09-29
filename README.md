# NMDA Sales Assistant v0.4.2

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
- cambia status;
- mueve leads a Recycled.

**Automatizado en esta versión:**

- **Crear la Task del siguiente paso** (Follow-up #1 → Task "Enviar Follow-up #2"; Follow-up #2 → Task "Revisar respuesta o reciclaje") con vencimiento a **3 días hábiles** (sin contar sábados/domingos).

## Nueva funcionalidad: Crear tarea del siguiente paso

En el detalle de un lead con acción `Follow-up #1` o `Follow-up #2` aparece un botón:

```text
Crear tarea del siguiente paso
```

Al pulsarlo:

1. Valida que la acción actual sea `FOLLOW_UP_1` o `FOLLOW_UP_2`.
2. Calcula la fecha de vencimiento sumando 3 días hábiles (usa `FOLLOWUP_2_AFTER_DAYS` para FU1, `RECYCLE_AFTER_DAYS` para FU2).
3. Crea la Task en EspoCRM vía API (`POST /api/v1/Task`):
   - `name`: "Enviar Follow-up #2" o "Revisar respuesta o reciclaje".
   - `dateStart`: ahora; `dateEnd`: vencimiento a las 18:00.
   - `status`: "Not Started".
   - `parentType`: "Lead", `parentId`: el lead.
   - `assignedUserId`: opcional (`ESPOCRM_ASSIGNED_USER` en `.env`).
4. Idempotente: si ya existe una Task abierta con el mismo nombre, la devuelve sin duplicar.
5. Devuelve el enlace a la Task en EspoCRM.

**Endpoint:** `POST /api/leads/<lead_id>/followup-task`

**Configuración en `.env`:**

```env
# Usuario asignado a las tareas creadas (opcional; ID de usuario EspoCRM)
ESPOCRM_ASSIGNED_USER=

# Días hábiles para FU1 (usado al crear Task desde Follow-up #1)
FOLLOWUP_2_AFTER_DAYS=3

# Días hábiles para recycle (usado al crear Task desde Follow-up #2)
RECYCLE_AFTER_DAYS=3
```

**Nota:** El correo se sigue enviando manualmente (copias y envías desde EspoCRM). La automatización solo crea la Task de recordatorio con el vencimiento correcto.


## v0.4.2 — Automatización de Tasks de Follow-up

- Botón "Crear tarea del siguiente paso" en el detalle del lead para `Follow-up #1` y `Follow-up #2`.
- Crea Task en EspoCRM con vencimiento a 3 días hábiles (saltando fin de semana).
- Idempotente: no duplica si ya existe Task abierta con el mismo nombre.
- Configurable via `ESPOCRM_ASSIGNED_USER`, `FOLLOWUP_2_AFTER_DAYS`, `RECYCLE_AFTER_DAYS`.

## v0.4.1 — Formato y revisión del First Email

- Ollama devuelve una lista de párrafos y el backend inserta dobles saltos de línea.
- Se refuerza la revisión de ortografía, acentos, concordancia y puntuación.
- Jimmy siempre se presenta como fundador de NMDA Solutions y desarrollador de NMDA Events.
- Se prohíbe presentarlo como "asistente".
- Se evitan frases robóticas como "nos complace" o "estaríamos encantados".
- Se siguen evitando listas crudas del CRM y lenguaje de campaña masiva.
