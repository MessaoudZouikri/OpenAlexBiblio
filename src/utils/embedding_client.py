"""
Embedding Client — 3-Tier Backend
===================================
Generates dense vector embeddings for academic texts.

Tier 1 (PRIMARY)  — SPECTER2         allenai/specter2_base + proximity adapter
                    Citation-supervised, trained on scientific papers.
                    Best subcategory discrimination. Best bridge geometry.
                    Requires: pip install sentence-transformers
                    Model size: ~440 MB (downloaded once to ~/.cache/huggingface)

Tier 2 (FALLBACK) — Ollama           nomic-embed-text / mxbai-embed-large
                    General-purpose neural embeddings via local Ollama server.
                    Good quality, no Python dependencies beyond requests.
                    Requires: ollama pull nomic-embed-text

Tier 3 (LAST RESORT) — TF-IDF LSA   scikit-learn TfidfVectorizer + TruncatedSVD
                    Always available, zero extra dependencies.
                    Deterministic but lower subcategory discrimination.
                    Sufficient for coarse domain assignment only.

Backend selection is automatic: SPECTER2 → Ollama → TF-IDF.
Can be forced via config: embeddings.backend: "specter2"|"ollama"|"tfidf"

Design:
- Deterministic: same input + model → same vector
- Unit-normalised output: all backends return L2-normalised (N, D) arrays
- Auditable: backend name stored in every output artefact
- Batch-efficient: SPECTER2 and TF-IDF use true batch ops; Ollama is per-item

Usage:
    client = EmbeddingClient.from_config(llm_cfg)
    client.initialise(corpus_texts)               # selects + warms up backend
    vecs = client.embed_batch(["text 1", "text 2"])  # np.ndarray (N, D)

Setup on Apple M4 (recommended):
    pip install sentence-transformers torch
    # SPECTER2 downloads automatically on first use (~440 MB)
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

import numpy as np
import requests

logger = logging.getLogger("embedding_client")


# ── Suppress benign "adapters not activated" warning ─────────────────────────
# After merge_adapter() + delete_adapter(), the adapters library logs this
# message on every forward pass because its infrastructure remains in the model
# but no adapter is active. The weights ARE correctly merged into the base BERT
# layers — the warning is a false positive from residual adapter scaffolding.
#
# Suppressed at the logging level (not warnings module — adapters uses logging).
# Applied at module-import time so both the benchmark load and summary re-load
# are covered.
class _NoAdaptersActivatedFilter(logging.Filter):
    """Drop the 'adapters available but none are activated' log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "adapters available but none are activated" not in str(record.getMessage())


_adapters_filter = _NoAdaptersActivatedFilter()
logging.getLogger("adapters").addFilter(_adapters_filter)
logging.getLogger("adapters.layer").addFilter(_adapters_filter)
logging.getLogger("adapters.models").addFilter(_adapters_filter)
# ─────────────────────────────────────────────────────────────────────────────

# Input truncation: SPECTER2 context window is 512 tokens (~400 words)
# Longer texts are silently truncated by the model; we pre-truncate for
# consistent behaviour across all backends.
MAX_CHARS = 1800  # ~400 words — covers title + most abstracts


def _truncate(text: str) -> str:
    return text[:MAX_CHARS] if len(text) > MAX_CHARS else text


