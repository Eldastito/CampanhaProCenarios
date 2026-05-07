# Arquitetura Inicial

## Visão macro
FORGE -> Ingestion API -> Normalization/Feature Store -> Predictive Engine -> Scenario Engine -> Report Engine -> Dashboard

## Componentes

### 1. Ingestion API
Recebe eventos e snapshots da FORGE com autenticação server-to-server.

### 2. Normalization Layer
Valida payloads, normaliza campos, registra origem, versiona e prepara features.

### 3. Predictive Engine
Calcula scores iniciais:
- aceitação da FORGE
- prontidão institucional
- risco de evasão
- resistência docente

### 4. Scenario Engine
Permite criar cenário base e cenário alternativo, rodar comparação e medir diferença projetada.

### 5. Agent Simulation Engine
Camada exploratória para personas e propagação de adesão ou resistência.

### 6. Report Engine
Gera relatório resumido e detalhado com fatores explicativos, alertas e recomendações.

## Segurança e governança
- RBAC por organização
- trilha de auditoria
- versionamento de cenários
- chaves de integração por cliente
- idempotência em ingestão

## Separação de domínios
- FORGE = sistema operacional educacional
- Scenario Lab = inteligência estratégica e simulação
