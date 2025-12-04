"""
Stock-Level HOPS Merger for Nested Beams

This module provides functionality for merging multiple .hop files (representing individual beams)
into a single .hop file for a timber stock, based on nesting information from a JSON file.

The merger handles:
- Reading nesting data to determine beam positions within stock
- Offsetting X-coordinates of machining operations based on nesting positions
- Sorting operations by tool type and position along the stock
- Generating a merged HOPS file for the entire stock

Classes:
    StockHopsMerger: Main class for merging multiple beams into a stock

Usage Example:
    ```python
    from merge_stock_hops import StockHopsMerger

    # Initialize merger with nesting JSON and hop files directory
    merger = StockHopsMerger(
        nesting_json_path='path/to/nesting.json',
        hop_directory='path/to/hop/files/'
    )

    # Merge and write output
    merger.merge('output_merged.hop')
    ```

Coordinate System Notes:
    - EBENEF(x, y, z, theta, beta, ...): Only X-coordinate is offset
    - EBENE0(): Standard top view, all subsequent SP/G01/SAEGEN coordinates are offset
    - SAEGEN(x1, y1, z1, x2, y2, z2, ...): Both x1 and x2 are offset
    - SP/G01: First parameter (X-coordinate) is offset when following EBENE0()
"""

import json
import os
import re
import glob
from typing import List, Tuple
from .hop_core import HopFile, HopOperation


