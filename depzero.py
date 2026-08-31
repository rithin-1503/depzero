#!/usr/bin/env python3
"""DepZero: zero-dependency static dependency auditor (Python 3.11+)."""
from __future__ import annotations
import argparse, ast, fnmatch, hashlib, json, os, re, shutil, sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Iterable
try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None

VERSION = "1.0.0"
SOURCE_EXTS = {".py":"python", ".js":"javascript", ".jsx":"javascript", ".ts":"typescript", ".tsx":"typescript"}
IGNORE_DIRS = {".git", ".hg", ".svn", "__pycache__", "node_modules", "venv", ".venv", "env", "dist", "build", "target", "coverage", ".idea", ".vscode"}
NODE_BUILTINS = {"assert","buffer","child_process","cluster","console","crypto","dgram","dns","events","fs","http","http2","https","module","net","os","path","perf_hooks","process","punycode","querystring","readline","repl","stream","string_decoder","timers","tls","tty","url","util","v8","vm","wasi","worker_threads","zlib"}
STDLIB = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}
MAX_FILE_BYTES = 5 * 1024 * 1024

class Category(str, Enum):
    STDLIB="standard_library"; LOCAL="local"; EXTERNAL="third_party"; UNKNOWN="unknown"

@dataclass(frozen=True)
class ImportRecord:
    module: str; file: str; line: int; category: str; import_type: str; relative_level: int = 0

@dataclass
class ManifestDependency:
    name: str; source: str; kind: str = "runtime"

@dataclass
class Finding:
    dependency: str; status: str; detail: str

@dataclass
class ScanResult:
    project: str
    files: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    imports: list[ImportRecord] = field(default_factory=list)
    manifests: list[ManifestDependency] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def external_modules(self): return sorted({i.module for i in self.imports if i.category == Category.EXTERNAL.value})
    def runtime_declared(self): return sorted({m.name for m in self.manifests if m.kind == "runtime"})
    def summary(self):
        cats={c.value:0 for c in Category}
        for i in self.imports: cats[i.category]=cats.get(i.category,0)+1
        return {"files_scanned":len(self.files),"imports":len(self.imports),"stdlib":cats[Category.STDLIB.value],"local":cats[Category.LOCAL.value],"external":cats[Category.EXTERNAL.value],"unknown":cats[Category.UNKNOWN.value]}

SUGGESTIONS = {
"requests":("HTTP client",["urllib.request","urllib.parse","http.client"],"MEDIUM","Lower-level APIs; sessions, retries, and conveniences require extra code."),
"click":("CLI framework",["argparse"],"EASY","argparse is less decorator-oriented but fully standard-library."),
"typer":("Typed CLI framework",["argparse"],"EASY","You implement validation/help wiring explicitly."),
"python-dotenv":("Environment configuration",["os.environ","configparser"],"EASY",".env parsing is not built in; prefer real environment variables or INI config."),
"dotenv":("Environment configuration",["os.environ","configparser"],"EASY",".env parsing is not built in; prefer real environment variables or INI config."),
"colorama":("Terminal colors",["ANSI escape sequences"],"EASY","Terminal capability handling is your responsibility."),
"rich":("Terminal UI",["ANSI escape sequences","shutil.get_terminal_size"],"MEDIUM","Advanced tables/progress/markup require custom rendering."),
"pytest":("Testing",["unittest"],"MEDIUM","Fixture/parametrization ergonomics differ."),
"dateutil":("Date/time utilities",["datetime","zoneinfo"],"MEDIUM","Some parsing and recurrence conveniences need custom code."),
"beautifulsoup4":("HTML parsing",["html.parser"],"MEDIUM","html.parser is lower-level and less forgiving/convenient."),
"bs4":("HTML parsing",["html.parser"],"MEDIUM","html.parser is lower-level and less forgiving/convenient."),
"networkx":("Graph algorithms",["dict/set adjacency structures"],"HARD","Complex graph algorithms must be implemented and tested manually."),
"flask":("Web server/framework",["http.server","socketserver"],"HARD","Routing, middleware, templates, security features, and production serving are not equivalent."),
"watchdog":("Filesystem watching",["pathlib/os.stat polling"],"MEDIUM","Polling is less efficient and less immediate than native event watchers."),
"toml":("TOML parsing",["tomllib"],"EASY","tomllib is read-only and requires Python 3.11+."),
"numpy":("Numerical arrays",[],"HARD","No general stdlib replacement for NumPy's vectorized numerical stack."),
"pandas":("Tabular data analysis",["csv","sqlite3"],"HARD","No equivalent DataFrame abstraction in the standard library."),
"express":("Node web framework",[],"HARD","DepZero's replacement knowledge base focuses on Python stdlib migration."),
"axios":("JavaScript HTTP client",[],"MEDIUM","Browser/Node native fetch may be available, but it is not Python stdlib."),
}

