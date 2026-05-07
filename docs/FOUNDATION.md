# CampanhaPro Cenários — Fundação

## Objetivo
Criar um aplicativo independente da ExamePad, integrado por API à plataforma CampanhaPro, para prever, comparar e debater cenários de modernização educacional, adoção institucional, risco de evasão, resistência à mudança e impacto de intervenções.

## Princípios
- Produto independente, não módulo interno do CampanhaPro
- Integração server-to-server com a FORGE
- Separação entre dado real, inferência e simulação
- Resultados sempre com fatores explicativos e nível de confiança
- Isolamento por organização e trilha de auditoria

## Casos de uso prioritários
1. Estimativa de aceitação do CampanhaPro em redes públicas e privadas
2. Simulação da mudança do professor para tutor
3. Estimativa de risco de evasão e desengajamento
4. Comparação entre estratégias pedagógicas, operacionais e comunicacionais

## Motores principais
- Ingestion API
- Data Foundation / Feature Store
- Predictive Engine
- Scenario Engine
- Agent Simulation Engine
- Explanation & Report Engine

## Stack sugerida
- Backend: Python + FastAPI
- Banco: PostgreSQL
- Cache/Fila: Redis
- Frontend: React + TypeScript
- LLM: OpenAI via backend
- Observabilidade: Sentry + PostHog

## Próximos passos
1. Fechar PRD técnico
2. Definir contrato da API com a FORGE
3. Modelar banco inicial
4. Criar skeleton do backend
5. Criar skeleton do frontend
