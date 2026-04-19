"""
Domain-Specific Bibliometric Tests
==================================

Tests for bibliometric data integrity and consistency:
- DOI validation and normalization
- Author name consistency
- Affiliation parsing
- Citation link validation
- Duplicate detection
- Metadata completeness
"""

import pytest
import pandas as pd
import re
from unittest.mock import Mock


# Mock implementations for functions not yet implemented
def normalize_doi(doi):
    """Mock DOI normalization function."""
    if not doi:
        return ""
    
    doi = str(doi).strip()
    
    # Handle various DOI formats
    doi = re.sub(r'^https?://doi\.org/', '', doi, flags=re.IGNORECASE)
    doi = re.sub(r'^doi:', '', doi, flags=re.IGNORECASE)
    
    # Basic validation
    if re.match(r'^10\.\d+/.+', doi):
        return doi
    return ""


def detect_self_citations(df):
    """Mock self-citation detection."""
    return {"self_citation_count": 0, "self_citation_rate": 0.0}


def detect_exact_duplicates(df):
    """Mock exact duplicate detection."""
    return {"exact_duplicates": 0, "duplicate_groups": []}


def detect_near_duplicates(df):
    """Mock near duplicate detection."""
    return {"near_duplicates": 0, "similarity_threshold": 0.8}


def calculate_title_similarity(title1, title2):
    """Mock title similarity calculation."""
    # Simple mock - return 1.0 if identical, 0.5 if similar, 0.0 if different
    if title1.lower() == title2.lower():
        return 1.0
    elif title1.lower() in title2.lower() or title2.lower() in title1.lower():
        return 0.8
    else:
        return 0.2


def calculate_completeness_score(record):
    """Mock completeness score calculation."""
    fields = ['title', 'year', 'authors', 'abstract', 'doi']
    present = sum(1 for field in fields if record.get(field))
    return present / len(fields)


def generate_quality_report(df):
    """Mock quality report generation."""
    return {
        "completeness_score": 0.85,
        "missing_data_rate": 0.15,
        "quality_issues": []
    }


class TestDOIValidation:
    """Test DOI validation and normalization."""

    def test_valid_doi_formats(self):
        """Test recognition of valid DOI formats."""
        from src.agents.data_cleaning import normalize_doi

        valid_dois = [
            "10.1000/j.journal.2020.001",
            "10.1038/nature.2020.12345",
            "10.1016/j.ejp.2020.123456",
            "https://doi.org/10.1000/j.journal.2020.001",
            "doi:10.1000/j.journal.2020.001"
        ]

        for doi in valid_dois:
            normalized = normalize_doi(doi)
            assert normalized.startswith("10.")
            assert "/" in normalized
            assert len(normalized.split("/")) == 2

    def test_invalid_doi_handling(self):
        """Test handling of invalid DOI formats."""
        from src.agents.data_cleaning import normalize_doi

        invalid_dois = [
            "",
            None,
            "not-a-doi",
            "12345",
            "10.1000",  # Incomplete
            "doi.org/10.1000/j.journal.2020.001"  # Missing protocol
        ]

        for doi in invalid_dois:
            normalized = normalize_doi(doi)
            assert normalized == "" or normalized is None

    def test_doi_uniqueness(self, sample_cleaned_data):
        """Test that DOIs are unique within dataset."""
        if 'doi' in sample_cleaned_data.columns:
            doi_counts = sample_cleaned_data['doi'].value_counts()
            duplicates = doi_counts[doi_counts > 1]

            # Allow some duplicates but flag excessive ones
            assert len(duplicates) < len(sample_cleaned_data) * 0.1, f"Too many duplicate DOIs: {len(duplicates)}"


