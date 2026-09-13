"""Identification output shape (KICKOFF.md). Changing this schema requires asking Ben."""

from __future__ import annotations

import json
from typing import List, Literal

from pydantic import BaseModel, Field

Category = Literal["board", "sensor", "actuator", "display", "power",
                   "passive", "connector", "bare_component", "other"]
Interface = Literal["i2c", "spi", "uart", "analog", "digital", "onewire",
                    "pwm", "none", "unknown"]
Confidence = Literal["high", "medium", "low"]


class BBox(BaseModel):
    shot: str = Field(description="photo filename this box refers to")
    x: float
    y: float
    w: float
    h: float


class Part(BaseModel):
    name: str = Field(description="human-readable name")
    canonical: str = Field(description="canonical designation, e.g. KY-015, SRD-05VDC-SL-C, 2N2222A")
    category: Category
    interface: Interface = "unknown"
    voltage: str = "unknown"
    qty: int = 1
    confidence: Confidence
    needs_reshoot: bool = False
    reshoot_reason: str = ""
    bboxes: List[BBox] = []


class BinIdentification(BaseModel):
    parts: List[Part]


class ShotFeedback(BaseModel):
    """Whole-photo verdict (Ben's photo-reject feature, DECISIONS #30)."""

    shot: str = Field(description="photo filename this verdict refers to")
    verdict: Literal["ok", "retake"]
    reason: str = ""


class AppBinIdentification(BinIdentification):
    """App-runtime variant only: adds per-photo feedback so capture can prompt an
    immediate reshoot. NEVER used by the eval (embedded schema text must stay
    identical for tuning comparability)."""

    photo_feedback: List[ShotFeedback] = []


UnitType = Literal["standalone_object", "component_attached_to_a_listed_object"]
Legibility = Literal["markings_read_clearly", "markings_partially_readable",
                     "markings_unreadable_or_hidden"]


class LocalPart(BaseModel):
    """Local-model variant (Ben approved 2026-09-08): schema-forced decisions.

    Field ORDER is deliberate — grammar-constrained decoding follows it, so the
    model must answer unit_type and legibility BEFORE confidence/needs_reshoot.
    The provider enforces the consequences (drops attached components; couples
    legibility to needs_reshoot). Claude's Part schema is untouched.
    """

    name: str
    canonical: str
    category: Category
    unit_type: UnitType
    legibility: Legibility
    interface: Interface = "unknown"
    voltage: str = "unknown"
    qty: int = 1
    confidence: Confidence
    needs_reshoot: bool = False
    reshoot_reason: str = ""
    bboxes: List[BBox] = []


class LocalBinIdentification(BaseModel):
    parts: List[LocalPart]


def json_schema_str() -> str:
    """Schema text embedded in prompts for providers without server-side enforcement."""
    return json.dumps(BinIdentification.model_json_schema(), indent=2)
