# aqEthnicity (R)

Race and ethnicity **probabilities** from a surname, a first name and an address, for population-level
analysis. A client for the hosted aqEthnicity service: BISG, BIFSG, the STRATA name-and-address model
(five-class probabilities plus an uncertainty index) and an address geocoding check.

> **0.1.0.** Not on CRAN yet; install from GitHub.

```r
# install.packages("remotes")
remotes::install_github("tleitch/aqEthnicity", subdir = "r")
```

## Quick start

```r
library(aqEthnicity)

aq_set_key()          # masked prompt; or set the AEQUUM_API_KEY environment variable. Never printed or logged.

people <- data.frame(surname = c("GARCIA", "CHEN"), first = c("MARIA", "WEI"),
                     address = c("9644 N 10TH AVE", "350 5TH AVE"),
                     city = c("PHOENIX", "NEW YORK"), state = c("AZ", "NY"), zip = c("85021", "10118"))

# a data frame back, with wru-style probability columns (pred.whi, pred.bla, pred.his, pred.asi, pred.oth)
predict_race_aq(people, address = "address", city = "city", state = "state", zip = "zip")

strata("MARIA", "GARCIA", address = "9644 N 10TH AVE", city = "PHOENIX", state = "AZ", zip5 = "85021")
bisg("GARCIA", zcta = "11201")
bifsg("MARIA", "GARCIA", zcta = "11201")
geocode("9644 N 10TH AVE", "PHOENIX", "AZ", "85021")
```

The service address is built in; you never type a URL. (For testing only, the `AEQUUM_BASE_URL`
environment variable overrides it.) In v1 every call is hosted and needs a key.

## Friendly errors

| Situation | What you get |
|---|---|
| No key set | an `aq_error_auth` condition saying how to set one (no request is made) |
| HTTP 401 | `aq_error_auth`: the key was not accepted; check it was pasted in full |
| HTTP 429 | `aq_error_quota`: today's free limit, resets tomorrow (a short-term rate limit is retried) |
| HTTP 422 | `aq_error_input`: the API couldn't read the input, with your row numbers |
| HTTP 503 | waits and retries (the address routes take about five minutes to load after a restart) |
| An unknown argument such as `mname =` | `aq_error_field` before anything is sent: the service would ignore it and score without the data (the middle name is `middle_name`) |

Requests are columnar and sent in batches (default 1,000 records; the service limit is 10,000).
Results come back as data frames in your row order.

## Notes

- Outputs are **statistical estimates for groups of people**, not statements about any individual's race.
- The hosted service does not store the names or addresses you send; it keeps a usage record (key,
  time, route, record count).

## Licence

Apache License 2.0 (`License: Apache License (>= 2)`); see `inst/NOTICE`: the licence covers this client
only, not the hosted service, its models or its data tables.