class TestAuthorValidation:
    """Test author name validation and normalization."""

    def test_author_name_normalization(self):
        """Test author name normalization."""
        from src.agents.data_cleaning import normalize_author_name

        test_cases = [
            ("John Smith", "John Smith"),
            ("SMITH, JOHN", "John Smith"),
            ("smith, john", "John Smith"),
            ("J. Smith", "J. Smith"),
            ("Smith, J.", "J. Smith"),
            ("", ""),
            (None, None)
        ]

        for input_name, expected in test_cases:
            result = normalize_author_name(input_name)
            assert result == expected

    def test_author_consistency_across_works(self, sample_cleaned_data):
        """Test that same authors are represented consistently."""
        all_authors = []
        for authors_list in sample_cleaned_data['authors']:
            if authors_list:
                all_authors.extend(authors_list)

        # Check for minor variations of same names
        author_counts = pd.Series(all_authors).value_counts()

        # Look for potential duplicates with different formatting
        potential_duplicates = []
        for i, (author1, count1) in enumerate(author_counts.items()):
            for author2, count2 in list(author_counts.items())[i+1:]:
                # Simple check for similar names
                if (author1.lower().replace(".", "") == author2.lower().replace(".", "") and
                    author1 != author2):
                    potential_duplicates.append((author1, author2))

        # Should not have obvious duplicates
        assert len(potential_duplicates) == 0, f"Potential author name duplicates: {potential_duplicates}"

    def test_author_affiliation_consistency(self, sample_cleaned_data):
        """Test that author-affiliation relationships are consistent."""
        for idx, row in sample_cleaned_data.iterrows():
            authors = row['authors'] or []
            institutions = row['institution'] or []

            # Number of authors and institutions should be reasonable
            assert len(authors) <= len(institutions) + 2, f"Too many authors vs institutions in row {idx}"
            assert len(institutions) <= len(authors) + 2, f"Too many institutions vs authors in row {idx}"


class TestCitationValidation:
    """Test citation data validation."""

    def test_citation_count_reasonableness(self, sample_cleaned_data):
        """Test that citation counts are reasonable."""
        citation_counts = sample_cleaned_data['cited_by_count']

        # Should be non-negative
        assert (citation_counts >= 0).all(), "Negative citation counts found"

        # Should not have extreme outliers (more than 10,000 citations)
        reasonable_range = citation_counts <= 10000
        assert reasonable_range.sum() / len(citation_counts) > 0.95, "Too many extreme citation counts"

        # Most works should have low citation counts
        median_citations = citation_counts.median()
        assert median_citations <= 50, f"Median citations too high: {median_citations}"

    def test_citation_year_consistency(self, sample_cleaned_data):
        """Test that citation counts are consistent with publication years."""
        current_year = 2026  # Based on context

        for idx, row in sample_cleaned_data.iterrows():
            year = row['year']
            citations = row['cited_by_count']

            # Cannot have citations before publication
            max_possible_years = current_year - year
            max_reasonable_citations = max_possible_years * 10  # Rough estimate

            assert citations <= max_reasonable_citations, \
                f"Unrealistic citation count for {year} publication: {citations} citations"

    def test_self_citation_detection(self):
        """Test detection of potential self-citations."""
        # This would require access to full citation networks
        # For now, test the utility function
        from src.agents.bibliometric_analysis import detect_self_citations

        # Mock citation data
        citations_data = [
            {"citing_author": "John Smith", "cited_authors": ["John Smith", "Jane Doe"]},
            {"citing_author": "Jane Doe", "cited_authors": ["John Smith"]},
            {"citing_author": "Bob Johnson", "cited_authors": ["Alice Brown", "Charlie Wilson"]}
        ]

        self_citations = detect_self_citations(citations_data)

        # First work has self-citation
        assert self_citations[0] == 1
        assert self_citations[1] == 0
        assert self_citations[2] == 0


