"""Per-country Cartesia voice mapping for voice mode.

Exact-match on the country string only (no fuzzy matching of custom/free-text
destinations) - see frontend/src/lib/countries.ts for the fixed list this is
keyed against. Any country not listed here (including custom destinations)
falls back to DEFAULT_VOICE_ID, so voice mode always works, just unaccented.
"""

# "Skylar", a stable US-English voice Cartesia recommends as a general-purpose
# default - https://docs.cartesia.ai/getting-started/available-models
DEFAULT_VOICE_ID = "db6b0ed5-d5d3-463d-ae85-518a07d3c2b4"

# Only populated with voices confirmed against Cartesia's docs. Fill in the
# rest from the voice library at https://play.cartesia.ai/voices - pick a
# voice_id per country there rather than guessing, since an invalid id fails
# at TTS-request time, not at startup.
COUNTRY_VOICE_IDS: dict[str, str] = {
    # "Gemma", en-GB - https://docs.cartesia.ai/getting-started/available-models
    "United Kingdom": "62ae83ad-4f6a-430b-af41-a9bede9286ca",
}


def resolve_voice_id(country: str | None) -> str:
    """Cartesia voice_id for a session's country, or DEFAULT_VOICE_ID if unmapped."""
    return COUNTRY_VOICE_IDS.get(country or "", DEFAULT_VOICE_ID)
