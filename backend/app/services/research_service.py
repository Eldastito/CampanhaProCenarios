"""AI Research Agent — researches Brazilian political candidates via OpenAI web search."""
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Demographic segments for rejection analysis
# ---------------------------------------------------------------------------

DEMOGRAPHIC_SEGMENTS: dict[str, list[str]] = {
    "region": ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"],
    "sex": ["Masculino", "Feminino"],
    "income": ["Até 1 SM", "1-2 SM", "2-5 SM", "5-10 SM", "Acima de 10 SM"],
    "age": ["16-24 anos", "25-34 anos", "35-44 anos", "45-59 anos", "60+ anos"],
    "education": ["Sem instrução", "Fundamental", "Médio", "Superior"],
    "religion": ["Católico", "Evangélico", "Sem religião", "Outras religiões"],
    "employment": ["Empregado CLT", "Autônomo", "Desempregado", "Funcionário público", "Aposentado"],
    "aid": ["Beneficiário Bolsa Família", "Não beneficiário"],
}


class ResearchService:
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY não configurada. Configure a chave no arquivo .env e reinicie o servidor.")

    # ------------------------------------------------------------------
    # Public: research a single candidate
    # ------------------------------------------------------------------

    def research_candidate(
        self,
        name: str,
        party: str,
        office: str,
        party_abbreviation: str,
    ) -> dict[str, Any]:
        """Run full web-search research on a candidate. Returns structured dict."""
        import openai
        client = openai.OpenAI(api_key=settings.openai_api_key)

        search_performed, raw_research, web_sources = self._gather_information(
            client, name, party, office, party_abbreviation
        )

        structured = self._synthesize_structured(
            client, name, party, office, party_abbreviation, raw_research
        )
        # Prefer sources from live web search; fall back to those extracted by synthesis
        if web_sources:
            structured["sources"] = web_sources

        rejection = self._analyze_rejection(
            client, name, party, office, party_abbreviation, structured.get("political_history", "")
        )

        graph_context = self._build_graph_context(
            name, party, office, party_abbreviation, structured
        )

        return {
            "name": name,
            "party": party,
            "party_abbreviation": party_abbreviation,
            "office": office,
            "search_performed": search_performed,
            "political_history": structured.get("political_history", ""),
            "current_mandates": structured.get("current_mandates", ""),
            "platform_and_goals": structured.get("platform_and_goals", ""),
            "recent_news": structured.get("recent_news", ""),
            "legal_issues": structured.get("legal_issues", ""),
            "ficha_limpa_status": structured.get("ficha_limpa_status", ""),
            "background": structured.get("background", ""),
            "rejection_profile": rejection,
            "graph_context_text": graph_context,
            "sources": structured.get("sources", []),
        }

    # ------------------------------------------------------------------
    # Public: compare rejection profiles of multiple candidates
    # ------------------------------------------------------------------

    def compare_rejection(self, candidates: list[dict[str, str]]) -> dict[str, Any]:
        """Generate comparative rejection analysis for a list of candidates."""
        import openai
        client = openai.OpenAI(api_key=settings.openai_api_key)

        profiles_desc = "\n".join(
            f"- {c['name']} ({c.get('party_abbreviation', c.get('party', ''))}) — concorrendo a {c.get('office', 'cargo')}"
            for c in candidates
        )

        prompt = f"""Você é um analista político especialista em opinião pública brasileira.

Analise a rejeição eleitoral comparativa dos seguintes candidatos:
{profiles_desc}

Para CADA segmento demográfico abaixo, estime a rejeição (0-100%) de CADA candidato.
Baseie-se no posicionamento ideológico, declarações públicas, partido político e perfil do candidato.

Segmentos:
- Região: Norte, Nordeste, Centro-Oeste, Sudeste, Sul
- Sexo: Masculino, Feminino
- Renda familiar: Até 1 SM, 1-2 SM, 2-5 SM, 5-10 SM, Acima de 10 SM
- Faixa etária: 16-24 anos, 25-34 anos, 35-44 anos, 45-59 anos, 60+ anos
- Escolaridade: Sem instrução, Fundamental, Médio, Superior
- Religião: Católico, Evangélico, Sem religião, Outras religiões
- Situação trabalhista: Empregado CLT, Autônomo, Desempregado, Funcionário público, Aposentado
- Beneficiário de auxílio: Beneficiário Bolsa Família, Não beneficiário

Retorne APENAS JSON válido:
{{
  "candidates": [
    {{
      "name": "nome do candidato",
      "rejection_by_segment": {{
        "region": {{"Norte": 35, "Nordeste": 28, "Centro-Oeste": 40, "Sudeste": 45, "Sul": 50}},
        "sex": {{"Masculino": 38, "Feminino": 42}},
        "income": {{"Até 1 SM": 25, "1-2 SM": 30, "2-5 SM": 40, "5-10 SM": 48, "Acima de 10 SM": 55}},
        "age": {{"16-24 anos": 35, "25-34 anos": 38, "35-44 anos": 42, "45-59 anos": 40, "60+ anos": 45}},
        "education": {{"Sem instrução": 30, "Fundamental": 32, "Médio": 38, "Superior": 50}},
        "religion": {{"Católico": 40, "Evangélico": 55, "Sem religião": 30, "Outras religiões": 38}},
        "employment": {{"Empregado CLT": 40, "Autônomo": 42, "Desempregado": 28, "Funcionário público": 45, "Aposentado": 42}},
        "aid": {{"Beneficiário Bolsa Família": 22, "Não beneficiário": 45}}
      }},
      "overall_rejection": 40,
      "key_weaknesses": ["grupo mais resistente ao candidato", "motivo principal"],
      "key_strengths": ["grupo mais favorável", "razão"]
    }}
  ],
  "analysis": "Análise comparativa geral em 3-4 frases"
}}"""

        try:
            resp = client.chat.completions.create(
                model=settings.openai_model,
                max_tokens=3000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            content = resp.choices[0].message.content or "{}"
            data = _extract_json(content)
            if data and isinstance(data, dict):
                return data
        except Exception as exc:
            logger.error("compare_rejection_error", extra={"error": str(exc)})

        return {"candidates": [], "analysis": "Erro ao gerar análise comparativa."}

    # ------------------------------------------------------------------
    # Internal: gather raw information (tries Responses API, falls back)
    # ------------------------------------------------------------------

    def _gather_information(
        self,
        client: Any,
        name: str,
        party: str,
        office: str,
        party_abbreviation: str,
    ) -> tuple[bool, str, list[dict]]:
        """Returns (search_performed, raw_text, sources_list)."""
        search_query = (
            f"{name} {party_abbreviation} candidato {office} Brasil "
            f"história política mandatos projetos ficha limpa processos judiciais"
        )

        # Try the Responses API (openai >= 1.56)
        try:
            responses_api = getattr(client, "responses", None)
            if responses_api and hasattr(responses_api, "create"):
                resp = responses_api.create(
                    model="gpt-4o",
                    tools=[{"type": "web_search_preview"}],
                    input=search_query,
                )
                text_parts: list[str] = []
                sources: list[dict] = []
                for item in resp.output:
                    item_type = getattr(item, "type", "")
                    if item_type == "message":
                        for block in item.content:
                            block_type = getattr(block, "type", "")
                            if block_type == "output_text":
                                text_parts.append(block.text)
                                for ann in getattr(block, "annotations", []):
                                    if getattr(ann, "type", "") == "url_citation":
                                        start = getattr(ann, "start_index", 0)
                                        end = getattr(ann, "end_index", min(start + 120, len(block.text)))
                                        sources.append({
                                            "title": getattr(ann, "title", "Fonte"),
                                            "url": getattr(ann, "url", ""),
                                            "snippet": block.text[start:end].strip(),
                                        })
                if text_parts:
                    return True, "\n\n".join(text_parts), sources
        except Exception as exc:
            logger.info("responses_api_unavailable", extra={"reason": str(exc)})

        # Fall back: use GPT knowledge — explicitly request citation-style output
        fallback_prompt = f"""Você é um especialista em política brasileira. Forneça um relatório detalhado e factual sobre:

Nome: {name}
Partido: {party} ({party_abbreviation})
Cargo pretendido: {office}

Inclua TUDO que sabe com certeza sobre:
1. Histórico político e trajetória desde o início
2. Mandatos exercidos — cargo, período, local e realizações
3. Principais projetos de lei, votações e posições
4. Plataforma e propostas para o cargo de {office}
5. Notícias e fatos relevantes dos últimos 2 anos
6. Processos e investigações em qualquer tribunal (TCE, TRE, TSE, STF, STJ, PGR, Polícia Federal)
7. Situação na Lei da Ficha Limpa — elegível, inelegível ou sob análise
8. Origem, formação acadêmica, carreira antes da política
9. Base eleitoral, alianças e principais apoiadores

Para cada informação factual, indique a fonte entre colchetes: [Fonte: nome do veículo ou órgão, ano].
Se não tiver certeza de algum dado, diga explicitamente.
Se não conhecer o candidato, explique e faça análise com base no partido {party_abbreviation}."""

        try:
            resp = client.chat.completions.create(
                model=settings.openai_model,
                max_tokens=3000,
                temperature=0.1,
                messages=[{"role": "user", "content": fallback_prompt}],
            )
            text = resp.choices[0].message.content or ""
            # Extract inline citations as pseudo-sources
            import re
            pseudo_sources = []
            for match in re.finditer(r'\[Fonte:\s*([^\]]+)\]', text):
                ref = match.group(1).strip()
                pseudo_sources.append({"title": ref, "url": "", "snippet": ""})
            return False, text, pseudo_sources
        except Exception as exc:
            logger.error("fallback_research_error", extra={"error": str(exc)})
            return False, f"Erro ao pesquisar candidato: {exc}", []

    # ------------------------------------------------------------------
    # Internal: synthesize raw research into structured sections + sources
    # ------------------------------------------------------------------

    def _synthesize_structured(
        self,
        client: Any,
        name: str,
        party: str,
        office: str,
        party_abbreviation: str,
        raw_research: str,
    ) -> dict[str, Any]:
        prompt = f"""Com base nas informações abaixo sobre {name} ({party_abbreviation}), estruture um relatório completo.

INFORMAÇÕES COLETADAS:
{raw_research[:6000]}

Retorne APENAS JSON válido:
{{
  "political_history": "Histórico político detalhado — trajetória, primeiros passos, evolução",
  "current_mandates": "Mandatos atuais ou anteriores — cargo, período, local",
  "platform_and_goals": "Propostas e metas para o cargo de {office}",
  "recent_news": "Notícias e eventos recentes relevantes (2022-2024)",
  "legal_issues": "Processos judiciais, investigações, inquéritos em qualquer tribunal ou órgão",
  "ficha_limpa_status": "Situação na Lei da Ficha Limpa — elegível, inelegível ou sob análise",
  "background": "Origem, formação acadêmica, vida profissional antes da política",
  "sources": [
    {{"title": "título da fonte", "url": "https://...", "snippet": "trecho relevante da informação"}}
  ]
}}

Se não houver fontes verificáveis, retorne sources como lista vazia.
Cada campo deve ter no mínimo 2-3 frases substanciais."""

        try:
            resp = client.chat.completions.create(
                model=settings.openai_model,
                max_tokens=3000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )
            content = resp.choices[0].message.content or "{}"
            data = _extract_json(content)
            if data and isinstance(data, dict):
                return data
        except Exception as exc:
            logger.error("synthesize_error", extra={"error": str(exc)})

        return {
            "political_history": raw_research[:500],
            "current_mandates": "",
            "platform_and_goals": "",
            "recent_news": "",
            "legal_issues": "",
            "ficha_limpa_status": "Não verificado",
            "background": "",
            "sources": [],
        }

    # ------------------------------------------------------------------
    # Internal: generate rejection analysis for a single candidate
    # ------------------------------------------------------------------

    def _analyze_rejection(
        self,
        client: Any,
        name: str,
        party: str,
        office: str,
        party_abbreviation: str,
        political_history: str,
    ) -> dict[str, Any]:
        prompt = f"""Você é um analista de opinião pública especialista em eleições brasileiras.

Analise o perfil de rejeição eleitoral de:
Nome: {name}
Partido: {party} ({party_abbreviation})
Cargo: {office}
Perfil: {political_history[:800]}

Estime a % de rejeição (0-100) em cada segmento demográfico brasileiro.
Baseie-se em dados históricos de partidos, ideologia e perfil do candidato.

Retorne APENAS JSON válido:
{{
  "overall_rejection": 38,
  "by_segment": {{
    "region": {{"Norte": 32, "Nordeste": 28, "Centro-Oeste": 40, "Sudeste": 45, "Sul": 48}},
    "sex": {{"Masculino": 35, "Feminino": 42}},
    "income": {{"Até 1 SM": 25, "1-2 SM": 30, "2-5 SM": 38, "5-10 SM": 45, "Acima de 10 SM": 52}},
    "age": {{"16-24 anos": 30, "25-34 anos": 35, "35-44 anos": 40, "45-59 anos": 42, "60+ anos": 45}},
    "education": {{"Sem instrução": 28, "Fundamental": 30, "Médio": 36, "Superior": 50}},
    "religion": {{"Católico": 38, "Evangélico": 50, "Sem religião": 28, "Outras religiões": 35}},
    "employment": {{"Empregado CLT": 38, "Autônomo": 40, "Desempregado": 25, "Funcionário público": 42, "Aposentado": 40}},
    "aid": {{"Beneficiário Bolsa Família": 20, "Não beneficiário": 45}}
  }},
  "key_weaknesses": ["Evangélicos — posição em pautas de costumes", "Alta renda — propostas redistributivas"],
  "key_strengths": ["Nordeste — base histórica do partido", "Beneficiários de programas sociais"]
}}"""

        try:
            resp = client.chat.completions.create(
                model=settings.openai_model,
                max_tokens=1500,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            content = resp.choices[0].message.content or "{}"
            data = _extract_json(content)
            if data and isinstance(data, dict):
                return data
        except Exception as exc:
            logger.error("rejection_analysis_error", extra={"error": str(exc)})

        return {"overall_rejection": None, "by_segment": {}, "key_weaknesses": [], "key_strengths": []}

    # ------------------------------------------------------------------
    # Internal: build text for graph context window
    # ------------------------------------------------------------------

    @staticmethod
    def _build_graph_context(
        name: str,
        party: str,
        office: str,
        party_abbreviation: str,
        structured: dict[str, Any],
    ) -> str:
        sections = [
            f"CANDIDATO: {name}",
            f"PARTIDO: {party} ({party_abbreviation})",
            f"CARGO PRETENDIDO: {office}",
            "",
            "=== HISTÓRICO POLÍTICO ===",
            structured.get("political_history", ""),
            "",
            "=== MANDATOS ===",
            structured.get("current_mandates", ""),
            "",
            "=== PLATAFORMA E PROPOSTAS ===",
            structured.get("platform_and_goals", ""),
            "",
            "=== NOTÍCIAS RECENTES ===",
            structured.get("recent_news", ""),
            "",
            "=== QUESTÕES LEGAIS E JUDICIAIS ===",
            structured.get("legal_issues", ""),
            "",
            "=== FICHA LIMPA ===",
            structured.get("ficha_limpa_status", ""),
            "",
            "=== ORIGEM E FORMAÇÃO ===",
            structured.get("background", ""),
        ]
        return "\n".join(s for s in sections)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict | list | None:
    start_obj = text.find("{")
    start_arr = text.find("[")
    if start_obj == -1 and start_arr == -1:
        return None
    if start_obj == -1:
        start = start_arr
    elif start_arr == -1:
        start = start_obj
    else:
        start = min(start_obj, start_arr)

    depth = 0
    open_char = text[start]
    close_char = "}" if open_char == "{" else "]"
    for i, ch in enumerate(text[start:], start):
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start: i + 1])
                except json.JSONDecodeError:
                    return None
    return None
