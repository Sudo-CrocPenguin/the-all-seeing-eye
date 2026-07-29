# Produccion V1

Esta guia deja un despliegue minimo real para The All Seeing Eye V1. El objetivo no es reemplazar una plataforma de infraestructura corporativa, sino asegurar que el backend multiempresa, el agente y el CLI de auditor corran con PostgreSQL, HTTPS, migraciones verificadas y procedimientos basicos de operacion.

## Requisitos

- Host Linux administrado por IT.
- Docker Compose v2.
- Dominio interno o publico para el backend.
- Reverse proxy con TLS, por ejemplo Nginx, Caddy o Traefik.
- Secretos generados fuera del repositorio.
- Proveedor SMS configurado, actualmente `twilio`.

## Configuracion

Crear `.env.production` desde `.env.production.example` y reemplazar todos los valores `change_me`.

Valores obligatorios:

```text
APP_ENV=production
PERSISTENCE_BACKEND=sqlalchemy
API_DOCS_ENABLED=false
HEALTH_REQUIRE_CURRENT_MIGRATION=true
OTP_DELIVERY_PROVIDER=twilio
```

En produccion, `Settings` rechaza:

- `/docs` habilitado.
- health sin exigir migracion actual.
- persistencia en memoria.
- base que no sea PostgreSQL.
- OTP local.
- secretos compartidos con menos de 32 caracteres.

## Despliegue

Construir e iniciar:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

Ver estado:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f backend
```

El contenedor backend ejecuta `alembic upgrade head` antes de arrancar. Si una migracion falla, el servicio no debe quedar disponible.

## Reverse Proxy HTTPS

El backend debe quedar escuchando solo en loopback o red interna:

```text
BACKEND_BIND_HOST=127.0.0.1
BACKEND_PORT=8000
```

Ejemplo Nginx:

```nginx
server {
    listen 443 ssl http2;
    server_name audit.example.com;

    ssl_certificate /etc/letsencrypt/live/audit.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/audit.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

No publicar el puerto `8000` directamente a internet.

## Healthcheck

```bash
curl -fsS https://audit.example.com/health
```

Respuesta esperada:

```json
{
  "status": "ok"
}
```

Con `HEALTH_REQUIRE_CURRENT_MIGRATION=true`, el health falla si Alembic no esta en `head`.

## Prueba PostgreSQL Local

Para validar migraciones y un smoke test contra PostgreSQL real:

```bash
docker run --name ase-v1-postgres-test \
  -e POSTGRES_DB=the_all_seeing_eye_test \
  -e POSTGRES_USER=audit \
  -e POSTGRES_PASSWORD=audit_pw \
  -p 127.0.0.1:55433:5432 \
  -d postgres:17-alpine

DATABASE_URL=postgresql+psycopg://audit:audit_pw@127.0.0.1:55433/the_all_seeing_eye_test \
  .venv/bin/alembic upgrade head

POSTGRES_SMOKE_DATABASE_URL=postgresql+psycopg://audit:audit_pw@127.0.0.1:55433/the_all_seeing_eye_test \
  .venv/bin/pytest tests/test_postgres_smoke.py

docker rm -f ase-v1-postgres-test
```

## Logs

Los logs de backend salen por stdout/stderr del contenedor:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production logs --since 1h backend
```

Para produccion real se recomienda enviar estos logs a journald, Loki, ELK, CloudWatch o equivalente.

## Backups

Ejecutar backup manual:

```bash
set -a
source .env.production
set +a
bash backend/deploy/production/backup-postgres.sh
```

Guardar los `.sql` fuera del host del backend y protegerlos con permisos restringidos. Programar el script con cron/systemd timer segun politica de retencion.

## Rollback Basico

1. Mantener imagen anterior disponible antes de desplegar.
2. Hacer backup antes de migrar.
3. Si falla el deploy antes de migraciones destructivas, volver a la imagen anterior y reiniciar.
4. Si la migracion ya escribio cambios incompatibles, restaurar el backup en una base nueva y apuntar `DATABASE_URL` al rollback.
5. Verificar `/health` y ejecutar el smoke test V1.

No ejecutar downgrade automatico de Alembic en produccion sin revisar la migracion concreta.
