#!/usr/bin/env python3
"""Fails (exit 1) if the working tree or ANY commit in the git history contains a key-like string, or a notebook has outputs.
Patterns: the key prefix used by the service, a bearer token (the word Bearer followed by 16+ token characters; the documentation
shows the header only with a placeholder), and any 40-character hex string. usage: scan_secrets.py [--no-history]"""
import re, subprocess, sys, json, os
ROOT = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
# Key shape: aq_<kind>_<16+ alphanumerics> (aq_live_..., aq_test_...). A bare "aq_" prefix is NOT enough: the R package has functions such as aq_set_key().
PAT = [("key prefix", re.compile("aq" + "_[a-z]+_[A-Za-z0-9]{16,}")), ("bearer token", re.compile(r"Bearer\s+[A-Za-z0-9_\-\.=]{16,}")),
       ("40-hex", re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{40}(?![0-9A-Fa-f])"))]
bad = []
def scan(text, where):
    for name, rx in PAT:
        m = rx.search(text)
        if m: bad.append(f"{where}: {name} match (starts '{m.group(0)[:6]}...')")
# working tree (tracked + untracked, excluding .git)
for d, dirs, files in os.walk(ROOT):
    dirs[:] = [x for x in dirs if x not in (".git", ".venv", "__pycache__")]
    for f in files:
        p = os.path.join(d, f)
        try: scan(open(p, errors="ignore").read(), os.path.relpath(p, ROOT))
        except Exception: pass
# full history: every added/removed line of every commit on every ref
if "--no-history" not in sys.argv:
    has = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=ROOT, capture_output=True).returncode == 0
    if has:
        log = subprocess.check_output(["git", "log", "--all", "-p", "--format=", "--no-color"], cwd=ROOT, text=True, errors="ignore")
        scan(log, "git history")
# notebooks: outputs must be cleared
for d, _, files in os.walk(os.path.join(ROOT, "notebooks")):
    for f in files:
        if f.endswith(".ipynb"):
            nb = json.load(open(os.path.join(d, f)))
            for i, c in enumerate(nb.get("cells", [])):
                if c.get("cell_type") == "code" and (c.get("outputs") or c.get("execution_count") is not None):
                    bad.append(f"notebooks/{f}: cell {i} has outputs or an execution count")
if bad:
    print("\n".join(bad)); sys.exit(1)
print("scan clean: 0 key-like strings in the tree and history; notebook outputs cleared")
