"""
Synthetic Test Data Generator
==============================
Generates a realistic mock dataset that mirrors the OpenAlex schema.
Used for pipeline testing when the API is not accessible.
Writes to data/raw/ as if produced by the data_collection agent.

Run:
    python tests/generate_test_data.py --n 150 --config config/config.yaml
"""

import argparse
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.io_utils import load_yaml, save_json, save_parquet, timestamped_path

random.seed(42)
np.random.seed(42)

# ── Realistic fixtures ────────────────────────────────────────────────────

TITLES = [
    "Populism and Democracy: Theoretical Challenges",
    "The Economic Roots of Populism: A Cross-National Study",
    "Social Media and Populist Communication Strategies",
    "Electoral Populism in Latin America: Venezuela and Brazil",
    "Radical Right Populism in Western Europe",
    "Trade Globalization and Populist Backlash",
    "Populism as a Thin-Centered Ideology",
    "Cultural Backlash and the Rise of Populist Movements",
    "Financial Crisis and Populist Voting Behavior",
    "Left Populism vs Right Populism: A Comparative Analysis",
    "Democratic Backsliding and Populist Governments",
    "Populism and Redistribution: Evidence from Survey Data",
    "Media Framing of Populist Leaders",
    "Populism in Post-Communist Europe: Hungary and Poland",
    "Identity Politics and Populist Mobilization",
    "Populism and Nationalism: Strange Bedfellows?",
    "The Populist Zeitgeist: A Global Survey",
    "Economic Inequality and Populist Electoral Success",
    "Populist Parties and Coalition Politics",
    "Anti-Elitism and Populist Discourse Analysis",
    "Illiberal Democracy and Populist Constitutionalism",
    "Grievance Politics: Populism and Resentment",
    "Populism and Foreign Policy: An Empirical Analysis",
    "Rural Populism and Urban Divide",
    "Nativist Populism and Immigration Politics",
    "Historical Roots of Agrarian Populism",
    "Psychological Correlates of Populist Attitudes",
    "Populism and the Media Ecosystem",
    "Party System Fragmentation and Populist Success",
    "Populism in Power: Governance and Policy",
    "Protest Voting and Populist Electoral Support",
    "Populist Rhetoric and Polarization",
    "Economic Grievances and Populist Vote",
    "Populism and Anti-Globalization Sentiment",
    "Gender and Populism: A Feminist Perspective",
    "Populism in the Developing World",
    "Electoral Volatility and Populist Parties",
    "Techno-Populism and Digital Movements",
    "Charismatic Leadership and Populist Politics",
    "Populism and the Rule of Law",
    "Welfare Chauvinism in Populist Parties",
    "Spatial Inequality and Populist Vote Share",
    "Post-materialism and the Populist Divide",
    "Populism and European Integration",
    "Crisis of Representation and Populist Surge",
    "Left-Wing Populism in Southern Europe",
    "Populist Communication on Twitter",
    "The Populist Appeal: Promise and Peril",
    "Populism and Judicial Independence",
    "Agrarian Populism in Historical Perspective",
]

ABSTRACTS = [
    "This article examines the relationship between populism and democracy, arguing that populism poses fundamental challenges to liberal democratic institutions while simultaneously reflecting genuine democratic grievances.",
    "We analyze cross-national data to assess the economic drivers of populist voting. Results indicate that trade-induced job displacement and austerity measures are strong predictors of populist electoral support.",
    "Drawing on computational text analysis of social media platforms, we show that populist actors strategically adapt their communication to exploit algorithmic amplification and mobilize supporters.",
    "This comparative study of Venezuela and Brazil demonstrates how charismatic leaders exploit institutional weaknesses to consolidate populist governments, with significant implications for regional democracy.",
    "Using party manifestos and expert surveys, we trace the evolution of radical right populism across fifteen Western European countries from 1990 to 2020.",
    "We construct a theoretical model linking trade liberalization to cultural and economic displacement, which in turn fuels populist backlash among manufacturing workers.",
    "Building on Mudde's thin-centered ideology framework, we propose refinements that better account for ideological variation within the populist family.",
    "Survey evidence from eighteen countries supports the cultural backlash hypothesis: post-materialist value change triggers a counter-reaction that benefits populist and authoritarian parties.",
    "Panel data analysis reveals a robust link between financial crises and populist vote shares in subsequent elections, mediated by perceptions of elite corruption.",
    "We develop a typology distinguishing left and right populism along economic and cultural dimensions, illustrating the framework with cases from Europe and Latin America.",
]

