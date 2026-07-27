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
AGENT_TOKEN=
AGENT_TOKEN_HEADER=X-Agent-Token
AGENT_HEARTBEAT_INTERVAL_SECONDS=60
AGENT_SCAN_INTERVAL_SECONDS=15
AGENT_NETWORK_EVENT_DEDUP_SECONDS=300
AGENT_REQUEST_TIMEOUT_SECONDS=10
```

`AGENT_DEVICE_ID` puede quedar vacio. En ese caso el agente genera un identificador estable a partir de datos tecnicos del equipo.

`AGENT_TOKEN` es obligatorio para reportar al backend. Se obtiene desde el endpoint de provision del backend y debe corresponder al `device_id` del equipo.

## Ejecucion

```bash
.venv/bin/python -m agent.app.cli --backend-url http://127.0.0.1:8000 --once
```

Ejecutar con token:

```bash
AGENT_TOKEN=token-generado .venv/bin/python -m agent.app.cli \
  --backend-url http://127.0.0.1:8000 \
  --device-id device-001 \
  --once
```

Comprobar identidad detectada:

```bash
.venv/bin/python -m agent.app.cli --identify
```

Ejecutar en modo continuo:

```bash
.venv/bin/python -m agent.app.cli --backend-url http://127.0.0.1:8000
```

## Que Reporta En El MVP

- Registro del dispositivo en el backend.
- `AGENT_STARTED` al iniciar.
- `AGENT_HEARTBEAT` en cada ciclo.
- `AGENT_STOPPING` y `AGENT_STOPPED` al finalizar correctamente.
- Conexiones salientes observadas mediante `psutil.net_connections`.

Los eventos de red incluyen IP local, IP destino, puerto destino, protocolo, interfaz y MAC cuando el sistema operativo permite leer esos datos. Los bytes enviados y recibidos quedan en `0` en este MVP porque `psutil.net_connections` no expone contadores por conexion individual.

## Limites Del MVP

- No captura contenido de solicitudes/respuestas.
- No interpreta metodo HTTP ni status code.
- No intercepta TLS.
- No intenta ocultarse ni impedir que IT lo administre.
