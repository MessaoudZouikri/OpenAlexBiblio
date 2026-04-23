# Contributing to OpenAlexBiblio

Thank you for your interest in contributing! This guide explains how to report bugs, propose changes, and submit pull requests.

---

## Quick Start for Contributors

```bash
# 1. Fork the repository, then clone your fork
git clone https://github.com/<your-username>/OpenAlexBiblio.git
cd OpenAlexBiblio

# 2. Create a virtual environment and install all dependencies
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

pip install -e ".[dev,test]"

# 3. Verify your setup
python scripts/check_setup.py --verbose

# 4. Create a feature branch
git checkout -b feature/my-feature

# 5. Make changes, add tests, then run the test suite
pytest --cov=src -q

# 6. Push and open a pull request
git push origin feature/my-feature
```

---

## Types of Contributions

### Bug Reports

Open a [GitHub Issue](https://github.com/MessaoudZouikri/OpenAlexBiblio/issues) with:
- Python version (`python --version`)
- OS and hardware
- Full traceback
- Minimal steps to reproduce

### Feature Requests

Open an issue describing:
- The problem you are trying to solve
- Your proposed solution or API
- Any alternatives you considered

### Domain Taxonomy Contributions

The pipeline classifies papers into 4 domains and 21 subcategories. To propose new subcategories or modify keyword mappings:

1. Read [`docs/research/TAXONOMY_UPDATE_TEMPLATE.md`](docs/research/TAXONOMY_UPDATE_TEMPLATE.md)
2. Open an issue or pull request with your proposal and justification

### Code Contributions

All code contributions require:
- Tests covering new or changed behaviour
- Docstrings on public functions and modules
- Type hints on all public function signatures
- Passing CI (tests, lint)

---

## Code Style

This project uses:
- **[Black](https://black.readthedocs.io)** for formatting (line length 100)
- **[Ruff](https://docs.astral.sh/ruff/)** for linting
- **[Mypy](https://mypy.readthedocs.io)** for type checking

Run all checks locally before pushing:

```bash
black src/ tests/
ruff check src/ tests/
mypy src/
pytest --cov=src -q
```

Or install pre-commit hooks to run them automatically:

```bash
pip install pre-commit
pre-commit install
```

---

## Testing

Tests live in `tests/` and are structured as:

```
tests/
├── unit/          # Per-function tests, no external calls
├── integration/   # Cross-agent data-flow tests
├── robustness/    # Error handling and edge cases
└── regression/    # Guard against regressions in known outputs
```

Run the full suite:
```bash
pytest --cov=src --cov-report=term-missing -q
```

Run a specific category:
```bash
pytest tests/unit/ -q
pytest -m "not slow" -q
```

Coverage target is 85%. New code must maintain or improve coverage.

---

## Pull Request Checklist

Before opening a PR, ensure:

- [ ] Tests pass locally (`pytest -q`)
- [ ] No new linting errors (`ruff check src/ tests/`)
- [ ] Docstrings on new public functions
- [ ] Type hints on new public function signatures
- [ ] `CITATION.cff` version updated if releasing a new version
- [ ] PR description explains *why*, not just *what*

---

## Questions?

Email: [econoPoPop@proton.me](mailto:econoPoPop@proton.me)

GitHub Discussions: [github.com/MessaoudZouikri/OpenAlexBiblio/discussions](https://github.com/MessaoudZouikri/OpenAlexBiblio/discussions)

---

**License**: All contributions are licensed under [GPL-3.0](LICENSE).
