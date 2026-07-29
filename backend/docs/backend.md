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

En entornos no locales (`APP_ENV=beta`, `staging` o similar), `/docs`, `/redoc` y `/openapi.json` se desactivan automaticamente aunque `API_DOCS_ENABLED=true`. Para local siguen activos por defecto.

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
POSTGRES_DB=the_all_seeing_eye
POSTGRES_USER=audit
POSTGRES_PASSWORD=audit
PERSISTENCE_BACKEND=sqlalchemy
```

Los valores `audit/audit` son solo defaults locales de Docker Compose. Para piloto controlado se deben reemplazar por credenciales fuertes y una base separada de los sistemas auditados.

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
POST /api/v1/companies
POST /api/v1/companies/{company_id}/auditor-access-requests
POST /api/v1/companies/{company_id}/auditor-access-requests/{request_id}/verify
POST /api/v1/companies/{company_id}/enrollment-codes
POST /api/v1/companies/enrollment-requests
GET  /api/v1/companies/device-links
POST /api/v1/companies/device-links/{company_device_link_id}/revoke
GET  /api/v1/companies/{company_id}/enrollment-requests
POST /api/v1/companies/{company_id}/enrollment-requests/{request_id}/review
GET  /api/v1/companies/{company_id}/summary
POST /api/v1/devices/agent-credentials
POST /api/v1/devices
GET  /api/v1/devices
POST /api/v1/audit/network-events
GET  /api/v1/audit/network-events
GET  /api/v1/audit/device-movements
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
POST /api/v1/companies/enrollment-requests
GET  /api/v1/companies/device-links?device_id=<device_id>
POST /api/v1/companies/device-links/{company_device_link_id}/revoke
POST /api/v1/audit/network-events
POST /api/v1/audit/lifecycle-events
```

El token no se guarda en claro. El backend guarda hash y sal en la tabla `agent_credentials`.

Los eventos de auditoria solo se aceptan para dispositivos ya registrados en `POST /api/v1/devices`. Aunque el payload incluya `hostname`, `os_name` o `agent_version`, el backend usa los valores registrados del dispositivo para esos campos estables y evita confiar en metadatos reclamados por el agente.

Los eventos de red y ciclo de vida tambien deben incluir:

```text
company_id
company_device_link_id
```

El backend valida que `company_device_link_id` pertenezca a `company_id`, al `device_id` autenticado y que el vinculo este `ACTIVE`. Los eventos historicos conservan esos IDs aunque el vinculo se revoque despues.

Desde V1 estos campos son obligatorios tambien en la base de datos. La migracion multiempresa asume una base limpia o eventos beta ya migrados con un `company_id` y `company_device_link_id` historico. Si existen eventos legacy sin contexto, se deben exportar, asociar por backfill o purgar antes de ejecutar Alembic en produccion.

El agente puede listar sus vinculos con `GET /api/v1/companies/device-links?device_id=<device_id>`. El backend valida que el `X-Agent-Token` pertenezca al `device_id` solicitado. La respuesta incluye `company_name`, `status`, `linked_at` y datos de revocacion para poblar el estado local.

La desvinculacion se hace con `POST /api/v1/companies/device-links/{company_device_link_id}/revoke` y body `{"device_id":"..."}`. El backend valida que el token corresponda al dispositivo y que el vinculo pertenezca a ese dispositivo. La revocacion marca el vinculo como `REVOKED`; no borra eventos historicos.

La IP publica observada se toma del socket de entrada o de headers de proxy solo si la solicitud llega desde un proxy confiable configurado en:

```text
TRUSTED_PROXY_IPS=127.0.0.1,10.0.0.0/24
```

Si `TRUSTED_PROXY_IPS` esta vacio, headers como `X-Forwarded-For`, `X-Real-IP` y `CF-Connecting-IP` se ignoran. Esto evita que un cliente directo falsifique la IP publica en evidencia.