AUTHORS_POOL = [
    {"name": "Cas Mudde", "institution": "University of Georgia"},
    {
        "name": "Cristóbal Rovira Kaltwasser",
        "institution": "Pontificia Universidad Católica de Chile",
    },
    {"name": "Pippa Norris", "institution": "Harvard University"},
    {"name": "Ronald Inglehart", "institution": "University of Michigan"},
    {"name": "Jan-Werner Müller", "institution": "Princeton University"},
    {"name": "Chantal Mouffe", "institution": "University of Westminster"},
    {"name": "Ernesto Laclau", "institution": "University of Essex"},
    {"name": "Kirk Hawkins", "institution": "Brigham Young University"},
    {"name": "Dani Rodrik", "institution": "Harvard Kennedy School"},
    {"name": "Yascha Mounk", "institution": "Johns Hopkins University"},
    {"name": "Anna Grzymala-Busse", "institution": "Stanford University"},
    {"name": "Steven Levitsky", "institution": "Harvard University"},
    {"name": "Daniel Ziblatt", "institution": "Harvard University"},
    {"name": "Frances Fukuyama", "institution": "Stanford University"},
    {"name": "Wendy Brown", "institution": "UC Berkeley"},
    {"name": "Michael Sandel", "institution": "Harvard University"},
    {"name": "Thomas Piketty", "institution": "Paris School of Economics"},
    {"name": "Nadia Urbinati", "institution": "Columbia University"},
    {"name": "Benjamin Moffitt", "institution": "Australian Catholic University"},
    {"name": "Ruth Levitas", "institution": "University of Bristol"},
]

JOURNALS = [
    "European Journal of Political Research",
    "Comparative Political Studies",
    "Journal of Democracy",
    "Political Studies",
    "Party Politics",
    "West European Politics",
    "Democratization",
    "Political Research Quarterly",
    "Electoral Studies",
    "Government and Opposition",
    "Journal of European Public Policy",
    "Nations and Nationalism",
    "New Political Economy",
    "Political Geography",
    "American Political Science Review",
    "World Politics",
    "Politics & Society",
    "Socio-Economic Review",
]

CONCEPTS_POOL = [
    {"id": "C2780916012", "name": "Populism", "level": 2, "score": 0.95},
    {"id": "C17744445", "name": "Political science", "level": 0, "score": 0.90},
    {"id": "C150903083", "name": "Democracy", "level": 1, "score": 0.85},
    {"id": "C199539241", "name": "Politics", "level": 1, "score": 0.80},
    {"id": "C162324750", "name": "Economics", "level": 0, "score": 0.75},
    {"id": "C144024400", "name": "Sociology", "level": 0, "score": 0.70},
    {"id": "C2776943663", "name": "Far-right politics", "level": 2, "score": 0.65},
    {"id": "C175444787", "name": "Political economy", "level": 1, "score": 0.70},
    {"id": "C2778154952", "name": "Social movement", "level": 2, "score": 0.65},
    {"id": "C523546767", "name": "Identity politics", "level": 2, "score": 0.60},
    {"id": "C2778793908", "name": "Economic inequality", "level": 2, "score": 0.75},
    {"id": "C136229726", "name": "Media studies", "level": 1, "score": 0.55},
    {"id": "C2779415391", "name": "Nationalism", "level": 2, "score": 0.60},
    {"id": "C2780591229", "name": "Elections", "level": 2, "score": 0.70},
    {"id": "C2776702681", "name": "Voting behavior", "level": 2, "score": 0.65},
    {"id": "C2780258038", "name": "Political parties", "level": 2, "score": 0.72},
    {"id": "C108827166", "name": "Public administration", "level": 1, "score": 0.50},
    {"id": "C175203074", "name": "Globalization", "level": 1, "score": 0.68},
    {"id": "C2781063489", "name": "Immigration", "level": 2, "score": 0.58},
]

COUNTRIES = ["US", "DE", "GB", "FR", "ES", "IT", "NL", "SE", "BR", "AR", "CL", "HU", "PL"]
INSTITUTIONS = [
    ("I136199984", "Harvard University", "US"),
    ("I97018004", "Princeton University", "US"),
    ("I40347166", "Stanford University", "US"),
    ("I185261750", "University of Oxford", "GB"),
    ("I41461786", "Sciences Po Paris", "FR"),
    ("I153911831", "University of Amsterdam", "NL"),
    ("I205783295", "Humboldt University of Berlin", "DE"),
    ("I214568946", "London School of Economics", "GB"),
    ("I168167295", "Columbia University", "US"),
    ("I169248326", "University of Toronto", "CA"),
]


# Shared reference pool — shared across all generated works to create coupling
SHARED_REF_POOL = [f"https://openalex.org/W{1000000000 + i}" for i in range(80)]

# Canonical "landmark" works frequently cited
LANDMARK_REFS = SHARED_REF_POOL[:20]


