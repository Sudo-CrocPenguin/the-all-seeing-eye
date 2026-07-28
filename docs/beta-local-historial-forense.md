# Beta Local De Historial Forense

## Que Es

Esta beta convierte el MVP en un historial forense local para equipos corporativos autorizados. El objetivo es reconstruir que dispositivos estaban activos, que conexiones salientes realizaron y que eventos del agente ocurrieron alrededor de una marca de tiempo de incidente.

## Para Que Sirve

Sirve para responder preguntas operativas despues de un incidente interno:

- Que equipos reportaron actividad dentro de una ventana exacta.
- Que equipos ya existian, pero no reportaron durante la ventana.
- Que equipos registraron apagado, inicio, heartbeat perdido o recuperacion.
- Que IP, dominio, puerto, proceso y usuario local estuvieron asociados a una conexion.
- Que conexion salio por la IP publica observada por el backend.

La beta no prueba por si sola que un usuario ejecuto una accion destructiva en una base de datos. Si permite reducir el universo de equipos y usuarios que estaban en posicion tecnica de hacerlo.

## Como Funciona

El agente observa conexiones salientes con `psutil.net_connections`, intenta asociarlas al PID local y envia los eventos al backend. Cuando el sistema operativo lo permite, cada conexion queda enriquecida con:

- Usuario local asociado al proceso.
- PID.
- Nombre del proceso.
- Ruta del ejecutable.
- Hostname destino por mapa de servicios o reverse DNS.
- Nombre conocido del servicio interno.

Antes de cada heartbeat y cada scan, el agente refresca la identidad tecnica del equipo. Si cambia la IP local, la interfaz activa o la VPN, vuelve a registrar el dispositivo y deja un evento `AGENT_CONFIG_CHANGED`.

El backend conserva esos campos en `NetworkAuditEvent` y expone una consulta de ventana forense que agrupa:

- Equipos activos dentro de la ventana.
- Equipos sin reporte antes de la ventana.
- Equipos vistos despues de la ventana, sin evidencia directa dentro de ella.
- Eventos de red.
- Eventos de ciclo de vida del agente.

Tambien expone una consulta unificada por equipo en `/api/v1/audit/device-movements`. Esa consulta devuelve conexiones y eventos del agente en una sola linea temporal, lista para revisar “todo lo que hizo el computador” dentro de un rango.

## Mapa Local De Servicios

Para que la app muestre `Base de datos produccion` en vez de solo `10.0.0.25:5432`, el agente puede leer un archivo JSON local configurado con `AGENT_SERVICE_MAP_FILE`.

Formato recomendado:

```json
{
  "services": [
    {
      "name": "Base de datos produccion",
      "destination_ip": "10.0.0.25",
      "destination_port": 5432,
      "destination_host": "db-produccion.local"
    },
    {
      "name": "VPN corporativa",
      "destination_ip": "198.51.100.20",
      "destination_port": 443,
      "destination_host": "vpn.empresa.local"
    }
  ]
}
```

Formato corto tambien soportado:

```json
{
  "10.0.0.25:5432": "Base de datos produccion",
  "198.51.100.20:443": "VPN corporativa"
}
```

Si el archivo configurado no existe, no se puede leer o tiene JSON invalido, el agente continua con un mapa vacio y registra una advertencia. Para redes donde reverse DNS sea lento o poco confiable, se puede desactivar con `AGENT_REVERSE_DNS_ENABLED=false`.

## Variables Del Agente Para Beta

```env
AGENT_BACKEND_URL=https://audit.empresa.local
AGENT_DEVICE_ID=DEV-LAPTOP-042
AGENT_TOKEN=token_provisionado_para_el_equipo
AGENT_TOKEN_HEADER=X-Agent-Token
AGENT_HEARTBEAT_INTERVAL_SECONDS=60
AGENT_SCAN_INTERVAL_SECONDS=10
AGENT_QUEUE_FILE=./agent-queue.jsonl
AGENT_SERVICE_MAP_FILE=./service-map.json
AGENT_REVERSE_DNS_ENABLED=true
AGENT_ALLOW_INSECURE_TRANSPORT=false
```

