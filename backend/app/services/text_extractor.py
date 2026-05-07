"""Extração de texto a partir de bytes em diversos formatos.

Suporta:
- PDF (via pypdf — pure Python, sem deps nativas)
- TXT, Markdown, CSV (decodificação UTF-8 com fallback latin-1)

Retorna texto cru. A normalização (quebras de linha, espaços) fica a cargo
do consumidor. Para PDFs muito grandes ou com layout complexo, considere
trocar para PyMuPDF (pip install pymupdf) — a interface é mantida.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    page_count: int | None = None
    extraction_method: str = "unknown"
    warnings: tuple[str, ...] = ()


def extract_text(content: bytes, source_type: str, *, filename: str | None = None) -> ExtractionResult:
    """Roteia para o extrator apropriado pelo source_type.

    source_type esperado: 'pdf' | 'txt' | 'md' | 'csv' | outros (fallback decode).
    """
    stype = (source_type or "").lower().strip()
    if stype == "pdf":
        return _extract_pdf(content)
    if stype in {"txt", "md", "markdown"}:
        return _decode(content, method=f"plain-{stype}")
    if stype == "csv":
        return _extract_csv(content)
    # Fallback: tenta decodificar como texto
    return _decode(content, method="fallback-decode")


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------


def _decode(content: bytes, *, method: str) -> ExtractionResult:
    try:
        text = content.decode("utf-8")
        return ExtractionResult(text=text, extraction_method=method)
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
            return ExtractionResult(
                text=text,
                extraction_method=method,
                warnings=("Conteúdo não estava em UTF-8; usado fallback latin-1.",),
            )
        except Exception as e:  # pragma: no cover
            logger.exception("decode_failed", extra={"method": method})
            return ExtractionResult(
                text="",
                extraction_method=method,
                warnings=(f"Falha ao decodificar bytes: {e}",),
            )


def _extract_pdf(content: bytes) -> ExtractionResult:
    try:
        from pypdf import PdfReader  # import local para não quebrar caso lib esteja ausente
    except ImportError:
        return ExtractionResult(
            text="",
            extraction_method="pdf-pypdf",
            warnings=("pypdf não está instalado; instale com: pip install pypdf",),
        )

    try:
        reader = PdfReader(io.BytesIO(content))
        chunks: list[str] = []
        for i, page in enumerate(reader.pages):
            try:
                chunks.append(page.extract_text() or "")
            except Exception as e:  # noqa: BLE001
                logger.warning("pdf_page_extract_failed page=%d err=%s", i, e)
                chunks.append("")
        return ExtractionResult(
            text="\n\n".join(c for c in chunks if c).strip(),
            page_count=len(reader.pages),
            extraction_method="pdf-pypdf",
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("pdf_extract_failed")
        return ExtractionResult(
            text="",
            extraction_method="pdf-pypdf",
            warnings=(f"Falha na extração PDF: {e}",),
        )


def _extract_csv(content: bytes) -> ExtractionResult:
    decoded = _decode(content, method="csv-decode")
    if not decoded.text:
        return decoded

    try:
        reader = csv.reader(io.StringIO(decoded.text))
        rows = list(reader)
        if not rows:
            return ExtractionResult(text="", extraction_method="csv")

        # Normaliza para tabela legível por LLM/humano: header + linhas
        header = rows[0]
        body = rows[1:]
        lines = [" | ".join(header)]
        lines.append(" | ".join(["---"] * len(header)))
        for r in body:
            # padding caso linha tenha menos colunas que o header
            padded = r + [""] * (len(header) - len(r))
            lines.append(" | ".join(padded[: len(header)]))
        return ExtractionResult(
            text="\n".join(lines),
            extraction_method="csv",
            warnings=decoded.warnings,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("csv_extract_failed err=%s", e)
        return ExtractionResult(
            text=decoded.text,
            extraction_method="csv-fallback-raw",
            warnings=(f"Falha ao parsear CSV; retornando texto cru: {e}",),
        )
