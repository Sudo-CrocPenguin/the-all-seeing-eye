# CLI De Auditor Multiempresa

El CLI de auditor permite operar una empresa auditora desde terminal con sesiones temporales por dispositivo. Sirve para que un auditor autorizado pueda crear codigos de vinculacion, aceptar dispositivos, consultar historial y exportar evidencia sin abrir Swagger ni escribir `curl` manualmente.

## Que Es

Es un cliente Python instalable con dos scripts:

```text
all-seeing-eye-auditor
ase-auditor
```

El comando usa los endpoints existentes del backend y guarda una sesion local temporal en JSON. La autorizacion real sigue estando en el backend mediante `X-Auditor-Session`.

## Para Que Sirve

- Crear empresas auditoras.
- Solicitar acceso temporal de auditor desde un dispositivo registrado.
- Verificar OTP/SMS y guardar una sesion local.
- Generar codigos de vinculacion para agentes.
- Listar, aceptar o denegar solicitudes de vinculacion.
- Consultar resumen de empresa.
- Consultar historial de red, lifecycle, movimientos y ventanas de incidente.
- Exportar evidencia JSON por empresa, rango de fechas y dispositivo opcional.

## Configuracion

Variables principales:

```text
AUDITOR_BACKEND_URL=http://127.0.0.1:8000
AUDITOR_DEVICE_ID=
AUDITOR_AGENT_TOKEN=
AUDITOR_AGENT_TOKEN_HEADER=X-Agent-Token
AUDITOR_SESSION_HEADER=X-Auditor-Session
AUDITOR_REQUEST_TIMEOUT_SECONDS=10
AUDITOR_SESSION_FILE=
AUDITOR_ALLOW_INSECURE_TRANSPORT=false
```

`AUDITOR_DEVICE_ID` identifica el dispositivo que solicita acceso auditor. Debe existir como dispositivo registrado en el backend.

`AUDITOR_AGENT_TOKEN` es el token de agente de ese dispositivo. Solo se usa para solicitar y verificar acceso de auditor. Si no se define, el CLI usa `AGENT_TOKEN` como fallback.

`AUDITOR_SESSION_FILE` guarda la sesion temporal verificada. Ruta por defecto:

```text
~/.local/state/the-all-seeing-eye/auditor-session.json
```

HTTP solo se permite por defecto hacia `127.0.0.1` o `localhost`. Para laboratorio con una IP LAN/VPN, usar `AUDITOR_ALLOW_INSECURE_TRANSPORT=true`. Para despliegue real, usar HTTPS.

## Flujo Operativo

Crear empresa:

```bash
ase-auditor company create --name "Acme Auditoria" --phone "+573001112233"
```

Solicitar acceso auditor:

```bash
AUDITOR_DEVICE_ID=device-auditor AUDITOR_AGENT_TOKEN=token \
ase-auditor access request --company company-1
```

En `APP_ENV=local`, el backend devuelve `Codigo local`. En produccion el codigo debe llegar por SMS al telefono de la empresa.

Verificar acceso:

```bash
ase-auditor access verify \
  --company company-1 \
  --request auditor-access-request-1 \
  --code 123456
```

La sesion queda guardada localmente y dura hasta `expires_at`, normalmente 12 horas.

Crear codigo de vinculacion:

```bash
ase-auditor enrollment-code create --ttl-seconds 3600 --max-uses 1
```

Listar solicitudes:

```bash
ase-auditor enrollment-requests list --status PENDING
```

Aceptar o denegar una solicitud:

```bash
ase-auditor enrollment-requests approve --request enrollment-request-1
ase-auditor enrollment-requests deny --request enrollment-request-2
```

Ver resumen:

```bash
ase-auditor summary
```

## Historial

Eventos de red:

```bash
ase-auditor history network \
  --from 2026-07-29T00:00:00+00:00 \
  --to 2026-07-29T23:59:59+00:00 \
  --device-id device-1
```

Eventos lifecycle:

```bash
ase-auditor history lifecycle --event-type AGENT_STOPPED
```

Movimientos unificados de un equipo:

```bash
ase-auditor history movements --device-id device-1 --limit 100
```

Ventana de incidente:

```bash
ase-auditor history incident-window \
  --from 2026-07-29T10:00:00+00:00 \
  --to 2026-07-29T10:30:00+00:00
```

Todas las consultas usan la empresa de la sesion local. Si se envia `--company`, debe coincidir con esa sesion; esto evita exportar o consultar accidentalmente otra empresa.

## Exportacion JSON

Exportar a archivo:

```bash
ase-auditor export-json \
  --from 2026-07-29T00:00:00+00:00 \
  --to 2026-07-29T23:59:59+00:00 \
  --device-id device-1 \
  --output evidencia-acme-device-1.json
```

Si se omite `--output`, el JSON se imprime en stdout.

Formato base:

```json
{
  "format_version": "audit-export/v1",
  "metadata": {
    "exported_at": "2026-07-29T12:00:00+00:00",
    "company": {
      "company_id": "company-1"
    },
    "filters": {
      "from": "2026-07-29T00:00:00+00:00",
      "to": "2026-07-29T23:59:59+00:00",
      "device_id": "device-1",
      "limit": 500
    }
  },
  "events": {
    "network_events": [],
    "lifecycle_events": [],
    "device_movements": [],
    "incident_window": {}
  }
}
```

La exportacion conserva los `company_id` y `company_device_link_id` historicos de cada evento. Si un dispositivo se desvincula despues, el historial previo sigue exportable por auditores autorizados de esa empresa.

## Controles Y Limites

- La sesion local no reemplaza permisos del backend; cada comando sensible usa `X-Auditor-Session`.
- Una sesion vencida o revocada se rechaza localmente antes de consultar.
- El CLI no guarda OTP.
- En produccion, el backend no debe exponer `verification_code`; debe enviarlo por proveedor SMS real.
- Falta implementar log persistente de comandos sensibles del auditor para hardening V1.
