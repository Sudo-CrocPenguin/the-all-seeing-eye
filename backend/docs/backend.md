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
6. Los endpoints `GET` consultan eventos persistidos por filtros operativos.

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

Variable principal:

```text
DATABASE_URL=postgresql+psycopg://audit:audit@localhost:5432/the_all_seeing_eye
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
POST /api/v1/devices
GET  /api/v1/devices
POST /api/v1/audit/network-events
GET  /api/v1/audit/network-events
POST /api/v1/audit/lifecycle-events
GET  /api/v1/audit/lifecycle-events
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
