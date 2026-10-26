"""Business-name detection for records nominally held by a natural person.

An administrative legal-form field (e.g. SBA BusinessType) removes most
non-individual entities. What survives are trade names registered under an
individual legal form -- "SUNRISE LANDSCAPING" filed as a sole
proprietorship. These carry no personal name to infer anything from.

The term list below was validated against 1,136 manually rated PPP records:
it flagged 6 of 39 true non-persons (15.4 percent recall) with ZERO false
positives among 1,072 confirmed real people. It is deliberately conservative
-- terms that are also common surnames (Baker, Mason, Carpenter, Church,
Taylor, Cook, Fisher, Miller, Barber, Marshall, Bishop) are EXCLUDED even
though they would raise recall, because a false positive deletes a real
person from the sample.
"""
import re

BUSINESS_TERMS = [
    # trades and construction
    "contractor","contractors","construction","builders","building","roofing",
    "plumbing","electric","electrical","heating","cooling","hvac","painting",
    "landscaping","masonry","carpentry","excavating","paving",
    # property and real estate
    "realty","properties","property","management","development","developers",
    "real estate","rentals","apartments","homes","housing",
    # cleaning and maintenance
    "cleaner","cleaners","cleaning","maintenance","janitorial","services",
    "service","repair","restoration",
    # retail and food
    "store","shop","market","mart","restaurant","cafe","deli","bakery",
    "grocery","foods","liquors","pharmacy",
    # automotive
    "auto","automotive","motors","garage","collision","towing","tires","body shop",
    # professional organisations
    "associates","partners","consulting","consultants","agency","solutions",
    "systems","technologies","engineering","architects","accounting",
    # institutional
    "school","academy","university","college","hospital","medical",
    "clinic","center","foundation","association","society","club",
    # financial and legal
    "bank","credit union","financial","capital","investments","insurance",
    "law","attorneys","trust",
    # industrial
    "manufacturing","industries","industrial","supply","supplies","equipment",
    "distribution","distributors",
]

# Legal-entity markers. Separated because an administrative legal-form screen
# usually removes these already; kept so the package stands alone.
ENTITY_TERMS = ["llc","l.l.c","inc","incorporated","corp","corporation","ltd",
                "limited","lp","llp","pllc","pc","co","company","dba","d/b/a"]

# Terms that are plainly institutional but ALSO common surnames. Excluded from
# the default screen and available via aggressive=True. "church" is the clear
# case: it names congregations and it names people.
SURNAME_COLLIDING = ["church","abbey","temple","chapel","priest","deacon"]

# Excluded on purpose: common surnames that double as occupation words.
# Adding any of these raises recall at the cost of deleting real people.
KNOWN_UNSAFE = ["baker","mason","carpenter","taylor","cook","fisher",
                "miller","barber","marshall","bishop","gardner","turner",
                "shepherd","abbott","chandler","farmer","hunter","porter",
                "sawyer","stone","wood","field","banks","price","rich"]

def _rx(terms): return re.compile(r"\b(" + "|".join(re.escape(t) for t in terms) + r")\b", re.IGNORECASE)
_BIZ = _rx(BUSINESS_TERMS)
_ENT = _rx(ENTITY_TERMS)
_AGG = _rx(SURNAME_COLLIDING)

def business_term(name, *, include_entity=False, aggressive=False):
    """Return the matched business term, or None.

    aggressive=True adds SURNAME_COLLIDING terms. Raises recall and will
    misclassify some real people; measure the false-positive rate on your own
    corpus before switching it on.
    """
    s = str(name or "")
    m = _BIZ.search(s)
    if m: return m.group(0).lower()
    if include_entity:
        m = _ENT.search(s)
        if m: return m.group(0).lower()
    if aggressive:
        m = _AGG.search(s)
        if m: return m.group(0).lower()
    return None

def is_business(name, *, include_entity=False, aggressive=False) -> bool:
    """True if the string carries a business or trade-name marker."""
    return business_term(name, include_entity=include_entity, aggressive=aggressive) is not None
