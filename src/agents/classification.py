"""
Classification Agent — 3-Stage Hybrid Architecture
====================================================

Stage 1 │ Rule-Based          High precision, zero compute cost
        │ OpenAlex concepts + keyword heuristics
        │ confidence >= rule_threshold → accept immediately
        ▼
Stage 2 │ Embedding Similarity  Core engine — fast, deterministic, scalable
        │ title + abstract + concepts → dense vector
        │ cosine >= embed_high_threshold → accept
        │ cosine in [embed_low, embed_high] → forward to LLM
        │ cosine < embed_low_threshold → flag as outlier
        ▼
Stage 3 │ LLM (Selective)       High-precision disambiguation only
        │ Invoked for ~10-30% of corpus
        │ Embedding top-K hints passed as context to LLM

Design principles:
  - Deterministic path (Stage 1+2) handles >= 70% of corpus
  - LLM is a scalpel, not a hammer
  - Every decision is auditable via domain_source + classification_notes
  - Feedback loop: high-confidence results update centroids

Standalone:
    python src/agents/classification.py --config config/config.yaml
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict, Counter
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.io_utils import load_parquet, save_parquet, save_json, load_yaml, safe_list
from src.utils.logging_utils import setup_logger
from src.utils.embedding_client import EmbeddingClient
from src.utils.prototype_store import PrototypeStore, SEED_TEXTS, SUBCATEGORY_TO_DOMAIN
from src.utils.llm_client import (
    OllamaClient, validate_classification_response,
    VALID_DOMAINS, VALID_SUBCATEGORIES,
)


# ── Domain / subcategory constants ────────────────────────────────────────────

DOMAIN_SUBCATEGORY: Dict[str, List[str]] = {
    "Political Science": [
        "comparative_politics", "political_theory", "electoral_politics",
        "democratic_theory", "radical_right", "latin_american_politics", "european_politics",
    ],
    "Economics": ["political_economy", "redistribution", "trade_globalization", "financial_crisis"],
    "Sociology": ["social_movements", "identity_politics", "media_communication", "culture_values"],
    "Other": ["international_relations", "history", "psychology", "geography", "interdisciplinary"],
}

CONCEPT_DOMAIN_MAP: Dict[str, str] = {
    "political science": "Political Science", "politics": "Political Science",
    "democracy": "Political Science", "populism": "Political Science",
    "government": "Political Science", "political party": "Political Science",
    "parliament": "Political Science", "election": "Political Science",
    "voting": "Political Science", "economics": "Economics",
    "economy": "Economics", "political economy": "Economics",
    "macroeconomics": "Economics", "inequality": "Economics",
    "redistribution": "Economics", "trade": "Economics",
    "sociology": "Sociology", "social movement": "Sociology",
    "identity": "Sociology", "media studies": "Sociology",
    "communication": "Sociology", "culture": "Sociology",
}

SUBCATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "comparative_politics": ["comparative", "cross-national", "cross national"],
    "political_theory": ["theory", "theoretical", "conceptual", "normative", "definition"],
    "electoral_politics": ["election", "electoral", "voting", "vote", "ballot"],
    "democratic_theory": ["democracy", "democratic", "backsliding", "illiberal", "autocratiz"],
    "radical_right": ["far-right", "radical right", "extreme right", "right-wing extremi"],
    "latin_american_politics": ["latin america", "brazil", "venezuela", "argentina", "mexico", "peru"],
    "european_politics": ["europe", "european union", "france", "germany", "italy", "spain"],
    "political_economy": ["political economy", "macroeconomic", "fiscal policy", "monetary"],
    "redistribution": ["redistribution", "welfare", "social protection", "inequality"],
    "trade_globalization": ["globalization", "globalisation", "trade", "protectionism"],
    "financial_crisis": ["financial crisis", "recession", "austerity", "economic crisis"],
    "social_movements": ["social movement", "mobilization", "mobilisation", "protest"],
    "identity_politics": ["identity", "ethnic", "nationalism", "religion", "nativism"],
    "media_communication": ["media", "communication", "framing", "social media", "twitter"],
    "culture_values": ["culture", "values", "post-material", "cultural backlash", "resentment"],
    "international_relations": ["international", "foreign policy", "geopolitics", "diplomacy"],
    "history": ["historical", "history", "19th century", "20th century", "interwar"],
    "psychology": ["psychological", "psychology", "personality", "cognitive", "attitude"],
    "geography": ["spatial", "geographic", "regional", "urban", "rural"],
    "interdisciplinary": [],
}


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — Rule-Based
# ─────────────────────────────────────────────────────────────────────────────

def stage1_rule(row: pd.Series) -> Tuple[str, str, float]:
    concepts = safe_list(row.get("concepts"))
    title    = str(row.get("title")    or "").lower()
    abstract = str(row.get("abstract") or "").lower()
    text     = title + " " + abstract

    domain_scores: Dict[str, float] = defaultdict(float)
    for c in concepts:
        if not isinstance(c, dict):
            continue
        name  = c.get("name",  "").lower()
        score = float(c.get("score", 0.5))
        for fragment, domain in CONCEPT_DOMAIN_MAP.items():
            if fragment in name:
                domain_scores[domain] += score

    total = sum(domain_scores.values()) if domain_scores else 0.0
    if total > 0:
        best       = max(domain_scores, key=domain_scores.__getitem__)
        confidence = domain_scores[best] / total
    else:
        best, confidence = "Other", 0.0

    valid_subs = DOMAIN_SUBCATEGORY.get(best, ["interdisciplinary"])
    subcategory = valid_subs[-1]
    for sub in valid_subs:
        if any(kw in text for kw in SUBCATEGORY_KEYWORDS.get(sub, [])):
            subcategory = sub
            break

    return best, subcategory, round(confidence, 4)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — Embedding Input Builder
# ─────────────────────────────────────────────────────────────────────────────

def make_input_text(row: pd.Series) -> str:
    title    = str(row.get("title")    or "")
    abstract = str(row.get("abstract") or "")[:600]
    concepts = ", ".join(
        c.get("name", "") for c in safe_list(row.get("concepts"))[:4]
        if isinstance(c, dict) and c.get("name")
    )
    parts = [title]
    if abstract:
        parts.append(abstract)
    if concepts:
        parts.append(f"Topics: {concepts}")
    return " | ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — LLM
# ─────────────────────────────────────────────────────────────────────────────

def stage3_llm(
    row: pd.Series,
    client: OllamaClient,
    llm_cfg: dict,
    logger: logging.Logger,
    embed_top_k: Optional[List[Tuple[str, float]]] = None,
) -> Tuple[str, str, float, str]:

    title    = str(row.get("title")    or "")
    abstract = str(row.get("abstract") or "")[:600]
    concepts = [c.get("name", "") for c in safe_list(row.get("concepts"))[:5]
                if isinstance(c, dict)]

    hint_str = ""
    if embed_top_k:
        hint_str = "\nEmbedding similarity hints (top matches from semantic search):\n"
        for label, score in embed_top_k[:3]:
            hint_str += f"  - {label}  (score={score:.3f})\n"

    system_prompt = llm_cfg["prompts"]["classification_system"]
    user_prompt   = (
        llm_cfg["prompts"]["classification_user"].format(
            title    = title,
            abstract = abstract,
            concepts = ", ".join(concepts) if concepts else "none",
        ) + hint_str
    )

    result, success = client.generate_json(
        system_prompt  = system_prompt,
        user_prompt    = user_prompt,
        required_keys  = ["domain", "subcategory", "confidence"],
    )

    if not success or result is None:
        return "Other", "interdisciplinary", 0.0, "llm_failed"

    is_valid, err = validate_classification_response(result)
    if not is_valid:
        logger.warning("LLM invalid (%s) for %s", err, row.get("id", "?"))
        return "Other", "interdisciplinary", 0.0, "llm_invalid"

    return result["domain"], result["subcategory"], float(result["confidence"]), "llm"


# ─────────────────────────────────────────────────────────────────────────────
# HybridClassifier
# ─────────────────────────────────────────────────────────────────────────────

class HybridClassifier:

    def __init__(
        self,
        embed_client:          EmbeddingClient,
        prototype_store:       PrototypeStore,
        llm_client:            Optional[OllamaClient],
        rule_threshold:        float = 0.75,
        embed_high_threshold:  float = 0.80,
        embed_low_threshold:   float = 0.55,
        logger:                Optional[logging.Logger] = None,
    ):
        self.embed_client          = embed_client
        self.store                 = prototype_store
        self.llm_client            = llm_client
        self.rule_threshold        = rule_threshold
        self.embed_high_threshold  = embed_high_threshold
        self.embed_low_threshold   = embed_low_threshold
        self.logger                = logger or logging.getLogger("hybrid_classifier")
        self.stats                 = Counter()

    def classify_dataframe(self, df: pd.DataFrame, llm_cfg: Optional[dict] = None) -> pd.DataFrame:
        n = len(df)
        self.logger.info("3-stage classification of %d records", n)

        corpus_texts = [make_input_text(row) for _, row in df.iterrows()]

        # Stage 1 — all records
        self.logger.info("Stage 1: rule-based...")
        s1 = [stage1_rule(row) for _, row in df.iterrows()]

        needs_s2 = [i for i, (_, _, conf) in enumerate(s1) if conf < self.rule_threshold]
        self.logger.info("  Stage 1 accepted: %d / %d", n - len(needs_s2), n)

        # Stage 2 — embedding similarity
        s2: Dict[int, Tuple] = {}
        if needs_s2:
            self.logger.info("Stage 2: embedding similarity for %d records...", len(needs_s2))
            texts_s2   = [corpus_texts[i] for i in needs_s2]
            embed_preds = self.store.classify_batch(texts_s2, top_k=3)
            for idx, pred in zip(needs_s2, embed_preds):
                s2[idx] = pred

        needs_s3 = [
            i for i in needs_s2
            if self.embed_low_threshold <= s2[i][2] < self.embed_high_threshold
        ]
        n_accepted_s2 = sum(1 for i in needs_s2 if s2[i][2] >= self.embed_high_threshold)
        n_outlier     = sum(1 for i in needs_s2 if s2[i][2] < self.embed_low_threshold)
        self.logger.info(
            "  Stage 2: accepted=%d, to LLM=%d, outliers=%d",
            n_accepted_s2, len(needs_s3), n_outlier
        )

        # Stage 3 — LLM (selective)
        s3: Dict[int, Tuple] = {}
        llm_ok = self.llm_client is not None and self.llm_client.is_available()
        if needs_s3:
            if llm_ok:
                self.logger.info("Stage 3: LLM for %d ambiguous records...", len(needs_s3))
                for i in needs_s3:
                    row    = df.iloc[i]
                    top_k  = s2[i][3]
                    s3[i]  = stage3_llm(row, self.llm_client, llm_cfg, self.logger, top_k)
            else:
                self.logger.warning(
                    "LLM unavailable — %d ambiguous records use best embedding result",
                    len(needs_s3)
                )

        # Assemble
        domains, subcats, confs, sources, notes = [], [], [], [], []
        for i in range(n):
            rd, rs, rc = s1[i]

            if rc >= self.rule_threshold:
                self.stats["stage1"] += 1
                domains.append(rd); subcats.append(rs); confs.append(rc)
                sources.append("rule")
                notes.append(f"rule_conf={rc:.3f}")
                continue

            ed, es, ec, etop = s2[i]

            if ec >= self.embed_high_threshold:
                self.stats["stage2_high"] += 1
                domains.append(ed); subcats.append(es); confs.append(ec)
                sources.append("embedding")
                notes.append(f"rule={rc:.3f}|emb={ec:.3f}")
                continue

            if i in s3:
                ld, ls, lc, lsrc = s3[i]
                self.stats["stage3"] += 1
                domains.append(ld); subcats.append(ls); confs.append(lc)
                sources.append(lsrc)
                notes.append(f"rule={rc:.3f}|emb={ec:.3f}|llm={lc:.3f}|emb_hint={ed}/{es}")
                continue

            # Fallback: best embedding result
            tag = "embedding_outlier" if ec < self.embed_low_threshold else "embedding_ambiguous"
            self.stats[tag] += 1
            domains.append(ed); subcats.append(es); confs.append(ec)
            sources.append(tag)
            notes.append(f"rule={rc:.3f}|emb={ec:.3f}|no_llm")

        df = df.copy()
        df["domain"]               = domains
        df["subcategory"]          = subcats
        df["domain_confidence"]    = [round(float(c), 4) for c in confs]
        df["domain_source"]        = sources
        df["classification_notes"] = notes

        self._log_summary(n)
        return df

    def _log_summary(self, total: int):
        self.logger.info("── Classification Routing ───────────────────────────")
        for stage, count in sorted(self.stats.items()):
            self.logger.info("  %-28s %4d  (%5.1f%%)", stage, count, count/total*100)
        llm = self.stats.get("stage3", 0)
        det = self.stats.get("stage1", 0) + self.stats.get("stage2_high", 0)
        self.logger.info("  Deterministic rate: %.1f%%  |  LLM rate: %.1f%%",
                         det/total*100, llm/total*100)

    def routing_stats(self, total: int) -> dict:
        return {k: {"count": v, "rate": round(v/total, 4)} for k, v in self.stats.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Feedback Loop
# ─────────────────────────────────────────────────────────────────────────────

def run_feedback_loop(
    df: pd.DataFrame,
    classifier: HybridClassifier,
    corpus_texts: List[str],
    min_samples: int = 5,
    logger: Optional[logging.Logger] = None,
) -> dict:
    log = logger or logging.getLogger("feedback_loop")
    log.info("Feedback loop: updating centroids from high-confidence results...")

    mask = (
        (df["domain_confidence"] >= 0.80) &
        (df["domain_source"].isin(["rule", "embedding"]))
    )
    df_hc = df[mask]
    log.info("  High-confidence records: %d / %d", len(df_hc), len(df))

    if len(df_hc) < min_samples:
        log.warning("  Insufficient samples — skipping feedback loop")
        return {}

    labels = [f"{r['domain']}::{r['subcategory']}" for _, r in df_hc.iterrows()]
    texts  = [corpus_texts[i] for i in df_hc.index]
    return classifier.store.update_centroids_from_corpus(texts, labels, min_samples)


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="3-Stage Hybrid Classification Agent")
    parser.add_argument("--config",          default="config/config.yaml")
    parser.add_argument("--llm-config",      default="config/llm.yaml")
    parser.add_argument("--no-feedback",     action="store_true")
    parser.add_argument("--load-prototypes", metavar="PATH")
    args = parser.parse_args()

    config  = load_yaml(args.config)
    llm_cfg = load_yaml(args.llm_config)
    logger  = setup_logger("classification", config["paths"]["logs"])
    logger.info("=== Classification Agent [3-Stage Hybrid] starting ===")

    df = load_parquet(f"{config['paths']['data_clean']}/openalex_clean.parquet")
    logger.info("Loaded %d records", len(df))
    corpus_texts = [make_input_text(row) for _, row in df.iterrows()]

    # Embedding client
    embed_client = EmbeddingClient.from_config(llm_cfg)
    embed_client.initialise(corpus_texts)
    logger.info("Embedding backend: %s", embed_client.backend_name)

    # Prototype store
    proc_dir   = config["paths"]["data_processed"]
    proto_path = f"{proc_dir}/prototypes.npz"
    store      = PrototypeStore(embed_client)

    if args.load_prototypes and Path(args.load_prototypes).exists():
        store.load(args.load_prototypes)
    else:
        store.build_from_seeds()
        store.save(proto_path)

    # LLM client (optional)
    llm_client = None
    try:
        llm_client = OllamaClient(
            endpoint        = llm_cfg["endpoint"],
            model           = llm_cfg["model"],
            temperature     = llm_cfg["generation"]["temperature"],
            max_tokens      = llm_cfg["generation"]["max_tokens"],
            max_retries     = llm_cfg["classification"]["max_retries"],
            fallback_models = llm_cfg.get("fallback_models", []),
        )
        if not llm_client.is_available():
            logger.warning("LLM unavailable — Stage 3 disabled")
            llm_client = None
    except Exception as exc:
        logger.warning("LLM init failed: %s", exc)

    # Thresholds from config
    emb_cfg = llm_cfg.get("embeddings", {})
    classifier = HybridClassifier(
        embed_client         = embed_client,
        prototype_store      = store,
        llm_client           = llm_client,
        rule_threshold       = emb_cfg.get("rule_threshold",       0.75),
        embed_high_threshold = emb_cfg.get("embed_high_threshold", 0.80),
        embed_low_threshold  = emb_cfg.get("embed_low_threshold",  0.55),
        logger               = logger,
    )

    # Classify
    df_out = classifier.classify_dataframe(df, llm_cfg=llm_cfg)

    # Feedback loop
    feedback_stats = {}
    if not args.no_feedback:
        feedback_stats = run_feedback_loop(df_out, classifier, corpus_texts, logger=logger)
        store.save(proto_path)

    # Save outputs
    Path(proc_dir).mkdir(parents=True, exist_ok=True)
    save_parquet(df_out, f"{proc_dir}/classified_works.parquet")

    report = {
        "timestamp":               datetime.now(UTC).isoformat(),
        "n_records":               len(df_out),
        "backend":                 embed_client.backend_name,
        "domain_distribution":     df_out["domain"].value_counts().to_dict(),
        "subcategory_distribution":df_out["subcategory"].value_counts().to_dict(),
        "source_distribution":     df_out["domain_source"].value_counts().to_dict(),
        "confidence_mean":         round(float(df_out["domain_confidence"].mean()), 4),
        "confidence_median":       round(float(df_out["domain_confidence"].median()), 4),
        "outlier_count":           int((df_out["domain_source"] == "embedding_outlier").sum()),
        "routing_stats":           classifier.routing_stats(len(df)),
        "feedback_loop_updates":   feedback_stats,
        "deterministic_rate":      round(
            (classifier.stats.get("stage1", 0) + classifier.stats.get("stage2_high", 0)) / len(df),
            4
        ),
        "llm_call_rate": round(classifier.stats.get("stage3", 0) / len(df), 4),
    }
    save_json(report, f"{proc_dir}/classification_report.json")
    save_json({d: s for d, s in DOMAIN_SUBCATEGORY.items()}, f"{proc_dir}/subcategory_taxonomy.json")

    logger.info("=== Classification Agent complete ===")
    logger.info("Deterministic: %.1f%% | LLM: %.1f%% | Outliers: %d",
                report["deterministic_rate"] * 100,
                report["llm_call_rate"]      * 100,
                report["outlier_count"])


if __name__ == "__main__":
    main()