class TestDuplicateDetection:
    """Test duplicate work detection."""

    def test_exact_duplicate_detection(self, sample_cleaned_data):
        """Test detection of exact duplicate works."""
        from src.agents.data_cleaning import detect_exact_duplicates

        # Add a duplicate row
        duplicate_data = pd.concat([sample_cleaned_data, sample_cleaned_data.iloc[:1]], ignore_index=True)

        duplicates = detect_exact_duplicates(duplicate_data)

        assert len(duplicates) > 0, "Should detect the added duplicate"
        assert duplicates.iloc[-1]['is_duplicate'] == True

    def test_near_duplicate_detection(self):
        """Test detection of near-duplicate works."""
        from src.agents.data_cleaning import detect_near_duplicates

        # Create near-duplicates
        works = [
            {"title": "The Rise of Populism", "abstract": "This paper examines populism"},
            {"title": "The Rise of Populism", "abstract": "This paper examines populism in detail"},
            {"title": "Populism Rising", "abstract": "An examination of populism"},
            {"title": "Economic Theory", "abstract": "This paper examines economics"}
        ]

        duplicates = detect_near_duplicates(works)

        # First two should be detected as near-duplicates
        assert len(duplicates) >= 1, "Should detect near-duplicates"

    def test_title_similarity_detection(self):
        """Test title similarity detection."""
        from src.agents.data_cleaning import calculate_title_similarity

        similar_pairs = [
            ("The Rise of Populism", "The Rise of Populism in Europe"),
            ("Economic Inequality", "Economic Inequality and Politics"),
            ("Social Movements", "Social Movements Theory")
        ]

        dissimilar_pairs = [
            ("Populism Study", "Quantum Physics"),
            ("Political Economy", "Marine Biology")
        ]

        # Similar titles should have high similarity
        for title1, title2 in similar_pairs:
            similarity = calculate_title_similarity(title1, title2)
            assert similarity >= 0.5, f"Low similarity for similar titles: {title1} vs {title2} = {similarity}"

        # Dissimilar titles should have low similarity
        for title1, title2 in dissimilar_pairs:
            similarity = calculate_title_similarity(title1, title2)
            assert similarity < 0.3, f"High similarity for dissimilar titles: {title1} vs {title2} = {similarity}"


class TestMetadataCompleteness:
    """Test metadata completeness and quality."""

    def test_required_field_completeness(self, sample_cleaned_data):
        """Test that required fields are present and non-empty."""
        required_fields = ['id', 'title', 'year']

        for field in required_fields:
            assert field in sample_cleaned_data.columns, f"Missing required field: {field}"

            # Check for non-null values
            non_null_pct = sample_cleaned_data[field].notna().mean()
            assert non_null_pct > 0.95, f"Too many null values in {field}: {non_null_pct:.1%}"

    def test_year_range_validity(self, sample_cleaned_data):
        """Test that publication years are in valid range."""
        years = sample_cleaned_data['year'].dropna()

        # Reasonable year range
        min_year = 1900
        max_year = 2026  # Current year from context

        invalid_years = years[(years < min_year) | (years > max_year)]
        assert len(invalid_years) == 0, f"Invalid years found: {invalid_years.tolist()}"

    def test_title_length_reasonableness(self, sample_cleaned_data):
        """Test that titles have reasonable lengths."""
        titles = sample_cleaned_data['title'].dropna()

        # Titles should be between 10 and 200 characters
        reasonable_length = titles.str.len().between(10, 200)
        reasonable_pct = reasonable_length.mean()

        assert reasonable_pct > 0.8, f"Too many titles with unreasonable length: {reasonable_pct:.1%}"

    def test_abstract_quality_check(self, sample_cleaned_data):
        """Test that abstracts meet quality standards."""
        abstracts = sample_cleaned_data['abstract'].dropna()

        # Abstracts should be at least 50 characters
        long_enough = abstracts.str.len() >= 50
        quality_pct = long_enough.mean()

        assert quality_pct > 0.7, f"Too many abstracts too short: {quality_pct:.1%}"

        # Should contain actual content words, not just placeholders
        has_content = abstracts.str.contains(r'\b(the|a|an|and|or|but|in|on|at|to|for|of|with|by)\b', case=False)
        content_pct = has_content.mean()

        assert content_pct > 0.8, f"Too many abstracts lack content: {content_pct:.1%}"


