# CORE Replatform Plan

## Objetivo
Construir o CampanhaPro Cenários com arquitetura própria, independente de serviços centrais acoplados, preparada para operar com camada de memória/grafo própria ou substituível, fila assíncrona, persistência forte, storage adequado, observabilidade e autenticação.

## Decisões iniciais
- Não acoplar o produto a um único fornecedor de memória/grafo.
- Criar interface interna para memória contextual e grafo.
- Iniciar com implementação local simples e preparar adapter para engine externa depois.
- Priorizar backend robusto antes de simulação avançada.

## Pilares técnicos
1. Backend endurecido
2. Banco relacional forte
3. Fila assíncrona
4. Storage abstraído
5. Observabilidade
6. Autenticação e trilha de auditoria
7. Camada de memória/grafo desacoplada

## Sequência recomendada
### Fase 0
- Docker
- Postgres
- Redis
- settings centralizados
- logs estruturados
- abstrações de memória e storage

### Fase 1
- modelos principais
- persistência inicial
- ingestão auditável
- autenticação básica
- API interna segura

### Fase 2
- execução assíncrona de cenários
- score de aceitação
- score de evasão v1
- relatórios v1

### Fase 3
- engine de personas
- simulação exploratória
- camada de memória/grafo avançada
- observabilidade ampliada

## Regra central
Nenhuma parte crítica do produto deve depender de um provedor único sem camada de abstração interna.