def norm_pkg(name: str) -> str:
    return re.split(r"[<>=!~\[\s]", name.strip(), maxsplit=1)[0].strip().lower().replace("_","-")

def read_text(path: Path, warnings: list[str]) -> str | None:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            warnings.append(f"Skipped large file (>5 MiB): {path}"); return None
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError) as e:
        warnings.append(f"Unreadable file {path}: {e}"); return None

def excluded(rel: str, patterns: list[str]) -> bool:
    p=rel.replace("\\","/")
    return any(fnmatch.fnmatch(p, x) or fnmatch.fnmatch(Path(p).name, x) for x in patterns)

def discover(root: Path, patterns: list[str], language: str|None, warnings: list[str]) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in SOURCE_EXTS and (not language or SOURCE_EXTS[root.suffix.lower()] == language) else []
    out=[]
    try:
        for cur, dirs, files in os.walk(root, followlinks=False):
            curp=Path(cur)
            dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS and not excluded(str((curp/ d).relative_to(root)), patterns) and not (curp/d).is_symlink())
            for name in sorted(files):
                p=curp/name
                try: rel=str(p.relative_to(root))
                except ValueError: rel=str(p)
                lang=SOURCE_EXTS.get(p.suffix.lower())
                if lang and (not language or lang==language) and not excluded(rel, patterns): out.append(p)
    except OSError as e: warnings.append(f"Discovery error: {e}")
    return out

def local_roots(root: Path, files: Iterable[Path]) -> set[str]:
    roots=set()
    base=root if root.is_dir() else root.parent
    for p in files:
        if p.suffix.lower() != ".py": continue
        try: rel=p.relative_to(base)
        except ValueError: rel=p
        if len(rel.parts)==1: roots.add(p.stem)
        else: roots.add(rel.parts[0]); roots.add(p.stem)
    return roots

def classify_python(module: str, level: int, locals_: set[str]) -> str:
    if level: return Category.LOCAL.value
    top=module.split(".")[0]
    if top in locals_: return Category.LOCAL.value
    if top in STDLIB: return Category.STDLIB.value
    if not top or not re.match(r"^[A-Za-z_]\w*$", top): return Category.UNKNOWN.value
    return Category.EXTERNAL.value

def analyze_python(path: Path, base: Path, locals_: set[str], warnings: list[str]) -> list[ImportRecord]:
    text=read_text(path,warnings)
    if text is None: return []
    try: tree=ast.parse(text, filename=str(path))
    except SyntaxError as e:
        warnings.append(f"Python syntax error {path}:{e.lineno}: {e.msg}"); return []
    rel=str(path.relative_to(base)) if path.is_relative_to(base) else str(path)
    out=[]
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                m=a.name.split(".")[0]; out.append(ImportRecord(m,rel,n.lineno,classify_python(m,0,locals_),"import",0))
        elif isinstance(n, ast.ImportFrom):
            m=(n.module or "").split(".")[0]
            if not m and n.names: m=n.names[0].name.split(".")[0]
            out.append(ImportRecord(m or ".",rel,n.lineno,classify_python(m,n.level,locals_),"from",n.level))
    return out

def strip_js_comments(text: str) -> str:
    out=[]; i=0; quote=None
    while i<len(text):
        c=text[i]; n=text[i+1] if i+1<len(text) else ""
        if quote:
            out.append(c)
            if c=="\\" and i+1<len(text): out.append(text[i+1]); i+=2; continue
            if c==quote: quote=None
            i+=1; continue
        if c in "'\"`": quote=c; out.append(c); i+=1; continue
        if c=="/" and n=="/":
            while i<len(text) and text[i]!="\n": i+=1
            out.append("\n"); i+=1; continue
        if c=="/" and n=="*":
            i+=2
            while i+1<len(text) and not(text[i]=="*" and text[i+1]=="/"):
                out.append("\n" if text[i]=="\n" else " "); i+=1
            i+=2; continue
        out.append(c); i+=1
    return "".join(out)