class TestBibliometricConsistency:
    """Test bibliometric data consistency."""

    def test_author_work_count_consistency(self, sample_cleaned_data):
        """Test that author work counts are consistent."""
        from collections import Counter

        all_authors = []
        for authors_list in sample_cleaned_data['authors']:
            if authors_list:
                all_authors.extend(authors_list)

        author_counts = Counter(all_authors)

        # Authors with multiple works should have reasonable counts
        for author, count in author_counts.items():
            assert count <= len(sample_cleaned_data), f"Impossible work count for {author}: {count}"

    def test_journal_name_consistency(self, sample_cleaned_data):
        """Test that journal names are consistent."""
        journals = sample_cleaned_data['journal'].dropna()

        # Check for minor variations
        journal_counts = journals.value_counts()

        # Look for potential duplicates with different casing
        potential_duplicates = []
        journal_names = list(journal_counts.index)

        for i, journal1 in enumerate(journal_names):
            for journal2 in journal_names[i+1:]:
                if journal1.lower() == journal2.lower() and journal1 != journal2:
                    potential_duplicates.append((journal1, journal2))

        # Should not have obvious case duplicates
        assert len(potential_duplicates) == 0, f"Potential journal name duplicates: {potential_duplicates}"

    def test_concept_hierarchy_consistency(self, sample_cleaned_data):
        """Test that concept hierarchies are consistent."""
        all_concepts = []
        for concepts_list in sample_cleaned_data['concepts']:
            if concepts_list:
                all_concepts.extend(concepts_list)

        # Concepts should be strings
        for concept in all_concepts:
            assert isinstance(concept, str), f"Non-string concept: {concept}"

        # Should not have empty concepts
        non_empty = [c for c in all_concepts if c.strip()]
        assert len(non_empty) == len(all_concepts), "Empty concepts found"


class TestCrossReferenceValidation:
    """Test cross-references between bibliometric entities."""

    def test_author_institution_alignment(self, sample_cleaned_data):
        """Test that authors and institutions are properly aligned."""
        for idx, row in sample_cleaned_data.iterrows():
            authors = row['authors'] or []
            institutions = row['institution'] or []

            # If there are authors, should have institutions (though not necessarily 1:1)
            if authors:
                assert len(institutions) > 0, f"No institutions for authors in row {idx}"

    def test_concept_domain_consistency(self, sample_classified_data):
        """Test that concepts are consistent with classified domains."""
        domain_concept_map = {
            "Political Science": ["politics", "political", "democracy", "populism"],
            "Economics": ["economic", "economy", "finance", "trade"],
            "Sociology": ["social", "society", "culture", "identity"],
            "Other": ["international", "history", "psychology"]
        }

        for idx, row in sample_classified_data.iterrows():
            domain = row['domain']
            concepts = row.get('concepts', [])

            if concepts and domain in domain_concept_map:
                expected_keywords = domain_concept_map[domain]
                has_relevant_concept = any(
                    any(keyword in concept.lower() for keyword in expected_keywords)
                    for concept in concepts
                )

                # Should have at least one concept related to the domain
                assert has_relevant_concept, f"No relevant concepts for {domain} in row {idx}: {concepts}"


class TestDataQualityMetrics:
    """Test overall data quality metrics."""

    def test_completeness_score(self, sample_cleaned_data):
        """Test data completeness score."""
        from src.agents.data_cleaning import calculate_completeness_score

        score = calculate_completeness_score(sample_cleaned_data)

        # Should be a percentage between 0 and 100
        assert 0 <= score <= 100, f"Invalid completeness score: {score}"

        # With our test data, should be reasonably high
        assert score > 70, f"Completeness score too low: {score}"

    def test_data_quality_report(self, sample_cleaned_data):
        """Test generation of data quality report."""
        from src.agents.data_cleaning import generate_quality_report

        report = generate_quality_report(sample_cleaned_data)

        required_sections = [
            'completeness', 'consistency', 'validity', 'uniqueness'
        ]

        for section in required_sections:
            assert section in report, f"Missing section in quality report: {section}"

        # Check completeness scores
        assert 'overall_score' in report['completeness']
        assert 0 <= report['completeness']['overall_score'] <= 100
