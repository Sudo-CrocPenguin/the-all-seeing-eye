# Piloto Controlado 0.1.0 Beta

## Que Es

Esta guia define el despliegue aceptable para `0.1.0-beta.1`. Es una beta interna para red controlada, VPN o laboratorio corporativo. No es una version lista para internet publico ni para produccion general.

## Condiciones Minimas

- Backend detras de HTTPS, reverse proxy o VPN estricta.
- `APP_ENV=beta` o equivalente no local.
- `API_DOCS_ENABLED=false` si el servicio queda accesible a mas personas que el equipo tecnico.
- `AUDITOR_TOKEN` y `PROVISIONING_TOKEN` de al menos 32 caracteres, generados como secretos fuertes.
- `TRUSTED_PROXY_IPS` configurado solo con proxies reales que terminan TLS o VPN.
- Base de datos separada de los sistemas auditados.
- Backups de la base de auditoria fuera del alcance de usuarios operativos de los sistemas auditados.
- `MISSED_HEARTBEAT_SCHEDULER_ENABLED=true` para registrar ausencias sin depender del endpoint manual.
- Un solo worker de backend mientras el scheduler embebido este activo.
- Politica manual de retencion definida antes del piloto.

## Variables Recomendadas

```env
APP_ENV=beta
API_DOCS_ENABLED=false
HEALTH_REQUIRE_CURRENT_MIGRATION=true
PERSISTENCE_BACKEND=sqlalchemy
DATABASE_URL=postgresql+psycopg://usuario:password@host:5432/the_all_seeing_eye
TRUSTED_PROXY_IPS=10.0.0.10/32
AUDITOR_TOKEN=secreto_fuerte_de_32_caracteres_o_mas
PROVISIONING_TOKEN=otro_secreto_fuerte_de_32_caracteres
MISSED_HEARTBEAT_SCHEDULER_ENABLED=true
MISSED_HEARTBEAT_SCHEDULER_INTERVAL_SECONDS=60
```

El agente debe apuntar a HTTPS:

```env
AGENT_BACKEND_URL=https://audit.empresa.local
AGENT_ALLOW_INSECURE_TRANSPORT=false
```

`AGENT_ALLOW_INSECURE_TRANSPORT=true` solo debe usarse en laboratorio o VPN temporal donde el riesgo este documentado. Por defecto, el agente rechaza HTTP hacia hosts no locales.

## Operacion Del Piloto

1. Crear una base de auditoria dedicada.
2. Ejecutar `alembic upgrade head`.
3. Verificar `/health`; debe reportar `database=ok` y `migration=ok` cuando se exige revision de migracion.
4. Provisionar tokens por dispositivo.
5. Instalar el agente como servicio visible en los equipos autorizados.
6. Confirmar que cada equipo reporta `AGENT_STARTED` y `AGENT_HEARTBEAT`.
7. Ejecutar una prueba controlada de conexion hacia un servicio interno conocido.
8. Consultar `/api/v1/audit/device-movements` y `/api/v1/audit/incident-window`.
9. Revisar que el scheduler registre `AGENT_MISSED_HEARTBEAT` al detener un agente mas alla del timeout.

## Scheduler Y Workers

En `0.1.0-beta.1`, el scheduler de `AGENT_MISSED_HEARTBEAT` vive dentro del lifespan de FastAPI. Si ejecutas varios workers, cada worker arranca su propio scheduler. Para piloto controlado usa un solo worker. Antes de escalar a multiples workers, ejecuta el detector como job singleton externo o servicio separado.

## Retencion Temporal

Para esta beta la retencion sigue siendo politica operativa, no automatizada. Antes del piloto se debe definir:

- Duracion maxima de conservacion.
- Responsable de purga.
- Procedimiento SQL o backup/rotacion.
- Evidencia que debe preservarse fuera de la purga por incidente abierto.

La retencion automatica queda como requisito para una version posterior antes de produccion plena.

## Limites Que Siguen Abiertos

- No hay autenticacion por usuario para auditoria; se usan secretos compartidos fuertes.
- No hay mTLS ni certificados cliente para agentes.
- No hay retencion automatica.
- No hay almacenamiento inalterable/WORM.
- No hay UI; la consulta se hace por API o SQL.
- No captura contenido HTTP/HTTPS ni comandos ejecutados en bases de datos.
