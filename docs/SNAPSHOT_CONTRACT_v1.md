# Snapshot Contract `campanhapro.snapshot.v1`

**Status:** vigente
**Origem:** PRD CampanhaProCenarios v2 — Fase 1
**Endpoint:** `POST /api/v1/campanhapro/ingest/snapshots`
**Autenticação:** header `X-CampanhaPro-Secret` (segredo combinado server-to-server)
**Idempotência:** `snapshotId` é usado como `request_id` no Cenários — duplicatas são aceitas como no-op.
**Resposta:** `202 Accepted` com `{ status, request_id, detail }`. O processamento posterior (mapper de fatores, dossiê) acontece em worker — ver Fase 2.

Este documento descreve o **contrato oficial v1** que o backend Express do CampanhaPro deve montar para enviar dados ao Cenários. O lado Cenários aceita simultaneamente o formato legado (sem `schemaVersion`, baseado em `snapshot_type`) e este formato v1; a presença do campo `schemaVersion = "campanhapro.snapshot.v1"` é o discriminador.

---

## 1. Envelope

```json
{
  "schemaVersion": "campanhapro.snapshot.v1",
  "snapshotId": "uuid-v4",
  "campaignId": "string",
  "organizationId": "string",
  "generatedAt": "ISO-8601 UTC",
  "source": "campanhapro-web",
  "actor": {
    "userId": "string",
    "role": "Admin | Candidato | Líder | Apoiador | Colaborador | Pesquisador"
  },
  "campaign": {
    "details": { ... },
    "settings": { ... },
    "configs": { ... }
  },
  "data": { ... },
  "privacyOptions": { ... },
  "metrics": { ... }
}
```

### Campos obrigatórios
- `schemaVersion` — string fixa `"campanhapro.snapshot.v1"`.
- `snapshotId` — UUID v4 gerado pelo CampanhaPro. Vira `request_id` no Cenários (chave de idempotência).
- `campaignId` — id externo da campanha. **Crítico**: o Cenários usa para escopar todos os dados (snapshots, dossiês, fatores, relatórios). Múltiplos snapshots para a mesma campanha são esperados ao longo do tempo.
- `organizationId` — id da organização (tenant).
- `generatedAt` — ISO-8601 UTC do momento da geração do snapshot.

### Campos recomendados
- `source` — string que identifica a origem (`campanhapro-web`, `campanhapro-cron`, etc).
- `actor` — quem gerou o envio (auditoria).

---

## 2. `campaign`

Metadados da campanha. Campos abaixo são extraídos de `settings` do CampanhaPro (que já são `camelCase`).

### 2.1 `campaign.details`

| Campo | Tipo | Origem CampanhaPro |
|---|---|---|
| `nomeUrna` | string | `settings.nomeUrna` |
| `partido` | string | `settings.partido` |
| `office` | string | `settings.cargo` — valores aceitos: `"Prefeito"`, `"Vereador"`, `"Deputado Estadual"`, `"Deputado Federal"`, `"Governador"`, `"Senador"`, `"Presidente"` |
| `municipio` | string \| null | `settings.municipio` |
| `uf` | string(2) \| null | `settings.uf` |
| `candidatePhotoUrl` | string \| null | `settings.candidatePhotoUrl` |
| `headerLogo` | string \| null | `settings.headerLogo` (url pública ou data URI) |
| `footerLogo` | string \| null | `settings.footerLogo` |

### 2.2 `campaign.settings` e `campaign.configs`

Espelham `settings` e `campaign_configs` do Supabase, **filtrados por `campaignId`**. Mantidos em `camelCase` exatamente como no CampanhaPro. Devem omitir chaves vazias para reduzir payload.

---

## 3. `data`

Listas escopadas por `campaignId`. **Toda chave abaixo é obrigatória** — quando vazia, enviar array `[]` (não omitir).

```json
"data": {
  "visits": [...],
  "pesquisa": [...],
  "engagementActions": [...],
  "teamMembers": [...],
  "locations": [...],
  "financial": {
    "incomes": [...],
    "expenses": [...]
  },
  "calculatorSettings": {...},
  "scenarios": [...],
  "streetReports": [...],
  "agentOutputs": [...],
  "fieldTickets": [...],
  "neighborhoodFlags": [...],
  "contentBriefs": [...],
  "aiUsage": [...]
}
```

### Tabelas excluídas do snapshot v1

Estas não trazem valor analítico para o Cenários e ficam fora intencionalmente:
- `backups` — operacional do CampanhaPro.
- `users` — informação interna de tenant; o Cenários só precisa do `actor` da requisição.
- `platform_stats` — métrica do CampanhaPro, não da campanha.

### 3.1 `data.visits[]`

Visitas porta a porta registradas no CampanhaPro.

