"""Group 800+ raw 311 request types into 15 plain-language topics.

The city renamed many types between 2024 and 2025 (for example "Road Pothole / Road
Damage" became "Road - Pot hole"), so questions like "how many pothole requests"
are unanswerable from request_type alone. The topic column fixes that.
Rules run in order; the first match wins.
"""
import re

RULES = [
    ("Hazardous waste",            r"hazardous"),
    ("Missed collection",          r"not picked up|not pick|curb day|collections|overflow"),
    ("Bins",                       r"\bbins?\b|containers"),
    ("Animals and wildlife",       r"wildlife|animal|\bdogs?\b|cadaver|stray|coyote|bite|leash|bees|wasp|custody|menace|attack|shelter|west nile|injured|domestic"),
    ("Noise",                      r"noise|sound|fireworks"),
    ("Trees",                      r"tree|pruning|stump|stemming|brush|storm clean"),
    ("Graffiti and postering",     r"graffiti|poster"),
    ("Snow and ice",               r"snow|\bic[ey]\b|salt|plow|plough|windrow|winter|sanding"),
    ("Potholes and road damage",   r"pot ?hole|road damage|road - (sinking|damaged)|sink hole|utility cut|plow damage|surface damage"),
    ("Water and sewer",            r"water|sewer|watermain|hydrant|catch ?basin|maintenance holes?|culvert|ditch|flooding|ponding|\blead\b|spill"),
    ("Litter and illegal dumping", r"litter|dumping|needle|syringe|debris|cleaning|clean ?up|biohazard|shopping cart|garbage"),
    ("Signs, signals and markings", r"sign|signal|marking|pxo|crossover|bollard|speed|crossing|traffic|intersection"),
    ("Sidewalks and boulevards",   r"sidewalk|walkway|boulevard|curb|driveway|laneway|fence|guardrail|furniture|bike|bicycle|bridge|expressway"),
    ("Property and bylaw",         r"property|zoning|heat|grass|weed|encroach|parking|licens|rooming|business|contractor|pest|excavation|waste|by-?law|park|taxi|idling|unsanitary|wrong location"),
    ("Feedback and complaints",    r"complaint|compliment|staff|timeliness|process|dispute|outcome|conduct"),
]
OTHER = "Other"
TOPICS = [t for t, _ in RULES] + [OTHER]
_COMPILED = [(t, re.compile(p, re.I)) for t, p in RULES]


def topic_for(request_type: str) -> str:
    for topic, rx in _COMPILED:
        if rx.search(request_type or ""):
            return topic
    return OTHER