def js_category(spec: str) -> tuple[str,str]:
    if spec.startswith(("./","../","/")): return spec,Category.LOCAL.value
    s=spec[5:] if spec.startswith("node:") else spec
    if s.split("/")[0] in NODE_BUILTINS: return s.split("/")[0],Category.STDLIB.value
    if spec.startswith("@"):
        parts=spec.split("/"); return "/".join(parts[:2]),Category.EXTERNAL.value
    return spec.split("/")[0],Category.EXTERNAL.value

def analyze_js(path: Path, base: Path, warnings: list[str]) -> list[ImportRecord]:
    text=read_text(path,warnings)
    if text is None:return []
    text=strip_js_comments(text); out=[]; rel=str(path.relative_to(base)) if path.is_relative_to(base) else str(path)
    patterns=[
      (re.compile(r"\bimport\s+(?:[\s\S]*?\s+from\s+)?['\"]([^'\"]+)['\"]",re.M),"import"),
      (re.compile(r"\brequire\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"),"require"),
      (re.compile(r"\bimport\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"),"dynamic_import")]
    seen=set()
    for rx,typ in patterns:
        for m in rx.finditer(text):
            key=(m.start(),typ)
            if key in seen: continue
            seen.add(key); spec=m.group(1); mod,cat=js_category(spec); line=text.count("\n",0,m.start())+1
            out.append(ImportRecord(mod,rel,line,cat,typ,0))
    return sorted(out,key=lambda x:(x.line,x.module,x.import_type))

def parse_requirements(path: Path, warnings: list[str]) -> list[ManifestDependency]:
    text=read_text(path,warnings); out=[]
    if text is None:return out
    for raw in text.splitlines():
        s=raw.strip()
        if not s or s.startswith("#") or s.startswith(("-r","--","git+","http:" ,"https:")): continue
        s=s.split("#",1)[0].strip(); name=norm_pkg(s)
        if name: out.append(ManifestDependency(name,str(path.name),"runtime"))
    return out

def parse_pyproject(path: Path,warnings:list[str]) -> list[ManifestDependency]:
    if not tomllib:return []
    try: data=tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as e: warnings.append(f"Malformed pyproject.toml: {e}"); return []
    out=[]
    for d in data.get("project",{}).get("dependencies",[]) or []:
        n=norm_pkg(str(d));
        if n: out.append(ManifestDependency(n,path.name,"runtime"))
    optional=data.get("project",{}).get("optional-dependencies",{}) or {}
    for vals in optional.values():
        for d in vals or []:
            n=norm_pkg(str(d));
            if n: out.append(ManifestDependency(n,path.name,"optional"))
    return out

def parse_package_json(path: Path,warnings:list[str]) -> list[ManifestDependency]:
    try:data=json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:warnings.append(f"Malformed package.json: {e}");return []
    out=[]
    for k,kind in (("dependencies","runtime"),("devDependencies","dev"),("optionalDependencies","optional")):
        for name in (data.get(k,{}) or {}): out.append(ManifestDependency(name.lower(),path.name,kind))
    return out

def analyze_manifests(root: Path,warnings:list[str]) -> list[ManifestDependency]:
    base=root if root.is_dir() else root.parent; out=[]
    for name,parser in (("requirements.txt",parse_requirements),("pyproject.toml",parse_pyproject),("package.json",parse_package_json)):
        p=base/name
        if p.exists() and p.is_file(): out.extend(parser(p,warnings))
    return out

def build_findings(result: ScanResult):
    observed={norm_pkg(i.module) for i in result.imports if i.category==Category.EXTERNAL.value}
    declared={norm_pkg(m.name) for m in result.manifests if m.kind=="runtime"}
    result.findings=[]
    for d in sorted(observed|declared):
        if d in observed and d in declared: status="declared_and_observed"; detail="Declared and observed in scanned source."
        elif d in observed: status="observed_apparently_undeclared"; detail="Observed external import, apparently undeclared in a runtime manifest."
        else: status="declared_not_observed"; detail="Declared runtime dependency, not observed in scanned source."
        result.findings.append(Finding(d,status,detail))