El campo persistido `public_ip` se calcula solo desde la conexion entrante o desde un proxy confiable. Si un agente envia `public_ip` en el JSON, ese valor no se usa como evidencia y, en eventos de red, queda separado en `request_metadata.agent_reported_public_ip`.

## Consultas Globales De Dispositivos

La consulta global de dispositivos requiere un token de auditoria separado del token de provisionamiento:

```text
X-Auditor-Token: <token-de-auditoria>
```

Configurar el token en el backend:

```text
AUDITOR_TOKEN=valor-de-auditoria-seguro
AUDITOR_TOKEN_HEADER=X-Auditor-Token
```

En entornos no locales, `AUDITOR_TOKEN` y `PROVISIONING_TOKEN` deben tener al menos 32 caracteres. Si no cumplen esa condicion, el backend no arranca.

El endpoint protegido por este token es:

```text
GET /api/v1/devices
```

## Consultas De Auditoria Por Empresa

Las consultas de eventos requieren una sesion temporal de auditor:

```text
X-Auditor-Session: <auditor_session_id>
```

La sesion contiene el `company_id` autorizado. Por eso las consultas de eventos siempre se filtran por empresa aunque el auditor envie `device_id`.

Los endpoints protegidos por sesion son:

```text
GET /api/v1/audit/network-events
GET /api/v1/audit/device-movements
GET /api/v1/audit/incident-window
GET /api/v1/audit/lifecycle-events
```

## Autenticacion Multiempresa Por Terminal

### Que Es

Es la base para operar varias empresas auditoras desde terminal. Cada empresa puede tener
dispositivos vinculados, codigos temporales de vinculacion y sesiones temporales de
auditor.

La sesion de auditor autoriza acciones de empresa como crear codigos de vinculacion,
revisar solicitudes, consultar resumen de empresa y revisar eventos de auditoria de esa
empresa.

### Para Que Sirve

Sirve para que una empresa controle que dispositivos reportan a su negocio y que
dispositivos pueden actuar como auditores durante una ventana corta.

En esta primera fase permite:

- Crear una empresa auditora.
- Solicitar acceso temporal de auditor desde un dispositivo registrado.
- Verificar el codigo OTP/SMS y obtener una sesion de 12 horas.
- Generar codigos temporales de vinculacion.
- Solicitar vinculacion de un dispositivo a una empresa.
- Aceptar o denegar solicitudes de vinculacion.
- Ver un resumen operativo de dispositivos vinculados y solicitudes pendientes.

### Como Funciona

Crear empresa:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/companies \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Auditoria","phone_number":"+573001112233"}'
```

Solicitar acceso auditor desde un dispositivo registrado:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/companies/<company_id>/auditor-access-requests \
  -H "Content-Type: application/json" \
  -H "X-Agent-Token: <token-del-dispositivo>" \
  -d '{"device_id":"device-auditor"}'
```

En `APP_ENV=local`, la respuesta incluye `verification_code` para desarrollo. En entornos
no locales, el campo no se expone y el canal esperado es SMS.

Verificar codigo y crear sesion de auditor:

```bash
curl -X POST \
  http://127.0.0.1:8000/api/v1/companies/<company_id>/auditor-access-requests/<request_id>/verify \
  -H "Content-Type: application/json" \
  -H "X-Agent-Token: <token-del-dispositivo>" \
  -d '{"device_id":"device-auditor","verification_code":"123456"}'
```

La respuesta incluye `auditor_session_id`. Las acciones de empresa usan:

```text
X-Auditor-Session: <auditor_session_id>
```

Crear codigo de vinculacion:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/companies/<company_id>/enrollment-codes \
  -H "Content-Type: application/json" \
  -H "X-Auditor-Session: <auditor_session_id>" \
  -d '{"ttl_seconds":3600,"max_uses":1}'
```

Solicitar vinculacion de otro dispositivo:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/companies/enrollment-requests \
  -H "Content-Type: application/json" \
  -H "X-Agent-Token: <token-del-dispositivo>" \
  -d '{"device_id":"device-001","enrollment_code":"codigo"}'
```

