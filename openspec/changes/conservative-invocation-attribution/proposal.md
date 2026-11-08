## Why

An assertion on a fake's received subprocess arguments currently remains unmapped,
even when exact target identity and a live monkeypatch establish the producer.

## What Changes

Add bounded AST-only attribution for an empty local dictionary populated by a
nested fake through `record.update(argument=parameter, **kwargs)`. The existing
ordered assertion analyzer MUST own ordering and exact production-call identity.
Only a single direct `subprocess.run` boundary, live module-object monkeypatch,
single target exercise, and direct dictionary equality assertion are supported.
Unknown calls, storage, control flow, aliases, or competing producers MUST fail
closed. No general provenance solver is proposed.

Classification, taxonomy, scoring, max-per-test reduction, thresholds, baselines,
dependency adoption, publication and integration MUST remain unchanged.

## Capabilities

### Modified Capabilities
- quality-assessment: conservative recorded invocation assertion attribution.

## Impact

Quality mapper internals and upstream-native regression tests only. This isolated
change is based on v0.9.3; independent review precedes any adoption decision.
