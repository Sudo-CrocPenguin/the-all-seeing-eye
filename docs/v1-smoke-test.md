# Smoke Test V1

Este checklist valida el flujo operativo completo despues de desplegar V1.

## Variables

```text
BACKEND_URL=https://audit.example.com
PROVISIONING_TOKEN=<secreto>
AGENT_TOKEN=<token-del-agente>
AUDITOR_DEVICE_ID=device-auditor
WORKER_DEVICE_ID=device-worker
COMPANY_ID=<se-completa-durante-la-prueba>
```

## Checklist

1. Verificar health:

```bash
curl -fsS "$BACKEND_URL/health"
```

2. Crear empresa:

```bash
ase-auditor --backend-url "$BACKEND_URL" company create \
  --name "Acme Auditoria" \
  --phone "+573001112233"
```

3. Provisionar y registrar dispositivo auditor.

4. Solicitar acceso auditor:

```bash
AUDITOR_BACKEND_URL="$BACKEND_URL" \
AUDITOR_DEVICE_ID="$AUDITOR_DEVICE_ID" \
AUDITOR_AGENT_TOKEN="$AGENT_TOKEN" \
ase-auditor access request --company "$COMPANY_ID"
```

5. Verificar OTP recibido por SMS:

```bash
ase-auditor access verify \
  --company "$COMPANY_ID" \
  --request "$AUDITOR_ACCESS_REQUEST_ID" \
  --code "$SMS_CODE"
```

6. Generar codigo de vinculacion:

```bash
ase-auditor enrollment-code create --ttl-seconds 3600 --max-uses 1
```

7. Vincular agente desde el dispositivo:

```bash
all-seeing-eye-agent link --code "$ENROLLMENT_CODE"
```

8. Aprobar solicitud:

```bash
ase-auditor enrollment-requests list --status PENDING
ase-auditor enrollment-requests approve --request "$ENROLLMENT_REQUEST_ID"
```

9. Seleccionar empresa activa e iniciar registro:

```bash
all-seeing-eye-agent companies
all-seeing-eye-agent use-company --company "$COMPANY_ID"
all-seeing-eye-agent start-recording
all-seeing-eye-agent run-once
```

10. Consultar resumen e historial:

```bash
ase-auditor summary
ase-auditor history network --from "$FROM" --to "$TO" --device-id "$WORKER_DEVICE_ID"
ase-auditor history lifecycle --from "$FROM" --to "$TO" --device-id "$WORKER_DEVICE_ID"
ase-auditor history incident-window --from "$FROM" --to "$TO"
```

11. Exportar JSON:

```bash
ase-auditor export-json \
  --from "$FROM" \
  --to "$TO" \
  --device-id "$WORKER_DEVICE_ID" \
  --output evidence.json
```

Validar que `evidence.json` contiene `format_version=audit-export/v1`, `company_id` correcto y no contiene `auditor_session_id`.

12. Probar aislamiento multiempresa:

- Crear empresa B.
- Crear sesion auditor para B.
- Consultar/exportar desde auditor A y B.
- Confirmar que auditor A no ve ni exporta eventos de B.

13. Probar cola offline:

- Cortar conexion al backend.
- Ejecutar `all-seeing-eye-agent run-once`.
- Confirmar que crece `AGENT_QUEUE_FILE`.
- Restaurar conexion.
- Ejecutar `all-seeing-eye-agent run-once`.
- Confirmar que la cola baja y los eventos suben con el `company_id` original.

14. Revocar vinculo:

```bash
all-seeing-eye-agent unlink --company "$COMPANY_ID"
```

Confirmar:

- La empresa no recibe eventos nuevos con ese vinculo.
- El historial anterior sigue consultable por auditor autorizado.

15. Prueba Windows/Linux:

- Linux: systemd registra `AGENT_STOPPING` y `AGENT_STOPPED` al detener servicio.
- Windows: Windows Service registra apagado controlado con `Stop-Service`.
