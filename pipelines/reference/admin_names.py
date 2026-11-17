"""District names in Khyber Pakhtunkhwa as each source spells them.

`canonical` follows PDMA's daily situation reports, because those are the
labels we extract. Spellings were checked against a sample of 400 cached PDMA
reports (district table, first column) on 18 Nov 2026.
"""

from __future__ import annotations

from backend.app.config.region import slugify

# COD-AB district name -> PDMA spelling, where they differ.
COD_TO_PDMA: dict[str, str] = {
    "Batagram": "Battagram",
    "Chitral Upper": "Upper Chitral",
    "Chitral Lower": "Lower Chitral",
    "Kohistan Lower": "Lower Kohistan",
    "Kohistan Upper": "Upper Kohistan",
    "Kolai Palas Kohistan": "Kohistan Kolai Pallas",
    "Tor Ghar": "Torghar",
    "D. I. Khan": "Dera Ismail Khan",
}

# Extra spellings seen or expected in reports and the census, by canonical name.
EXTRA_DISTRICT_ALIASES: dict[str, list[str]] = {
    "Dera Ismail Khan": ["D.I. Khan", "DI Khan", "D I Khan"],
    "South Waziristan": ["South Waziristan Lower", "South Waziristan Upper",
                         "Lower South Waziristan", "Upper South Waziristan"],
    "Kohistan Kolai Pallas": ["Kolai Pallas", "Kolai Palas", "Kolai Palas Kohistan"],
    "Upper Dir": ["Dir Upper"],
    "Lower Dir": ["Dir Lower"],
    "Battagram": ["Batagram"],
    "Torghar": ["Tor Ghar", "Tor Garh"],
    "Abbottabad": ["Abbotabad"],
}


def canonical_district(cod_name: str) -> str:
    return COD_TO_PDMA.get(cod_name, cod_name)


def district_slug(canonical_name: str) -> str:
    return slugify(canonical_name)
