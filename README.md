# The All Seeing Eye

The All Seeing Eye es una plataforma de auditoria de red para computadores corporativos de equipos de desarrollo. Su objetivo es registrar actividad de red autorizada, centralizar evidencia tecnica y facilitar revisiones de seguridad cuando se necesite investigar un equipo, una IP, un rango de fechas o un posible incidente interno.

El sistema esta pensado para ambientes empresariales donde los empleados son informados de la auditoria y los equipos pertenecen a la compania. No esta disenado para monitoreo oculto, evasion de controles del sistema operativo ni captura no consentida de informacion personal.

## Para Que Sirve

- Auditar actividad de red de equipos corporativos Windows y Linux.
- Registrar hora, fecha, dispositivo, IP local, IP publica y conexiones realizadas.
- Asociar eventos tecnicos a un equipo especifico sin depender inicialmente de login de usuario.
- Consultar historicos por fecha, dispositivo, IP local, IP publica, dominio, IP destino, puerto o protocolo.
- Detectar periodos en los que el agente dejo de reportar, fue detenido o volvio a iniciar.
- Centralizar evidencias en una base de datos externa para revision de seguridad.
- Servir como base para controles corporativos mas completos mediante proxy o VPN.

## Alcance De Auditoria

El MVP debe capturar metadatos de red con la mayor precision posible desde cada equipo:

- Fecha y hora del evento.
- Identificador del dispositivo.
- Hostname.
- Sistema operativo.
- Version del agente.
- IP local.
- IP publica observada por el backend.
- Interfaces de red disponibles.
- MAC address de interfaces activas.
- Dominio destino cuando este disponible.
- IP destino.
- Puerto destino.
- Protocolo.
- Metodo HTTP cuando este disponible.
- Status code cuando este disponible.
- Bytes enviados.
- Bytes recibidos.
- Estado del agente.

La captura de contenido completo de solicitudes y respuestas requiere un componente adicional de proxy corporativo con inspeccion TLS autorizada. Esta capacidad debe implementarse con controles de seguridad, politicas internas claras y redaccion automatica de secretos.

## Arquitectura General

La arquitectura recomendada es hibrida:

1. Agente por equipo.
2. Backend central.
3. Base de datos externa.
4. Proxy o VPN corporativo para captura HTTP/HTTPS avanzada.

### Agente

El agente corre como servicio en segundo plano en equipos Windows y Linux. Su responsabilidad es recolectar telemetria tecnica del dispositivo y enviarla al backend.

Responsabilidades principales:

- Identificar el equipo.
- Capturar IP local e interfaces de red.
- Obtener o reportar IP publica mediante el backend.
- Registrar conexiones salientes.
- Medir bytes enviados y recibidos cuando el sistema operativo lo permita.
- Enviar eventos de auditoria al backend.
- Mantener una cola local temporal cuando no haya conexion.
- Reportar eventos de vida del servicio.

El agente no debe intentar ocultarse del sistema operativo. Debe instalarse como servicio corporativo administrado por IT.

### Backend

El backend central recibe eventos del agente, los valida, los persiste y expone consultas para auditoria.

Responsabilidades principales:

- Registrar dispositivos autorizados.
- Autenticar agentes mediante token, certificado o mTLS.
- Recibir eventos de red.
- Recibir heartbeats del agente.
- Detectar ausencias de telemetria.
- Guardar registros en base de datos externa.
- Consultar historicos por filtros de auditoria.
- Exportar datos en formatos operativos como JSON o CSV.

### Base De Datos

La base de datos recomendada es PostgreSQL. Para alto volumen de eventos se puede evaluar TimescaleDB.

Entidades iniciales:

- Device.
- NetworkAuditEvent.
- AgentLifecycleEvent.
- NetworkInterface.
- PublicIpObservation.
- AuditQuery.

### Proxy O VPN Corporativo

Para obtener metodo HTTP, status code, headers y contenido de solicitudes/respuestas HTTPS, el trafico debe pasar por un proxy o VPN corporativo autorizado.

Este componente debe:

- Usar certificados corporativos instalados por IT.
- Documentar claramente el alcance de inspeccion TLS.
- Excluir dominios sensibles cuando aplique.
- Redactar automaticamente credenciales y secretos.
- Evitar almacenar tokens, passwords, cookies de sesion o llaves privadas en claro.

## Eventos Del Agente

El sistema debe registrar el ciclo de vida del agente para detectar apagados, reinicios o interrupciones.

Eventos principales:

- AGENT_STARTED: el servicio inicio correctamente.
- AGENT_STOPPING: el servicio comenzo apagado controlado.
- AGENT_STOPPED: el servicio se apago correctamente.
- AGENT_HEARTBEAT: el servicio sigue activo.
- AGENT_MISSED_HEARTBEAT: el backend detecto que el agente dejo de reportar.
- AGENT_RECOVERED: el agente volvio a reportar despues de una ausencia.
- AGENT_CONFIG_CHANGED: cambio una configuracion del agente.

El backend debe calcular ventanas de inactividad cuando un agente deje de enviar heartbeats.

Ejemplo:

```json
{
  "device_id": "DEV-LAPTOP-042",
  "event_type": "AGENT_MISSED_HEARTBEAT",
  "last_seen_at": "2026-07-27T14:20:00-05:00",
  "detected_at": "2026-07-27T14:23:00-05:00",
  "downtime_seconds": 180
}
```