Aceptar o denegar solicitud:

```bash
curl -X POST \
  http://127.0.0.1:8000/api/v1/companies/<company_id>/enrollment-requests/<request_id>/review \
  -H "Content-Type: application/json" \
  -H "X-Auditor-Session: <auditor_session_id>" \
  -d '{"decision":"ACCEPT"}'
```

Consultar resumen de empresa:

```bash
curl -H "X-Auditor-Session: <auditor_session_id>" \
  http://127.0.0.1:8000/api/v1/companies/<company_id>/summary
```

### Limites De Esta Fase

- El envio real de SMS todavia no esta integrado.
- El dispositivo aun no tiene menu local para seleccionar empresa activa.
- La desvinculacion libre con aviso a empresa queda para la siguiente fase.
- La exportacion JSON de auditor por terminal queda para la siguiente fase.

### Historial Unificado Del Equipo

Para ver todos los movimientos de un equipo en una sola linea temporal:

```bash
curl -H "X-Auditor-Session: <auditor_session_id>" \
  "http://127.0.0.1:8000/api/v1/audit/device-movements?device_id=DEV-LAPTOP-042&limit=100"
```

La respuesta mezcla conexiones de red y ciclo de vida del agente con campos comunes:

- `movement_type`: `NETWORK_CONNECTION`, `AGENT_STARTED`, `AGENT_HEARTBEAT`, `AGENT_STOPPED`, etc.
- `summary`: destino o evento resumido.
- `local_username`, `process_id`, `process_name`: cuando el sistema operativo permite asociar proceso.
- `destination_host`, `destination_ip`, `destination_port`: cuando aplica.
- `connection_status`: estado TCP/UDP observado por `psutil`.

La base tambien crea una vista SQL `device_movements` para revisar este historial directo en la DB:

```sql
SELECT occurred_at, movement_type, company_id, device_id, process_name, summary
FROM device_movements
WHERE company_id = '<company_id>' AND device_id = 'DEV-LAPTOP-042'
ORDER BY occurred_at DESC;
```

### Ventana De Incidente

La consulta `/api/v1/audit/incident-window` calcula los equipos activos con una busqueda agregada independiente del `limit` usado para devolver eventos. Esto evita que una ventana con muchos eventos o un limite bajo oculte equipos que si reportaron dentro del rango.

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

Para no depender de ejecucion manual, el backend puede correr el detector en segundo plano:

```text
MISSED_HEARTBEAT_SCHEDULER_ENABLED=true
MISSED_HEARTBEAT_SCHEDULER_INTERVAL_SECONDS=60
```

Este scheduler corre dentro del proceso FastAPI. Para `0.1.0-beta.1`, si `MISSED_HEARTBEAT_SCHEDULER_ENABLED=true`, despliega el backend con un solo worker. Con varios workers se iniciaria un scheduler por proceso; antes de escalar, mueve este detector a un job singleton externo.

El detector se ejecuta con un endpoint administrativo protegido por `X-Provisioning-Token`:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/audit/lifecycle-events/detect-missed-heartbeats \
  -H "X-Provisioning-Token: valor-administrativo-seguro"
```

El endpoint revisa todos los dispositivos registrados. Si `last_seen_at` es anterior al timeout configurado y el ultimo evento de ciclo de vida no explica ya la ausencia, crea un evento `AGENT_MISSED_HEARTBEAT`.

Cuando un agente vuelve a enviar `AGENT_STARTED`, `AGENT_HEARTBEAT`, `AGENT_CONFIG_CHANGED` o un evento de red despues de estar marcado como perdido, el backend registra automaticamente `AGENT_RECOVERED` y actualiza `last_seen_at`.

## Salud Operativa

`GET /health` revisa el proceso, la conexion a base de datos y el estado de migracion Alembic. En despliegues controlados se puede exigir que la DB este en la revision actual:

```text
HEALTH_REQUIRE_CURRENT_MIGRATION=true
```

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
