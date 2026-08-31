# DepZero Standard-Library Engineering Log

DepZero deliberately has **zero third-party runtime dependencies**. The core substitutions are:

| Normally used | DepZero uses | Purpose |
|---|---|---|
| Click / Typer | `argparse` | CLI parsing and help |
| Rich / Colorama | ANSI + `sys.stdout.isatty()` | restrained terminal formatting |
| Third-party Python parser | `ast` | accurate Python import parsing |
| NetworkX | `dict`, `list`, `set` | dependency graph representation |
| pytest | `unittest` | automated tests |
| TOML package | `tomllib` | `pyproject.toml` parsing |
| Hashing package | `hashlib` | deterministic SHA-256 proof |
| Filesystem helper | `pathlib` + `os.walk` | project discovery |
| Glob helper | `fnmatch` | user exclusions |
| Data-model library | `dataclasses` | typed internal records |
| JSON package | `json` | config/manifests/CI output |
| Regex package | `re` | conservative JS/TS lexical scanning |

## Trade-offs

`argparse` requires more explicit command wiring than decorator-based CLI frameworks. ANSI formatting is intentionally minimal because DepZero refuses terminal UI dependencies. Python gets a real syntax-tree parser through `ast`; JavaScript/TypeScript cannot, so DepZero documents that scanner as conservative rather than pretending it is a full parser. Graph output implements only what DepZero needs rather than importing a general graph framework. `unittest` is more verbose than pytest but keeps the test suite dependency-free. `tomllib` is read-only, which is sufficient because DepZero only inspects manifests. The proof generator sorts inputs and hashes source content with `hashlib` so its evidence is reproducible without a cryptography package.
