"""O1 quality assessment pipeline for gaze-py.

Provides contract coverage analysis by pairing test functions with their
production targets, detecting assertion sites, mapping assertions to side
effects, and computing coverage percentages.

Entry point: quality.pipeline.assess()
"""

from gaze_py.quality.pipeline import AssessResult as AssessResult
from gaze_py.quality.pipeline import build_contract_coverage_map as build_contract_coverage_map