def scan_project(path: str, excludes=None, language=None) -> ScanResult:
    root=Path(path).expanduser().resolve(); cli_excludes=list(excludes or [])
    if not root.exists(): raise FileNotFoundError(path)
    config_base=root if root.is_dir() else root.parent
    config_excludes=[]
    config_path=config_base / ".depzero.json"
    if config_path.exists():
        try:
            cfg=json.loads(config_path.read_text(encoding="utf-8"))
            config_excludes=list(cfg.get("exclude",[]) or [])
            if language is None and len(cfg.get("languages",[]) or []) == 1:
                language=cfg["languages"][0]
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    excludes=cli_excludes if cli_excludes else config_excludes
    result=ScanResult(str(root)); files=discover(root,excludes,language,result.warnings); base=root if root.is_dir() else root.parent
    result.files=[str(p.relative_to(base)) if p.is_relative_to(base) else str(p) for p in files]
    result.languages=sorted({SOURCE_EXTS[p.suffix.lower()] for p in files})
    locals_=local_roots(root,files)
    for p in files:
        if p.suffix.lower()==".py": result.imports.extend(analyze_python(p,base,locals_,result.warnings))
        else: result.imports.extend(analyze_js(p,base,result.warnings))
    result.imports.sort(key=lambda x:(x.file,x.line,x.module,x.import_type))
    result.manifests=analyze_manifests(root,result.warnings); build_findings(result); return result

def result_json(r:ScanResult):
    return {"tool":"depzero","version":VERSION,"project":r.project,"languages":r.languages,"summary":r.summary(),"dependencies":[asdict(i) for i in r.imports],"manifests":[asdict(m) for m in r.manifests],"findings":[asdict(f) for f in r.findings],"warnings":r.warnings,"result":"pass" if not r.external_modules() else "fail"}

def ansi(s,code,use): return f"\033[{code}m{s}\033[0m" if use else s

def use_color(args): return not getattr(args,"no_color",False) and sys.stdout.isatty() and not getattr(args,"json",False)

def print_scan(r,args):
    if getattr(args,"json",False): print(json.dumps(result_json(r),indent=2,sort_keys=True)); return
    c=use_color(args); s=r.summary(); print("# DEPZERO PROJECT AUDIT\n"); print(f"Project: {r.project}"); print(f"Languages: {', '.join(r.languages) or 'None detected'}"); print(f"Files scanned: {s['files_scanned']}"); print(f"Imports detected: {s['imports']}\n")
    print("## DEPENDENCY SUMMARY\n"); print(f"Standard library {s['stdlib']}\nLocal modules     {s['local']}\nThird-party       {s['external']}\nUnknown           {s['unknown']}\n")
    print("## THIRD-PARTY DEPENDENCIES\n")
    ext=r.external_modules()
    if not ext: print("None detected.\n")
    for d in ext:
        print(ansi(d,"31",c));
        for i in r.imports:
            if i.category==Category.EXTERNAL.value and i.module==d: print(f"  {i.file}:{i.line}")
        print()
    print("## MANIFEST FINDINGS\n")
    if not r.findings: print("No runtime manifest findings.\n")
    for f in r.findings: print(f"{f.dependency}: {f.detail}")
    print("\n## RESULT\n"); print(f"{len(ext)} external dependencies detected." if ext else ansi("[PASS] ZERO EXTERNAL RUNTIME DEPENDENCIES DETECTED","32",c))
    if r.warnings and getattr(args,"verbose",False):
        print("\n## WARNINGS"); [print(f"- {w}") for w in r.warnings]

def print_check(r,args):
    ext=r.external_modules()
    if getattr(args,"json",False): print(json.dumps({"tool":"depzero","version":VERSION,"external":ext,"result":"pass" if not ext else "fail"},indent=2,sort_keys=True)); return
    c=use_color(args); print("# DEPZERO ZERO-DEPENDENCY CHECK\n"); print(f"Files scanned: {len(r.files)}"); print(f"External runtime dependencies detected: {len(ext)}\n")
    if ext:
        print(ansi(f"[FAIL] {len(ext)} EXTERNAL RUNTIME DEPENDENCIES DETECTED","31",c));
        for d in ext:
            print(f"\n{d}"); [print(f"  {i.file}:{i.line}") for i in r.imports if i.category==Category.EXTERNAL.value and i.module==d]
    else: print(ansi("[PASS] ZERO EXTERNAL RUNTIME DEPENDENCIES DETECTED","32",c))

