"""Single-source official standards fixtures used for candidate-only smoke tests."""

AUSTIN_WATER_CONSTRUCTION_STANDARDS_SOURCE = {
    "source_id": "austin_water_construction_standards",
    "source_url": "https://www.austintexas.gov/water/construction-standards",
    "jurisdiction": {"city": "Austin", "state": "Texas"},
    "agency": "Austin Water",
    "source_type": "official_utility",
    "discipline": "utilities",
    "document_title": "Construction Standards",
    "why_official": (
        "Hosted on the City of Austin austintexas.gov domain and presented as Austin Water "
        "construction standards resources for water, reclaimed water, and wastewater infrastructure."
    ),
}

AUSTIN_WATER_CONSTRUCTION_STANDARDS_ALLOWLIST = [
    {
        "jurisdiction": AUSTIN_WATER_CONSTRUCTION_STANDARDS_SOURCE["jurisdiction"],
        "agency": AUSTIN_WATER_CONSTRUCTION_STANDARDS_SOURCE["agency"],
        "allowed_domains": ["www.austintexas.gov"],
        "allowed_source_types": [AUSTIN_WATER_CONSTRUCTION_STANDARDS_SOURCE["source_type"]],
        "disciplines": [AUSTIN_WATER_CONSTRUCTION_STANDARDS_SOURCE["discipline"]],
        "configured_by": "chat_23_real_standards_source_smoke",
        "configured_at": "2026-06-05",
        "confidence_cap": "trusted_candidate",
    }
]

AUSTIN_WATER_CONSTRUCTION_STANDARDS_RECORDED_HTML = """
<html>
  <head><title>Construction Standards | Austin Water | AustinTexas.gov</title></head>
  <body>
    <h1>Construction Standards</h1>
    <p>
      Austin Water offers resources to help engineers and contractors design and build
      water, reclaimed water and wastewater infrastructure in the City of Austin.
    </p>
    <ul>
      <li>Utilities Criteria Manual</li>
      <li>Current Standard Specifications</li>
      <li>Current Standard Details</li>
      <li>Standard Products Lists</li>
    </ul>
  </body>
</html>
"""
