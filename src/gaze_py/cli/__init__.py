"""CLI layer — Click command group and subcommands.

Provides the gazepy entrypoint with two subcommands:
- analyze <path> [--format=json|text] [--coverage-json <path>]
- report <src> <tests> [--format=json|text] [--coverage-json <path>]

The CLI layer wires the full pipeline: detector → classifier → scorer →
formatter. Business logic lives in the domain modules; this layer handles
argument parsing, error reporting via click.echo(err=True), and exit codes.
"""
