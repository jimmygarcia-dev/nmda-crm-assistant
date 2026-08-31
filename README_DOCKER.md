# Docker — NMDA CRM Assistant v0.1

Copia estos archivos a la raíz del proyecto `nmda-crm-assistant-v0.1`:

- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`

La estructura debe quedar así:

```text
nmda-crm-assistant-v0.1/
├── api.py
├── services/
├── static/
├── requirements.txt
├── .env
├── Dockerfile
├── docker-compose.yml
└── .dockerignore
```

Tu `.env` conserva la API key:

```env
ESPOCRM_API_KEY=TU_API_KEY
OUR_EMAIL=contact@nmdasolutions.com
```

`docker-compose.yml` sustituye `ESPOCRM_URL` dentro del contenedor por:

```text
http://host.docker.internal:8080
```

Esto es necesario porque `localhost:8080` dentro del contenedor apuntaría al propio contenedor y no a EspoCRM.

## Levantar

```bash
docker compose up -d --build
```

Abrir:

```text
http://localhost:8090
```

## Logs

```bash
docker compose logs -f
```

## Reconstruir después de cambios

```bash
docker compose up -d --build
```

## Detener

```bash
docker compose down
```
