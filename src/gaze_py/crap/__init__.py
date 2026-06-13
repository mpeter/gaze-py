"""CRAP and GazeCRAP scoring layer.

Implements the CRAP formula (Change Risk Anti-Patterns), GazeCRAP extension
for contract coverage, quadrant assignment (Q1–Q4), fix strategy selection
(SC-005 evaluation order), recommended action generation, and CRAPload
counting. All scoring functions are pure — they accept numeric inputs and
return numeric outputs or None when inputs are unavailable.
"""
