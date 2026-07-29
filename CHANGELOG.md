# Changelog

## 1.0.0 - 2026-07-29

### Agregado

- Backend multiempresa con empresas auditoras, codigos de vinculacion, solicitudes de dispositivos y sesiones temporales de auditor por 12 horas.
- Auditoria de eventos de red y ciclo de vida asociada historicamente a `company_id` y `company_device_link_id`.
- Agente operativo por terminal con estado local multiempresa, seleccion de empresa activa, apagado controlado, desvinculacion y cola offline.
- CLI de auditor para crear empresas, solicitar/verificar acceso, administrar vinculaciones, consultar historial y exportar evidencia JSON.
- Proveedor OTP por SMS mediante Twilio, manteniendo proveedor local solo para entornos locales/test.
- Rate limit de OTP por empresa, dispositivo e IP con auditoria de eventos `REQUESTED`, `FAILED`, `BLOCKED` y `VERIFIED`.
- Configuracion de produccion con PostgreSQL obligatorio, docs desactivados, healthcheck con migracion actual y secretos fuertes.
- Dockerfile, `docker-compose.prod.yml`, `.env.production.example`, guia de despliegue, smoke test V1 y script de backup PostgreSQL.

### Corregido

- El rate limit por IP de OTP usa cabeceras reenviadas solo cuando el cliente es un proxy declarado en `TRUSTED_PROXY_IPS`.
- Los eventos historicos siguen consultables tras desvincular un dispositivo, pero eventos nuevos con vinculo revocado se rechazan.
- La cola local descarta eventos legacy incompatibles sin bloquear eventos nuevos con contexto multiempresa.

### Validacion

- Suite completa: `111 passed, 1 skipped`.
- Ruff: limpio.
- Mypy: sin errores.
- Alembic: cadena lineal hasta `202607290004`.
- Smoke PostgreSQL real: migraciones y `tests/test_postgres_smoke.py` pasan contra `postgres:17-alpine`.
