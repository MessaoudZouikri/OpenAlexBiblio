"""
Centralized Domain Taxonomy Management
=====================================
Single source of truth for domain/subcategory definitions.
Shared across all classification and analysis modules.

Version: 1.0
Last updated: 2026-04-16

Usage:
    from src.utils.taxonomy import DOMAIN_SUBCATEGORY, CONCEPT_DOMAIN_MAP, SUBCATEGORY_KEYWORDS
"""

from typing import Dict, List

# ─────────────────────────────────────────────────────────────────────────────
# Primary Domain Structure
# ─────────────────────────────────────────────────────────────────────────────

DOMAIN_SUBCATEGORY: Dict[str, List[str]] = {
    "Political Science": [
        "comparative_politics",
        "political_theory",
        "electoral_politics",
        "democratic_theory",
        "radical_right",
        "latin_american_politics",
        "european_politics",
    ],
    "Economics": [
        "political_economy",
        "redistribution",
        "trade_globalization",
        "financial_crisis",
    ],
    "Sociology": [
        "social_movements",
        "identity_politics",
        "media_communication",
        "culture_values",
    ],
    "Other": [
        "international_relations",
        "history",
        "psychology",
        "geography",
        "interdisciplinary",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# OpenAlex Concept → Domain Mapping
# ─────────────────────────────────────────────────────────────────────────────

CONCEPT_DOMAIN_MAP: Dict[str, str] = {
    # Political Science
    "political science": "Political Science",
    "politics": "Political Science",
    "democracy": "Political Science",
    "populism": "Political Science",
    "government": "Political Science",
    "political party": "Political Science",
    "parliament": "Political Science",
    "election": "Political Science",
    "voting": "Political Science",
    "political ideology": "Political Science",
    "political culture": "Political Science",
    "political behavior": "Political Science",
    "political system": "Political Science",
    # Economics
    "economics": "Economics",
    "economy": "Economics",
    "political economy": "Economics",
    "macroeconomics": "Economics",
    "inequality": "Economics",
    "redistribution": "Economics",
    "trade": "Economics",
    "economic development": "Economics",
    "fiscal policy": "Economics",
    "employment": "Economics",
    # Sociology
    "sociology": "Sociology",
    "social movement": "Sociology",
    "identity": "Sociology",
    "media studies": "Sociology",
    "communication": "Sociology",
    "culture": "Sociology",
    "social science": "Sociology",
    "social network": "Sociology",
    "social change": "Sociology",
    # Other
    "international relations": "Other",
    "foreign policy": "Other",
    "history": "Other",
    "psychology": "Other",
    "geography": "Other",
}

# ─────────────────────────────────────────────────────────────────────────────
# Subcategory → Keywords Mapping
# Used for Stage 1 (rule-based) routing
# ─────────────────────────────────────────────────────────────────────────────

SUBCATEGORY_KEYWORDS: Dict[str, List[str]] = {
    # Political Science subcategories
    "comparative_politics": [
        "comparative",
        "cross-national",
        "cross national",
        "cross-country",
        "institutional",
        "regime",
        "party system",
    ],
    "political_theory": [
        "theory",
        "theoretical",
        "conceptual",
        "normative",
        "definition",
        "philosophical",
        "genealogy",
        "intellectual",
    ],
    "electoral_politics": [
        "election",
        "electoral",
        "voting",
        "vote",
        "ballot",
        "turnout",
        "volatility",
        "realignment",
    ],
    "democratic_theory": [
        "democracy",
        "democratic",
        "backsliding",
        "illiberal",
        "autocratization",
        "liberal",
        "consolidation",
        "erosion",
        "institutional decay",
    ],
    "radical_right": [
        "far-right",
        "radical right",
        "extreme right",
        "right-wing",
        "extremist",
        "nativist",
        "authoritarian",
        "ethnonational",
    ],
    "latin_american_politics": [
        "latin america",
        "brazil",
        "venezuela",
        "argentina",
        "mexico",
        "peru",
        "pink tide",
        "chávismo",
        "peronism",
        "andes",
    ],
    "european_politics": [
        "europe",
        "european union",
        "france",
        "germany",
        "italy",
        "spain",
        "fidesz",
        "law and justice",
        "national rally",
        "eurosceptic",
    ],
    # Economics subcategories
    "political_economy": [
        "political economy",
        "macroeconomic",
        "fiscal policy",
        "monetary",
        "economic institution",
        "economic policy",
    ],
    "redistribution": [
        "redistribution",
        "welfare",
        "social protection",
        "inequality",
        "social benefit",
        "minimum wage",
    ],
    "trade_globalization": [
        "globalization",
        "globalisation",
        "trade",
        "import",
        "export",
        "protectionism",
        "offshoring",
        "automation",
    ],
    "financial_crisis": [
        "crisis",
        "recession",
        "austerity",
        "financial crash",
        "banking",
        "sovereign debt",
        "unemployment shock",
    ],
    # Sociology subcategories
    "social_movements": [
        "social movement",
        "mobilization",
        "mobilisation",
        "protest",
        "occupy",
        "yellow vest",
        "civil society",
        "contentious",
    ],
    "identity_politics": [
        "identity",
        "ethnic",
        "nationalism",
        "religion",
        "nativism",
        "racial",
        "resentment",
        "masculinity",
    ],
    "media_communication": [
        "media",
        "communication",
        "framing",
        "social media",
        "twitter",
        "facebook",
        "disinformation",
        "fake news",
    ],
    "culture_values": [
        "culture",
        "values",
        "post-material",
        "cultural backlash",
        "resentment",
        "status anxiety",
        "authoritarian personality",
    ],
    # Other subcategories
    "international_relations": [
        "international",
        "foreign policy",
        "geopolitics",
        "diplomacy",
        "multilateral",
        "nato",
        "transatlantic",
    ],
    "history": [
        "historical",
        "history",
        "19th century",
        "20th century",
        "interwar",
        "weimar",
        "agrarian",
        "narodniks",
    ],
    "psychology": [
        "psychological",
        "psychology",
        "personality",
        "cognitive",
        "attitude",
        "authoritarianism",
        "conspiracy",
    ],
    "geography": [
        "spatial",
        "geographic",
        "regional",
        "urban",
        "rural",
        "place-based",
        "electoral geography",
    ],
    "interdisciplinary": [
        "interdisciplinary",
        "mixed methods",
        "review",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Domain Fragments (substring matching for rule-based classification)
# ─────────────────────────────────────────────────────────────────────────────

DOMAIN_CONCEPT_FRAGMENTS: Dict[str, List[str]] = {
    "Political Science": [
        "political science",
        "politics",
        "democracy",
        "populism",
        "government",
        "voting",
        "electoral",
        "party",
        "parliament",
    ],
    "Economics": [
        "economics",
        "economy",
        "political economy",
        "macroeconomics",
        "inequality",
        "redistribution",
        "trade",
    ],
    "Sociology": [
        "sociology",
        "social science",
        "social movement",
        "identity",
        "media",
        "communication",
        "culture",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Metadata
# ─────────────────────────────────────────────────────────────────────────────

TAXONOMY_METADATA = {
    "version": "1.0",
    "created": "2026-04-16",
    "n_domains": len(DOMAIN_SUBCATEGORY),
    "n_subcategories": sum(len(v) for v in DOMAIN_SUBCATEGORY.values()),
    "source": "hand-curated with researcher feedback",
}


def get_all_labels() -> List[str]:
    """Return all domain::subcategory labels."""
    return [
        f"{domain}::{subcat}"
        for domain, subcats in DOMAIN_SUBCATEGORY.items()
        for subcat in subcats
    ]


def get_domain_from_subcategory(subcategory: str) -> str:
    """Reverse lookup: subcategory → domain."""
    for domain, subcats in DOMAIN_SUBCATEGORY.items():
        if subcategory in subcats:
            return domain
    return "Other"


def is_valid_domain(domain: str) -> bool:
    """Check if domain is valid."""
    return domain in DOMAIN_SUBCATEGORY


def is_valid_subcategory(subcategory: str) -> bool:
    """Check if subcategory is valid."""
    for subcats in DOMAIN_SUBCATEGORY.values():
        if subcategory in subcats:
            return True
    return False


def is_valid_label(label: str) -> bool:
    """Check if label is valid 'domain::subcategory' format."""
    if "::" not in label:
        return False
    domain, subcategory = label.split("::", 1)
    return is_valid_domain(domain) and is_valid_subcategory(subcategory)
