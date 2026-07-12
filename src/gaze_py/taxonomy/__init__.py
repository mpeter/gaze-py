"""Taxonomy layer — domain types, effect taxonomy, and shared exceptions.

Defines the 48-type SideEffectType StrEnum (EC-001), Tier enum, TIER_MAP,
all value-object dataclasses (SideEffect, Signal, ClassificationResult, Score,
FunctionTarget, AnalysisResult, Summary), and shared exception classes
(GazeParseError, GazeConfigError).

All other subpackages import domain types from this module. No subpackage
may define exceptions that other subpackages need to import (AP-008).
"""