class StockHopsMerger:
    """
    Merges multiple .hop files (beams) into a single .hop file (stock) based on nesting data.

    The merger:
    1. Loads nesting JSON to determine beam positions in stock
    2. Auto-discovers .hop files and matches them to beams by dimension validation
    3. Applies X-offsets to all operations based on nesting positions
    4. Sorts operations by tool type and position (left to right)
    5. Generates merged HOPS file for the stock

    Attributes:
        nesting_data (dict): Loaded nesting JSON data
        stock_info (dict): Extracted stock dimensions and element positions
        hop_files (List[Tuple[HopFile, float]]): List of (HopFile, x_offset) tuples
    """

    def __init__(self, nesting_json_path: str, hop_directory: str):
        """
        Initialize the stock merger.

        Args:
            nesting_json_path: Path to the nesting JSON file
            hop_directory: Directory containing the .hop files to merge
        """
        self.nesting_data = self._load_nesting(nesting_json_path)
        self.hop_directory = hop_directory
        self.stock_info = self._extract_stock_info()
        self.hop_files = []
        self._auto_load_hop_files(hop_directory)

    def _load_nesting(self, json_path: str) -> dict:
        """Load and parse the nesting JSON file."""
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _extract_stock_info(self) -> dict:
        """
        Extract stock information from nesting data.

        Automatically finds the correct stock by matching beam keys from .hop filenames.

        Returns:
            dict: {
                'length': stock length,
                'cross_section': [width, height],
                'elements': {
                    beam_key: {
                        'length': beam length,
                        'offset': x-position in stock
                    }
                }
            }
        """
        # Get beam keys from .hop filenames
        hop_beam_keys = self._get_beam_keys_from_files()

        if not hop_beam_keys:
            raise ValueError("No R_00 .hop files found in directory")

        # Find which stock contains these beam keys
        stocks = self.nesting_data["data"]["stocks"]
        matching_stock = None

        for stock_idx, stock in enumerate(stocks):
            stock_data = stock["data"]
            stock_beam_keys = set()

            for element_data in stock_data["element_data"].values():
                stock_beam_keys.add(element_data["key"])

            # Check if all hop file beam keys are in this stock
            if hop_beam_keys.issubset(stock_beam_keys):
                matching_stock = stock
                print(
                    f"Found matching stock (index {stock_idx}) containing beams: {sorted(hop_beam_keys)}"
                )
                break

        if matching_stock is None:
            raise ValueError(
                f"No stock found containing all beam keys from .hop files: {sorted(hop_beam_keys)}\n"
                f"Available stocks have these beam keys:\n"
                + "\n".join(
                    [
                        f"  Stock {i}: {sorted([e['key'] for e in s['data']['element_data'].values()])}"
                        for i, s in enumerate(stocks[:5])
                    ]
                )
            )

        stock_data = matching_stock["data"]

        stock_info = {
            "length": stock_data["length"],
            "cross_section": stock_data["cross_section"],
            "elements": {},
            "element_order": [],  # Preserve order from nesting JSON
        }

        # Extract element data (beams) - preserve insertion order
        for element_id, element_data in stock_data["element_data"].items():
            beam_key = element_data["key"]
            beam_length = element_data["length"]
            x_offset = element_data["frame"]["data"]["point"][0]

            stock_info["elements"][beam_key] = {
                "length": beam_length,
                "offset": x_offset,
            }
            stock_info["element_order"].append(beam_key)

        return stock_info

    def _get_beam_keys_from_files(self) -> set:
        """Extract beam keys from R_00 .hop filenames in the directory."""
        all_hop_files = glob.glob(os.path.join(self.hop_directory, "*.hop"))
        hop_files = [
            f for f in all_hop_files if re.search(r"R_?0{2}", os.path.basename(f))
        ]

        beam_keys = set()
        for hop_path in hop_files:
            filename = os.path.basename(hop_path)
            match = re.search(r"R_?0{2}_(\d+)\.hop", filename)
            if match:
                beam_keys.add(int(match.group(1)))

        return beam_keys

    def _get_beam_keys_in_order(self) -> List[int]:
        """
        Get beam keys in the order they appear in the nesting result.

        Returns:
            List of beam keys in nesting order
        """
        return self.stock_info["element_order"]

    def _auto_load_hop_files(self, directory: str):
        """
        Automatically discover and load .hop files, matching them to beams.

        Files are matched by extracting beam key from filename (e.g., R_00_163.hop → beam 163)
        and matching to the nesting result beam keys.

        Args:
            directory: Directory containing .hop files
        """
        # Filter for files containing "R" followed by two zeros (R_00, R00, etc.)
        all_hop_files = glob.glob(os.path.join(directory, "*.hop"))
        hop_files = [
            f for f in all_hop_files if re.search(r"R_?0{2}", os.path.basename(f))
        ]

        available_beam_keys = set(self.stock_info["elements"].keys())

        # Match each file to its beam key from filename
        for hop_path in hop_files:
            filename = os.path.basename(hop_path)

            # Extract beam key from filename (e.g., R_00_163.hop → 163)
            match = re.search(r"R_?0{2}_(\d+)\.hop", filename)
            if not match:
                print(f"⚠ Skipping {filename}: Cannot extract beam key from filename")
                continue

            beam_key = int(match.group(1))

            # Check if this beam exists in nesting data
            if beam_key not in available_beam_keys:
                print(
                    f"⚠ Skipping {filename}: Beam {beam_key} not found in nesting data"
                )
                continue

            hop_file = HopFile(hop_path)
            x_offset = self.stock_info["elements"][beam_key]["offset"]

            self.hop_files.append((hop_file, x_offset, beam_key))
            print(f"✓ Matched {filename} → Beam {beam_key} (Offset: {x_offset:.2f}mm)")

        if len(self.hop_files) != len(available_beam_keys):
            raise ValueError(
                f"Incomplete match: Found {len(self.hop_files)} matching .hop files but {len(available_beam_keys)} beams in nesting"
            )

    def merge(self, output_path: str):
        """
        Merge all .hop files into a single stock .hop file.

        Process:
        1. Collect all operations from all files
        2. Apply X-offsets based on nesting positions
        3. Sort operations by tool type and position
        4. Generate merged file with stock dimensions

        Args:
            output_path: Path for the output merged .hop file
        """
        print(f"\n🔧 Merging {len(self.hop_files)} beams into stock...")

        # Collect all operations with offsets applied
        all_operations = []
        for hop_file, x_offset, beam_key in self.hop_files:
            for operation in hop_file.operations:
                # Apply offset and calculate min_x for sorting
                offset_lines = operation.apply_offset(x_offset)
                operation.calculate_min_x()
                operation.min_x += x_offset  # Update min_x with offset

                # Store operation with offset lines
                all_operations.append((operation, offset_lines))

        # Sort operations by tool type and position
        all_operations.sort(
            key=lambda x: (
                x[0].tool_type.value,  # Tool type priority from enum
                x[0].min_x,  # Position along stock
            )
        )

        print(f"📊 Sorted {len(all_operations)} operations by tool and position")

        # Generate merged file
        self._write_merged_file(output_path, all_operations)
        print(f"✅ Merged file written to: {output_path}")

    def _write_merged_file(
        self, output_path: str, sorted_operations: List[Tuple[HopOperation, List[str]]]
    ):
        """
        Write the merged HOPS file.

        Args:
            output_path: Output file path
            sorted_operations: List of (operation, offset_lines) tuples
        """
        with open(output_path, "w", encoding="utf-8") as f:
            # Write header
            f.write(";MERGED STOCK FILE\n")
            f.write(";Generated by merge_stock_hops.py\n")
            f.write(";MASCHINE=HOLZHER\n")

            # Write VARS section with stock dimensions
            stock_length = self.stock_info["length"]
            stock_width, stock_height = self.stock_info["cross_section"]

            f.write("VARS\n")
            f.write(f"   DX := {stock_length:.3f};*VAR* Piece Length\n")
            f.write(f"   DY := {stock_width:.3f};*VAR* Piece Height\n")
            f.write(f"   DZ := {stock_height:.3f};*VAR* Piece Thickness\n")
            f.write("START\n")
            f.write("FERTIGTEIL(DX,DY,DZ,0,0,0,0,0,'',0,0,0)\n")
            f.write("CALL Park_V7 ( VAL MODE:=11,POSX:=0,POSY:=0)\n")

            # Write all operations
            for operation, offset_lines in sorted_operations:
                f.write("; ---------------------------------\n")
                f.write(
                    f"; Operation: {operation.tool_type} at X={operation.min_x:.1f}\n"
                )
                f.write("; ---------------------------------\n")
                for line in offset_lines:
                    f.write(line)
                f.write("\n")

            # Write footer
            f.write("EBENE0()\n")


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) >= 3:
        nesting_json = sys.argv[1]
        hop_dir = sys.argv[2]
        output = sys.argv[3] if len(sys.argv) > 3 else "merged_output.hop"

        merger = StockHopsMerger(nesting_json, hop_dir)
        merger.merge(output)
    else:
        # Default test with sample data
        base_path = os.path.dirname(__file__)
        test_path = os.path.join(base_path, "test_files", "2811_whole_model")

        if os.path.exists(test_path):
            merger = StockHopsMerger(
                nesting_json_path=os.path.join(
                    test_path, "2811_whole_model_nesting.json"
                ),
                hop_directory=os.path.join(test_path, "2811_whole_model"),
            )
            output_file = os.path.join(
                test_path, "2811_whole_model", "merged_stock.hop"
            )
            merger.merge(output_file)
        else:
            print(
                "Usage: python merge_stock_hops.py <nesting_json> <hop_directory> [output_file]"
            )