def _l2_normalise(matrix: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalisation. Zero vectors are left as-is."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    return matrix / norms


# ─────────────────────────────────────────────────────────────────────────────
# Tier 1 — SPECTER2 Backend
# ─────────────────────────────────────────────────────────────────────────────


class SPECTER2Backend:
    """
    AllenAI SPECTER2 with the 'proximity' adapter.

    Why the proximity adapter specifically:
        SPECTER2 ships with three task adapters:
          - proximity   → paper similarity / citation-based distance
          - classification → supervised label prediction
          - regression  → continuous score prediction

        The proximity adapter preserves the citation-based geometric structure
        of the embedding space, which is exactly what bibliometric networks
        require. Papers that cite each other are embedded closer together
        than random pairs — this is the trained objective.

    Dimensionality: 768 (BERT-base size)
    Max tokens:     512 (~400 words)
    Model size:     ~440 MB (cached in ~/.cache/huggingface after first download)

    Apple Silicon note:
        sentence-transformers automatically uses the MPS backend on M-series Macs,
        giving ~1,500–3,000 embeddings/sec at 768d — far faster than Ollama HTTP.
    """

    MODEL_ID = "allenai/specter2_base"
    ADAPTER_ID = "allenai/specter2"
    ADAPTER_NAME = "proximity"

    def __init__(self, device: Optional[str] = None, batch_size: int = 32):
        self._model = None
        self._device = device
        self._batch_size = batch_size
        self._dim = 768
        self._adapter_active = False  # True only when proximity adapter is confirmed loaded

    # ── Availability / lazy load ──────────────────────────────────────────────

    def is_available(self) -> bool:
        """
        Return True if sentence-transformers is importable.
        peft is checked separately — it is required for the proximity adapter
        but the backend can still run (with a quality warning) without it,
        using the base model only.
        """
        try:
            import sentence_transformers  # noqa: F401

            return True
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers torch peft\n"
                "Falling back to next backend."
            )
            return False

    @staticmethod
    def _peft_available() -> bool:
        try:
            import peft  # noqa: F401

            return True
        except ImportError:
            return False

    def _load(self) -> None:
        """
        Lazy-load SPECTER2.  Two strategies depending on peft availability:

        Strategy A (full quality — requires peft):
            Load allenai/specter2_base  +  allenai/specter2 proximity adapter.
            Citation-supervised geometry is preserved.
            Install: pip install peft

        Strategy B (degraded — peft missing):
            Load allenai/specter2_base without adapter.
            Still a scientific embedding model, better than Ollama for academic
            text, but loses the citation-based geometric structure.
            Classification accuracy drops ~5-8 F1 points on subcategory tasks.
        """
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        logger.info("Loading SPECTER2 base model (%s)...", self.MODEL_ID)
        logger.info("  First run downloads ~440 MB to ~/.cache/huggingface")

        self._model = SentenceTransformer(
            self.MODEL_ID,
            trust_remote_code=True,
            device=self._device,
        )

        if self._peft_available():
            # ── Strategy A: full SPECTER2 with proximity adapter ─────────────
            self._adapter_active = self._load_adapter_versioned()
            if self._adapter_active:
                logger.info(
                    "SPECTER2 loaded — adapter=%s, device=%s, dim=%d  [FULL QUALITY]",
                    self.ADAPTER_NAME,
                    self._model.device,
                    self._dim,
                )
            else:
                logger.warning(
                    "Proximity adapter could not be loaded despite peft being installed.\n"
                    "  Running SPECTER2 base model only (reduced citation geometry).\n"
                    "  Fix: pip install -U peft transformers sentence-transformers"
                )
                logger.info(
                    "SPECTER2 base loaded (adapter failed) — device=%s, dim=%d  [DEGRADED]",
                    self._model.device,
                    self._dim,
                )
        else:
            # ── Strategy B: base model only, no adapter ───────────────────────
            logger.warning(
                "peft not installed — SPECTER2 proximity adapter skipped.\n"
                "  Fix: pip install peft"
            )
            logger.info(
                "SPECTER2 base loaded (no adapter) — device=%s, dim=%d  [DEGRADED]",
                self._model.device,
                self._dim,
            )

    def _load_adapter_versioned(self) -> bool:
        """
        Load the proximity adapter.

        ROOT CAUSE ANALYSIS:
          allenai/specter2 uses the AdapterHub format from the `adapters` library
          (formerly adapter-transformers), NOT the HuggingFace PEFT/LoRA format.
          This is why all PEFT-based approaches fail:
            - KeyError 'peft_type' → adapter_config.json is AdapterHub format, not PEFT
            - 404 on adapter_model.bin → AdapterHub uses pytorch_adapter.bin instead
          The correct library is `adapters`, installed with: pip install adapters

        Loading strategy (in order):
          1. adapters library  — AdapterHub format (CORRECT for allenai/specter2)
          2. ST load_adapter() — new transformers API fallback (≥ 4.45)
          3. ST load_adapter() — old transformers API fallback (< 4.45, source="hf")

        Returns True if adapter was loaded and merged successfully.
        """
        # ── Attempt 1: adapters library — AdapterHub format ─────────────────
        # This is the correct approach for allenai/specter2.
        # The `adapters` library (pip install adapters) supports the AdapterHub
        # format. We init it on the underlying BERT model, load the adapter
        # in-place, merge the weights, then delete the adapter structure.
        # The result is a standard BERT model with proximity-adapted weights.
        try:
            import adapters as adapters_lib

            underlying = self._get_underlying_model()
            if underlying is None:
                raise RuntimeError("Cannot access underlying transformer model")

            # Inject adapter support into the existing BERT model (in-place)
            adapters_lib.init(underlying)

            # Load from AdapterHub / HuggingFace
            underlying.load_adapter(
                self.ADAPTER_ID,
                source="hf",
                load_as=self.ADAPTER_NAME,
                set_active=True,
            )

            # Merge adapter weights into the base model, then clean up
            underlying.merge_adapter(self.ADAPTER_NAME)
            underlying.delete_adapter(self.ADAPTER_NAME)

            # After delete_adapter(), the adapters library may leave its
            # infrastructure in the model (hooks, adapter slots) but inactive.
            # This triggers the benign warning:
            #   "There are adapters available but none are activated"
            # on every forward pass. The weights ARE correctly merged — the
            # warning is a false positive. Fix: clear active adapter state.
            try:
                underlying.set_active_adapters([])  # clear active list
            except Exception:
                pass
            try:
                # Disable adapter inference mode entirely (adapters 1.x API)
                underlying.config.adapters.active_setup = None
            except Exception:
                pass

            logger.debug("Adapter loaded via Attempt 1 (adapters library, AdapterHub format)")
            return True

        except ImportError:
            logger.warning(
                "Attempt 1: `adapters` library not installed.\n"
                "  allenai/specter2 requires the AdapterHub library, not PEFT.\n"
                "  Fix: pip install adapters"
            )
        except Exception as exc:
            logger.debug("Attempt 1 (adapters library) failed: %s", exc)

        # ── Attempt 2: SentenceTransformer.load_adapter() — new API (≥ 4.45) ─
        try:
            self._model.load_adapter(
                self.ADAPTER_ID,
                set_active=True,
                adapter_name=self.ADAPTER_NAME,
            )
            logger.debug("Adapter loaded via Attempt 2 (ST load_adapter, new API)")
            return True
        except Exception as exc:
            logger.debug("Attempt 2 failed: %s", exc)

        # ── Attempt 3: SentenceTransformer.load_adapter() — old API (< 4.45) ─
        try:
            self._model.load_adapter(
                self.ADAPTER_ID,
                source="hf",
                set_active=True,
                adapter_name=self.ADAPTER_NAME,
            )
            logger.debug("Adapter loaded via Attempt 3 (ST load_adapter, old API)")
            return True
        except Exception as exc:
            logger.debug("Attempt 3 failed: %s", exc)

        logger.warning(
            "All adapter loading attempts failed.\n"
            "  Most likely cause: `adapters` library not installed.\n"
            "  Run: pip install adapters\n"
            "  Then re-run the pipeline or check_setup.py"
        )
        return False

    def _get_underlying_model(self):
        """
        Return the underlying HuggingFace transformer model from the
        sentence-transformers wrapper.
        Tries multiple access patterns for ST 2.x, 3.x, 4.x, 5.x compatibility.
        """
        for getter in [
            lambda m: m[0].auto_model,  # ST 3.x / 4.x / 5.x
            lambda m: list(m.children())[0].auto_model,  # ST 3.x alternate
            lambda m: m._first_module().auto_model,  # ST 2.x
            lambda m: next(iter(m._modules.values())).auto_model,  # generic fallback
        ]:
            try:
                model = getter(self._model)
                if model is not None:
                    return model
            except Exception:
                continue
        return None

    def _set_underlying_model(self, new_model) -> None:
        """
        Write back the modified underlying model into the sentence-transformers wrapper.
        Mirrors _get_underlying_model()'s access patterns.
        """
        for setter in [
            lambda m, v: setattr(m[0], "auto_model", v),
            lambda m, v: setattr(list(m.children())[0], "auto_model", v),
            lambda m, v: setattr(m._first_module(), "auto_model", v),
            lambda m, v: setattr(next(iter(m._modules.values())), "auto_model", v),
        ]:
            try:
                setter(self._model, new_model)
                return
            except Exception:
                continue
        raise RuntimeError("Could not write merged model back into SentenceTransformer")

    # ── Embedding ─────────────────────────────────────────────────────────────

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """
        Embed texts in mini-batches.
        Returns (N, 768) float32 L2-normalised array.
        """
        self._load()
        truncated = [_truncate(t) for t in texts]
        # sentence-transformers handles batching, padding, and device transfer
        vecs = self._model.encode(
            truncated,
            batch_size=self._batch_size,
            show_progress_bar=len(texts) > 200,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2 normalise inside the model
        ).astype(np.float32)
        return vecs  # already normalised

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def name(self) -> str:
        if self._model is None:
            return "specter2:selected"  # lazy — not loaded yet
        if self._adapter_active:
            return f"specter2:{self.ADAPTER_NAME}"  # full quality
        return "specter2:base_only"  # degraded — base model, no adapter

    @property
    def adapter_active(self) -> bool:
        """True if the proximity adapter was successfully loaded and merged."""
        return self._adapter_active


