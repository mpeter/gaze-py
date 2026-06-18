## ADDED Requirements

### Requirement: _find_project_root returns file's parent when no project root marker found
Tests MUST verify that when `_find_project_root` walks up the directory tree and finds no `pyproject.toml`, `go.mod`, or other marker, it returns `start.parent` for a file input.

#### Scenario: No project root marker returns start.parent for file
- **WHEN** `_find_project_root(some_file)` is called with a file whose directory tree contains no project-root markers
- **THEN** the return value is `some_file.parent`

### Requirement: _pair_astroid uses stem-only fallback when file is not under project root
Tests MUST verify that when `file_path.relative_to(project_root)` raises `ValueError` (file is outside the project root), `_pair_astroid` falls back to using only the file stem for FQN construction.

#### Scenario: File outside project root uses stem fallback
- **WHEN** `_find_project_root` is monkeypatched to return a path that is not an ancestor of the test file
- **THEN** `_pair_astroid` does not raise and uses the file stem for matching
