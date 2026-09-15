"""Conversation persistence models + repository (P0-03).

conversations / conversation_messages / conversation_tasks / conversation_result_links
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


def utcnow():
    return datetime.now(UTC)


class ConversationRow(Base):
    __tablename__ = "conversations"
    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="active")
    data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ConversationMessageRow(Base):
    __tablename__ = "conversation_messages"
    message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant | system
    content: Mapped[str] = mapped_column(Text)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ConversationTaskRow(Base):
    __tablename__ = "conversation_tasks"
    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    goal: Mapped[str] = mapped_column(String(48), default="discover_only")
    intent: Mapped[str] = mapped_column(String(48))
    state: Mapped[str] = mapped_column(String(48), index=True)
    stage_label: Mapped[str] = mapped_column(Text, default="")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    planning_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    access_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    download_job_ids: Mapped[list] = mapped_column(JSON, default=list)
    build_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ConversationResultLinkRow(Base):
    __tablename__ = "conversation_result_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    result_id: Mapped[str] = mapped_column(String(128), index=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_kind: Mapped[str] = mapped_column(String(32))  # candidate|artifact|build
    source_ref: Mapped[str] = mapped_column(String(256))
    position: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(32), default="FOUND")  # FOUND|ACQUIRING|WAITING_USER|READY|BUILDING|FINAL|FAILED
    title: Mapped[str] = mapped_column(Text, default="")
    provider_id: Mapped[str] = mapped_column(String(64), default="")
    data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ConversationInterventionRow(Base):
    __tablename__ = "conversation_interventions"
    intervention_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    access_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    download_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    browser_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), default="LOGIN_REQUIRED")
    provider_name: Mapped[str] = mapped_column(String(64), default="")
    state: Mapped[str] = mapped_column(String(32), default="WAITING_USER")  # WAITING_USER|RESOLVED|SKIPPED|EXPIRED
    message: Mapped[str] = mapped_column(Text, default="")
    data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
