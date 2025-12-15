"""Example: Merge multiple HOP files into a stock-level HOP file.

This script merges individual beam HOP files into a single stock-level HOP file
based on nesting data. Operations are grouped by tool type (not by piece) for
efficient machining across the entire stock.

Usage:
    python merge_stock_example.py <nesting_json> <hop_directory>

The merged HOP file will be created in the same directory as the nesting JSON,
named "merged_stock.hop".
"""

import os
import sys

# Add src to path so we can import easyhops
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from easyhops.merge_stock_hops import StockHopsMerger

# Define your paths here
NESTING_JSON = r"c:\Users\kapso\OneDrive\Documents\GitHub\easyhops\examples\251212\1212_whole_model_nesting.json"
HOP_DIRECTORY = r"c:\Users\kapso\OneDrive\Documents\GitHub\easyhops\examples\251212\1212_whole_model"


def main():
    """Merge HOP files and create merged stock HOP file."""

    nesting_json = NESTING_JSON
    hop_dir = HOP_DIRECTORY

    # Verify files exist
    if not os.path.exists(nesting_json):
        print(f"Error: Nesting JSON not found: {nesting_json}")
        return

    if not os.path.exists(hop_dir):
        print(f"Error: HOP directory not found: {hop_dir}")
        return

    try:
        # Use new filename-based merging (handles S<idx>_R<id>_<beam>(<flip>).hop format)
        StockHopsMerger.merge_by_filename_pattern(nesting_json, hop_dir)

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
