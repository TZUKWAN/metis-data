"""Candidate Analyzer (P01-004) — implementation lives in build_planner (shared LLM plumbing);
this module re-exports it so the module inventory required by the task list is stable."""
from app.agent.build_planner import analyze_candidate  # noqa: F401

__all__ = ["analyze_candidate"]