Para pruebas locales con `http://127.0.0.1:8000` no se requiere override. Si se usa HTTP hacia una IP LAN o VPN temporal, debe configurarse `AGENT_ALLOW_INSECURE_TRANSPORT=true` y documentar el riesgo.

## Variables Del Backend Para Evidencia

```env
TRUSTED_PROXY_IPS=
MISSED_HEARTBEAT_SCHEDULER_ENABLED=true
MISSED_HEARTBEAT_SCHEDULER_INTERVAL_SECONDS=60
```

`TRUSTED_PROXY_IPS` define que proxies pueden aportar headers como `X-Forwarded-For`, `X-Real-IP` o `CF-Connecting-IP`. Si queda vacio, el backend ignora esos headers y toma la IP observada solo desde la conexion entrante cuando es publica.

La evidencia `public_ip` nunca se toma del JSON enviado por el agente. Si el agente reporta una IP publica propia, se conserva aparte como `request_metadata.agent_reported_public_ip` en eventos de red.

## Consulta Por Ventana De Incidente

Consulta directa por rango:

```bash
curl -H "X-Auditor-Token: dev-auditor-token" \
  "http://localhost:8000/api/v1/audit/incident-window?from=2026-07-27T14:00:00-05:00&to=2026-07-27T14:15:00-05:00"
```

Consulta alrededor de una marca exacta:

```bash
curl -H "X-Auditor-Token: dev-auditor-token" \
  "http://localhost:8000/api/v1/audit/incident-window?at=2026-07-27T14:03:00-05:00&window_seconds=900"
```

Estados de equipo en la respuesta:

- `ACTIVE_IN_WINDOW`: el equipo genero evento de red o ciclo de vida dentro de la ventana.
- `WITHOUT_REPORT_BEFORE_WINDOW`: el equipo ya existia, pero su ultimo reporte fue anterior a la ventana.
- `SEEN_AFTER_WINDOW`: el equipo fue visto despues, pero no hay evento directo dentro de la ventana.

Los equipos activos se calculan con una consulta independiente del `limit` de eventos. Puedes pedir pocos eventos para revisar una muestra sin perder el listado completo de dispositivos que estuvieron activos en la ventana.

## Consulta De Todos Los Movimientos De Un Equipo

```bash
curl -H "X-Auditor-Token: dev-auditor-token" \
  "http://localhost:8000/api/v1/audit/device-movements?device_id=DEV-LAPTOP-042&limit=500"
```

Ejemplo de fila:

```json
{
  "occurred_at": "2026-07-28T18:04:59Z",
  "movement_type": "NETWORK_CONNECTION",
  "device_id": "DEV-LAPTOP-042",
  "summary": "Base de datos produccion:5432",
  "local_username": "maria.gomez",
  "process_name": "psql",
  "destination_host": "db-produccion.local",
  "destination_ip": "10.0.0.25",
  "destination_port": 5432,
  "connection_status": "ESTABLISHED"
}
```

La base local tambien crea la vista `device_movements` para revisar el mismo historial directo en SQL.

## Flujo De Prueba En Dispositivo

1. Iniciar el backend local con tokens de desarrollo.
2. Provisionar un token para el equipo de prueba.
3. Crear `service-map.json` con los servicios internos relevantes.
4. Configurar el agente con `AGENT_BACKEND_URL`, `AGENT_DEVICE_ID`, `AGENT_TOKEN` y `AGENT_SERVICE_MAP_FILE`.
5. Ejecutar el agente en el dispositivo.
6. Abrir una conexion controlada, por ejemplo hacia una base de datos o servicio interno de prueba.
7. Consultar `/api/v1/audit/incident-window` alrededor de la hora de la prueba.
8. Validar que aparezcan equipo, usuario local, proceso, destino, servicio y eventos de ciclo de vida.

## Limites De La Beta

- La persistencia sigue siendo local para esta etapa.
- La asociacion proceso-conexion depende de permisos del sistema operativo.
- Reverse DNS puede no resolver todos los destinos.
- No se captura pantalla, teclado ni contenido HTTP/HTTPS.
- La proteccion inalterable de evidencia queda para el despliegue real con base separada y backups protegidos.
