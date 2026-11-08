import csv
import unicodedata
import re
from functools import cache
from config.settings import RECONCILED_TAXONOMY, LOCATIONS, RELIABILITY_CLASS, ADDRESSES
import reverse_geocoder as rg

def to_signed(part):
    match = re.search(r'([-+]?\d+\.?\d*)\s*([NSEW])', part, re.IGNORECASE)
    if not match:
        raise ValueError(f"Couldn't parse coordinate")
    value, direction = float(match.group(1)), match.group(2).upper()

    if direction in ('S', 'W'):
        value = -value
    return value

def parse_coord(coord):
    tokens = coord.split()
    mid = len(tokens) // 2
    lat_part = ' '.join(tokens[:mid])
    lon_part = ' '.join(tokens[mid:])

    lat = to_signed(lat_part)
    lon = to_signed(lon_part)
    return lat, lon

def round_coord(coord, precision=4):
    lat, lon = parse_coord(coord)
    return (round(lat, precision), round(lon, precision))

@cache
def reverse_lookup(coord):
    return rg.search(coord, mode=1)[0]

def get_locale_from_coord(coord):
    lat, lon = round_coord(coord)
    locale = reverse_lookup((lat, lon)) 
    return {
        "country": locale["cc"],
        "state": locale["admin1"],
        "city": locale["name"]
    }

def get_locale_from_geo_loc(geo_loc):
    locale = geo_loc.split(":")
    return {
        "country": locale[0].strip(),
        "description": locale[1].strip() if len(locale) > 1 else None
    }

def normalize(value):
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    return "".join(c for c in value if not unicodedata.combining(c)).lower().strip()

def get_matches(address):
    if not address: return {}
    country = normalize(address.get("country"))
    state = normalize(address.get("state"))
    city = normalize(address.get("city"))
    description = normalize(address.get("description"))

    return {
        "country": country in LOCATIONS["countries"],
        "state": any(value in description for value in LOCATIONS["states"]) or state in LOCATIONS["states"],
        "city": any(value in description for value in LOCATIONS["cities"]) or city in LOCATIONS["cities"],
        "river": any(value in description for value in LOCATIONS["rivers"])
    }

def get_relevance(address):
    if (address == {}):
        relevance = "none"
    elif address["river"]:
        relevance = "highest"
    elif address["city"] or address["state"]:
        relevance = "high"
    elif address["country"]:
        relevance = "medium"
    else:
        relevance = "low"
    return relevance

reliability_class = []
with open(RECONCILED_TAXONOMY, "r") as reconciled:
    reader = csv.DictReader(reconciled)

    for row in reader:
        loc = row.get("geo_loc_name", None)
        coord = row.get("lat_lon", None)
        reliability = "high" if (loc or coord) else "low"

        address = {}
        relevance = {}

        if reliability == "high":
            if coord:
                address = get_locale_from_coord(coord)
            elif loc:
                address = get_locale_from_geo_loc(loc)
    
        matches = get_matches(address)
        relevance = get_relevance(matches)
        reliability_class.append(row | {"reliability": reliability, "relevance": relevance})

fieldnames = reliability_class[0].keys()

with open(RELIABILITY_CLASS, "w", newline="") as outfile:
    writer = csv.DictWriter(outfile, fieldnames=fieldnames,  restval='')
    writer.writeheader()
    writer.writerows(reliability_class)
