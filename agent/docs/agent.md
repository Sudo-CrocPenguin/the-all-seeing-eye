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
AGENT_ENV_FILE=
AGENT_DEVICE_ID=
AGENT_TOKEN=
AGENT_TOKEN_HEADER=X-Agent-Token
AGENT_HEARTBEAT_INTERVAL_SECONDS=60
AGENT_SCAN_INTERVAL_SECONDS=15
AGENT_NETWORK_EVENT_DEDUP_SECONDS=300
AGENT_REQUEST_TIMEOUT_SECONDS=10
AGENT_REQUEST_RETRY_BACKOFF_SECONDS=30
AGENT_QUEUE_FILE=
AGENT_SERVICE_MAP_FILE=
AGENT_REVERSE_DNS_ENABLED=true
AGENT_ALLOW_INSECURE_TRANSPORT=false
```

`AGENT_DEVICE_ID` puede quedar vacio. En ese caso el agente genera un identificador estable a partir de datos tecnicos del equipo.

`AGENT_TOKEN` es obligatorio para reportar al backend. Se obtiene desde el endpoint de provision del backend y debe corresponder al `device_id` del equipo.

`AGENT_BACKEND_URL` debe usar HTTPS cuando apunta a un host no local. HTTP hacia `127.0.0.1` o `localhost` se permite para desarrollo. HTTP hacia LAN/VPN solo funciona si `AGENT_ALLOW_INSECURE_TRANSPORT=true`, y debe limitarse a laboratorio o piloto documentado.

`AGENT_ENV_FILE` permite apuntar a un archivo de configuracion `KEY=VALUE`. Si no se define, el agente busca automaticamente:

```text
/etc/the-all-seeing-eye/agent.env
C:\ProgramData\TheAllSeeingEye\agent.env
```

## Cola Local Y Reintentos

### Que Es

Es una cola local en formato JSONL donde el agente guarda eventos que no pudo entregar al backend por caidas temporales de red o indisponibilidad del servidor.

### Para Que Sirve

- Evitar perder eventos cuando el backend no responde.
- Permitir que el agente siga corriendo aunque una solicitud falle.
- Reenviar eventos pendientes cuando el backend vuelve a estar disponible.

### Como Funciona

Cada solicitud al backend intenta vaciar primero la cola pendiente. Si el envio actual falla, el agente guarda la solicitud completa con su ruta y payload en `AGENT_QUEUE_FILE`.

El intervalo minimo entre reintentos de vaciado se configura con:

```text
AGENT_REQUEST_RETRY_BACKOFF_SECONDS=30
```

Rutas recomendadas para servicio:

```text
/var/lib/the-all-seeing-eye/agent-queue.jsonl
C:\ProgramData\TheAllSeeingEye\agent-queue.jsonl
```

El agente usa esta cola para registro del dispositivo, eventos de ciclo de vida y eventos de red.

Si existe cola pendiente y no se puede vaciar por backoff o fallo temporal, el agente no envia el request actual por delante. Lo agrega detras de los pendientes para conservar el orden, por ejemplo registro de dispositivo antes de `AGENT_STARTED`.

Si el archivo JSONL queda parcialmente corrupto tras un corte, el agente ignora las lineas invalidas, conserva los registros validos y reescribe la cola limpia.

Los errores temporales de red, HTTP `408`, `429` y respuestas `5xx` se consideran reintentables y se guardan en cola. Los errores fatales como token invalido, permisos insuficientes o payload rechazado (`401`, `403`, `422`) no se encolan indefinidamente: el agente los expone como fallo para corregir la configuracion o los datos enviados.

## Identidad Dinamica Y Resolucion De Destino

El agente vuelve a recolectar identidad tecnica antes de cada heartbeat y cada scan de red. Si cambian interfaces, IP local, VPN o metadatos del dispositivo, registra nuevamente el equipo y envia `AGENT_CONFIG_CHANGED`. Esto mantiene la correlacion actualizada sin reiniciar el servicio.

`AGENT_SERVICE_MAP_FILE` permite cargar nombres conocidos para servicios internos. Si el archivo no existe o esta corrupto, el agente degrada a un mapa vacio y sigue recolectando eventos.

`AGENT_REVERSE_DNS_ENABLED` controla la resolucion DNS inversa. Por defecto esta en `true`; si en una red causa latencia, se puede poner en `false` y depender del mapa de servicios o de la IP/puerto destino.

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

Ejecutar usando archivo de configuracion:

```bash
.venv/bin/python -m agent.app.cli --env-file /etc/the-all-seeing-eye/agent.env
```

## Servicio Linux Con systemd

### Que Es

Es una unidad systemd que ejecuta el agente como proceso administrado del sistema operativo. La unidad no oculta el agente: aparece en `systemctl`, logs del sistema y herramientas normales de administracion.

### Para Que Sirve

- Arrancar el agente automaticamente con el equipo.
- Reiniciar el agente si falla.
- Enviar apagados controlados cuando IT detiene el servicio.
- Mantener una configuracion persistente fuera de la terminal.

### Como Funciona

El instalador copia el proyecto a `/opt/the-all-seeing-eye`, crea un entorno virtual Python, instala el paquete y registra la unidad `all-seeing-eye-agent.service`.

Instalar:

```bash
sudo agent/deploy/linux/install-systemd.sh
```

Configurar token y backend:

```bash
sudo nano /etc/the-all-seeing-eye/agent.env
```

Operar el servicio:

```bash
sudo systemctl status all-seeing-eye-agent
sudo systemctl stop all-seeing-eye-agent
sudo systemctl start all-seeing-eye-agent
sudo journalctl -u all-seeing-eye-agent -f
```

Al detenerse con `systemctl stop`, systemd envia `SIGTERM`; el agente registra `AGENT_STOPPING` y `AGENT_STOPPED` antes de terminar.

## Servicio Windows

### Que Es

Es un Windows Service basado en `pywin32` que ejecuta el mismo runner del agente. El servicio queda visible como `AllSeeingEyeAgent` en la consola de servicios y en `Get-Service`.

### Para Que Sirve

- Arrancar el agente con Windows.
- Administrarlo con herramientas corporativas.
- Registrar detenciones e inicios del servicio.
- Mantener configuracion en `C:\ProgramData\TheAllSeeingEye\agent.env`.

### Como Funciona

Instalar desde PowerShell como administrador:

```powershell
.\agent\deploy\windows\install-service.ps1 -BackendUrl "http://backend:8000" -AgentToken "token-del-agente"
```

Operar el servicio:

```powershell
Get-Service -Name AllSeeingEyeAgent
Stop-Service -Name AllSeeingEyeAgent
Start-Service -Name AllSeeingEyeAgent
```

Desinstalar:

```powershell
.\agent\deploy\windows\uninstall-service.ps1
```

Al detenerse con `Stop-Service`, el wrapper solicita apagado al runner; el agente reporta `AGENT_STOPPING` y `AGENT_STOPPED`.

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
- Si el proceso se mata forzadamente o el equipo pierde energia/red, no puede enviar apagado limpio; esa ausencia debe detectarse en backend con heartbeats perdidos.
