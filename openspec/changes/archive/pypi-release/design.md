## Release workflow design

### Trigger

`workflow_dispatch` with a single required input:

```yaml
on:
  workflow_dispatch:
    inputs:
      tag:
        description: 'Release tag (e.g., v0.2.0)'
        required: true
        type: string
```

This is intentionally manual — no accidental releases from tag pushes.
Mirrors the Go gaze release workflow pattern.

### Jobs

**Job 1: `preflight`** (no environment, read-only permissions)

1. Validate tag format: must match `^v[0-9]+\.[0-9]+\.[0-9]+$`
2. Verify tag does not already exist on remote:
   `git ls-remote --tags origin | grep "refs/tags/${TAG}$"`
3. Extract version from tag (strip leading `v`) and compare against
   `pyproject.toml` `[project] version`. Fail if they don't match:
   ```bash
   pyproject_ver=$(python3 -c "import tomllib; ...")
   tag_ver="${TAG#v}"
   if [ "$pyproject_ver" != "$tag_ver" ]; then exit 1; fi
   ```
   This enforces that version bumps go through normal PRs before release.

**Job 2: `publish`** (needs: preflight, environment: pypi)

```yaml
environment:
  name: pypi
  url: https://pypi.org/p/gaze-py
permissions:
  id-token: write   # OIDC trusted publishing
  contents: write   # create and push git tag
```

Steps:
1. `actions/checkout@<SHA>` with `fetch-depth: 0`
2. `astral-sh/setup-uv@<SHA>` (same pins as test.yml)
3. Create and push git tag: `git tag $TAG && git push origin $TAG`
4. `uv build` — produces `dist/gaze_py-*.whl` and `dist/gaze_py-*.tar.gz`
5. `pypa/gh-action-pypi-publish@6733eb7d741f0b11ec6a39b58540dab7590f9b7d`
   (v1.14.0, SHA-pinned per Constitution Principle VII)

### Trusted publishing setup (manual, one-time)

These steps are NOT automated — must be done before the first release:

**On pypi.org:**
1. Log in → Your projects → Add new project → name: `gaze-py`
2. Go to project → Settings → Publishing → Add a new publisher:
   - Publisher: GitHub Actions
   - Owner: `mpeter`
   - Repository: `gaze-py`
   - Workflow filename: `release.yml`
   - Environment: `pypi`

**On GitHub:**
1. Repo settings → Environments → New environment → name: `pypi`
2. (Optional) Add required reviewers for an approval gate before publish

### pyproject.toml additions

```toml
[project]
# existing fields unchanged...
authors = [{name = "Unbound Force"}]
keywords = ["crap", "gaze", "cyclomatic-complexity", "ast", "code-quality", "testing"]
classifiers = [
    "Development Status :: 4 - Beta",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Software Development :: Quality Assurance",
    "Topic :: Software Development :: Testing",
    "Typing :: Typed",
]

[project.urls]
Homepage = "https://github.com/mpeter/gaze-py"
Repository = "https://github.com/mpeter/gaze-py"
"Bug Tracker" = "https://github.com/mpeter/gaze-py/issues"
```

### README Installation section

Add after the existing intro, before "Basic Usage":

```markdown
## Installation

```bash
# Recommended (no permanent install)
uvx gaze-py --help

# Permanent install
uv tool install gaze-py
pip install gaze-py
```

### Release process (post-merge)

```
1. Bump version in pyproject.toml + src/gaze_py/__init__.py → PR → merge
2. GitHub Actions → Release → Run workflow → enter tag (e.g. v0.2.0)
3. Approve the `pypi` environment gate (if configured)
4. Workflow publishes to PyPI automatically
```
