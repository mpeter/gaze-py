"""Analysis layer — AST-based side-effect detection and cyclomatic complexity.

Provides FileDetector for two-phase AST scanning (module-level SentinelError
pass + per-function FunctionVisitor pass) and cyclomatic_complexity() for
McCabe complexity scoring. All analysis is AST-only — no code execution,
no import of analyzed modules, no runtime introspection.
"""
