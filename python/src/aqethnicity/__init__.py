"""aqEthnicity: race/ethnicity probabilities from name and geography.

Drop-in superset of ``pyethnicity``::

    import aqethnicity as aq
    aq.bisg("GARCIA", zcta="11201")            # local, free: needs  pip install 'aqethnicity[local]'

and the aqEthnicity STRATA model (hosted; needs a key), which adds 5-class posteriors, an
uncertainty index and address input::

    aq.set_api_key("...")                      # or set the AEQUUM_API_KEY environment variable
    aq.strata("MARIA", "GARCIA", address="9644 N 10TH AVE", city="PHOENIX",
              state="AZ", zip5="85021")

The service address is built in. The only override is the ``AEQUUM_BASE_URL`` environment
variable, for testing. The key is never printed or logged.
"""

from __future__ import annotations

__version__ = "0.1.0"

from . import names, ppp
from ._api import (
    bifsg,
    bifsg6,
    bisg,
    bisg6,
    geocode,
    predict_race,
    predict_race_fl,
    predict_race_flg,
    predict_sex_f,
    predict_sex_ssa,
    strata,
    stratabgt,
    strataname,
    stratatract,
    stratazcta,
    tier_coverage,
)
from ._errors import (
    AequumError,
    AuthenticationError,
    BadRequest,
    MissingDependency,
    NotImplementedYet,
    PlanRequired,
    QuotaExceeded,
    RateLimited,
    ServiceUnavailable,
)
from ._transport import Client, configure, default_client, set_api_key


def health() -> dict:
    """Service health and model versions (no key needed)."""
    return default_client().health()


__all__ = [  # noqa: RUF022 - grouped by family, not alphabetical
    "__version__",
    # local (pyethnicity-compatible)
    "bisg", "bisg6", "bifsg", "bifsg6", "predict_sex_ssa",
    "predict_race", "predict_race_fl", "predict_race_flg",
    # hosted
    "strata", "strataname", "stratazcta", "stratatract", "stratabgt",
    "geocode", "tier_coverage", "predict_sex_f", "health",
    # local tools (no key, nothing leaves the machine)
    "names", "ppp",
    # plumbing
    "set_api_key", "Client", "configure", "default_client",
    "AequumError", "BadRequest", "AuthenticationError", "PlanRequired",
    "RateLimited", "QuotaExceeded", "ServiceUnavailable", "NotImplementedYet", "MissingDependency",
]
