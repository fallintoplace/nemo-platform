#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Run all unit tests across packages and services with summary reporting.

This script discovers and runs unit tests from all packages and services,
providing a comprehensive summary of test results.

Usage:
    python tools/run_all_tests.py                    # Run all unit tests
    python tools/run_all_tests.py --integration      # Include integration tests
    python tools/run_all_tests.py --e2e              # Include e2e tests
    python tools/run_all_tests.py --all              # Include all test types
    python tools/run_all_tests.py --coverage         # Run with coverage
    python tools/run_all_tests.py --summary-only     # Just show what would run
"""

import argparse
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Optional, Tuple


class Colors:
    """ANSI color codes for terminal output."""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def find_test_directories(root_dir: Path) -> List[Tuple[str, Path]]:
    """
    Find all test directories in packages and services.

    Returns:
        List of (category, path) tuples where category is 'package' or 'service'
    """
    test_dirs = []

    # Find package test directories
    packages_dir = root_dir / "packages"
    if packages_dir.exists():
        for package_dir in packages_dir.iterdir():
            if package_dir.is_dir() and not package_dir.name.startswith("."):
                test_dir = package_dir / "tests"
                if test_dir.exists() and any(test_dir.rglob("test_*.py")):
                    test_dirs.append(("package", test_dir))

    # Find service test directories
    services_dir = root_dir / "services"
    if services_dir.exists():
        for service_dir in services_dir.iterdir():
            if service_dir.is_dir() and not service_dir.name.startswith("."):
                # Check main tests directory
                test_dir = service_dir / "tests"
                if test_dir.exists() and any(test_dir.rglob("test_*.py")):
                    test_dirs.append(("service", test_dir))

                # Check infrastructure subdirectories
                infra_dir = service_dir / "infrastructure"
                if infra_dir.exists():
                    for infra_component in infra_dir.iterdir():
                        if infra_component.is_dir():
                            infra_test_dir = infra_component / "tests"
                            if infra_test_dir.exists() and any(infra_test_dir.rglob("test_*.py")):
                                test_dirs.append(("service", infra_test_dir))

    # Find root-level integration tests
    root_tests = root_dir / "tests" / "integration"
    if root_tests.exists() and any(root_tests.rglob("test_*.py")):
        test_dirs.append(("integration", root_tests))

    return sorted(test_dirs, key=lambda x: str(x[1]))


def run_pytest(
    test_dirs: List[Path],
    markers: Optional[List[str]] = None,
    coverage: bool = False,
    verbose: bool = True,
) -> Tuple[int, dict]:
    """
    Run pytest on specified directories.

    Returns:
        (exit_code, stats_dict)
    """
    cmd = ["uv", "run", "pytest"]

    # Add verbosity
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    # Add marker filters
    if markers:
        marker_expr = " and ".join(markers)
        cmd.extend(["-m", marker_expr])
    elif markers is not None:
        # Default: exclude slow, e2e, and integration tests for unit tests
        cmd.extend(["-m", "not slow and not e2e and not integration"])

    # Add coverage if requested
    if coverage:
        cmd.extend(["--cov", "--cov-report=term-missing", "--cov-report=html"])

    # Add test directories
    cmd.extend([str(d) for d in test_dirs])

    # Run pytest
    print(f"\n{Colors.OKBLUE}Running: {' '.join(cmd)}{Colors.ENDC}\n")
    result = subprocess.run(cmd, capture_output=False)

    return result.returncode, {}


def print_summary(test_dirs: List[Tuple[str, Path]]):
    """Print summary of what will be tested."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}Test Discovery Summary{Colors.ENDC}")
    print("=" * 80)

    by_category = defaultdict(list)
    for category, path in test_dirs:
        by_category[category].append(path)

    total = 0
    for category in sorted(by_category.keys()):
        paths = by_category[category]
        print(f"\n{Colors.OKCYAN}{category.upper()}:{Colors.ENDC} ({len(paths)} directories)")
        for path in sorted(paths):
            # Count test files
            test_files = list(path.rglob("test_*.py"))
            print(f"  - {path.relative_to(Path.cwd())} ({len(test_files)} test files)")
            total += len(test_files)

    print(f"\n{Colors.BOLD}Total: {len(test_dirs)} test directories, ~{total} test files{Colors.ENDC}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Run all tests across packages and services",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Run all unit tests
  %(prog)s --integration      # Include integration tests
  %(prog)s --e2e              # Include e2e tests
  %(prog)s --all              # Run all test types
  %(prog)s --coverage         # Run with coverage
  %(prog)s --summary-only     # Show what would be tested
        """,
    )

    parser.add_argument("--integration", action="store_true", help="Include integration tests")
    parser.add_argument("--e2e", action="store_true", help="Include end-to-end tests")
    parser.add_argument("--regression", action="store_true", help="Include regression tests")
    parser.add_argument("--all", action="store_true", help="Include all test types (integration, e2e, regression)")
    parser.add_argument("--coverage", action="store_true", help="Run with coverage reporting")
    parser.add_argument(
        "--summary-only", action="store_true", help="Show summary of test directories without running tests"
    )
    parser.add_argument("--quiet", action="store_true", help="Reduce output verbosity")

    args = parser.parse_args()

    # Find repository root
    repo_root = Path(__file__).parent.parent

    # Discover test directories
    print(f"{Colors.BOLD}Discovering test directories...{Colors.ENDC}")
    test_dirs = find_test_directories(repo_root)

    if not test_dirs:
        print(f"{Colors.FAIL}No test directories found!{Colors.ENDC}")
        return 1

    # Print summary
    print_summary(test_dirs)

    if args.summary_only:
        return 0

    # Determine markers
    markers = []
    if args.all:
        markers = None  # Run everything
    else:
        if args.integration:
            markers.append("integration")
        if args.e2e:
            markers.append("e2e")
        if args.regression:
            markers.append("regression")

    # Extract just the paths
    paths = [path for _, path in test_dirs]

    # Run tests
    print(f"\n{Colors.BOLD}{Colors.OKGREEN}Running Tests...{Colors.ENDC}\n")

    exit_code, stats = run_pytest(paths, markers=markers, coverage=args.coverage, verbose=not args.quiet)

    # Print final result
    print()
    if exit_code == 0:
        print(f"{Colors.BOLD}{Colors.OKGREEN}✓ All tests passed!{Colors.ENDC}")
    else:
        print(f"{Colors.BOLD}{Colors.FAIL}✗ Some tests failed (exit code: {exit_code}){Colors.ENDC}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
