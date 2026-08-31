# NMDA Sales Assistant v0.1

MVP **read-only** para quitar el trabajo administrativo del seguimiento de NMDA Events.

## Qué hace
- Se conecta a EspoCRM mediante REST API.
- Lee Leads `Assigned` / `In Process`.
- Lee emails y tareas relacionados.
- Recomienda: First Email, Follow-up #1, Follow-up #2, Recycled o Revisar respuesta.
- Usa días hábiles para calcular fechas.
- Abre el Lead original en EspoCRM.
- **No modifica EspoCRM y no envía correos.**

## Regla v0.1
```text
0 emails  → First Email
1 email   → Follow-up #1
2 emails  → Follow-up #2
3+ emails → esperar y luego Recycled
respuesta → STOP / revisión humana
```

## 1. API User en EspoCRM
1. `Administration > Roles`.
2. Crea `NMDA Sales Assistant Read Only`.
3. Da acceso **Read** a Lead, Email y Task.
4. `Administration > API Users`.
5. Crea un API User con autenticación **API Key** y asigna ese role.
6. Copia la API Key.

EspoCRM usa `/api/v1/` y el header `X-Api-Key`.

## 2. Configurar
```bash
cp .env.example .env
```
Edita `.env`:
```env
ESPOCRM_URL=http://localhost:8080
ESPOCRM_API_KEY=TU_API_KEY
OUR_EMAIL=contact@nmdasolutions.com
```

## 3. Instalar
```bash
python -m venv .venv
```
Git Bash:
```bash
source .venv/Scripts/activate
```
PowerShell:
```powershell
.venv\Scripts\Activate.ps1
```
Después:
```bash
pip install -r requirements.txt
```

## 4. Ejecutar
```bash
python api.py
```
Abre:
```text
http://localhost:8090
```
Tu EspoCRM puede seguir en `http://localhost:8080`.

## 5. Validación obligatoria
Antes de confiar en el dashboard compara manualmente 5 leads:
- solo First Email;
- First Email + Follow-up #1;
- tres correos;
- uno con respuesta;
- uno sin emails.

## Relaciones
EspoCRM permite `GET /api/v1/Lead/{id}/{link}`. Esperamos links `emails` y `tasks`. Si tu instancia usa nombres distintos, cambia en `.env`:
```env
ESPOCRM_EMAIL_LINK=emails
ESPOCRM_TASK_LINK=tasks
```
Confírmalos en `Administration > Entity Manager > Lead > Relationships`.

## No hacemos todavía
- enviar emails;
- crear tareas;
- cambiar status;
- generar First Email automáticamente;
- importar CSV.

Primero queremos resolver bien una sola pregunta: **¿qué acción de seguimiento corresponde hoy a cada lead?**
