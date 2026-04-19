"""
Generate Mock Test Datasets
===========================

Creates synthetic bibliometric data for testing purposes.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json


def generate_mock_raw_openalex_data(n_works=100):
    """Generate mock raw OpenAlex data."""
    np.random.seed(42)  # For reproducibility

    # Generate work IDs
    work_ids = [f"W{100000 + i}" for i in range(n_works)]

    # Generate titles
    title_templates = [
        "The Rise of Populism in {}",
        "Economic Inequality and {}",
        "Social Movements in {}",
        "Political Theory of {}",
        "Democracy and {}",
        "Globalization and {}",
        "Identity Politics in {}",
        "Media Influence on {}",
        "Institutional Change in {}",
        "Cultural Backlash and {}"
    ]

    locations = ["Europe", "Latin America", "Asia", "Africa", "North America", "Modern Society", "Contemporary Politics"]

    titles = []
    for i in range(n_works):
        template = np.random.choice(title_templates)
        location = np.random.choice(locations)
        titles.append(template.format(location))

    # Generate years (2010-2023)
    years = np.random.randint(2010, 2024, n_works)

    # Generate citation counts (realistic distribution)
    citation_counts = np.random.exponential(5, n_works).astype(int)
    citation_counts = np.clip(citation_counts, 0, 500)

    # Generate open access status
    is_open_access = np.random.choice([True, False], n_works, p=[0.3, 0.7])

    # Generate concepts
    concept_pool = [
        "Political Science", "Economics", "Sociology", "Populism",
        "Democracy", "Inequality", "Social Movements", "Identity",
        "Media", "Culture", "Globalization", "Politics"
    ]

    concepts = []
    for _ in range(n_works):
        n_concepts = np.random.randint(1, 4)
        work_concepts = np.random.choice(concept_pool, n_concepts, replace=False)
        concepts.append([{"display_name": c} for c in work_concepts])

    # Create DataFrame
    df = pd.DataFrame({
        "id": work_ids,
        "title": titles,
        "year": years,
        "cited_by_count": citation_counts,
        "is_open_access": is_open_access,
        "concepts": concepts
    })

    return df


def generate_mock_cleaned_data(n_works=50):
    """Generate mock cleaned bibliometric data."""
    np.random.seed(42)

    # Base data
    raw_df = generate_mock_raw_openalex_data(n_works)

    # Add cleaned fields
    abstracts = []
    authors = []
    institutions = []
    journals = []

    author_pool = [
        "John Smith", "Jane Doe", "Maria Garcia", "Carlos Rodriguez",
        "Anna Johnson", "David Brown", "Sarah Wilson", "Michael Davis",
        "Laura Martinez", "James Anderson", "Emily Taylor", "Robert Thomas"
    ]

    institution_pool = [
        "University of Amsterdam", "Harvard University", "MIT",
        "University of Sao Paulo", "University of Oxford", "Stanford University",
        "University of Cambridge", "University of Toronto", "ETH Zurich"
    ]

    journal_pool = [
        "American Political Science Review", "European Journal of Political Research",
        "Journal of Politics", "Political Studies", "Latin American Politics and Society",
        "World Politics", "International Organization", "Comparative Political Studies"
    ]

    for i in range(n_works):
        # Generate abstract
        abstract = f"This paper examines {raw_df.iloc[i]['title'].lower()} through a comprehensive analysis of relevant literature and empirical evidence."
        abstracts.append(abstract)

        # Generate authors (1-4 per paper)
        n_authors = np.random.randint(1, 5)
        paper_authors = np.random.choice(author_pool, n_authors, replace=False)
        authors.append(list(paper_authors))

        # Generate institutions
        n_institutions = min(n_authors + np.random.randint(0, 3), len(institution_pool))
        paper_institutions = np.random.choice(institution_pool, n_institutions, replace=False)
        institutions.append(list(paper_institutions))

        # Generate journal
        journals.append(np.random.choice(journal_pool))

    # Add to DataFrame
    raw_df["abstract"] = abstracts
    raw_df["authors"] = authors
    raw_df["institution"] = institutions
    raw_df["journal"] = journals
    raw_df["decade"] = (raw_df["year"] // 10) * 10

    return raw_df


def generate_mock_classified_data(n_works=30):
    """Generate mock classified data."""
    cleaned_df = generate_mock_cleaned_data(n_works)

    # Add classification fields
    domains = ["Political Science", "Economics", "Sociology", "Other"]
    subcategories = {
        "Political Science": ["radical_right", "comparative_politics", "political_theory", "electoral_politics"],
        "Economics": ["political_economy", "redistribution", "trade_globalization", "financial_crisis"],
        "Sociology": ["social_movements", "identity_politics", "media_communication", "culture_values"],
        "Other": ["international_relations", "history", "psychology", "interdisciplinary"]
    }

    classified_domains = []
    classified_subcategories = []
    confidences = []
    stages = []
    methods = []

    for _ in range(n_works):
        domain = np.random.choice(domains, p=[0.4, 0.2, 0.3, 0.1])
        subcategory = np.random.choice(subcategories[domain])

        # Generate realistic confidence scores
        if domain == "Political Science":
            confidence = np.random.beta(8, 2)  # High confidence
            stage = np.random.choice(["rule_based", "embedding", "llm"], p=[0.6, 0.3, 0.1])
        else:
            confidence = np.random.beta(5, 3)  # Medium confidence
            stage = np.random.choice(["rule_based", "embedding", "llm"], p=[0.4, 0.4, 0.2])

        method = "rule_based" if stage == "rule_based" else "embedding"

        classified_domains.append(domain)
        classified_subcategories.append(subcategory)
        confidences.append(round(confidence, 3))
        stages.append(stage)
        methods.append(method)

    cleaned_df["domain"] = classified_domains
    cleaned_df["subcategory"] = classified_subcategories
    cleaned_df["confidence"] = confidences
    cleaned_df["classification_stage"] = stages
    cleaned_df["classification_method"] = methods

    return cleaned_df


def generate_mock_network_data(n_nodes=20):
    """Generate mock network analysis data."""
    np.random.seed(42)

    # Generate node IDs
    node_ids = [f"W{1000 + i}" for i in range(n_nodes)]

    # Generate realistic shared references (power law distribution)
    shared_refs = np.random.zipf(2.5, n_nodes)
    shared_refs = np.clip(shared_refs, 1, 50)

    # Citation counts correlated with shared references
    citation_counts = shared_refs * np.random.uniform(2, 8, n_nodes)
    citation_counts = citation_counts.astype(int)

    df = pd.DataFrame({
        "id": node_ids,
        "shared_references": shared_refs,
        "cited_by_count": citation_counts
    })

    return df


def save_mock_datasets():
    """Generate and save all mock datasets."""
    fixtures_dir = Path("tests/fixtures")

    # Generate datasets
    print("Generating mock datasets...")

    raw_data = generate_mock_raw_openalex_data(100)
    raw_data.to_parquet(fixtures_dir / "raw" / "mock_raw_openalex.parquet")

    cleaned_data = generate_mock_cleaned_data(50)
    cleaned_data.to_parquet(fixtures_dir / "processed" / "mock_cleaned_data.parquet")

    classified_data = generate_mock_classified_data(30)
    classified_data.to_parquet(fixtures_dir / "processed" / "mock_classified_data.parquet")

    network_data = generate_mock_network_data(20)
    network_data.to_parquet(fixtures_dir / "processed" / "mock_network_data.parquet")

    # Generate reference snapshots for regression testing
    reference_results = {
        "classification_accuracy": 0.87,
        "domain_distribution": {
            "Political Science": 0.42,
            "Economics": 0.18,
            "Sociology": 0.32,
            "Other": 0.08
        },
        "avg_confidence": 0.76,
        "network_metrics": {
            "avg_degree": 4.2,
            "modularity": 0.34,
            "n_communities": 3
        }
    }

    with open(fixtures_dir / "reference_results.json", "w") as f:
        json.dump(reference_results, f, indent=2)

    print("Mock datasets saved to tests/fixtures/")
    print(f"  Raw data: {len(raw_data)} works")
    print(f"  Cleaned data: {len(cleaned_data)} works")
    print(f"  Classified data: {len(classified_data)} works")
    print(f"  Network data: {len(network_data)} nodes")


if __name__ == "__main__":
    save_mock_datasets()
