# Agente MVP De Auditoria

El agente MVP corre en equipos corporativos Windows y Linux de forma autorizada. Su objetivo es observar metadatos de red, reportar el estado del servicio y enviar eventos al backend central.

## Que Es

Es un proceso Python instalable como servicio corporativo. En este MVP no se oculta del usuario ni intenta evadir controles del sistema operativo.

## Para Que Sirve

- Registrar el dispositivo auditado.
- Reportar inicio, heartbeat y apagado del agente.
- Capturar conexiones salientes con metadatos tecnicos.
- Enviar eventos al backend para consulta posterior.

## Configuracion

Variables principales:

```text
AGENT_BACKEND_URL=http://127.0.0.1:8000
AGENT_DEVICE_ID=
AGENT_HEARTBEAT_INTERVAL_SECONDS=60
AGENT_SCAN_INTERVAL_SECONDS=15
AGENT_NETWORK_EVENT_DEDUP_SECONDS=300
AGENT_REQUEST_TIMEOUT_SECONDS=10
```

`AGENT_DEVICE_ID` puede quedar vacio. En ese caso el agente genera un identificador estable a partir de datos tecnicos del equipo.

## Ejecucion

```bash
.venv/bin/python -m agent.app.cli --backend-url http://127.0.0.1:8000 --once
```