| Campo | Tipo | Sempre enviado? | Notas |
|---|---|---|---|
| `id` | string | sim | id do registro no CampanhaPro |
| `data` | ISO-8601 | sim | data da visita |
| `bairro` | string \| null | sim | |
| `endereco` | string \| null | sim | logradouro/numero, mascarado se PII off |
| `lat` | number \| null | sim | |
| `lng` | number \| null | sim | |
| `interesseDeclarado` | string \| null | sim | declaração de apoio/interesse |
| `responsavelId` | string \| null | sim | id do colaborador que coletou |
| `tel` | string | **só se `privacyOptions.includePII = true`** | telefone do contatado |
| `nomeContato` | string | **só se `privacyOptions.includePII = true`** | |
| `nasc` | ISO-8601 \| null | **só se `privacyOptions.includePII = true`** | |
| `obs` | string \| null | sim | observações |

### 3.2 `data.pesquisa[]`

Respostas de pesquisa estruturada. Cada objeto representa **uma resposta**.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | string | |
| `data` | ISO-8601 | quando a resposta foi coletada |
| `bairro` | string \| null | |
| `intencaoVoto` | string \| null | nome do candidato apontado, ou `null` se não declarou |
| `fatorRejeicao` | string \| null | nome do candidato rejeitado |
| `conheceCandidato` | boolean \| null | resposta a "conhece o candidato próprio?" |
| `prioridadeLocal` | string \| null | tema apontado como prioridade |
| `nps` | number \| null | 0-10 quando aplicável |
| `responsavelId` | string \| null | |

### 3.3 `data.engagementActions[]`

Ações de engajamento promovidas pela campanha (eventos, comícios, distribuição).

| Campo | Tipo |
|---|---|
| `id` | string |
| `data` | ISO-8601 |
| `tipo` | string (`comicio` \| `evento` \| `distribuicao` \| `digital` \| `outro`) |
| `bairro` | string \| null |
| `participantesEstimados` | number \| null |
| `responsavelId` | string \| null |
| `descricao` | string \| null |

### 3.4 `data.teamMembers[]`

Equipe da campanha (lideranças, coordenadores, voluntários).

| Campo | Tipo |
|---|---|
| `id` | string |
| `nome` | string (mascarado se PII off) |
| `role` | string (`coordenador` \| `lider` \| `voluntario` \| `liderPolitico` \| `outro`) |
| `bairro` | string \| null |
| `ativo` | boolean |
| `entradaEm` | ISO-8601 \| null |

### 3.5 `data.locations[]`

Pontos de interesse e bases territoriais.

| Campo | Tipo |
|---|---|
| `id` | string |
| `nome` | string |
| `tipo` | string (`comite` \| `casa-apoio` \| `ponto-distribuicao` \| `outro`) |
| `bairro` | string \| null |
| `ativo` | boolean |
| `liderResponsavelId` | string \| null |

### 3.6 `data.financial`

Espelha `incomes` e `expenses` do CampanhaPro, escopados pela campanha.

```json
"financial": {
  "incomes": [
    { "id": "...", "data": "ISO-8601", "valor": 0, "categoria": "...", "fonte": "...", "obs": "..." }
  ],
  "expenses": [
    { "id": "...", "data": "ISO-8601", "valor": 0, "categoria": "...", "destino": "...", "obs": "..." }
  ]
}
```

### 3.7 `data.calculatorSettings`

Espelha `calculator_settings` do CampanhaPro. Inclui `metaArrecadacao`, `metaVisitas`, `tetoCampanha`, etc.

### 3.8 `data.scenarios[]`, `data.streetReports[]`, `data.agentOutputs[]`, `data.fieldTickets[]`, `data.neighborhoodFlags[]`, `data.contentBriefs[]`, `data.aiUsage[]`

Espelhos das tabelas homônimas do CampanhaPro escopadas por `campaignId`. Mantidas em `camelCase`. O Cenários consome especificamente:
- `streetReports[].climaPredominante` (`positivo` \| `neutro` \| `negativo`) → `local_agenda_fit` e `reputation_risk`.
- `neighborhoodFlags[].tipo` (`alerta` \| `oportunidade`) → reforça `reputation_risk`.
- `fieldTickets[].status` (`aberto` \| `concluido` \| `cancelado`) → `operational_efficiency`.
- `agentOutputs[]` — referência cruzada para auditoria (não entra no score direto em v1).

---

## 4. `privacyOptions`

Controla mascaramento aplicado pelo CampanhaPro **antes** de enviar.

```json
"privacyOptions": {
  "includePII": false,
  "anonymizeNames": true,
  "anonymizePhones": true,
  "anonymizeBirthdates": true
}
```

