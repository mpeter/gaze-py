## Why

The `astral-sh/setup-uv` CI action is pinned to v5.4.2, three major versions behind the current v8.2.0. The v8.0.0 release hardened supply chain security by eliminating floating major/minor tags and introducing immutable releases — the security model gaze-py's Principle VII (Supply Chain Integrity) is designed to align with. The uv binary pin (`0.7.8`) is also significantly behind the current stable (`0.11.21`). Both should be updated before the constitution PR merges to avoid shipping an immediately-stale CI configuration.

## What Changes

- Update `astral-sh/setup-uv` action SHA from `d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86` (v5.4.2) to `fac544c07dec837d0ccb6301d7b5580bf5edae39` (v8.2.0)
- Update uv binary pin from `version: "0.7.8"` to `version: "0.11.21"`
- No other CI logic changes

## Capabilities

### New Capabilities

- `ci-action-upgrade`: The process for upgrading a SHA-pinned CI action — resolving the new SHA, verifying it against the published tag, updating the workflow, and confirming CI passes.

### Modified Capabilities

(none — no existing spec-level behavior is changing)

### Removed Capabilities

(none)

## Impact

- `.github/workflows/test.yml` — two line edits (action SHA + version comment; uv binary version)
- No production code, tests, or analysis behavior is affected
- CI will use a newer, security-hardened action with a current uv binary; behaviour is identical
