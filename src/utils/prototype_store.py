"""
Prototype Store
===============
Manages per-subcategory prototype embeddings (centroid vectors).
These are the "anchors" against which corpus papers are compared.

Two sources of prototypes:
  A. Curated seed texts  — hand-crafted canonical descriptions of each
                           subcategory (always available, deterministic)
  B. Centroid update     — after first-pass classification, recompute centroids
                           from the classified corpus (feedback loop)

The store is persisted to disk so it can be audited and reproduced.

Usage:
    store = PrototypeStore(embedding_client)
    store.build_from_seeds()
    label, score, domain = store.classify_one(text)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("prototype_store")


# ─────────────────────────────────────────────────────────────────────────────
# Seed Texts — Canonical descriptions per subcategory
# Written to capture the core intellectual identity of each subfield.
# These are NOT copied from any paper — they are purpose-built anchors.
# ─────────────────────────────────────────────────────────────────────────────

SEED_TEXTS: Dict[str, List[str]] = {
    # ── Political Science ────────────────────────────────────────────────────
    "Political Science::comparative_politics": [
        "Cross-national comparison of party systems and electoral outcomes across multiple countries. "
        "Comparative analysis of democratic institutions, government formation, and coalition dynamics. "
        "Structured focused comparison of political regimes and their variation.",
        "Quantitative cross-country dataset on political parties, elections, voting behavior. "
        "Regression analysis of institutional determinants across democracies. "
        "Multi-level modeling of political outcomes controlling for country fixed effects.",
    ],
    "Political Science::political_theory": [
        "Normative and conceptual analysis of populism as a political phenomenon. "
        "Theoretical framework for understanding the relationship between populism and democracy. "
        "Definitional debates around thin-centered ideology, discourse theory, and political logic.",
        "Philosophical examination of democratic theory, sovereignty, and political representation. "
        "Conceptual genealogy of populism from agrarian movements to contemporary manifestations. "
        "Theoretical typology distinguishing left and right populism along ideological dimensions.",
    ],
    "Political Science::electoral_politics": [
        "Electoral analysis of populist party vote shares and voter turnout. "
        "Voting behavior, electoral volatility, and protest voting in national elections. "
        "Survey data on electoral support for populist candidates and ballot choices.",
        "Party competition, strategic voting, and electoral realignment in populist contexts. "
        "Regression models predicting populist vote with socioeconomic and attitudinal variables. "
        "Panel study of electoral switching toward populist parties across election cycles.",
    ],
    "Political Science::democratic_theory": [
        "Democratic backsliding, autocratization, and illiberal democracy under populist governments. "
        "Erosion of checks and balances, judicial independence, and press freedom. "
        "Constitutional capture and institutional decay in populist regimes.",
        "Relationship between populism and liberal democracy: complementary or antithetical? "
        "Competitive authoritarianism and hybrid regimes emerging from populist rule. "
        "Rule of law, separation of powers, and democratic consolidation.",
    ],
    "Political Science::radical_right": [
        "Radical right, far-right, and extreme right parties in Western democracies. "
        "Nativist, authoritarian, and populist ideology in right-wing movements. "
        "Electoral breakthrough and mainstream response to far-right populism.",
        "Anti-immigration politics, ethnonationalism, and xenophobia in radical right platforms. "
        "Supply-side and demand-side explanations for radical right party success. "
        "Cordon sanitaire, normalization, and coalition strategies toward far-right parties.",
    ],
    "Political Science::latin_american_politics": [
        "Populism in Latin America: Venezuela, Bolivia, Ecuador, Argentina, Brazil, Peru, Mexico. "
        "Pink tide, left-wing populism, and resource nationalism in South America. "
        "Chávismo, Peronism, and the historical tradition of Latin American populism.",
        "Institutional decay and executive aggrandizement in Latin American populist governments. "
        "Social movement mobilization, indigenous politics, and popular sectors in the Andes. "
        "Electoral democracy and democratic erosion in Central and South America.",
    ],
    "Political Science::european_politics": [
        "Populism in Europe: Hungary, Poland, France, Italy, Netherlands, Spain, Germany, Austria. "
        "Euroscepticism, European integration, and populist challengers to mainstream parties. "
        "Fidesz, Law and Justice, National Rally, and the transformation of European party systems.",
        "East-Central European illiberalism and democratic backsliding within the European Union. "
        "Western European populist parties and their electoral strategies. "
        "Migration crisis, Islam, and identitarian politics in European populism.",
    ],
    # ── Economics ────────────────────────────────────────────────────────────
    "Economics::political_economy": [
        "Political economy of populism: macroeconomic policy under populist governments. "
        "Fiscal policy, public spending, and redistribution in populist regimes. "
        "Interaction between economic institutions and political incentives for populist policies.",
        "Economic voting and retrospective evaluation of government economic performance. "
        "Macroeconomic determinants of populist electoral success: growth, inflation, unemployment. "
        "Structural adjustment, economic reform, and populist backlash.",
    ],
    "Economics::redistribution": [
        "Inequality, redistribution, and welfare state retrenchment as drivers of populist support. "
        "Income polarization, social protection, and demand for redistribution. "
        "Welfare chauvinism and the exclusion of immigrants from social benefits.",
        "Subjective economic insecurity, perceived relative deprivation, and populist voting. "
        "Top income shares, Gini coefficient, and their relationship to political radicalization. "
        "Universal basic income, minimum wage, and populist economic platforms.",
    ],
    "Economics::trade_globalization": [
        "Trade liberalization, import competition, and economic dislocation from globalization. "
        "Manufacturing job losses, offshoring, and the populist backlash against free trade. "
        "China shock, automation, and labor market polarization.",
        "Protectionism, economic nationalism, and anti-globalization sentiment in populist politics. "
        "Regional variation in trade exposure and populist vote shares. "
        "Brexit, Trump tariffs, and the political economy of deglobalization.",
    ],
    "Economics::financial_crisis": [
        "Financial crisis, austerity, and the rise of populist parties after 2008. "
        "Sovereign debt crisis, banking collapse, and anti-establishment sentiment. "
        "Great Recession, unemployment shock, and electoral consequences for mainstream parties.",
        "Austerity politics, spending cuts, and voter punishment of incumbent governments. "
        "Economic grievances, financial hardship, and support for populist challengers. "
        "Post-crisis political polarization and the breakdown of centrist consensus.",
    ],
    # ── Sociology ────────────────────────────────────────────────────────────
    "Sociology::social_movements": [
        "Social movement mobilization, collective action, and populist protest. "
        "Occupy, Yellow Vests, Tea Party, and grassroots populist movements. "
        "Resource mobilization, political opportunity structures, and framing processes.",
        "Civil society, civic engagement, and bottom-up populist organizing. "
        "Contentious politics, repertoires of action, and populist challengers. "
        "Movement-party nexus and the institutionalization of populist protest.",
    ],
    "Sociology::identity_politics": [
        "Identity politics, nativism, nationalism, and ethnic boundaries in populism. "
        "Cultural threat, group identity, and anti-immigrant attitudes. "
        "In-group versus out-group dynamics, people versus elite framing.",
        "Religious identity, secularization, and the role of Christianity in right-wing populism. "
        "Ethnic nationalism, racial resentment, and white identity politics. "
        "Gender, masculinity, and the appeal of authoritarian populism.",
    ],
    "Sociology::media_communication": [
        "Media framing of populist leaders and movements. Social media, Twitter, Facebook. "
        "Populist communication style: anti-establishment rhetoric, direct address, emotional appeals. "
        "Digital populism, algorithmic amplification, and online mobilization.",
        "Political communication, agenda-setting, and the media logic of populism. "
        "Disinformation, fake news, and media trust in populist contexts. "
        "Tabloid press, partisan media, and the construction of populist narratives.",
    ],
    "Sociology::culture_values": [
        "Cultural backlash, post-materialism, and the value divide underlying populism. "
        "Silent revolution, value change, and the counter-reaction toward tradition and authority. "
        "Cosmopolitan versus communitarian values and the new political cleavage.",
        "Status anxiety, cultural displacement, and nostalgia in populist support. "
        "Authoritarian personality, social dominance orientation, and populist attitudes. "
        "Resentment politics, perceived disrespect, and the politics of recognition.",
    ],
    # ── Other ─────────────────────────────────────────────────────────────────
    "Other::international_relations": [
        "Populism and foreign policy: nationalism, sovereignty, and international institutions. "
        "Anti-multilateralism, withdrawal from international agreements, and populist geopolitics. "
        "Transatlantic relations, NATO, and the foreign policy of populist governments.",
    ],
    "Other::history": [
        "Historical origins of populism: agrarian movements, Narodniks, American Populist Party. "
        "Interwar fascism, Weimar Republic, and historical analogies with contemporary populism. "
        "Long-run historical analysis of populist cycles and democratic crises.",
    ],
    "Other::psychology": [
        "Psychological correlates of populist attitudes: authoritarianism, need for cognition. "
        "Personality traits, dark triad, and support for populist leaders. "
        "Cognitive styles, conspiracy thinking, and anti-establishment psychology.",
    ],
    "Other::geography": [
        "Spatial analysis of populist vote shares: urban-rural divide, regional inequality. "
        "Geographic concentration of populist support in left-behind regions and peripheries. "
        "Place-based grievances, spatial polarization, and electoral geography of populism.",
    ],
    "Other::interdisciplinary": [
        "Interdisciplinary study combining political science, economics, sociology, and psychology. "
        "Mixed methods analysis of populism using multiple theoretical frameworks. "
        "Review article synthesizing research across disciplines on populism.",
    ],
}

# Domain lookup from subcategory key
SUBCATEGORY_TO_DOMAIN: Dict[str, str] = {
    sc.split("::")[1]: sc.split("::")[0] for sc in SEED_TEXTS.keys()
}

ALL_LABELS: List[str] = list(SEED_TEXTS.keys())


# ─────────────────────────────────────────────────────────────────────────────
# Prototype Store
# ─────────────────────────────────────────────────────────────────────────────


class PrototypeStore:
    """
    Holds per-subcategory centroid vectors.
    Built from seed texts; optionally updated from classified corpus.
    """

    def __init__(self, embedding_client):
        self._client = embedding_client
        # label → unit-norm centroid vector
        self._centroids: Dict[str, np.ndarray] = {}
        self._backend_name: Optional[str] = None
        self._metadata: Dict = {}

    # ── Build ─────────────────────────────────────────────────────────────────

    def build_from_seeds(self) -> "PrototypeStore":
        """
        Embed all seed texts per subcategory and average into centroid vectors.
        """
        logger.info("Building prototype embeddings from %d subcategories...", len(SEED_TEXTS))
        for label, texts in SEED_TEXTS.items():
            vecs = self._client.embed_batch(texts)  # (N_seeds, D)
            centroid = vecs.mean(axis=0)
            # Unit-normalise
            norm = np.linalg.norm(centroid)
            self._centroids[label] = centroid / norm if norm > 0 else centroid

        self._backend_name = self._client.backend_name
        self._metadata = {
            "backend": self._backend_name,
            "n_labels": len(self._centroids),
            "labels": ALL_LABELS,
            "source": "seeds",
        }
        logger.info(
            "Prototype store built: %d centroids, backend=%s",
            len(self._centroids),
            self._backend_name,
        )
        return self

    # ── Classify ─────────────────────────────────────────────────────────────

    def classify_one(
        self,
        text: str,
        top_k: int = 3,
    ) -> Tuple[str, str, float, List[Tuple[str, float]]]:
        """
        Classify a single text by cosine similarity to centroids.

        Returns:
            domain        : str
            subcategory   : str
            best_score    : float (cosine similarity, 0–1)
            top_k_matches : List[(label, score)]
        """
        vec = self._client.embed_one(text)
        scores = {
            label: float(np.dot(vec, centroid)) for label, centroid in self._centroids.items()
        }
        sorted_matches = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_label, best_score = sorted_matches[0]
        domain, subcategory = best_label.split("::")
        return domain, subcategory, best_score, sorted_matches[:top_k]

    def classify_batch(
        self,
        texts: List[str],
        top_k: int = 3,
    ) -> List[Tuple[str, str, float, List[Tuple[str, float]]]]:
        """
        Classify a list of texts. Returns list of (domain, subcat, score, top_k).
        Uses matrix multiplication for efficiency.
        """
        if not texts:
            return []

        # Build centroid matrix (L, D)
        labels = list(self._centroids.keys())
        centroid_matrix = np.stack([self._centroids[l] for l in labels])  # (L, D)

        # Embed all texts at once (N, D)
        vecs = self._client.embed_batch(texts)

        # Cosine similarity matrix (N, L) — both sides already unit-normed
        sim_matrix = vecs @ centroid_matrix.T  # (N, L)

        results = []
        for i in range(len(texts)):
            row = sim_matrix[i]
            sorted_idx = np.argsort(row)[::-1]
            top_k_matches = [(labels[j], float(row[j])) for j in sorted_idx[:top_k]]
            best_label, best_score = top_k_matches[0]
            domain, subcategory = best_label.split("::")
            results.append((domain, subcategory, best_score, top_k_matches))

        return results

    # ── Centroid Update (Feedback Loop) ──────────────────────────────────────

    def update_centroids_from_corpus(
        self,
        texts: List[str],
        labels: List[str],  # "Domain::subcategory" format
        min_samples: int = 5,
    ) -> Dict[str, int]:
        """
        Recompute centroids using classified corpus texts (feedback loop).
        Only updates labels with ≥ min_samples to avoid noise.

        Returns dict of {label: n_samples_used}.
        """
        from collections import defaultdict

        vecs = self._client.embed_batch(texts)
        label_vecs: Dict[str, List[np.ndarray]] = defaultdict(list)

        for vec, label in zip(vecs, labels):
            label_vecs[label].append(vec)

        updated = {}
        for label, label_vec_list in label_vecs.items():
            if len(label_vec_list) < min_samples:
                logger.debug(
                    "Skipping centroid update for %s (only %d samples)", label, len(label_vec_list)
                )
                continue
            centroid = np.stack(label_vecs[label]).mean(axis=0)
            norm = np.linalg.norm(centroid)
            self._centroids[label] = centroid / norm if norm > 0 else centroid
            updated[label] = len(label_vec_list)

        logger.info("Centroid update: %d labels refreshed from corpus", len(updated))
        self._metadata["source"] = "seeds+corpus_feedback"
        self._metadata["corpus_update"] = updated
        return updated

    # ── Persistence ──────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        """Save centroids as .npz + metadata as JSON."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        arrays = {k.replace("::", "__"): v for k, v in self._centroids.items()}
        np.savez_compressed(path, **arrays)
        meta_path = path.replace(".npz", "_metadata.json")
        with open(meta_path, "w") as f:
            import json

            json.dump(self._metadata, f, indent=2)
        logger.info("Prototype store saved to %s", path)

    def load(self, path: str) -> "PrototypeStore":
        """Load centroids from .npz file."""
        data = np.load(path)
        self._centroids = {k.replace("__", "::"): data[k].astype(np.float32) for k in data.files}
        meta_path = path.replace(".npz", "_metadata.json")
        if Path(meta_path).exists():
            import json

            with open(meta_path) as f:
                self._metadata = json.load(f)
        logger.info("Prototype store loaded: %d centroids from %s", len(self._centroids), path)
        return self

    @property
    def labels(self) -> List[str]:
        return list(self._centroids.keys())

    @property
    def n_labels(self) -> int:
        return len(self._centroids)