| Campo | Default | Efeito |
|---|---|---|
| `includePII` | `false` | Quando `false`, os campos PII listados acima são removidos (não enviados, nem em null). Quando `true`, vão tal como estão na origem. |
| `anonymizeNames` | `true` | Quando `true` e `includePII=true`, nomes próprios são truncados para iniciais. |
| `anonymizePhones` | `true` | Quando `true` e `includePII=true`, telefones viram `***-****`. |
| `anonymizeBirthdates` | `true` | Quando `true` e `includePII=true`, datas de nascimento viram só ano. |

O Cenários **não** reaplica mascaramento — confia no que o CampanhaPro enviou. Recomendação: manter `includePII=false` por default e habilitar caso a caso com consentimento.

---

## 5. `metrics`

Metadados leves para diagnóstico e auditoria.

```json
"metrics": {
  "recordsCount": 0,
  "windowStart": "ISO-8601",
  "windowEnd": "ISO-8601"
}
```

| Campo | Notas |
|---|---|
| `recordsCount` | soma do `length` de todos os arrays em `data.*` (inclusive aninhados em `financial`). |
| `windowStart` / `windowEnd` | janela temporal coberta. Default recomendado: 90 dias. |

---

## 6. Compatibilidade com formato legado

O endpoint continua aceitando o payload antigo (sem `schemaVersion`):

```json
{
  "request_id": "uuid",
  "source_system": "campanhapro",
  "organization_id": "...",
  "snapshot_type": "electoral_metrics",
  "reference_date": "ISO-8601",
  "payload_version": "1.0",
  "payload": { "factors": { ... } }
}
```

A presença de `schemaVersion == "campanhapro.snapshot.v1"` é o **único discriminador**. Sem `schemaVersion`, o endpoint segue a rota legada.

A migração para v1 não é forçada agora; a Fase 2 (mapper) consome ambos via tabelas internas. Migrações futuras podem deprecar o legado quando o CampanhaPro houver migrado.

---

## 7. Idempotência e duplicatas

- `snapshotId` é gravado em `campanhapro_snapshots.request_id` (UNIQUE).
- Duplicata → `202 Accepted` + `detail = "Duplicate request_id..."`. Não cria registro novo.
- O CampanhaPro **deve** persistir o `snapshotId` localmente em `snapshot_send_logs` (Fase 1 do lado CampanhaPro) para evitar regerar UUID em retries.

---

## 8. Exemplo mínimo válido v1

```json
{
  "schemaVersion": "campanhapro.snapshot.v1",
  "snapshotId": "5d9f8c1e-3b2a-4f56-9a01-2c8e7b1d0f44",
  "campaignId": "cmp_pref_recife_2028",
  "organizationId": "org_demo_001",
  "generatedAt": "2028-03-15T14:32:00Z",
  "source": "campanhapro-web",
  "actor": { "userId": "usr_42", "role": "Admin" },
  "campaign": {
    "details": {
      "nomeUrna": "Maria 13",
      "partido": "PT",
      "office": "Prefeito",
      "municipio": "Recife",
      "uf": "PE",
      "candidatePhotoUrl": null,
      "headerLogo": null,
      "footerLogo": null
    },
    "settings": {},
    "configs": {}
  },
  "data": {
    "visits": [],
    "pesquisa": [],
    "engagementActions": [],
    "teamMembers": [],
    "locations": [],
    "financial": { "incomes": [], "expenses": [] },
    "calculatorSettings": {},
    "scenarios": [],
    "streetReports": [],
    "agentOutputs": [],
    "fieldTickets": [],
    "neighborhoodFlags": [],
    "contentBriefs": [],
    "aiUsage": []
  },
  "privacyOptions": {
    "includePII": false,
    "anonymizeNames": true,
    "anonymizePhones": true,
    "anonymizeBirthdates": true
  },
  "metrics": {
    "recordsCount": 0,
    "windowStart": "2027-12-15T00:00:00Z",
    "windowEnd": "2028-03-15T00:00:00Z"
  }
}
```

---

## 9. Erros possíveis

| Status | Quando |
|---|---|
| `401` | Header `X-CampanhaPro-Secret` ausente ou incorreto. |
| `422` | `schemaVersion` é `"campanhapro.snapshot.v1"` mas `snapshotId`/`campaignId`/`organizationId`/`generatedAt` faltam ou têm tipo errado. Detalhe inclui apontamento Pydantic. |
| `422` | Sem `schemaVersion` e payload legado também inválido. |
| `202` | Aceito (novo registro ou duplicata idempotente). |

---

## 10. Roadmap

- **Fase 2:** mapper que transforma `data.*` → 12 fatores eleitorais (ver `services/campanhapro_factor_mapper.py`).
- **Fase 5:** branding em relatórios consome `campaign.details.headerLogo`, `footerLogo`, `candidatePhotoUrl`.
- **v2 do contrato (futuro):** suportar streaming incremental por delta em vez de snapshot completo. Requer renegociação com o time CampanhaPro.