## Consultas De Auditoria

El sistema debe permitir consultas como:

- Eventos por dispositivo.
- Eventos por IP local.
- Eventos por IP publica.
- Eventos por rango de fechas.
- Eventos por dominio destino.
- Eventos por IP destino.
- Eventos por puerto o protocolo.
- Historial de encendido, apagado y recuperacion del agente.
- Ventanas de tiempo sin reporte.
- Resumen diario por equipo.

## Stack Propuesto

No se debe usar npm en este proyecto.

Stack recomendado:

- Backend: Python con FastAPI.
- Base de datos: PostgreSQL.
- ORM y migraciones: SQLAlchemy y Alembic.
- Agente MVP: Python.
- Agente futuro: Go o Rust si se requiere binario mas robusto.
- Contenedores locales: Docker Compose.
- Pruebas: pytest.
- Formato y calidad: Ruff, mypy y herramientas equivalentes.

Si en algun momento se requiere frontend, se debe usar pnpm como gestor de paquetes.

## Arquitectura De Codigo

El proyecto debe seguir una arquitectura modular basada en DDD y POO cuando aplique.

Estructura objetivo:

```text
backend/
  src/
    audit/
      domain/
      application/
      infrastructure/
      presentation/
    devices/
      domain/
      application/
      infrastructure/
      presentation/
    shared/
  tests/
  docs/

agent/
  src/
    collector/
    device_identity/
    network/
    transport/
    lifecycle/
    config/
  tests/
  docs/
```

## Primer Paso De Desarrollo

El primer incremento debe crear la base del backend:

- Proyecto FastAPI modular.
- Configuracion de PostgreSQL.
- Modelo inicial de dispositivos.
- Modelo inicial de eventos de auditoria de red.
- Modelo inicial de eventos de ciclo de vida del agente.
- Endpoint de health check.
- Endpoint de ingesta de eventos.
- Documentacion tecnica minima.
- Pruebas iniciales de dominio y API.

## GitFlow

El desarrollo debe seguir GitFlow:

- main: codigo estable de produccion.
- develop: integracion de cambios.
- feature/*: nuevas funcionalidades.
- bugfix/*: correcciones sobre develop.
- refactor/*: cambios internos sin alterar comportamiento.
- chore/*: mantenimiento.
- docs/*: documentacion.
- release/*: preparacion de version.
- hotfix/*: correcciones urgentes desde main.

Los commits deben ser progresivos, especificos y escritos en espanol con prefijos convencionales:

- feat:
- fix:
- docs:
- refactor:
- chore:
- test:
- style:
- perf:
- ci:

## Seguridad Y Privacidad

La plataforma debe implementar controles de proteccion desde el inicio:

- Auditoria solo en equipos corporativos autorizados.
- Comunicacion cifrada entre agente y backend.
- Autenticacion fuerte del agente.
- Redaccion de datos sensibles antes de persistir contenido HTTP.
- Retencion configurable de datos.
- Trazabilidad de cambios de configuracion.
- Separacion entre metadatos de red y contenido completo.
- Documentacion clara para empleados y administradores.

## Estado Actual

El proyecto se encuentra en etapa de MVP. La API cuenta con modelos de dominio, repositorios SQLAlchemy, migraciones Alembic, persistencia PostgreSQL configurada y autenticacion por token para agentes. El backend actualiza `last_seen_at` cuando recibe senales validas de agentes autenticados. El agente MVP puede identificar el equipo, reportar ciclo de vida, enviar conexiones salientes basicas y desplegarse como servicio administrado en Linux/Windows.

## Despliegue Del Agente Como Servicio

El agente esta preparado para ejecutarse en segundo plano como servicio corporativo visible y administrable por IT. Esta capacidad sirve para que el proceso arranque con el sistema operativo, se reinicie ante fallos y registre eventos de apagado/encendido cuando el servicio se detiene de forma controlada.

En Linux se usa systemd:

```bash
sudo agent/deploy/linux/install-systemd.sh
sudo systemctl status all-seeing-eye-agent
sudo systemctl stop all-seeing-eye-agent
sudo systemctl start all-seeing-eye-agent
```

La configuracion queda en:

```text
/etc/the-all-seeing-eye/agent.env
```

En Windows se usa Windows Service con `pywin32`:

```powershell
.\agent\deploy\windows\install-service.ps1 -BackendUrl "http://backend:8000" -AgentToken "token"
Get-Service -Name AllSeeingEyeAgent
Stop-Service -Name AllSeeingEyeAgent
Start-Service -Name AllSeeingEyeAgent
```

La configuracion queda en:

```text
C:\ProgramData\TheAllSeeingEye\agent.env
```

Cuando el servicio se detiene con `systemctl stop`, `Stop-Service` o la consola de servicios de Windows, el agente envia `AGENT_STOPPING` y `AGENT_STOPPED`. Cuando vuelve a iniciar envia `AGENT_STARTED`. Si el proceso es terminado de forma forzada o el equipo pierde red/energia, el backend debe detectar la ventana sin reporte mediante heartbeats ausentes.

## Documentacion Tecnica

- [Backend de auditoria](backend/docs/backend.md)
- [Agente MVP de auditoria](agent/docs/agent.md)
