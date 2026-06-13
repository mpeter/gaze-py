"""Signal analyzers for the classification engine.

Each module in this package implements one of the five classification signals:
- interface.py  — ABC/Protocol base class detection (+30)
- visibility.py — exported function and return/receiver type visibility (+20 max)
- caller.py     — cross-file caller count weight table (0 / +5 / +10 / +15)
- naming.py     — contractual/incidental prefix tables and sentinel special case
- docstring.py  — keyword scan of docstrings (direct +15, indirect +5)

Each signal returns a Signal dataclass with source (str) and weight (int).
"""
