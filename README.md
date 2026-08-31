# DepZero

**Know every dependency. Remove what you don't need. Prove what's left.**

DepZero is a zero-install, zero-third-party-runtime-dependency developer tool for static dependency auditing. It discovers Python and JavaScript/TypeScript source, classifies imports, compares observed external imports with manifests, suggests standard-library migration options, generates graphs and escape plans, and creates deterministic static dependency proofs.

## The problem
Dependency manifests tell you what is declared, not necessarily what source actually references. Grep misses Python syntax details and can produce false positives. Heavy auditing tools can themselves require installation. DepZero is designed for the opposite constraint: one Python file, the standard library, and static analysis only.

## 30-second demo

```powershell
python depzero.py scan examples\python_with_dependencies
python depzero.py suggest examples\python_with_dependencies
python depzero.py check examples\clean_python
python depzero.py check .
```

## Requirements / installation
Python **3.11+**. There is no `pip install` step and no runtime dependency manifest is required.

```powershell
git clone <your-repository-url>
cd depzero
python depzero.py scan .
```

## Commands

```text
python depzero.py scan PATH
python depzero.py check PATH
python depzero.py suggest PATH
python depzero.py explain DEPENDENCY
python depzero.py graph PATH
python depzero.py graph PATH --format dot
python depzero.py proof PATH --output DEPENDENCY_PROOF.txt
python depzero.py stats PATH
python depzero.py escape PATH
python depzero.py --help
python depzero.py --version
```

`scan` reports source locations and manifest mismatches. `check` is CI-friendly: exit 0 on a clean static audit and 1 when external imports are detected. `--json` emits machine-readable output without ANSI noise. `--exclude PATTERN`, `--language`, `--no-color`, and `--verbose` are available on project commands.

## How it works
1. Recursively discover supported source files while ignoring common generated/vendor directories.
2. Parse Python with `ast` and record import module, source file, line, import form, and relative level.
3. Classify Python imports using `sys.stdlib_module_names`, discovered local modules/packages, and conservative fallback rules.
4. Lexically scan JS/TS for common static imports, `require()` and literal dynamic imports. Relative paths are local; known Node built-ins are standard; package specifiers are external.
5. Parse `requirements.txt`, `pyproject.toml`, and `package.json` using standard-library parsers.
6. Compare *observed* external imports against *declared* runtime dependencies with careful language such as “apparently undeclared” and “not observed in scanned source.”

## Security model
Scanned repositories are untrusted. DepZero does **not** import target modules, execute Python/JavaScript, call pip/npm, run package scripts, use `eval`/`exec`, or execute project subprocesses. Symlinked directories are not followed. Malformed and unreadable files are reported as warnings instead of terminating the whole scan.

## Accuracy and limitations
DepZero is deterministic static analysis, not a runtime dependency oracle. Dynamic imports whose target cannot be seen statically, plugin discovery, generated code, environment-specific loading, native binaries, and dependencies used only outside scanned languages may not be observable. JavaScript/TypeScript analysis is intentionally conservative because Python's standard library has no full JS parser. “Declared but not observed” does **not** mean unused.

## Zero-dependency engineering
See [STDLIB.md](STDLIB.md) for the engineering log. DepZero uses `argparse`, `ast`, `dataclasses`, `fnmatch`, `hashlib`, `json`, `os`, `pathlib`, `re`, `shutil`, `sys`, `tomllib`, `typing`, and `unittest` instead of third-party packages.

## Testing

```powershell
python -m unittest discover -s tests -v
```

Tests cover Python AST behavior, local/stdlib/external classification, syntax failures, JS imports, manifests, ignored directories, graphs, deterministic proofs, migration ordering, JSON, and exit codes.

## Proof generation

```powershell
python depzero.py proof . --output DEPENDENCY_PROOF.txt
```

The proof contains sorted observed stdlib modules, manifest status, a deterministic SHA-256 over scanned source paths/content, PASS/FAIL, and the static-analysis limitation. No timestamp is inserted.

## Performance
DepZero performs a single filesystem walk and parses supported source files in-process. Files above 5 MiB are skipped with a warning. No benchmark numbers are claimed here because repository and hardware characteristics vary.

## Hackathon compliance
Built for Zero Dependency 2026, Track A — Developer Tools & CLI. Runtime uses Python 3.11+ standard library only. The primary executable is the single file `depzero.py`; tests, examples and documentation are separate. DepZero can self-audit with `python depzero.py check .`.

## Bonus positioning
- **Single File:** runtime implementation is `depzero.py`.
- **Package Killer:** curated, honest migration guidance for common packages.
- **STDLIB Log:** `STDLIB.md` documents meaningful substitutions.
- **Proof:** deterministic evidence generated by DepZero itself.

## Roadmap
Potential future work: stronger JS/TS tokenization, additional language analyzers, richer manifest mapping between import names and distribution names, configurable dependency-name aliases, and optional SARIF output—all while preserving a zero-dependency core.

## License
MIT. See `LICENSE`.

## Optional Local Web Dashboard

DepZero also includes an optional browser dashboard implemented entirely with the Python standard library and vanilla HTML/CSS/JavaScript. It does not require Flask, FastAPI, React, npm, pip, or any external package.

```bash
python web_ui.py
```

Then open `http://127.0.0.1:8765` if your browser does not open automatically. Enter a local project path and click **Scan Project**.

The CLI remains the canonical hackathon interface; the dashboard is an optional visualization layer over the same `scan_project()` analysis engine.
