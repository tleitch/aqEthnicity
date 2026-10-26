# aqEthnicity

Race and ethnicity **probabilities** from a name and a place, for population-level analysis, in **Python** and **R**.
Both clients talk to the hosted aqEthnicity service (the STRATA name-and-address model with an uncertainty index, and an
address geocoding check); the Python client also runs BISG and BIFSG locally through
[pyethnicity](https://github.com/CangyuanLi/pyethnicity). The service address is built in; you never type a URL.

| | Install | Docs |
|---|---|---|
| **Python** (`import aqethnicity as aq`) | `pip install "aqethnicity[local]"` | [`python/README.md`](python/README.md), [`python/CHANGELOG.md`](python/CHANGELOG.md) |
| **R** (`library(aqEthnicity)`) | `remotes::install_github("tleitch/aqEthnicity", subdir = "r")` | [`r/README.md`](r/README.md) |

Runnable, made-up-data examples for both languages: [aqethnicity-examples](https://github.com/tleitch/aqethnicity-examples).

## Quick start

```python
import aqethnicity as aq
aq.set_api_key("...")            # or the AEQUUM_API_KEY environment variable; never printed or logged
aq.strata(["MARIA"], ["GARCIA"], address=["9644 N 10TH AVE"], city=["PHOENIX"], state=["AZ"], zip5=["85021"])
aq.bisg("GARCIA", zcta="11201")  # local and free: needs the `local` extra
```

```r
library(aqEthnicity)
aq_set_key()                     # masked prompt, or the AEQUUM_API_KEY environment variable
strata("MARIA", "GARCIA", address = "9644 N 10TH AVE", city = "PHOENIX", state = "AZ", zip5 = "85021")
```

An API key is needed for the hosted calls. Until self-service registration is live, email terry@aequum.ai for a free key.

## Layout

```
python/    the Python package (PyPI: aqEthnicity, import aqethnicity)
r/         the R package (aqEthnicity; install with subdir = "r")
scripts/   scan_secrets.py: fails if the tree or full git history holds a key-shaped string
```

## Notes

- Outputs are **statistical estimates for groups of people**, not statements about any individual's race, and must not
  be used for decisions about individuals.
- The hosted service does not store the names or addresses you send; it keeps a usage record (key, time, route, record count).

## Licence

[Apache License 2.0](LICENSE) for the client code in this repository. The hosted service, its models and its data tables
are not covered by it (see [NOTICE](NOTICE)).
