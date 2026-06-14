"""CLI layer — Click command group and subcommands.

Provides the gazepy entrypoint with 8 subcommands:
- analyze <path>: Detect side effects; all CRAP-derived fields are null.
- crap <path>: Detect, classify, and compute CRAP/GazeCRAP scores.
- quality [path]: Stub — requires O1 (change 002/A).
- docscan [path]: Stub — requires O3.
- report [path]: Stub — migration guidance to 'gazepy crap'.
- schema: Emit the JSON schema for AnalysisResult output.
- self-check: Run CRAP analysis on gaze-py's own source.
- init: Scaffold .opencode agent + command assets into the current project.

The CLI layer wires the full pipeline: detector → classifier → scorer →
formatter. Business logic lives in the domain modules; this layer handles
argument parsing, error reporting via click.echo(err=True), and exit codes.
"""
