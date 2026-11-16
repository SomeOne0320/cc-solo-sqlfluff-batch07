# Reproducible local environment

Source: SQLFluff4.5.0, upstream commit `0a7c698408dc56e5efcbe37edc1ec23c782c003b`.
Fixed image: `adminfather/benzhi-claude-code@sha256:159e0b167850ddc1993271972df001dcb9815b1bd25b4fa55b9c69aedae6b922`.
Platform: Linux ARM64 / Python3.11.2, supported by this source version.

The lock records SQLFluff runtime and local Python development/test dependencies.
The selected source runs in pure Python; optional Rust and external dbt services are not required.

```bash
curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/sqlfluff-get-pip.py
python3 /tmp/sqlfluff-get-pip.py --user --break-system-packages pip==24.3.1
python3 -m pip install --user --break-system-packages -r requirements-cc-solo.txt
python3 -m pip install --user --break-system-packages --no-build-isolation --no-deps -e .
python3 -m pytest -q test/cli/formatters_test.py
```

Select further tests relevant to the changed components, following the repository instructions.
Use explicit dialects and isolated temporary project directories for reproducible local checks.
No remote database, private data, destination credential, Rust build or dbt integration service is supplied by this local environment. Report unavailable broader checks accurately; do not claim they were tested.
