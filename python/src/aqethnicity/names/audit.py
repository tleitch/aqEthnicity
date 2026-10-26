"""Stratified manual-audit toolkit: draw a sample, rate it, score it.

Generalised from the PPP name-extraction audit. Nothing here is PPP-specific;
supply your own frame and stratification columns.
"""
import csv
import os
import shutil
import tempfile

import numpy as np
import pandas as pd

CODES = {"p":"P","t":"T","n":"N","a":"A"}
LABEL = {"P":"personal name, correctly tokenized",
         "T":"personal name, tokenization wrong",
         "N":"not a personal name",
         "A":"ambiguous"}

def draw_sample(df, strata, *, name_col, first_col, last_col,
                target=1000, min_cell=12, seed=20260809, extra_cols=()):
    """Stratified sample with a floor, so small cells stay estimable.

    Returns a sheet with blank verdict columns, ready for two raters.
    """
    cells = df.groupby(list(strata)).size().rename("N").reset_index()
    cells = cells[cells.N > 0].copy()
    prop = (cells.N / cells.N.sum() * target).round().astype(int)
    cells["n"] = np.maximum(np.minimum(prop, cells.N), np.minimum(min_cell, cells.N))
    parts = []
    for r in cells.itertuples():
        mask = np.ones(len(df), bool)
        for s in strata:
            mask &= (df[s] == getattr(r, s)).values
        parts.append(df[mask].sample(n=int(r.n), random_state=seed))
    s = pd.concat(parts, ignore_index=True).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    s.insert(0, "audit_id", [f"A{i+1:04d}" for i in range(len(s))])
    keep = ["audit_id", name_col, first_col, last_col] + list(strata) + list(extra_cols)
    sheet = s[[c for c in keep if c in s.columns]].copy()
    sheet = sheet.rename(columns={name_col:"name_raw", first_col:"extracted_first",
                                  last_col:"extracted_last"})
    for c in ("verdict_rater1","verdict_rater2","notes"): sheet[c] = ""
    return sheet, cells

def wilson(k, n, z=1.96):
    """Wilson score interval; correct at small n and near 0/1, unlike normal."""
    if n == 0: return (float("nan"),)*3
    p = k/n; d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    h = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return 100*p, 100*max(0,c-h), 100*min(1,c+h)

def cohens_kappa(a, b, codes=("P","T","N","A")):
    a, b = pd.Series(list(a)), pd.Series(list(b))
    po = float((a == b).mean())
    pe = sum((a == c).mean()*(b == c).mean() for c in codes)
    return (po - pe)/(1 - pe) if pe < 1 else float("nan"), po

def score_sheet(sheet, strata=()):
    """Agreement, precision with Wilson intervals overall and by stratum.

    Point estimates use consensus rows only. Disagreements are reported, not
    silently resolved, and a conservative bound treats every disagreement as a
    failure -- so the headline cannot be inflated by resolving ties favourably.
    """
    s = sheet.copy()
    for c in ("verdict_rater1","verdict_rater2"):
        s[c] = s[c].fillna("").astype(str).str.strip().str.upper()
    done = s[s.verdict_rater1.isin(CODES.values()) & s.verdict_rater2.isin(CODES.values())]
    if len(done) == 0: return {"n_rated": 0}
    kappa, po = cohens_kappa(done.verdict_rater1, done.verdict_rater2)
    cons = done[done.verdict_rater1 == done.verdict_rater2].copy()
    cons["verdict"] = cons.verdict_rater1
    def blk(d, nm):
        k = int((d.verdict == "P").sum()); p, lo, hi = wilson(k, len(d))
        return dict(stratum=nm, n=len(d), correct=k, pct=p, lo=lo, hi=hi)
    rows = [blk(cons, "ALL")]
    for st in strata:
        for v, g in cons.groupby(st): rows.append(blk(g, f"{st}: {v}"))
    ck = int((cons.verdict == "P").sum())
    cp, clo, chi = wilson(ck, len(done))
    return dict(n_sampled=len(s), n_rated=len(done), n_consensus=len(cons),
                raw_agreement=100*po, kappa=float(kappa), strata=rows,
                distribution={c:int((cons.verdict==c).sum()) for c in CODES.values()},
                conservative=dict(pct=cp, lo=clo, hi=chi),
                confusion=pd.crosstab(done.verdict_rater1, done.verdict_rater2).to_dict())

def rate_cli(path, rater, *, show_cols=()):
    """Keystroke rater. Saves after every entry; resumable; blind to the other
    rater's column, since agreement is part of the result."""
    import sys
    import termios
    import tty
    col = f"verdict_{rater}"
    B,D,Y,C,G,R = "\033[1m","\033[2m","\033[33m","\033[36m","\033[32m","\033[0m"
    def load():
        with open(path, newline="", encoding="utf-8") as f:
            rd = csv.DictReader(f); return list(rd), rd.fieldnames
    def save(rows, cols):
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".csv"); os.close(fd)
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
        shutil.move(tmp, path); os.chmod(path, 0o644)
    def key():
        fd = sys.stdin.fileno(); old = termios.tcgetattr(fd)
        try: tty.setraw(fd); return sys.stdin.read(1)
        finally: termios.tcsetattr(fd, termios.TCSADRAIN, old)
    rows, cols = load()
    if col not in cols: raise SystemExit(f"{path} has no column {col}")
    todo = [i for i,r in enumerate(rows) if not (r.get(col) or "").strip()]
    done0 = len(rows) - len(todo)
    print(f"\n{B}manual audit -- {rater}{R}\n{done0:,}/{len(rows):,} already scored\n")
    for k,v in LABEL.items(): print(f"  {B}{k.lower()}{R} {v}")
    print(f"  {B}u{R} undo   {B}q{R} save and quit\n"); input("Enter to begin ")
    hist, k = [], 0
    while k < len(todo):
        i = todo[k]; r = rows[i]
        os.system("clear")
        print(f"{D}{r.get('audit_id','')}   {done0+k:,}/{len(rows):,}"
              f"  ({100*(done0+k)/len(rows):.1f}%)   {rater}{R}\n")
        print(f"  {D}raw{R}\n    {B}{Y}{r.get('name_raw','')}{R}\n")
        print(f"  {D}extracted{R}\n    first  {C}{r.get('extracted_first','')}{R}"
              f"\n    last   {C}{r.get('extracted_last','')}{R}\n")
        for c in show_cols:
            if c in r: print(f"  {D}{c}: {r[c]}{R}")
        print(f"\n  {D}p ok   t tokenization wrong   n not a person   a ambiguous   u undo   q quit{R}")
        ch = key().lower()
        if ch == "q": break
        if ch == "u":
            if hist: j = hist.pop(); rows[j][col] = ""; k -= 1; save(rows, cols)
            continue
        if ch not in CODES: continue
        rows[i][col] = CODES[ch]; hist.append(i); k += 1; save(rows, cols)
    save(rows, cols)
    left = sum(1 for r in rows if not (r.get(col) or "").strip())
    os.system("clear"); print(f"\n{G}saved{R}  {len(rows)-left:,}/{len(rows):,} scored by {rater}\n")
