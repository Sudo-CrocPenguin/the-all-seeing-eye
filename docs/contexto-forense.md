# Contexto Forense De La Aplicacion

## Que Es

The All Seeing Eye es una plataforma de historial forense de actividad online para equipos corporativos autorizados. Su proposito es mantener evidencia tecnica por dispositivo para reconstruir que equipos estaban activos, que conexiones realizaron y que cambios de estado ocurrieron alrededor de una marca de tiempo de incidente.

## Para Que Sirve

La aplicacion nace de un incidente en el que una persona con acceso interno borro una base de datos y su backup. El unico rastro disponible fue la IP publica del router corporativo, por lo que la investigacion no pudo distinguir con precision que dispositivo oficial realizo la accion.

El sistema busca que, si vuelve a ocurrir un evento similar, el equipo responsable pueda revisar:

- Que equipos estaban activos a una hora exacta.
- Que equipos dejaron de reportar antes, durante o despues del incidente.
- Que equipo se apago, reinicio o recupero cerca de la marca de tiempo.
- Que conexiones salientes hizo cada equipo.
- A que IP, dominio o servicio se conecto cada equipo.
- Desde que IP publica salio la actividad.
- Que usuario local o dispositivo estaba asociado a la actividad cuando sea posible.

## Como Funciona

Cada equipo corporativo ejecuta un agente visible y administrado por IT. El agente identifica el dispositivo, obtiene datos tecnicos del sistema y reporta:

- Registro del dispositivo.
- Heartbeats periodicos.
- Inicio y apagado controlado del agente.
- Conexiones salientes observadas.
- Cola local de eventos cuando el backend no responde.

El backend central recibe eventos autenticados, los valida, los guarda en PostgreSQL local y permite consultas protegidas por token de auditoria.

## Tipo De Evidencia Esperada

La aplicacion no busca capturar pantalla, teclado ni contenido personal. La evidencia esperada es tecnica y orientada a reconstruccion temporal.

Ejemplo de evidencia objetivo:

```text
A las 14:03, el equipo DEV-LAPTOP-042, usuario maria.gomez, activo en red,
desde la IP publica 203.0.113.10, abrio una conexion hacia
db-produccion:5432. Cinco minutos despues el agente dejo de reportar.
```

Este tipo de registro no prueba por si solo que una persona ejecuto un comando destructivo, pero reduce el universo de equipos y usuarios que estaban en posicion tecnica de hacerlo.

## Alcance Beta

Para la beta local, el sistema debe permitir:

- Provisionar un agente con token.
- Ejecutar backend y base de datos local.
- Ejecutar el agente en el dispositivo de prueba.
- Registrar usuario local, proceso, PID y destino enriquecido cuando el sistema operativo lo permita.
- Definir un mapa local de servicios internos, por ejemplo `10.0.0.25:5432 = Base de datos produccion`.
- Consultar una ventana de incidente con equipos activos, equipos sin reporte, eventos de ciclo de vida y conexiones salientes.

## Fuera De Alcance Inicial

- Captura de pantalla.
- Keylogger.
- Captura de contenido HTTP/HTTPS.
- Lectura de archivos personales.
- Inspeccion TLS sin proxy corporativo autorizado.
- Atribucion legal definitiva sin correlacion con otras fuentes.

## Proteccion De La Evidencia

Para beta se mantiene persistencia local. Para despliegue real, la base de auditoria debe vivir separada de los sistemas auditados, con backups protegidos y acceso restringido. Si la evidencia queda en la misma superficie que los sistemas productivos, un atacante interno podria intentar borrar tambien el historial.
