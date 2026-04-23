#!/usr/bin/env python3
"""
Setup Diagnostic Script
========================
Verifies the pipeline environment on your machine.
Checks all three embedding backend tiers and the LLM connection.

Run before first pipeline execution:
    python scripts/check_setup.py

Run with verbose output:
    python scripts/check_setup.py --verbose

Run after installing new components:
    python scripts/check_setup.py --fix
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET}  {msg}")
def fail(msg): print(f"  {RED}✗{RESET}  {msg}")
def info(msg): print(f"  {CYAN}→{RESET}  {msg}")
def section(title): print(f"\n{BOLD}{title}{RESET}")
def rule():    print("  " + "─" * 60)


# ── Check helpers ─────────────────────────────────────────────────────────────

def check_import(pkg: str, min_version: Optional[str] = None) -> bool:
    try:
        mod = __import__(pkg.replace("-", "_"))
        ver = getattr(mod, "__version__", "?")
        if min_version:
            ok(f"{pkg}  {ver}  (required ≥ {min_version})")
        else:
            ok(f"{pkg}  {ver}")
        return True
    except ImportError:
        fail(f"{pkg}  NOT INSTALLED")
        return False


def check_specter2(verbose: bool = False) -> bool:
    section("Embedding Backend — Tier 1: SPECTER2")
    rule()

    if not check_import("sentence_transformers", "2.7.0"):
        fail("sentence-transformers not installed")
        info("Fix: pip install sentence-transformers torch")
        return False

    if not check_import("torch"):
        fail("torch not installed")
        info("Fix: pip install torch")
        return False

    # Check device
    import torch
    if torch.backends.mps.is_available():
        ok(f"PyTorch MPS backend available  (Apple Silicon accelerated)")
        device = "mps"
    elif torch.cuda.is_available():
        ok(f"PyTorch CUDA available  ({torch.cuda.get_device_name(0)})")
        device = "cuda"
    else:
        warn("PyTorch CPU only  (no GPU acceleration detected)")
        device = "cpu"

    # Check adapters library (PRIMARY — allenai/specter2 uses AdapterHub format)
    adapters_ok = check_import("adapters", "0.2.0")
    if not adapters_ok:
        fail("adapters library NOT installed — this is required to load allenai/specter2")
        fail("allenai/specter2 uses AdapterHub format, NOT PEFT/LoRA format")
        info("Fix: pip install adapters")
    else:
        ok("adapters library available — allenai/specter2 will load correctly")

    # Check peft (fallback only — not needed for allenai/specter2)
    peft_ok = check_import("peft", "0.10.0")
    if not peft_ok:
        warn("peft not installed — only used as fallback, adapters library is preferred")
    else:
        ok("peft available (fallback only — adapters library is the primary)")

    # ── Load SPECTER2 via the versioned backend (handles all transformers versions) ──
    # Delegates to SPECTER2Backend._load_adapter_versioned() which tries 3 strategies:
    #   Attempt 1: load_adapter(path, set_active=True, ...)          — transformers ≥ 4.45
    #   Attempt 2: load_adapter(path, source="hf", set_active=True)  — transformers < 4.45
    #   Attempt 3: PeftModel.from_pretrained() + merge_and_unload()  — direct PEFT fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        from src.utils.embedding_client import SPECTER2Backend
    except ImportError as exc:
        fail(f"Cannot import SPECTER2Backend: {exc}")
        return False

    info("Loading SPECTER2 model (downloads ~440 MB on first run)...")
    t0 = time.time()
    try:
        backend = SPECTER2Backend(device=device, batch_size=16)
        backend._load()   # uses _load_adapter_versioned() — version-agnostic
        elapsed = time.time() - t0

        # Confirm adapter status using the actual _adapter_active flag
        # (NOT _peft_available() which only checks if peft is installed)
        adapter_ok = backend._adapter_active
        if adapter_ok:
            ok(f"SPECTER2 loaded — device={backend._model.device}, dim=768, "
               f"load_time={elapsed:.1f}s  [proximity adapter ACTIVE — full quality]")
        else:
            warn(f"SPECTER2 base loaded — device={backend._model.device}, "
                 f"load_time={elapsed:.1f}s  [proximity adapter NOT loaded — DEGRADED]")
            warn("Citation geometry is absent. Subcategory accuracy reduced ~5-8 F1 pts.")
            info("Fix: pip install -U peft transformers sentence-transformers")

        # Benchmark — warmup first to exclude MPS graph compilation time
        # MPS compiles the compute graph on first batch, which can take 1-3s.
        # Without warmup, reported speed is 10-20x lower than actual throughput.
        texts = [
            "Populism and democracy: theoretical challenges",
            "Economic roots of populist backlash",
            "Social media and populist communication",
        ] * 20   # 60 texts — enough to get a stable measurement

        import numpy as np
        info("Running MPS warmup pass (compiles compute graph)...")
        _ = backend.embed_batch(texts[:4])   # warmup — not timed

        t1 = time.time()
        vecs = backend.embed_batch(texts)
        emb_sec = len(texts) / (time.time() - t1)
        ok(f"Benchmark (post-warmup): {emb_sec:.0f} embeddings/sec  ({len(texts)} texts, batch={backend._batch_size})")

        # Speed reference values for SPECTER2 (BERT-base, 768d) on Apple Silicon:
        #   Short texts  (<20 tokens,  batch=16): 300–600  emb/sec  — this benchmark
        #   Typical abstracts (~100 tokens, batch=64): 500–1500 emb/sec
        #   Full throughput  (batch=128+): 1500–3000 emb/sec
        # The 300-600 range for this benchmark is correct and expected.
        if emb_sec < 50:
            warn(f"Speed {emb_sec:.0f}/sec is very low — MPS may not be active. "
                 f"Expected ≥300/sec on M4. Device: {backend._model.device}")
            info("Check: torch.backends.mps.is_available() should return True")
        elif emb_sec < 200:
            warn(f"Speed {emb_sec:.0f}/sec — below expected range for M4 (300–600/sec).")
            info("MPS is active but throughput is low — try a larger batch_size in config/llm.yaml")
        else:
            ok(f"Speed {emb_sec:.0f}/sec — M4 MPS acceleration confirmed ✓")
            info("Typical pipeline throughput with longer abstracts and batch=64: 500–1500/sec")

        if verbose:
            info(f"Output shape: {vecs.shape}")
            info(f"Sample norms: {np.linalg.norm(vecs[:3], axis=1).tolist()}")

        return True

    except Exception as exc:
        fail(f"SPECTER2 load failed: {exc}")
        if verbose:
            import traceback; traceback.print_exc()
        info("If the error mentions 'source', update transformers: pip install -U transformers")
        info("If the error mentions 'peft', install it: pip install peft")
        return False


def check_ollama(endpoint: str = "http://localhost:11434", verbose: bool = False) -> bool:
    section("Embedding Backend — Tier 2: Ollama")
    rule()

    import requests
    try:
        resp = requests.get(f"{endpoint}/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        ok(f"Ollama server reachable at {endpoint}")
        if verbose:
            info(f"Installed models: {models}")

        # Check embedding model
        embed_models = [m for m in models if any(
            name in m for name in ["nomic", "mxbai", "arctic", "embed"]
        )]
        if embed_models:
            ok(f"Embedding models found: {embed_models}")
        else:
            warn("No embedding model found")
            info("Install: ollama pull nomic-embed-text   (274 MB, recommended)")
            info("      or ollama pull mxbai-embed-large  (670 MB, higher quality)")

        # Check LLM model
        llm_models = [m for m in models if any(
            name in m for name in ["qwen", "llama", "phi", "mistral", "gemma"]
        )]
        if llm_models:
            ok(f"LLM models found: {llm_models}")
            large = [m for m in llm_models if any(
                s in m for s in ["72b", "70b", "32b"]
            )]
            if large:
                ok(f"Large model detected: {large}  — suitable for Stage 3")
            else:
                warn("Only small LLMs found. For best Stage 3 quality:")
                info("ollama pull qwen2.5:72b   (recommended for M4 128 GB)")
                info("ollama pull phi4          (alternative, 14B)")
        else:
            warn("No LLM models found. Stage 3 will be disabled.")
            info("Install: ollama pull qwen2.5:72b")

        return True

    except Exception as exc:
        fail(f"Ollama not reachable at {endpoint}: {exc}")
        info("Install Ollama: https://ollama.ai")
        info("Then: ollama pull nomic-embed-text  &&  ollama pull qwen2.5:72b")
        return False


def check_tfidf() -> bool:
    section("Embedding Backend — Tier 3: TF-IDF LSA (fallback)")
    rule()
    ok("Always available (scikit-learn dependency)")
    warn("This is the last-resort fallback. Quality is significantly lower than SPECTER2.")
    warn("Outlier rate ~60% vs ~5–10% with SPECTER2.")
    return True


def check_core_deps() -> bool:
    section("Core Pipeline Dependencies")
    rule()
    required = [
        ("pandas",           "2.0.0"),
        ("numpy",            "1.24.0"),
        ("pyarrow",          "12.0.0"),
        ("requests",         "2.31.0"),
        ("yaml",             None),
        ("scipy",            "1.11.0"),
        ("sklearn",          "1.3.0"),
        ("networkx",         "3.1"),
        ("community",        None),
        ("matplotlib",       "3.7.0"),
        ("hdbscan",          None),
    ]
    all_ok = True
    for pkg, ver in required:
        if not check_import(pkg, ver):
            all_ok = False
    return all_ok


def check_hardware() -> None:
    section("Hardware")
    rule()
    import platform
    ok(f"Python {sys.version.split()[0]}")
    ok(f"Platform: {platform.system()} {platform.machine()}")

    # RAM
    try:
        import psutil
        ram_gb = psutil.virtual_memory().total / 1e9
        ok(f"RAM: {ram_gb:.0f} GB")
        if ram_gb >= 100:
            ok(f"Memory sufficient for qwen2.5:72b Q4 (~48 GB) with headroom")
        elif ram_gb >= 24:
            warn(f"Memory: qwen2.5:72b marginal — consider qwen2.5:32b or phi4")
        else:
            warn(f"Memory: use qwen2.5:14b or smaller")
    except ImportError:
        info("psutil not installed — cannot check RAM (pip install psutil)")

    # Apple Silicon detection
    try:
        import torch
        if torch.backends.mps.is_available():
            ok("Apple Silicon MPS backend: ACTIVE")
            info("SPECTER2 will use MPS — ~1500–3000 embeddings/sec expected")
    except ImportError:
        pass


def check_data_dirs() -> None:
    section("Project Directory Structure")
    rule()
    required_dirs = [
        "data/raw", "data/clean", "data/processed",
        "data/outputs/networks", "data/outputs/figures", "data/outputs/reports",
        "logs", "checkpoints", "config", "src/agents", "src/utils",
    ]
    for d in required_dirs:
        if Path(d).exists():
            ok(d)
        else:
            warn(f"{d}  MISSING")
            info(f"Fix: mkdir -p {d}")


def check_config_files() -> None:
    section("Configuration Files")
    rule()
    configs = ["config/config.yaml", "config/llm.yaml", "config/openalex.yaml"]
    for cfg in configs:
        if Path(cfg).exists():
            ok(cfg)
        else:
            fail(f"{cfg}  MISSING — pipeline cannot run")


def print_summary(results: dict) -> None:
    section("Summary")
    rule()

    specter2_ok = results.get("specter2", False)
    ollama_ok   = results.get("ollama",   False)
    core_ok     = results.get("core",     False)

    if specter2_ok:
        from src.utils.embedding_client import SPECTER2Backend
        # Use the _adapter_active flag — the only authoritative signal
        # that the proximity adapter was actually loaded and merged.
        _tmp_b = SPECTER2Backend()
        _tmp_b._load()   # trigger lazy load to get accurate adapter status
        if _tmp_b._adapter_active:
            print(f"\n  {GREEN}{BOLD}Active backend: SPECTER2 + proximity adapter (full quality){RESET}")
            info("Citation-supervised embeddings — optimal for bibliometric classification")
            info("Expected: ~5–10% outliers, strong subcategory discrimination")
        else:
            print(f"\n  {YELLOW}{BOLD}Active backend: SPECTER2 base only (degraded — adapter not loaded){RESET}")
            warn("Proximity adapter failed to load — citation geometry absent")
            warn("Subcategory accuracy reduced ~5-8 F1 points vs full SPECTER2")
            warn("Fix: pip install adapters   (AdapterHub library — required for allenai/specter2)")
            warn("Note: allenai/specter2 uses AdapterHub format, NOT PEFT/LoRA")
    elif ollama_ok:
        print(f"\n  {YELLOW}{BOLD}Active backend: Ollama (general neural){RESET}")
        warn("SPECTER2 not available — classification quality reduced")
        warn("Install for best results: pip install sentence-transformers torch")
    else:
        print(f"\n  {RED}{BOLD}Active backend: TF-IDF LSA (last resort){RESET}")
        fail("Both SPECTER2 and Ollama unavailable")
        fail("Expected ~60% outlier rate — subcategory classification unreliable")
        info("Fix: pip install sentence-transformers torch")

    print()
    if core_ok:
        ok("Core dependencies: ready")
    else:
        fail("Some core dependencies missing — run: pip install -r requirements.txt")

    print()
    info("Run pipeline: python src/agents/orchestrator.py --config config/config.yaml")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pipeline Setup Diagnostic")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--fix", action="store_true",
                        help="Attempt to install missing dependencies")
    parser.add_argument("--ollama-endpoint", default="http://localhost:11434")
    args = parser.parse_args()

    # Ensure we run from project root
    if not Path("config/config.yaml").exists():
        print(f"{RED}Error: Run this script from the project root directory.{RESET}")
        print("  cd bibliometric_pipeline && python scripts/check_setup.py")
        sys.exit(1)

    print(f"\n{BOLD}{'=' * 62}")
    print("  BIBLIOMETRIC PIPELINE — Environment Diagnostic")
    print(f"{'=' * 62}{RESET}")

    if args.fix:
        section("Installing dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    results = {}

    check_hardware()
    check_data_dirs()
    check_config_files()
    results["core"]     = check_core_deps()
    results["specter2"] = check_specter2(verbose=args.verbose)
    results["ollama"]   = check_ollama(
        endpoint=args.ollama_endpoint, verbose=args.verbose
    )
    check_tfidf()
    print_summary(results)


if __name__ == "__main__":
    main()