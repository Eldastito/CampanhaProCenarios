from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class SavedResearch(Base):
    __tablename__ = "saved_research"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    party: Mapped[str] = mapped_column(String(255), nullable=False)
    party_abbreviation: Mapped[str] = mapped_column(String(50), nullable=False)
    office: Mapped[str] = mapped_column(String(100), nullable=False)
    search_performed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    political_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_mandates: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform_and_goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    recent_news: Mapped[str | None] = mapped_column(Text, nullable=True)
    legal_issues: Mapped[str | None] = mapped_column(Text, nullable=True)
    ficha_limpa_status: Mapped[str | None] = mapped_column(String(255), nullable=True)
    background: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    graph_context_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
