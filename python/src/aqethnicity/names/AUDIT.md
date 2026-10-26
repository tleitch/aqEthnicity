# Validation record

Rules in this package were derived from a stratified manual audit of PPP
borrower records, August 2026.

## Design

1,136 records, stratified by assigned race (5) × legal form (5), proportional
allocation with a floor of 12 per cell, seed 20260809. Drawn from 4,767,224
analytic records, all of which had retrievable name tokens.

Four codes: **P** correct, **T** tokenization wrong, **N** not a personal
name, **A** ambiguous.

## What it found

**Single-rater pass (n = 1,136):** P 94.4%, T 2.0%, N 3.4%, A 0.2%.
Kappa and consensus precision require the second rater and are not yet
recorded here.

**The suffix defect.** 18 of 23 tokenization failures had a suffix as the
extracted surname; in 17 the raw string ended in a suffix and the tokenizer
took that final token as the family name. Across the full corpus this
affected 65,716 records (1.38%), and the rate was sharply differential:

| assigned race | affected |
|---|---|
| Asian | 7.87% |
| other | 2.84% |
| White | 1.35% |
| Hispanic | 0.72% |
| Black | 0.44% |

Professional suffixes (`MD`, `CPA`, `PHD`) drove the Asian concentration.
99.8% were recoverable from the raw string.

**What the defect does to downstream inference.** Re-parsing the full corpus
with this package changed the surname on 69,289 records (1.45%), and 68,645
of those were re-scored through the same race model under *identical*
geographic features — once with the old surname, once with the corrected one.
A control pass reproduced the stored predictions at **97.77%**, so the
old-vs-new difference is the parse fix rather than run-to-run drift.

**47.1% of affected records changed predicted race.** Net movement:

| assigned race | net change |
|---|---|
| Asian | −20,894 |
| Black | +17,154 |
| White | +3,924 |
| Hispanic | +364 |
| other | −548 |

The dominant flows were Asian→White (10,738) and Asian→Black (10,612). The
mechanism is that a stranded suffix token (`JR`, `III`, `MD`) is short and
orthographically unusual, and a character-level model reads it as
Asian-looking. Left uncorrected the defect inflates the Asian category by
roughly 6.8% and suppresses Black by about 1%.

**This matters for category counts far more than for regression estimates.**
In the PPP study the errors were close to orthogonal to the outcome, so
excluding affected records moved the headline coefficient by 0.018 points and
correcting them moved it by 0.053. Any analysis whose *estimand is a
composition* — group shares, rates by race, population counts — should assume
the defect is first-order and fix it. Analyses estimating a conditional
mean difference should check, not assume, that it is second-order.

**The business screen.** The term list flagged 6 of 39 true non-persons
(15.4% recall) with **zero** false positives across 1,072 confirmed real
people. Across the corpus it flags 0.73% of records, which forgive at 93.1%
against 85.8% for the rest — consistent with them being genuine businesses.
Applying it moved the headline by 0.043 points.

**What no rule catches.** 33 of 39 non-persons contained no business keyword
at all, and 97.4% had their first token extracted correctly, so the extractor
"worked." These are trade names that read like people. No pattern separates
them from genuine names, and roughly 3% of a screened corpus should be
expected to remain misclassified. Report it rather than chase it.

## Reproducing

`nameparse.audit.draw_sample` with the parameters above regenerates the frame
given the same seed and corpus.
