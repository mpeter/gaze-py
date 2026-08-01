"""Regenerate `tests/testdata/coverage_ownership.json`.

The committed JSON is a *real* coverage.py report over
`tests/testdata/analysis/coverage_ownership.py`. Tests compare computed
per-function line ownership against it, so it must be produced by coverage.py
rather than hand-written — hand-written expectations would encode the same
assumptions as the implementation they are meant to check.

Run after editing the fixture source (its line layout is load-bearing):

    uv run python scripts/regen_coverage_ownership.py

The script copies the fixture to a scratch directory, exercises every function
except the two that must stay uncovered (`never_called` and
`has_uncalled_nested.unused_inner`), runs coverage.py over it with the repo's
own config disabled, and rewrites the single file key to the repo-relative
fixture path the tests look up.

`--rcfile=/dev/null` matters: the repo's `pyproject.toml` scopes coverage to
the `gaze_py` package, which would collect nothing here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE_SRC = _REPO_ROOT / "tests" / "testdata" / "analysis" / "coverage_ownership.py"
_FIXTURE_OUT = _REPO_ROOT / "tests" / "testdata" / "coverage_ownership.json"
_FIXTURE_KEY = "tests/testdata/analysis/coverage_ownership.py"

# Calls every function except `never_called` and `has_uncalled_nested.unused_inner`,
# which must stay uncovered for the 0% assertions to mean anything.
_DRIVER = """\
import coverage_ownership as m

m.fully_covered(1)
m.partially_covered(False)
m.has_nested(2)
m.has_uncalled_nested(3)
m.docstring_only()
"""


def main() -> int:
    """Regenerate the reference JSON in place. Returns a process exit code."""
    if not _FIXTURE_SRC.exists():
        print(f"fixture source not found: {_FIXTURE_SRC}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        shutil.copy(_FIXTURE_SRC, work / "coverage_ownership.py")
        (work / "driver.py").write_text(_DRIVER, encoding="utf-8")
        data_file = work / ".coverage"
        raw_out = work / "raw.json"

        run = subprocess.run(
            [
                sys.executable,
                "-m",
                "coverage",
                "run",
                "--rcfile=/dev/null",
                f"--data-file={data_file}",
                f"--source={work}",
                "driver.py",
            ],
            cwd=work,
            capture_output=True,
            text=True,
            check=False,
        )
        if run.returncode != 0:
            print(run.stdout, file=sys.stderr)
            print(run.stderr, file=sys.stderr)
            return run.returncode

        report = subprocess.run(
            [
                sys.executable,
                "-m",
                "coverage",
                "json",
                "--rcfile=/dev/null",
                f"--data-file={data_file}",
                "--show-contexts",
                "-o",
                str(raw_out),
            ],
            cwd=work,
            capture_output=True,
            text=True,
            check=False,
        )
        if report.returncode != 0:
            print(report.stdout, file=sys.stderr)
            print(report.stderr, file=sys.stderr)
            return report.returncode

        raw = json.loads(raw_out.read_text(encoding="utf-8"))

    files = raw.get("files", {})
    fixture_entries = [k for k in files if k.endswith("coverage_ownership.py")]
    if len(fixture_entries) != 1:
        print(
            f"expected exactly one fixture entry, found {fixture_entries}",
            file=sys.stderr,
        )
        return 1

    # Rewrite the scratch path to the repo-relative key the tests look up, and
    # keep only the fixture entry (the driver is not under test).
    raw["files"] = {_FIXTURE_KEY: files[fixture_entries[0]]}

    _FIXTURE_OUT.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    functions = raw["files"][_FIXTURE_KEY].get("functions", {})
    named = [q for q in functions if q]
    print(f"wrote {_FIXTURE_OUT.relative_to(_REPO_ROOT)} ({len(named)} function entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
