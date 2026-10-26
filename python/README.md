# aqEthnicity

Race and ethnicity **probabilities** from a name and a place, for population-level analysis.
`import aqethnicity as aq`.

```bash
pip install aqethnicity            # STRATA + geocoding (hosted; needs a key)
pip install "aqethnicity[local]"   # + the free local BISG/BIFSG and ML models (pyethnicity)
```

## Quick start

```python
import aqethnicity as aq

# free and local: no key, nothing leaves your machine (needs the `local` extra)
aq.bisg("GARCIA", zcta="11201")
aq.bifsg(["MARIA", "WEI"], ["GARCIA", "CHEN"], zcta=["11201", "94110"])

# aqEthnicity STRATA (hosted): five-class probabilities, an uncertainty index, address input
aq.set_api_key("...")              # or set the AEQUUM_API_KEY environment variable; never printed or logged
aq.strata(["MARIA", "WEI"], ["GARCIA", "CHEN"],
          address=["9644 N 10TH AVE", "350 5TH AVE"], city=["PHOENIX", "NEW YORK"],
          state=["AZ", "NY"], zip5=["85021", "10118"])
```

The service address is built in; you never type a URL. (For testing only, the `AEQUUM_BASE_URL`
environment variable overrides it.)

## What runs where

| Function | Runs | Needs a key |
|---|---|---|
| `bisg`, `bisg6`, `bifsg`, `bifsg6`, `predict_race`, `predict_race_fl`, `predict_race_flg` | **locally**, by [pyethnicity](https://github.com/CangyuanLi/pyethnicity) (its tables and models are used as installed, not re-bundled) | no |
| `strata`, `strataname`, `stratazcta`, `stratatract`, `stratabgt`, `geocode`, `tier_coverage` | hosted | yes |
| `predict_sex_f`, `predict_sex_ssa` | hosted (pyethnicity 0.0.27's own versions fail) | yes |

Pass `address`/`city`/`state`/`zip5` to a local function instead of a GEOID and that call goes to the
hosted service, which resolves the address for you (key required).

**Rows in, rows out.** pyethnicity 0.0.27 does not return one result per input row in your order: it
returns one row per *distinct* name-and-place (300 inputs with 42 distinct keys come back as 42 rows), in an
order that changes between runs, and it rejects pandas columns. aqEthnicity returns exactly one row per input
row, in *your* order (rows with a missing name or place come back with empty probabilities), and the values
are identical to pyethnicity's (tests compare 10,000 rows exactly).

## Friendly errors

| Situation | What you get |
|---|---|
| No key set | `AuthenticationError`: how to set one (no request is made) |
| HTTP 401 | `AuthenticationError`: the key was not accepted; check it was pasted in full |
| HTTP 429 | `QuotaExceeded`: today's free limit, resets tomorrow (a short-term rate limit is retried) |
| HTTP 422 | `BadRequest`: the API couldn't read the input, with your row numbers |
| HTTP 503 | waits and retries (the address routes take about five minutes to load after a service restart) |
| An unknown field such as `mname=` | `BadRequest` before anything is sent: the service would ignore it and score without the data (the middle name is `middle_name`) |

## Notes

- Outputs are **statistical estimates for groups of people**, not statements about any individual's race.
- The hosted service does not store the names or addresses you send; it keeps a usage record (key,
  time, route, record count).
- `output="pandas"` or `"dict"` returns those types instead of polars.
- `aqethnicity.names` and `aqethnicity.ppp` are local tools (name parsing and the PPP study loader);
  they never contact the service.

## Licence

Apache License 2.0 (see `LICENSE` and `NOTICE`). The licence covers this client code only; the hosted
service, its models and its data tables are not covered by it.
