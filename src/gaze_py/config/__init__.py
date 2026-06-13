"""Configuration layer — .gaze.yaml discovery and loading.

Provides GazeConfig dataclass and load_config() which walks up from a given
path to discover .gaze.yaml, stopping at the project root sentinel
(pyproject.toml or .git). Raises GazeConfigError (imported from
taxonomy/exceptions.py) on invalid YAML or out-of-range threshold values.
Unknown keys are silently ignored for forward-compatibility.
"""
