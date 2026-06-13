"""Classification layer — contractual vs incidental effect classification.

Provides ClassificationEngine which runs five signal analyzers (interface,
visibility, caller, naming, docstring) and combines their weights with a
tier boost and contradiction penalty to produce a ClassificationResult with
a label (contractual / ambiguous / incidental) and score in [0, 100].
"""
