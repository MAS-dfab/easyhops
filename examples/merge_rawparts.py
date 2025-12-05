"""
Script to merge nested .hop files into a single stock file.

This script uses the StockHopsMerger to combine multiple beam .hop files
based on nesting information from a JSON file.

Usage:
    python merge_rawparts.py --merge [--nesting PATH] [--hops-dir PATH] [--output PATH]
"""

import os
import sys

# Add parent directory to path for src package import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.easyhops.merge_stock_hops import StockHopsMerger

HERE = os.path.dirname(__file__)
DEFAULT_TEST_DIR = os.path.join(HERE, "251202_model")
DEFAULT_NESTING_JSON = os.path.join(DEFAULT_TEST_DIR, "251202_model_nesting.json")
DEFAULT_HOPS_DIR = os.path.join(DEFAULT_TEST_DIR, "251202_model")
DEFAULT_OUTPUT = os.path.join(DEFAULT_HOPS_DIR, "merged_stock.hop")


def merge_hops(nesting_json=None, hops_dir=None, output_file=None):
    """Merge nested .hop files into a single stock file."""
    # Use defaults if not provided
    nesting_json = nesting_json or DEFAULT_NESTING_JSON
    hops_dir = hops_dir or DEFAULT_HOPS_DIR
    output_file = output_file or DEFAULT_OUTPUT

    print(f"Nesting JSON: {nesting_json}")
    print(f"HOPS directory: {hops_dir}")
    print(f"Output file: {output_file}")

    # Validate inputs
    if not os.path.exists(nesting_json):
        raise FileNotFoundError(f"Nesting JSON file not found: {nesting_json}")

    if not os.path.isdir(hops_dir):
        raise FileNotFoundError(f"HOPS directory not found: {hops_dir}")

    # Run merger
    print(f"\n{'=' * 60}")
    print("MERGING NESTED HOPS FILES")
    print(f"{'=' * 60}\n")

    merger = StockHopsMerger(nesting_json, hops_dir)
    merger.merge(output_file)

    print(f"\n{'=' * 60}")
    print(f"✅ Merged file created: {output_file}")
    print(f"{'=' * 60}\n")


def main():
    """Main function to merge nested .hop files."""
    try:
        print("Merging HOPS files...")
        merge_hops()
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
