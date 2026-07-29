# Diseno De Autenticacion Multiempresa Por Terminal

## Proposito

Este documento registra la idea de autenticacion y autorizacion para convertir The All
Seeing Eye en una plataforma multiempresa de auditoria por terminal.

El objetivo es que cualquier persona pueda crear una empresa auditora para su propio
negocio, vincular dispositivos autorizados, registrar actividad tecnica de red para una
empresa activa y permitir auditorias temporales desde CLI.

La aplicacion debe poder ser usada por personas y tambien por herramientas de terminal
como Codex, siempre bajo una sesion autorizada y auditable.

## Principios

- El sistema no debe depender de credenciales internas del sistema operativo que se
  intenten extraer del computador.
- No existe un identificador fisico que nunca cambie; por eso el sistema debe crear su
  propia identidad estable al instalarse.
- Un dispositivo puede estar vinculado a varias empresas, pero solo puede registrar
  actividad para una empresa activa a la vez.
- La desvinculacion de una empresa no borra los eventos historicos.
- Los accesos de auditor son temporales, trazables y revocables.
- El agente debe seguir guardando eventos localmente si pierde internet y subirlos al
  recuperar conexion.
- La interfaz del dispositivo debe ser simple: mostrar estado, empresa activa y acciones
  basicas.
- Toda consulta o exportacion de auditoria debe quedar registrada.

## Identidad Del Dispositivo

El dispositivo debe tener una identidad creada por el sistema durante la instalacion o
primer arranque.

Campos recomendados:

```text
device_id
device_secret_hash
device_public_key
device_private_key_path
created_at
last_seen_at
fingerprint_metadata
```

`device_id` debe ser un UUID o identificador aleatorio fuerte generado por la aplicacion.
Debe persistirse en un archivo local protegido, por ejemplo:

```text
/etc/the-all-seeing-eye/device-id
C:\ProgramData\TheAllSeeingEye\device-id
```

El fingerprint del computador no debe ser la autenticacion principal. Puede usarse como
senal auxiliar para detectar cambios sospechosos.

Datos utiles de fingerprint:

- hostname
- machine-id o MachineGuid
- MAC principal
- interfaces activas
- sistema operativo
- version del agente

Estos datos pueden cambiar, por eso no deben ser la unica prueba de identidad.

## Empresa Auditora

Cualquier persona puede crear una empresa auditora para registrar los eventos de su propio
negocio.

Campos recomendados:

```text
company_id
name
phone_number
created_at
status
```

`company_id` es estable y no cambia. No debe funcionar como secreto.

Para permitir que dispositivos soliciten vincularse, la empresa debe generar codigos de
vinculacion temporales.

Campos recomendados para codigo de vinculacion:

```text
enrollment_code_id
company_id
code_hash
expires_at
max_uses
used_count
revoked_at
created_by_auditor_session_id
```

El codigo de vinculacion no debe ser permanente. Si se filtra, la empresa debe poder
rotarlo o revocarlo.

## Vinculacion Empresa-Dispositivo

Un dispositivo usa un codigo de vinculacion para solicitar registro en una empresa.

Flujo:

```text
1. La empresa genera un codigo de vinculacion.
2. El dispositivo ingresa el codigo desde terminal.
3. El backend crea una solicitud pendiente.
4. Un auditor activo acepta o deniega la solicitud.
5. Si se acepta, se crea la vinculacion empresa-dispositivo.
6. El dispositivo puede seleccionar esa empresa como empresa activa.
```

Solo un auditor puede aceptar o denegar dispositivos.

Campos recomendados para solicitud:

```text
enrollment_request_id
company_id
device_id
requested_at
status = PENDING | ACCEPTED | DENIED | CANCELLED
reviewed_by_auditor_session_id
reviewed_at
device_fingerprint_snapshot
```

Campos recomendados para la vinculacion:

```text
company_device_link_id
company_id
device_id
status = ACTIVE | PAUSED | REVOKED
linked_at
revoked_at
revoked_by_device
revoked_by_auditor_session_id
```

Un dispositivo puede tener varias vinculaciones activas con distintas empresas, pero solo
una empresa puede estar seleccionada para registrar eventos en un momento dado.

## Empresa Activa De Registro

El dispositivo debe mantener una sola empresa activa para captura.

Campos locales recomendados:

```text
active_company_id
active_company_device_link_id
recording_enabled
```

Si el usuario cambia la empresa activa, el sistema debe registrar un evento de ciclo de
vida o configuracion.

Evento recomendado:

```text
AGENT_ACTIVE_COMPANY_CHANGED
```

Mientras `recording_enabled=true`, todos los eventos capturados se asocian a:

```text
company_id
device_id
company_device_link_id
occurred_at
```