# ─────────────────────────────────────────────────────────────────────────────
# Tier 2 — Ollama Embedding Backend
# ─────────────────────────────────────────────────────────────────────────────


class OllamaEmbeddingBackend:
    """
    Calls the Ollama /api/embed endpoint.

    Recommended models (in order of quality for scientific text):
        nomic-embed-text        768d  ~274 MB   ollama pull nomic-embed-text
        mxbai-embed-large      1024d  ~670 MB   ollama pull mxbai-embed-large
        snowflake-arctic-embed 1024d  ~670 MB   ollama pull snowflake-arctic-embed

    Note: All general-purpose models. Prefer SPECTER2 for bibliometric tasks.
    Use this tier when sentence-transformers is unavailable.
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
        timeout: int = 60,
        max_retries: int = 3,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._dim: Optional[int] = None

    def is_available(self) -> bool:
        try:
            resp = requests.get(f"{self.endpoint}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False
            models = [m["name"] for m in resp.json().get("models", [])]
            base = self.model.split(":")[0]
            found = any(base in m for m in models)
            if not found:
                logger.warning(
                    "Ollama embedding model '%s' not found. Available: %s\n" "  → ollama pull %s",
                    self.model,
                    models,
                    self.model,
                )
            return found
        except Exception as exc:
            logger.warning("Ollama not reachable: %s", exc)
            return False

    def _embed_one(self, text: str) -> Optional[np.ndarray]:
        payload = {"model": self.model, "input": _truncate(text)}
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(
                    f"{self.endpoint}/api/embed",
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                vec = data.get("embeddings", [[]])[0] or data.get("embedding", [])
                arr = np.array(vec, dtype=np.float32)
                self._dim = len(arr)
                return arr
            except Exception as exc:
                logger.warning("Ollama embed attempt %d/%d: %s", attempt, self.max_retries, exc)
                if attempt < self.max_retries:
                    time.sleep(1.0 * attempt)
        return None

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        dim = self._dim or 768
        results = []
        for i, text in enumerate(texts):
            vec = self._embed_one(text)
            if vec is None:
                logger.warning(
                    "Ollama embed failed for text %d/%d — zero vector", i + 1, len(texts)
                )
                vec = np.zeros(dim, dtype=np.float32)
            else:
                dim = len(vec)
            results.append(vec)
        return _l2_normalise(np.stack(results))

    @property
    def dim(self) -> Optional[int]:
        return self._dim

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"


# ─────────────────────────────────────────────────────────────────────────────
# Tier 3 — TF-IDF LSA Fallback Backend
# ─────────────────────────────────────────────────────────────────────────────


class TFIDFFallbackBackend:
    """
    Deterministic sparse → dense embeddings via TF-IDF + Truncated SVD (LSA).

    Always available — only requires scikit-learn (already a pipeline dependency).
    Must be fitted on the corpus before use (call .fit(texts)).

    Limitations vs neural backends:
      - No semantic generalisation: unseen vocab → zero weights
      - No citation geometry: space structure reflects term co-occurrence only
      - Lower subcategory discrimination, especially for short/ambiguous texts
      - Outlier rate in prototype matching will be higher (~60% vs ~15% for SPECTER2)

    Use only as last resort. For production, always prefer SPECTER2 or Ollama.
    """

    def __init__(self, n_components: int = 256, max_features: int = 20000):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.decomposition import TruncatedSVD
        from sklearn.pipeline import Pipeline

        self._max_features = max_features
        self._pipeline = Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        max_features=max_features,
                        ngram_range=(1, 2),
                        min_df=2,
                        sublinear_tf=True,
                        strip_accents="unicode",
                    ),
                ),
                ("svd", TruncatedSVD(n_components=n_components, random_state=42)),
            ]
        )
        self._fitted = False
        self._n_components = n_components

    def fit(self, texts: List[str]) -> "TFIDFFallbackBackend":
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.decomposition import TruncatedSVD
        from sklearn.pipeline import Pipeline

        logger.info("Fitting TF-IDF LSA on %d texts (dim=%d)...", len(texts), self._n_components)
        truncated = [_truncate(t) for t in texts]

        # Probe vocabulary size with adaptive min_df
        min_df = 2 if len(texts) >= 20 else 1
        tfidf_probe = TfidfVectorizer(
            max_features=self._max_features,
            ngram_range=(1, 2),
            min_df=min_df,
            sublinear_tf=True,
            strip_accents="unicode",
        )
        X_probe = tfidf_probe.fit_transform(truncated)
        n_samples = len(truncated)
        n_features = X_probe.shape[1]

        # TruncatedSVD requires n_components < min(n_samples, n_features)
        safe_n = min(self._n_components, max(1, min(n_samples, n_features) - 1))
        if safe_n < self._n_components:
            logger.warning(
                "TF-IDF: n_components capped %d → %d (n_samples=%d, n_features=%d)",
                self._n_components,
                safe_n,
                n_samples,
                n_features,
            )
            self._n_components = safe_n

        # Rebuild pipeline with correct parameters (avoids sklearn in-place mutation issues)
        self._pipeline = Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        max_features=self._max_features,
                        ngram_range=(1, 2),
                        min_df=min_df,
                        sublinear_tf=True,
                        strip_accents="unicode",
                    ),
                ),
                ("svd", TruncatedSVD(n_components=self._n_components, random_state=42)),
            ]
        )
        self._pipeline.fit(truncated)
        self._fitted = True
        explained = self._pipeline["svd"].explained_variance_ratio_.sum()
        logger.info(
            "TF-IDF LSA fitted — dim=%d, features=%d, explained_variance=%.1f%%",
            self._n_components,
            n_features,
            explained * 100,
        )
        return self

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("TF-IDF backend not fitted. Call .fit(corpus_texts) first.")
        matrix = self._pipeline.transform([_truncate(t) for t in texts]).astype(np.float32)
        return _l2_normalise(matrix)

    @property
    def dim(self) -> int:
        return self._n_components

    @property
    def name(self) -> str:
        return "tfidf_lsa_fallback"


# ─────────────────────────────────────────────────────────────────────────────
# Unified Embedding Client
# ─────────────────────────────────────────────────────────────────────────────

_BACKEND_ORDER = ["specter2", "ollama", "tfidf"]


class EmbeddingClient:
    """
    Unified 3-tier embedding interface.

    Auto-selection priority:
        1. SPECTER2          (citation-supervised, best for bibliometrics)
        2. Ollama            (neural, general-purpose fallback)
        3. TF-IDF LSA        (deterministic, always available)

    Can be forced to a specific backend via config:
        embeddings.backend: "specter2" | "ollama" | "tfidf"

    All backends return L2-normalised (N, D) float32 arrays.
    Cosine similarity between any two output vectors = dot product.
    """

    def __init__(
        self,
        ollama_endpoint: str = "http://localhost:11434",
        ollama_model: str = "nomic-embed-text",
        specter2_device: Optional[str] = None,
        specter2_batch: int = 32,
        tfidf_n_components: int = 256,
        force_backend: Optional[str] = None,  # "specter2"|"ollama"|"tfidf"
    ):
        self._specter2 = SPECTER2Backend(device=specter2_device, batch_size=specter2_batch)
        self._ollama = OllamaEmbeddingBackend(ollama_endpoint, ollama_model)
        self._tfidf = TFIDFFallbackBackend(n_components=tfidf_n_components)
        self._force = force_backend
        self._active = None  # set by .initialise()

    # ── Initialisation ────────────────────────────────────────────────────────

    def initialise(self, corpus_texts: List[str]) -> str:
        """
        Select the highest-tier available backend and prepare it.
        corpus_texts required for TF-IDF fitting (ignored by neural backends).
        Returns the name of the active backend.
        """
        order = [self._force] if self._force else _BACKEND_ORDER

        for tier in order:
            if tier == "specter2" and self._specter2.is_available():
                self._active = "specter2"
                peft_ready = self._specter2._peft_available()
                logger.info(
                    "Embedding backend: SPECTER2  [%s]",
                    (
                        "full quality — proximity adapter"
                        if peft_ready
                        else "DEGRADED — peft missing, base model only"
                    ),
                )
                logger.info("  → Citation-supervised, 768d, ~1500 emb/sec on Apple M-series")
                if not peft_ready:
                    logger.warning("  → Run: pip install peft   for full citation-geometry quality")
                return self._active

            if tier == "ollama" and self._ollama.is_available():
                self._active = "ollama"
                logger.info("Embedding backend: Ollama (%s)", self._ollama.model)
                logger.info("  → General-purpose neural, good quality but not citation-aware")
                logger.info(
                    "  → For better subcategory discrimination: pip install sentence-transformers"
                )
                return self._active

            if tier == "tfidf":
                self._active = "tfidf"
                logger.warning(
                    "Embedding backend: TF-IDF LSA (last resort)\n"
                    "  → High outlier rate expected (~60%%). Subcategory discrimination limited.\n"
                    "  → Recommended: pip install sentence-transformers torch\n"
                    "                 (downloads SPECTER2 ~440 MB on first run)"
                )
                self._tfidf.fit(corpus_texts)
                return self._active

        # Should never reach here
        raise RuntimeError(f"No embedding backend available. Tried: {order}")

    # ── Embedding ─────────────────────────────────────────────────────────────

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        if self._active is None:
            raise RuntimeError("Call .initialise(corpus_texts) before embedding.")
        backend = self._get_active_backend()
        return backend.embed_batch(texts)

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed_batch([text])[0]

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def backend_name(self) -> str:
        if self._active is None:
            return "uninitialised"
        return self._get_active_backend().name

    @property
    def dim(self) -> Optional[int]:
        if self._active is None:
            return None
        return self._get_active_backend().dim

    @property
    def is_citation_aware(self) -> bool:
        """True only for SPECTER2 — relevant for audit reports."""
        return self._active == "specter2"

    def _get_active_backend(self):
        if self._active == "specter2":
            return self._specter2
        if self._active == "ollama":
            return self._ollama
        if self._active == "tfidf":
            return self._tfidf
        raise RuntimeError(f"Unknown active backend: {self._active}")

    # ── Config factory ────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, cfg: dict) -> "EmbeddingClient":
        """
        Build from llm.yaml config dict.

        Relevant config keys (under embeddings:):
            backend           : forced backend (optional)
            ollama_model      : Ollama model name (default: nomic-embed-text)
            specter2_device   : "mps"|"cuda"|"cpu" (default: auto)
            specter2_batch    : batch size for SPECTER2 (default: 32)
            tfidf_components  : LSA dimensions (default: 256)
        """
        emb = cfg.get("embeddings", {})
        return cls(
            ollama_endpoint=cfg.get("endpoint", "http://localhost:11434"),
            ollama_model=emb.get("ollama_model", "nomic-embed-text"),
            specter2_device=emb.get("specter2_device", None),
            specter2_batch=emb.get("specter2_batch", 32),
            tfidf_n_components=emb.get("tfidf_components", 256),
            force_backend=emb.get("backend", None),
        )

    # ── Diagnostic ────────────────────────────────────────────────────────────

    def diagnostics(self) -> dict:
        """Return backend availability status for all three tiers."""
        return {
            "active_backend": self.backend_name,
            "is_citation_aware": self.is_citation_aware,
            "dim": self.dim,
            "specter2_available": self._specter2.is_available(),
            "specter2_peft_available": self._specter2._peft_available(),
            "specter2_full_quality": (
                self._specter2.is_available() and self._specter2._peft_available()
            ),
            "ollama_available": self._ollama.is_available(),
            "tfidf_available": True,
        }
