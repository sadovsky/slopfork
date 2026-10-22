#!/usr/bin/env python3
"""Leak audit for slopfork cleanroom mode.

--mode spec : audit spec documents (markdown) for source leakage:
              code fences, private identifiers from the source, and long
              verbatim token runs shared with the source.
--mode code : audit target code for long token runs shared with the source
              (after identifier normalization, so renamed copies still match).

Output never includes source text, only locations in the audited files and
the matching source file, so the report is safe to hand to the clean side.
Exit status is 1 if anything is flagged.
"""

import argparse
import os
import re
import sys

SOURCE_EXTS = {".py", ".pyx", ".pxd", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java", ".kt",
               ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift", ".scala", ".m"}
DOC_EXTS = {".md", ".rst", ".txt", ".adoc"}
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|==|!=|<=|>=|->|=>|\*\*|//|[^\sA-Za-z0-9_]")
# Language keywords survive identifier normalization in code mode, so structure still matches.
KEYWORDS = set("""
and as break case catch class const continue def del do elif else enum except export extends false finally fn for
from func function if impl import in is let loop match mod mut new nil none not null or pass pub raise return self
static struct switch this throw trait true try type use var while with yield async await lambda
""".split())


def walk(root, exts):
    if os.path.isfile(root):
        yield root
        return
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if not x.startswith(".") and x not in ("node_modules", "target", "dist", "build")]
        for f in files:
            if os.path.splitext(f)[1] in exts:
                yield os.path.join(d, f)


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def tokens_with_lines(text, normalize_idents):
    out = []
    for m in TOKEN.finditer(text):
        t = m.group(0)
        line = text.count("\n", 0, m.start()) + 1
        if normalize_idents and IDENT.fullmatch(t) and t not in KEYWORDS:
            t = "ID"
        out.append((t.lower() if not normalize_idents else t, line))
    return out


def shingles(toks, n):
    return {tuple(t for t, _ in toks[i:i + n]): toks[i][1] for i in range(len(toks) - n + 1)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="sealed source dir")
    ap.add_argument("--against", required=True, help="spec dir (spec mode) or target code dir (code mode)")
    ap.add_argument("--mode", choices=["spec", "code"], required=True)
    ap.add_argument("--allow-identifiers-from", action="append", default=[],
                    help="public docs dirs/files; their identifiers and text are not counted as leaks")
    ap.add_argument("--allow", action="append", default=[], help="extra allowed identifiers")
    ap.add_argument("--ngram", type=int, default=0, help="shared-run length to flag (default 12 spec, 25 code)")
    args = ap.parse_args()
    n = args.ngram or (12 if args.mode == "spec" else 25)

    src_files = list(walk(args.source, SOURCE_EXTS))
    if not src_files:
        sys.exit(f"no source files under {args.source}")
    normalize = args.mode == "code"
    src_index = {}
    src_idents = set()
    for f in src_files:
        text = read(f)
        src_idents.update(IDENT.findall(text))
        rel = os.path.relpath(f, args.source)
        for sh, line in shingles(tokens_with_lines(text, normalize), n).items():
            src_index.setdefault(sh, (rel, line))

    # Identifiers and verbatim runs that appear in public docs are not leaks.
    public = set(args.allow)
    public_shingles = set()
    for p in args.allow_identifiers_from:
        for f in walk(p, DOC_EXTS | SOURCE_EXTS):
            text = read(f)
            public.update(IDENT.findall(text))
            public_shingles.update(shingles(tokens_with_lines(text, normalize), n))

    against_exts = DOC_EXTS if args.mode == "spec" else SOURCE_EXTS
    findings = []
    for f in walk(args.against, against_exts):
        text = read(f)
        if args.mode == "spec":
            for m in re.finditer(r"^```", text, re.M):
                findings.append((f, text.count("\n", 0, m.start()) + 1, "code fence in spec"))
            private = set()
            for ident in set(IDENT.findall(text)):
                # Only flag identifiers that look code-like and are not public.
                code_like = "_" in ident.strip("_") or re.search(r"[a-z][A-Z]", ident) or ident.startswith("_")
                if code_like and ident in src_idents and ident not in public:
                    private.add(ident)
            for ident in sorted(private):
                line = text.count("\n", 0, text.find(ident)) + 1
                findings.append((f, line, f"private source identifier '{ident}'"))
        toks = tokens_with_lines(text, normalize)
        last_flag_line = -10
        for sh, line in shingles(toks, n).items():
            if sh in src_index and sh not in public_shingles and line > last_flag_line + 3:
                srel, sline = src_index[sh]
                findings.append((f, line, f"{n}-token run shared with source {srel}:{sline}"))
                last_flag_line = line

    for f, line, why in sorted(findings):
        print(f"{f}:{line}: {why}")
    print(f"\nleak audit ({args.mode}): {len(findings)} finding(s) across {len(src_files)} source files")
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
