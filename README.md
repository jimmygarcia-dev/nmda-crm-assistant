# NMDA Sales Assistant v0.3

## Qué cambia

La v0.3 agrega el **First Email** al flujo semi-automatizado.

Cuando un lead tiene **0 emails enviados** y la siguiente acción es `First Email`:

1. Abres el lead.
2. El Sales Assistant prepara automáticamente un borrador.
3. Usa datos que ya existen en EspoCRM, cuando están disponibles:
   - empresa,
   - nombre del contacto,
   - servicios,
   - descripción,
   - industria.
4. Puedes editar el asunto y el cuerpo.
5. Copias el texto.
6. Tú sigues enviando manualmente.

También conserva:
- Follow-up #1
- Follow-up #2
- detección de respuestas
- recomendación de Recycled
- acceso directo al Lead en EspoCRM

## Importante

El First Email de esta versión **no usa Ollama todavía**.

Es un borrador determinista basado en los datos enriquecidos que ya están guardados
en EspoCRM. Su objetivo es quitarte la hoja en blanco, no reemplazar la investigación.

Si un lead es importante, conviene revisar el sitio/LinkedIn y ajustar el primer párrafo
antes de enviarlo.

## Filosofía

```text
CRM sabe qué toca
        ↓
Sales Assistant prepara el borrador
        ↓
Jimmy revisa / personaliza
        ↓
Jimmy envía
```

Nada se envía automáticamente.

## Docker

Conserva tu `.env`.

```bash
docker compose down
docker compose up -d --build
```

Abrir:

```text
http://localhost:8090
```

## Siguiente evolución posible

Una futura versión puede usar Ollama **solo para redactar** el First Email o follow-ups,
mientras la decisión de qué acción corresponde sigue siendo determinista.
