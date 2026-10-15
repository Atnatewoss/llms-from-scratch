"""Shared core for the API: rule-based logic and (later) the model code."""

from core.rule.rules import GROUPS, Response, respond

__all__ = ["GROUPS", "Response", "respond"]
