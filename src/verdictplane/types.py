"""Core schemas for governed actions and ledger entries.

Enforcement-path module: deterministic, zero-egress, no model client.
Pydantic is used only for boundary validation; the hot path works on plain dicts.
"""

from enum import Enum

from pydantic import BaseModel, Field


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_HUMAN = "require_human"


class Action(BaseModel):
    """One consequential AI-driven action, described before it commits."""

    tool: str
    effect: str = "write"
    args: dict = Field(default_factory=dict)
    agent: str = "unknown"
    context: dict = Field(default_factory=dict)


class LedgerEntry(BaseModel):
    """One hash-chained provenance record as persisted to the ledger."""

    ts: int
    prev: str
    record: dict
    hash: str
