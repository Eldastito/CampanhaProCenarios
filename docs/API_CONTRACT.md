# API Contract — FORGE <> Scenario Lab

## Princípios
- comunicação server-to-server
- autenticação por token/chave
- payloads versionados
- idempotência por request_id
- rastreabilidade por source_system e timestamp

## Endpoints iniciais

### POST /api/v1/forge/ingest/events
Recebe eventos operacionais e pedagógicos.

Payload base:
```json
{
  "request_id": "uuid",
  "source_system": "campanhapro",
  "organization_id": "org_123",
  "event_type": "student_engagement.updated",
  "occurred_at": "2026-04-04T12:00:00Z",
  "payload_version": "1.0",
  "payload": {}
}
```

### POST /api/v1/forge/ingest/snapshots
Recebe snapshots agregados por período, escola ou rede.

### POST /api/v1/scenarios
Cria cenário.

### POST /api/v1/scenarios/{id}/run
Executa cenário.

### GET /api/v1/scenarios/{id}/results
Retorna resultados do cenário.

### POST /api/v1/predictions/acceptance
Gera estimativa de aceitação.

### POST /api/v1/predictions/evasion-risk
Gera estimativa de risco de evasão.

### POST /api/v1/reports/generate
Gera relatório executivo.

## Regras mínimas
- toda ingestão deve ser auditável
- toda previsão deve retornar confiança
- toda simulação deve ser identificada como simulação