def suggestion_for(name): return SUGGESTIONS.get(norm_pkg(name))

def print_suggestion(name):
    s=suggestion_for(name); print(f"# {name}\n")
    if not s: print("No curated standard-library migration entry is available.\nThis does not mean the package is unnecessary or replaceable."); return
    purpose,alts,diff,trade=s; print(f"Category:\n{purpose}\n\nStandard-library options:")
    print("\n".join(alts) if alts else "No general Python standard-library equivalent.")
    print(f"\nMigration difficulty:\n{diff}\n\nTrade-offs:\n{trade}")

def print_suggest(r):
    print("# DEPZERO STANDARD-LIBRARY SUGGESTIONS\n")
    ext=r.external_modules()
    if not ext: print("No external dependencies detected."); return
    for d in ext:
        s=suggestion_for(d); print(d)
        if s:
            purpose,alts,diff,trade=s; print(f"  Purpose: {purpose}\n  Alternatives: {', '.join(alts) if alts else 'No general stdlib equivalent'}\n  Migration: {diff}\n  Trade-offs: {trade}")
        else: print("  No curated replacement entry. Review manually.")
        print()

def graph_text(r,fmt="ascii"):
    byfile={}
    for i in r.imports: byfile.setdefault(i.file,[]).append(i)
    if fmt=="dot":
        lines=["digraph depzero {","  rankdir=LR;"]
        for f in sorted(byfile):
            for i in sorted(byfile[f],key=lambda x:(x.module,x.line)):
                lines.append(f"  {json.dumps(f)} -> {json.dumps(i.module)} [label={json.dumps(i.category)}];")
        return "\n".join(lines+["}"])
    lines=[]
    for f in sorted(byfile):
        lines.append(f)
        imps=sorted(byfile[f],key=lambda x:(x.module,x.line))
        for idx,i in enumerate(imps): lines.append(("`-- " if idx==len(imps)-1 else "+-- ")+f"{i.module} [{i.category.upper()}]")
        lines.append("")
    return "\n".join(lines).rstrip() or "No imports detected."

def escape_text(r):
    ext=r.external_modules(); rank={"EASY":0,"MEDIUM":1,"HARD":2}; rows=[]
    for d in ext:
        s=suggestion_for(d)
        if s: rows.append((rank[s[2]],d,s))
        else: rows.append((99,d,None))
    rows.sort(key=lambda x:(x[0],x[1])); replaceable=sum(bool(x[2] and x[2][1]) for x in rows)
    out=["# DEPENDENCY ESCAPE PLAN","",f"External dependencies detected: {len(ext)}",""]
    for n,(_,d,s) in enumerate(rows,1):
        out.append(f"{n}. {d}")
        if s:
            _,alts,diff,trade=s; out += [f"Replacement: {', '.join(alts) if alts else 'No general stdlib equivalent'}",f"Migration difficulty: {diff}",f"Trade-offs: {trade}",""]
        else: out += ["Replacement: No curated entry","Migration difficulty: UNKNOWN",""]
    out += ["RECOMMENDED MIGRATION ORDER", " -> ".join(d for _,d,_ in rows) if rows else "No migration required.", "", f"Potentially replaceable: {replaceable} of {len(ext)}"]
    if ext and replaceable==len(ext): out.append(f"Potential external dependency count: {len(ext)} -> 0 (subject to application-specific trade-offs).")
    return "\n".join(out)

def proof_text(r):
    base=Path(r.project); base=base if base.is_dir() else base.parent
    std=sorted({i.module for i in r.imports if i.category==Category.STDLIB.value}); ext=r.external_modules()
    h=hashlib.sha256()
    for rel in sorted(r.files):
        p=base/rel
        try:
            data=p.read_bytes(); h.update(rel.replace("\\","/").encode()); h.update(b"\0"); h.update(data); h.update(b"\0")
        except OSError: pass
    declared=r.runtime_declared()
    out=["# DEPZERO STATIC DEPENDENCY PROOF","",f"Project: {r.project}",f"Scanner: DepZero {VERSION}",f"Python: {sys.version_info.major}.{sys.version_info.minor}+",f"Files scanned: {len(r.files)}",f"Third-party runtime dependencies detected: {len(ext)}","","STANDARD-LIBRARY MODULES OBSERVED"]
    out += std or ["None"]
    out += ["","MANIFEST STATUS"]
    out += (["No third-party runtime dependencies declared."] if not declared else ["Declared runtime dependencies: "+", ".join(declared)])
    out += ["","SOURCE HASH","SHA-256:",h.hexdigest(),"","RESULT","PASS" if not ext else "FAIL","",("ZERO EXTERNAL RUNTIME DEPENDENCIES DETECTED BY DEPZERO STATIC ANALYSIS." if not ext else f"{len(ext)} EXTERNAL DEPENDENCIES DETECTED BY DEPZERO STATIC ANALYSIS."),"","IMPORTANT LIMITATION","This report is based on deterministic static analysis.","Dynamic runtime loading or dependencies not represented in scanned source may not be observable."]
    return "\n".join(out)+"\n"