def make_work(i: int) -> dict:
    """Generate one realistic synthetic work with overlapping references."""
    work_id = f"https://openalex.org/W{2000000000 + i}"
    title_base = TITLES[i % len(TITLES)]
    title = title_base if i < len(TITLES) else f"{title_base} — Study {i}"
    abstract = ABSTRACTS[i % len(ABSTRACTS)]
    year = int(
        np.random.choice(
            range(1995, 2024),
            p=np.array([max(0.01, (y - 1994) * 0.004) for y in range(1995, 2024)])
            / sum([max(0.01, (y - 1994) * 0.004) for y in range(1995, 2024)]),
        )
    )

    cited_by = int(np.random.pareto(1.2) * 20)

    n_authors = random.choices([1, 2, 3, 4], weights=[35, 40, 20, 5])[0]
    chosen_authors = random.sample(AUTHORS_POOL, min(n_authors, len(AUTHORS_POOL)))
    authors = []
    for a in chosen_authors:
        inst_id, inst_name, country = random.choice(INSTITUTIONS)
        authors.append(
            {
                "id": f"https://openalex.org/A{hash(a['name']) % 10000000:08d}",
                "name": a["name"],
                "orcid": None,
                "institutions": [
                    {
                        "id": f"https://openalex.org/{inst_id}",
                        "name": inst_name,
                        "country": country,
                        "type": "education",
                    }
                ],
            }
        )

    n_concepts = random.randint(2, 5)
    concepts_raw = random.sample(CONCEPTS_POOL, n_concepts)
    concepts = sorted(concepts_raw, key=lambda x: x["score"], reverse=True)

    # References: mix of shared pool (creates coupling) + unique refs
    # Each paper cites 3-6 landmark refs + 5-15 from shared pool + a few unique
    n_landmark = random.randint(2, 5)
    n_shared = random.randint(4, 12)
    n_unique = random.randint(2, 6)
    refs = (
        random.sample(LANDMARK_REFS, min(n_landmark, len(LANDMARK_REFS)))
        + random.sample(SHARED_REF_POOL[20:], min(n_shared, len(SHARED_REF_POOL) - 20))
        + [
            f"https://openalex.org/W{random.randint(3000000000, 3999999999)}"
            for _ in range(n_unique)
        ]
    )
    refs = list(set(refs))  # deduplicate

    journal = random.choice(JOURNALS)
    journal_id = f"https://openalex.org/S{hash(journal) % 100000:06d}"

    return {
        "id": work_id,
        "doi": f"https://doi.org/10.1080/{random.randint(10000000, 99999999)}",
        "title": title,
        "abstract": abstract,
        "year": year,
        "publication_date": f"{year}-{random.randint(1,12):02d}-01",
        "cited_by_count": cited_by,
        "authors": authors,
        "institutions": [inst for a in authors for inst in a["institutions"]],
        "concepts": concepts,
        "journal": journal,
        "journal_id": journal_id,
        "open_access": random.random() < 0.3,
        "type": "article",
        "references": refs,
        "mesh_terms": [],
        "keywords_matched": [random.choice(["populism", "populist", "populists"])],
        "query_batch": f"query_{random.choice(['populism', 'populist', 'populists'])}",
    }


def main():
    parser = argparse.ArgumentParser(description="Synthetic Test Data Generator")
    parser.add_argument("--n", type=int, default=150, help="Number of records to generate")
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    config = load_yaml(args.config)
    raw_dir = config["paths"]["data_raw"]
    Path(raw_dir).mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.n} synthetic OpenAlex records...")
    records = [make_work(i) for i in range(args.n)]
    df = pd.DataFrame(records)

    output_path = timestamped_path(raw_dir, "openalex_raw", "parquet")
    save_parquet(df, str(output_path))

    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "test_synthetic",
        "total_records": len(df),
        "output_file": str(output_path),
        "query_stats": [{"term": "populism", "new_records": args.n, "elapsed_s": 0.0}],
        "api_parameters": {"source": "synthetic_generator", "seed": 42},
        "columns": list(df.columns),
        "abstract_coverage": int((df["abstract"].str.len() > 20).sum()),
        "concept_coverage": int((df["concepts"].apply(len) > 0).sum()),
    }
    save_json(manifest, f"{raw_dir}/collection_manifest.json")

    print(f"✓ Written {len(df)} records to {output_path}")
    print(f"✓ Manifest written to {raw_dir}/collection_manifest.json")
    print(f"  Year range: {int(df['year'].min())}–{int(df['year'].max())}")
    print(f"  Avg citations: {df['cited_by_count'].mean():.1f}")


if __name__ == "__main__":
    main()