Esto conserva la propiedad historica de los eventos aunque luego se desvincule el
dispositivo.

## Desvinculacion

El dispositivo puede desvincularse libremente de una empresa.

La desvinculacion no elimina metadatos ni eventos historicos. Solo cambia el estado de la
vinculacion.

Flujo:

```text
1. El usuario selecciona desvincular empresa.
2. Se registra evento local y remoto de desvinculacion.
3. La vinculacion cambia a REVOKED.
4. La empresa recibe un aviso.
5. Los eventos anteriores siguen consultables por auditores autorizados de esa empresa.
```

Evento recomendado:

```text
DEVICE_UNLINKED_FROM_COMPANY
```

Si no hay internet, la notificacion de desvinculacion debe quedar en la cola local y subir
cuando vuelva la conexion.

## Estados Del Dispositivo

La aplicacion local del dispositivo debe mostrar un estado simple.

Estados principales:

```text
REGISTRANDO
APAGADO
SIN_CONEXION
PENDIENTE_DE_VINCULACION
SIN_EMPRESA_ACTIVA
```

Acciones principales:

```text
1. Establecer conexion
2. Comenzar a registrar
3. Apagar registro
4. Desvincular empresa
5. Solicitar acceso de auditor
6. Salir
```

Al apagar registro, solo se detiene la captura de red. La aplicacion puede seguir abierta.

Al salir, primero debe reportar el apagado controlado y luego cerrar.

Eventos recomendados:

```text
AGENT_STARTED
AGENT_RECORDING_STARTED
AGENT_RECORDING_STOPPING
AGENT_RECORDING_STOPPED
AGENT_STOPPING
AGENT_STOPPED
AGENT_CONFIG_CHANGED
AGENT_MISSED_HEARTBEAT
AGENT_RECOVERED
```

## Cola Local Offline

Si el computador queda sin internet, el agente debe seguir registrando eventos localmente.

La cola local debe conservar:

```text
path
payload
company_id
company_device_link_id
queued_at
retry_count
```

Al recuperar conexion, debe subir los eventos pendientes a la empresa asociada al momento
de captura, no necesariamente a la empresa activa actual.

Esto es importante para conservar evidencia historica correcta cuando el usuario cambia
de empresa activa mientras estuvo sin conexion.

## Auditores

Una empresa puede tener varios auditores.

Un auditor no necesariamente es una persona con usuario permanente. En esta etapa, un
dispositivo puede solicitar acceso temporal de auditor y, si la empresa lo autoriza por
SMS, obtiene una sesion valida por 12 horas.

Solo auditores con sesion activa pueden:

- aceptar dispositivos
- denegar dispositivos
- consultar historiales
- ver resumen de empresa
- exportar datos JSON

Campos recomendados para sesion de auditor:

```text
auditor_session_id
company_id
device_id
created_at
expires_at
revoked_at
scopes
```

Scopes iniciales:

```text
company:read
devices:read
devices:approve
audit:read
audit:export_json
```

## Solicitud De Auditor Por SMS

El acceso de auditor se verifica con un codigo SMS enviado al numero telefonico registrado
de la empresa.

Flujo:

```text
1. Un dispositivo solicita acceso de auditor para una empresa.
2. El backend genera un codigo OTP.
3. El codigo se envia por SMS al telefono registrado de la empresa.
4. Si la empresa decide dar acceso, entrega el codigo al operador del dispositivo.
5. El operador ingresa el codigo en la terminal.
6. Si el codigo es correcto, el backend crea una sesion de auditor por 12 horas.
7. Al vencer la sesion, las herramientas de auditor dejan de funcionar.
```

Campos recomendados para solicitud:

```text
auditor_access_request_id
company_id
device_id
otp_hash
requested_at
expires_at
verified_at
auditor_session_id
failed_attempts
status = PENDING | VERIFIED | EXPIRED | DENIED
```

Controles recomendados:

- OTP con expiracion corta, por ejemplo 5 a 10 minutos.
- limite de intentos fallidos.
- bloqueo temporal por abuso.
- registro de IP publica observada por backend.
- registro del dispositivo solicitante.

## Uso Por Codex U Otra IA Desde Terminal

La IA no es auditor como entidad propia.

La regla es:

```text
Codex no tiene permisos permanentes.
Codex solo puede usar comandos de auditor si corre en un dispositivo con sesion de auditor activa.
```

Ejemplo:

```bash
ase auditor solicitar-acceso --empresa <company_id>
ase auditor verificar-sms --empresa <company_id> --codigo 123456
ase auditor resumen --empresa <company_id>
ase auditor historial --empresa <company_id> --desde 2026-07-29T00:00:00Z --hasta 2026-07-29T23:59:59Z
ase auditor exportar-json --empresa <company_id> --desde ... --hasta ...
```

