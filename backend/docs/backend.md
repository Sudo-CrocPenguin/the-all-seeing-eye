# Backend De Auditoria

Este backend recibe telemetria de agentes instalados en computadores corporativos autorizados. Los eventos se persisten con SQLAlchemy en PostgreSQL y las migraciones se gestionan con Alembic.

## Que Es

Es una API FastAPI modular que centraliza:

- Registro de dispositivos.
- Eventos de auditoria de red.
- Eventos de ciclo de vida del agente.
- Consultas iniciales por filtros operativos.

## Para Que Sirve

Sirve para que los agentes Windows/Linux reporten actividad tecnica de red y estado del servicio. Con esos datos, el equipo de seguridad puede revisar que equipo hizo una conexion, cuando ocurrio, que IPs participaron y si el agente tuvo interrupciones.

## Como Funciona

1. El agente registra o actualiza el dispositivo en `POST /api/v1/devices`.
2. El agente envia conexiones observadas a `POST /api/v1/audit/network-events`.
3. El agente envia eventos de estado a `POST /api/v1/audit/lifecycle-events`.
4. El backend valida los datos con entidades de dominio.
5. Los repositorios SQLAlchemy guardan los registros en la base de datos.
6. Cuando recibe eventos validos del agente, el backend actualiza `devices.last_seen_at`.
7. Los endpoints `GET` consultan eventos persistidos por filtros operativos.

## Ultima Vez Visto

`devices.last_seen_at` representa la ultima vez que el backend recibio una senal valida de un agente autenticado. Se actualiza cuando:

- El agente registra o actualiza el dispositivo en `POST /api/v1/devices`.
- El agente envia un evento de red en `POST /api/v1/audit/network-events`.
- El agente envia eventos de ciclo de vida que prueban presencia, como `AGENT_STARTED`, `AGENT_HEARTBEAT`, `AGENT_STOPPING`, `AGENT_STOPPED`, `AGENT_RECOVERED` o `AGENT_CONFIG_CHANGED`.

El backend usa su propia hora de recepcion para `last_seen_at`. No usa `occurred_at` para este campo, porque en versiones con cola local podrian llegar eventos atrasados y no deben mover hacia atras la lectura operativa de actividad reciente.

## Ejecutar Localmente

Crear entorno virtual e instalar dependencias:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

Levantar el backend:

```bash
.venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Validar salud del servicio:

```bash
curl http://127.0.0.1:8000/health
```

La documentacion interactiva de FastAPI queda disponible en:

```text
http://127.0.0.1:8000/docs
```

## Base De Datos Local

Levantar PostgreSQL:

```bash
docker compose up -d postgres
```

Si el puerto `5432` ya esta ocupado en tu maquina, puedes levantarlo en otro puerto:

```bash
POSTGRES_PORT=5433 docker compose up -d postgres
```

Variable principal:

```text
DATABASE_URL=postgresql+psycopg://audit:audit@localhost:5432/the_all_seeing_eye
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
PERSISTENCE_BACKEND=sqlalchemy
```

Crear o actualizar las tablas:

```bash
.venv/bin/python -m alembic upgrade head
```

Modo alternativo en memoria para pruebas rapidas sin base de datos externa:

```text
PERSISTENCE_BACKEND=memory
```

## Endpoints Iniciales

```text
GET  /health
POST /api/v1/devices/agent-credentials
POST /api/v1/devices
GET  /api/v1/devices
POST /api/v1/audit/network-events
GET  /api/v1/audit/network-events
POST /api/v1/audit/lifecycle-events
POST /api/v1/audit/lifecycle-events/detect-missed-heartbeats
GET  /api/v1/audit/lifecycle-events
```

## Autenticacion De Agentes

Las escrituras realizadas por agentes requieren un token por dispositivo enviado en el header:

```text
X-Agent-Token: <token-del-agente>
```

Los endpoints protegidos son:

```text
POST /api/v1/devices
POST /api/v1/audit/network-events
POST /api/v1/audit/lifecycle-events
```

El token no se guarda en claro. El backend guarda hash y sal en la tabla `agent_credentials`.

## Consultas De Auditoria

Las consultas operativas requieren un token de auditoria separado del token de provisionamiento:

```text
X-Auditor-Token: <token-de-auditoria>
```

Configurar el token en el backend:

```text
AUDITOR_TOKEN=valor-de-auditoria-seguro
AUDITOR_TOKEN_HEADER=X-Auditor-Token
```

Los endpoints protegidos son:

```text
GET /api/v1/devices
GET /api/v1/audit/network-events
GET /api/v1/audit/lifecycle-events
```

Este token sirve para revisar historicos sin conceder permisos de provisionamiento de agentes.

### Provisionar Token

Para crear o rotar un token de agente se usa el endpoint de provision protegido por token administrativo:

```text
X-Provisioning-Token: <token-administrativo>
```

Configurar el token administrativo en el backend:

```text
PROVISIONING_TOKEN=valor-administrativo-seguro
```

Crear credencial:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/devices/agent-credentials \
  -H "Content-Type: application/json" \
  -H "X-Provisioning-Token: valor-administrativo-seguro" \
  -d '{"device_id":"device-001"}'
```

La respuesta incluye el token una sola vez para configurar el agente.

## Estado Operativo Del Agente

El backend mantiene el estado operativo del agente a partir de `devices.last_seen_at` y los eventos de ciclo de vida.

### Que Es

Es el mecanismo que permite saber si un agente sigue reportando, dejo de enviar heartbeats o volvio a reportar despues de una ausencia.

### Para Que Sirve

- Detectar equipos que dejaron de reportar sin un apagado limpio.
- Registrar eventos `AGENT_MISSED_HEARTBEAT` con `last_seen_at`, `detected_at` y `downtime_seconds`.
- Registrar `AGENT_RECOVERED` cuando el agente vuelve a reportar despues de un heartbeat perdido.
- Dar una base confiable para alertas, reportes diarios y revisiones de incidentes.

### Como Funciona

`AGENT_HEARTBEAT_TIMEOUT_SECONDS` define cuantos segundos puede pasar un agente sin reportar antes de considerarse vencido. El valor por defecto es `180`.

El detector se ejecuta con un endpoint administrativo protegido por `X-Provisioning-Token`:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/audit/lifecycle-events/detect-missed-heartbeats \
  -H "X-Provisioning-Token: valor-administrativo-seguro"
```

El endpoint revisa todos los dispositivos registrados. Si `last_seen_at` es anterior al timeout configurado y el ultimo evento de ciclo de vida no explica ya la ausencia, crea un evento `AGENT_MISSED_HEARTBEAT`.

Cuando un agente vuelve a enviar `AGENT_STARTED`, `AGENT_HEARTBEAT`, `AGENT_CONFIG_CHANGED` o un evento de red despues de estar marcado como perdido, el backend registra automaticamente `AGENT_RECOVERED` y actualiza `last_seen_at`.

## Filtros Disponibles

Eventos de red:

- `device_id`
- `local_ip`
- `public_ip`
- `destination_host`
- `destination_ip`
- `protocol`
- `from`
- `to`
- `limit`

Eventos de ciclo de vida:

- `device_id`
- `event_type`
- `from`
- `to`
- `limit`

## Pruebas

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
```

Las pruebas del API usan SQLAlchemy sobre SQLite en memoria. Esto valida los repositorios y la transaccion por request sin depender de Docker o de una base PostgreSQL local.