def stats_text(r):
    s=r.summary(); counts={lang:0 for lang in r.languages}
    for f in r.files:
        lang=SOURCE_EXTS.get(Path(f).suffix.lower()); counts[lang]=counts.get(lang,0)+1
    files_ext=len({i.file for i in r.imports if i.category==Category.EXTERNAL.value})
    lines=["# PROJECT STATISTICS","",f"Source files: {len(r.files)}"]
    lines += [f"{k.title()} files: {v}" for k,v in sorted(counts.items())]
    lines += [f"Imports observed: {s['imports']}","",f"Standard library: {s['stdlib']}",f"Local modules: {s['local']}",f"External dependencies: {s['external']}",f"Unknown: {s['unknown']}","",f"Files with external deps: {files_ext}"]
    return "\n".join(lines)

def add_common(p):
    p.add_argument("path"); p.add_argument("--exclude",action="append",default=[]); p.add_argument("--language",choices=["python","javascript","typescript"]); p.add_argument("--no-color",action="store_true"); p.add_argument("--verbose",action="store_true"); p.add_argument("--quiet",action="store_true"); p.add_argument("--json",action="store_true")

def parser():
    ep="Examples:\n  python depzero.py scan .\n  python depzero.py check .\n  python depzero.py proof . --output DEPENDENCY_PROOF.txt"
    p=argparse.ArgumentParser(prog="depzero",description="Zero-install static dependency auditing and verification.",epilog=ep,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version",action="version",version=f"DepZero {VERSION}"); sp=p.add_subparsers(dest="command",required=True)
    for name,help_ in (("scan","Audit project dependencies"),("check","Fail if external dependencies are detected"),("suggest","Suggest stdlib replacements"),("stats","Show project statistics"),("escape","Generate migration order")):
        q=sp.add_parser(name,help=help_); add_common(q)
    q=sp.add_parser("graph",help="Generate dependency graph"); add_common(q); q.add_argument("--format",choices=["ascii","dot"],default="ascii"); q.add_argument("--output")
    q=sp.add_parser("proof",help="Generate deterministic dependency proof"); add_common(q); q.add_argument("--output",default="DEPENDENCY_PROOF.txt")
    q=sp.add_parser("explain",help="Explain a dependency and migration options"); q.add_argument("dependency")
    return p

def main(argv=None):
    args=parser().parse_args(argv)
    if args.command=="explain": print_suggestion(args.dependency); return 0
    try:r=scan_project(args.path,args.exclude,args.language)
    except FileNotFoundError: print(f"depzero: path not found: {args.path}",file=sys.stderr); return 2
    except Exception as e: print(f"depzero: analysis failure: {e}",file=sys.stderr); return 3
    if args.command=="scan": print_scan(r,args); return 0
    if args.command=="check": print_check(r,args); return 1 if r.external_modules() else 0
    if args.command=="suggest": print_suggest(r); return 0
    if args.command=="stats":
        if args.json: print(json.dumps({"tool":"depzero","version":VERSION,"summary":r.summary()},indent=2,sort_keys=True))
        else: print(stats_text(r)); return 0
    if args.command=="escape": print(escape_text(r)); return 0
    if args.command=="graph":
        text=graph_text(r,args.format)
        if args.output: Path(args.output).write_text(text+"\n",encoding="utf-8")
        else: print(text)
        return 0
    if args.command=="proof":
        text=proof_text(r); Path(args.output).write_text(text,encoding="utf-8");
        if not args.quiet: print(f"Wrote deterministic proof: {args.output}")
        return 1 if r.external_modules() else 0
    return 2

if __name__=="__main__": raise SystemExit(main())