Todo comando ejecutado por Codex debe quedar registrado igual que si lo ejecutara un
humano.

Campos recomendados para log de comandos:

```text
audit_command_log_id
company_id
auditor_session_id
device_id
command_name
arguments_summary
executed_at
result_status
export_file_id
```

## Menu De Terminal

### Menu Local Del Dispositivo

```text
The All Seeing Eye

Estado: REGISTRANDO
Empresa activa: Acme S.A.
Dispositivo: lenovo-book

1. Establecer conexion
2. Comenzar a registrar
3. Apagar registro
4. Desvincular empresa
5. Solicitar acceso de auditor
6. Salir
```

### Menu De Auditor

```text
Auditoria De Empresa

Empresa: Acme S.A.
Sesion expira: 2026-07-29 18:00:00 UTC

1. Ver resumen
2. Ver dispositivos registrados
3. Ver dispositivos conectados
4. Ver dispositivos apagados o sin reporte
5. Revisar solicitudes pendientes
6. Aceptar dispositivo
7. Denegar dispositivo
8. Auditar historial por rango de fechas
9. Buscar conexiones
10. Exportar JSON
11. Cerrar sesion
```

## Resumen De Empresa Para Auditores

El auditor debe poder ver:

```text
company_id
nombre
dispositivos vinculados
dispositivos registrando
dispositivos apagados
dispositivos sin reporte
solicitudes pendientes
ultima actividad
```

## Auditoria Por Rango De Fechas

El auditor debe poder consultar desde terminal:

```text
desde
hasta
device_id opcional
local_ip opcional
public_ip opcional
destination_ip opcional
destination_host opcional
process_name opcional
local_username opcional
```

La salida debe poder mostrarse en tabla resumida o exportarse como JSON.

Ejemplo:

```bash
ase auditor historial \
  --empresa acme \
  --desde 2026-07-29T00:00:00Z \
  --hasta 2026-07-29T23:59:59Z \
  --json
```

## Conservacion Historica

La regla principal:

```text
Los eventos pertenecen a la empresa activa en el momento de captura.
```

Por eso cada evento debe guardar `company_id` y `company_device_link_id`.

Si un dispositivo se desvincula, la empresa pierde la capacidad de recibir eventos nuevos
de ese dispositivo, pero conserva acceso a los eventos historicos capturados mientras la
vinculacion estaba activa.

## Riesgos Y Decisiones Abiertas

- Definir si el primer auditor de una empresa se crea automaticamente al crear la empresa
  o si requiere verificacion inicial.
- Definir proveedor SMS.
- Definir tiempo de expiracion del OTP.
- Definir si una sesion de auditor puede renovarse o siempre requiere nuevo SMS.
- Definir si el dispositivo puede cambiar empresa activa sin confirmacion adicional.
- Definir si el usuario local puede apagar registro aunque la empresa quiera monitoreo
  continuo.
- Definir politica de retencion de eventos.
- Definir cifrado y limite de tamano de la cola local.
- Definir si se usaran tokens compartidos, llaves asimetricas o mTLS para dispositivos.

## Recomendacion De Implementacion

Implementar por fases:

```text
Fase 1: empresas, device_id persistente, vinculacion y empresa activa.
Fase 2: solicitudes de vinculacion aceptadas por auditor.
Fase 3: sesiones temporales de auditor por OTP/SMS.
Fase 4: menu CLI de dispositivo y auditor.
Fase 5: cola local con company_id historico.
Fase 6: exportacion JSON y log de comandos de auditor.
Fase 7: hardening: llaves de dispositivo, rotacion, limites, retencion y alertas.
```

## Estado Implementado Inicial

La primera implementacion de backend cubre:

```text
Company
EnrollmentCode
EnrollmentRequest
CompanyDeviceLink
AuditorAccessRequest
AuditorSession
```

Tambien expone endpoints para crear empresas, solicitar y verificar acceso auditor,
generar codigos de vinculacion, solicitar vinculacion de dispositivos, revisar solicitudes,
consultar resumen de empresa, listar vinculos del dispositivo, revocar vinculos desde el
agente y consultar eventos de auditoria filtrados por sesion de empresa.

Los eventos de red y ciclo de vida ya guardan `company_id` y
`company_device_link_id`. El backend valida que el vinculo este activo al ingerir eventos
nuevos y conserva los eventos historicos aunque el vinculo se revoque despues.

El agente ya cuenta con estado local multiempresa en `agent-state.json` y comandos de
terminal para sincronizar empresas, seleccionar empresa activa, encender/apagar registro
de red, solicitar vinculacion, desvincular empresas y ejecutar el runner.

Pendiente para siguientes iteraciones:

- menu terminal de auditor
- exportacion JSON de auditor
- proveedor real de SMS
