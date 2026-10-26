# Changelog

## 0.1.0 (2026-10-26)

First public release of **aqEthnicity** (import name `aqethnicity`), built from the internal `aequum` client (0.0.4.dev0).

### Added
- `aqethnicity.strata()` (and `strataname`, `stratazcta`, `stratatract`, `stratabgt`), `geocode()` and `tier_coverage()`: the hosted aqEthnicity STRATA model (five-class probabilities, an uncertainty index, address input). These need an API key: `aqethnicity.set_api_key(...)` or the `AEQUUM_API_KEY` environment variable. The key is never printed or logged.
- The service address is built in. The only override is the `AEQUUM_BASE_URL` environment variable, for testing.
- Friendly errors: no key, HTTP 401, 429, 422 (with your row numbers), and a wait-and-retry for HTTP 503 after a service restart.
- Unknown fields such as `mname=` are refused before anything is sent (the service would ignore them and score without that data); the middle name is `middle_name`.
- A response whose row count differs from the request is refused rather than returned misaligned.
- pyethnicity-compatible `bisg`, `bisg6`, `bifsg`, `bifsg6`, `predict_race`, `predict_race_fl`, `predict_race_flg` run **locally** through pyethnicity (install with `pip install "aqethnicity[local]"`); pyethnicity's own tables and models are used as installed, not re-bundled. Passing an address instead of a GEOID sends that call to the hosted service.
- `predict_sex_f` and `predict_sex_ssa` run on the hosted service.

### Changed
- The distribution is renamed from `aequum` to `aqEthnicity` (import `aqethnicity`). Prefixed `aequum_*` aliases are removed; the base URL can no longer be passed as an argument.
- Licence: Apache-2.0 (see `LICENSE` and `NOTICE`; the licence covers this client code only, not the hosted service, its models or its data tables).

### Fixed (relative to calling pyethnicity 0.0.27 directly)
Measured with pyethnicity 0.0.27 on polars 1.20, 1.30 and 1.35.2:
- **Row order.** pyethnicity returns the same rows but not in input order, and the order differs from run to run. aqEthnicity returns results in your row order.
- **Row collapse.** pyethnicity returns one row per *distinct* name-and-place key: 300 inputs with 42 distinct keys came back as 42 rows. aqEthnicity returns exactly one row per input row (each distinct key is scored once and mapped back to every input row; rows with a missing name or place come back with empty probabilities).
- **Input types.** pyethnicity rejects pandas Series; aqEthnicity accepts lists, numpy arrays, pandas and polars columns (NaN is treated as missing).
- Values are identical to pyethnicity's for the same key: tests compare 10,000 rows exactly for BISG/BIFSG, and the ML functions to 2e-5 (measured 6e-8, the same as two consecutive pyethnicity calls).
- pyethnicity 0.0.27's `predict_sex_f` raises `TypeError` for every input and its `predict_sex_ssa` calls a removed polars method; both are served by the hosted service here.

### Notes
- Outputs are statistical estimates for groups of people, not statements about any individual's race.
- Requires Python 3.10+ and `polars<=1.35.2` (the ceiling pyethnicity 0.0.27 needs).
