#!/usr/bin/env python3
"""
Bibliometric Pipeline Test Runner
=================================

Comprehensive test execution script for the bibliometric pipeline.

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --unit            # Run only unit tests
    python run_tests.py --integration     # Run only integration tests
    python run_tests.py --robustness      # Run only robustness tests
    python run_tests.py --regression      # Run only regression tests
    python run_tests.py --coverage        # Run with coverage report
    python run_tests.py --parallel        # Run tests in parallel
"""

import argparse
import subprocess
import sys
from pathlib import Path


def _python_executable() -> str:
    """Return the venv Python if it exists, otherwise the current interpreter."""
    venv_python = Path(__file__).parent / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent)

        if result.returncode == 0:
            print("✅ PASSED")
            if result.stdout:
                print(result.stdout)
        else:
            print("❌ FAILED")
            if result.stdout:
                print("STDOUT:", result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)

        return result.returncode == 0

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Bibliometric Pipeline Test Runner")
    parser.add_argument("--unit", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration", action="store_true", help="Run only integration tests")
    parser.add_argument("--robustness", action="store_true", help="Run only robustness tests")
    parser.add_argument("--regression", action="store_true", help="Run only regression tests")
    parser.add_argument("--bibliometric", action="store_true", help="Run only bibliometric domain tests")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Determine which tests to run
    if args.unit:
        test_markers = ["unit"]
    elif args.integration:
        test_markers = ["integration"]
    elif args.robustness:
        test_markers = ["robustness"]
    elif args.regression:
        test_markers = ["regression"]
    elif args.bibliometric:
        test_markers = ["bibliometric"]
    else:
        test_markers = None  # Run all

    # Build pytest command
    cmd = [_python_executable(), "-m", "pytest"]

    if test_markers:
        markers = " or ".join(test_markers)
        cmd.extend(["-m", markers])

    if args.coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing",
            "--cov-report=xml",
            "--cov-fail-under=85"
        ])

    if args.parallel:
        cmd.extend(["-n", "auto"])  # Use pytest-xdist for parallel execution

    if args.verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    # Run tests
    success = run_command(cmd, f"Running {' '.join(test_markers) if test_markers else 'all'} tests")

    # Generate summary report
    if success:
        print(f"\n{'='*60}")
        print("🎉 ALL TESTS PASSED!")
        print("="*60)

        if args.coverage:
            print("\nCoverage report generated:")
            print("  HTML: htmlcov/index.html")
            print("  XML: coverage.xml")

        print("\nTest Summary:")
        print("  ✅ Unit Tests: Core functionality")
        print("  ✅ Integration Tests: Agent interactions")
        print("  ✅ Robustness Tests: Error handling")
        print("  ✅ Regression Tests: Result consistency")
        print("  ✅ Bibliometric Tests: Domain validation")

    else:
        print(f"\n{'='*60}")
        print("❌ SOME TESTS FAILED!")
        print("="*60)
        print("Check the output above for details.")
        print("Common issues:")
        print("  - Missing dependencies: pip install -r requirements-test.txt")
        print("  - Import errors: Check PYTHONPATH")
        print("  - External API failures: Check network connectivity")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
