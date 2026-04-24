"""
Unit tests for src/utils/taxonomy.py
Pure data lookups — no I/O, no mocking needed.
"""

import pytest

from src.utils.taxonomy import (
    DOMAIN_SUBCATEGORY,
    TAXONOMY_METADATA,
    VALID_DOMAINS,
    VALID_SUBCATEGORIES,
    get_all_labels,
    get_domain_from_subcategory,
    is_valid_domain,
    is_valid_label,
    is_valid_subcategory,
)


# ── Taxonomy structure ────────────────────────────────────────────────────────


def test_valid_domains_not_empty():
    assert len(VALID_DOMAINS) > 0


def test_valid_subcategories_covers_all_domains():
    assert set(VALID_SUBCATEGORIES.keys()) == set(VALID_DOMAINS)


def test_domain_subcategory_consistent_with_valid_domains():
    assert set(DOMAIN_SUBCATEGORY.keys()) == set(VALID_DOMAINS)


def test_taxonomy_metadata_keys():
    assert "version" in TAXONOMY_METADATA
    assert "n_domains" in TAXONOMY_METADATA
    assert "n_subcategories" in TAXONOMY_METADATA


def test_taxonomy_metadata_counts():
    expected_domains = len(DOMAIN_SUBCATEGORY)
    expected_subcats = sum(len(v) for v in DOMAIN_SUBCATEGORY.values())
    assert TAXONOMY_METADATA["n_domains"] == expected_domains
    assert TAXONOMY_METADATA["n_subcategories"] == expected_subcats


# ── get_all_labels ────────────────────────────────────────────────────────────


def test_get_all_labels_format():
    labels = get_all_labels()
    assert len(labels) > 0
    for label in labels:
        assert "::" in label, f"Label missing '::' separator: {label}"


def test_get_all_labels_count_matches_subcategories():
    total_subcats = sum(len(v) for v in DOMAIN_SUBCATEGORY.values())
    assert len(get_all_labels()) == total_subcats


def test_get_all_labels_contains_known_entry():
    labels = get_all_labels()
    assert any("Economics" in label for label in labels)


# ── get_domain_from_subcategory ───────────────────────────────────────────────


def test_get_domain_from_subcategory_known():
    for domain, subcats in DOMAIN_SUBCATEGORY.items():
        for subcat in list(subcats)[:2]:
            assert get_domain_from_subcategory(subcat) == domain


def test_get_domain_from_subcategory_unknown_returns_other():
    assert get_domain_from_subcategory("NonExistentSubcat") == "Other"


# ── is_valid_domain ───────────────────────────────────────────────────────────


def test_is_valid_domain_true():
    for domain in VALID_DOMAINS:
        assert is_valid_domain(domain) is True


def test_is_valid_domain_false():
    assert is_valid_domain("Astrology") is False
    assert is_valid_domain("") is False


# ── is_valid_subcategory ──────────────────────────────────────────────────────


def test_is_valid_subcategory_true():
    for subcats in DOMAIN_SUBCATEGORY.values():
        for subcat in list(subcats)[:1]:
            assert is_valid_subcategory(subcat) is True


def test_is_valid_subcategory_false():
    assert is_valid_subcategory("NonExistent") is False
    assert is_valid_subcategory("") is False


# ── is_valid_label ────────────────────────────────────────────────────────────


def test_is_valid_label_true():
    for label in get_all_labels()[:5]:
        assert is_valid_label(label) is True


def test_is_valid_label_missing_separator():
    assert is_valid_label("EconomicsPoliticalEconomy") is False


def test_is_valid_label_invalid_domain():
    assert is_valid_label("Astrology::Something") is False


def test_is_valid_label_invalid_subcategory():
    first_domain = next(iter(DOMAIN_SUBCATEGORY))
    assert is_valid_label(f"{first_domain}::NonExistentSub") is False


def test_is_valid_label_empty():
    assert is_valid_label("") is False
    assert is_valid_label("::") is False
