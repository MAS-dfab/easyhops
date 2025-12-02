"""
Stock-Level HOPS Merger for Nested Beams

This module merges multiple .hop files (representing individual beams) into a single
.hop file for a timber stock, based on nesting information from a JSON file.

The merger handles:
- Reading nesting data to determine beam positions within stock
- Offsetting X-coordinates of machining operations based on nesting positions
- Sorting operations by tool type and position along the stock
- Generating a merged HOPS file for the entire stock

Classes:
    HopOperation: Represents a single machining operation block with offset capabilities
    HopFile: Parses and represents a single .hop file
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


class HopOperation:
    """
    Represents a single machining operation block in a HOPS file.

    An operation consists of:
    - Tool command (WZF or WZS)
    - Work plane definition (EBENEF or EBENE0/EBENE2/EBENE4)
    - Machining commands (SP, G01, EP for milling; SAEGEN for sawing)
    - Associated comment lines

    Attributes:
        tool_command (str): Full tool command line (e.g., "WZS(201,10000,7000,20000,_SD,_ANF,'1')")
        tool_type (str): Extracted tool identifier (e.g., "WZS201", "WZF504")
        lines (List[str]): All lines comprising this operation
        has_ebenef (bool): True if operation uses EBENEF work plane
        min_x (float): Minimum X-coordinate for sorting purposes
    """

    def __init__(self, tool_command: str, lines: List[str]):
        """
        Initialize a machining operation.

        Args:
            tool_command: The tool selection command line
            lines: All lines belonging to this operation block
        """
        self.tool_command = tool_command
        self.lines = lines
        self.tool_type = self._extract_tool_type()
        self.has_ebenef = self._check_ebenef()
        self.min_x = None

    def _extract_tool_type(self) -> str:
        """Extract tool identifier from tool command (e.g., 'WZS201' from 'WZS(201,...)')."""
        match = re.match(r"(WZ[SF])\((\d+)", self.tool_command)
        if match:
            return f"{match.group(1)}{match.group(2)}"
        return "UNKNOWN"

    def _check_ebenef(self) -> bool:
        """Check if this operation uses EBENEF work plane definition."""
        return any("EBENEF" in line for line in self.lines)

    def calculate_min_x(self) -> float:
        """
        Calculate minimum X-coordinate in this operation for sorting.

        Returns:
            Minimum X-coordinate found in operation commands
        """
        x_coords = []

        for line in self.lines:
            # Extract X from EBENEF
            if "EBENEF" in line:
                match = re.search(r"EBENEF\(([-+]?\d+\.?\d*)", line)
                if match:
                    x_coords.append(float(match.group(1)))

            # Extract X from SP
            elif line.strip().startswith("SP("):
                match = re.search(r"SP\(([-+]?\d+\.?\d*)", line)
                if match:
                    x_coords.append(float(match.group(1)))

            # Extract X from SAEGEN
            elif "SAEGEN" in line:
                match = re.search(r"SAEGEN\(([-+]?\d+\.?\d*)", line)
                if match:
                    x_coords.append(float(match.group(1)))

        self.min_x = min(x_coords) if x_coords else 0.0
        return self.min_x

    def apply_offset(self, x_offset: float) -> List[str]:
        """
        Apply X-offset to all coordinates in this operation.

        Offsetting rules:
        - EBENEF: Only first parameter (X-coordinate)
        - SP, G01 (after EBENE0): First parameter (X-coordinate)
        - SAEGEN: Parameters 1 and 4 (X1 and X2)

        Args:
            x_offset: Distance to offset X-coordinates (mm)

        Returns:
            List of offset lines for this operation
        """
        offset_lines = []
        in_ebene0_block = False

        for line in self.lines:
            # Check if we're entering an EBENE0 block
            if "EBENE0()" in line or "EBENE2()" in line or "EBENE4()" in line:
                in_ebene0_block = True
                offset_lines.append(line)
                continue

            # EBENEF: offset only first parameter (X)
            if "EBENEF" in line:
                in_ebene0_block = False
                offset_lines.append(self._offset_ebenef(line, x_offset))

            # SAEGEN: offset parameters 1 and 4 (X1, X2)
            elif "SAEGEN" in line:
                offset_lines.append(self._offset_saegen(line, x_offset))

            # SP, G01: offset first parameter (X) if in EBENE0 block
            elif (
                line.strip().startswith("SP(") or line.strip().startswith("G01(")
            ) and in_ebene0_block:
                offset_lines.append(self._offset_coordinate_line(line, x_offset))

            # All other lines pass through unchanged
            else:
                offset_lines.append(line)

        return offset_lines

    def _offset_ebenef(self, line: str, x_offset: float) -> str:
        """Offset X-coordinate (first parameter) in EBENEF command."""
        match = re.match(r"EBENEF\(([-+]?\d+\.?\d*)(,.*)", line)
        if match:
            x_val = float(match.group(1)) + x_offset
            return f"EBENEF({x_val:.4f}{match.group(2)}\n"
        return line

    def _offset_saegen(self, line: str, x_offset: float) -> str:
        """Offset X1 and X2 (parameters 1 and 4) in SAEGEN command."""
        # SAEGEN(x1, y1, z1, x2, y2, z2, ...)
        match = re.match(
            r"SAEGEN\(([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*)(,.*)",
            line,
        )
        if match:
            x1 = float(match.group(1)) + x_offset
            y1 = float(match.group(2))
            z1 = float(match.group(3))
            x2 = float(match.group(4)) + x_offset
            y2 = float(match.group(5))
            z2 = float(match.group(6))
            rest = match.group(7)
            return (
                f"SAEGEN({x1:.3f},{y1:.3f},{z1:.3f},{x2:.3f},{y2:.3f},{z2:.3f}{rest}\n"
            )
        return line

    def _offset_coordinate_line(self, line: str, x_offset: float) -> str:
        """Offset X-coordinate (first parameter) in SP or G01 command."""
        # SP(x, y, z, ...) or G01(x, y, z, ...)
        match = re.match(r"(SP|G01)\(([-+]?\d+\.?\d*)(,.*)", line)
        if match:
            command = match.group(1)
            x_val = float(match.group(2)) + x_offset
            rest = match.group(3)
            return f"{command}({x_val:.3f}{rest}\n"
        return line


class HopFile:
    """
    Represents and parses a single .hop file.

    Parses the file into:
    - Header comments (lines starting with ';')
    - VARS section (variable definitions)
    - Operations (machining command blocks)

    Attributes:
        filepath (str): Path to the .hop file
        header (List[str]): Comment lines at top of file
        vars_section (List[str]): VARS...START section
        operations (List[HopOperation]): Parsed machining operations
        dx (float): Piece length extracted from VARS section
        dy (float): Piece height
        dz (float): Piece thickness
    """

    def __init__(self, filepath: str):
        """
        Initialize HopFile parser.

        Args:
            filepath: Path to the .hop file
        """
        self.filepath = filepath
        self.header = []
        self.vars_section = []
        self.operations = []
        self.dx = None
        self.dy = None
        self.dz = None
        self._parse()

    def _parse(self):
        """Parse the .hop file into header, vars, and operations."""
        with open(self.filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        # Extract header comments
        i = 0
        while i < len(lines) and lines[i].startswith(";"):
            self.header.append(lines[i])
            i += 1

        # Extract VARS section (up to START)
        while i < len(lines) and "START" not in lines[i]:
            self.vars_section.append(lines[i])
            # Extract DX, DY, DZ values
            if "DX :=" in lines[i]:
                match = re.search(r"DX := ([-+]?\d+\.?\d*)", lines[i])
                if match:
                    self.dx = float(match.group(1))
            elif "DY :=" in lines[i]:
                match = re.search(r"DY := ([-+]?\d+\.?\d*)", lines[i])
                if match:
                    self.dy = float(match.group(1))
            elif "DZ :=" in lines[i]:
                match = re.search(r"DZ := ([-+]?\d+\.?\d*)", lines[i])
                if match:
                    self.dz = float(match.group(1))
            i += 1

        # Add START line
        if i < len(lines):
            self.vars_section.append(lines[i])
            i += 1

        # Skip FERTIGTEIL and Park lines (part of initialization, not operations)
        while i < len(lines) and not (lines[i].strip().startswith("WZ")):
            i += 1

        # Parse operations (WZF/WZS blocks)
        while i < len(lines):
            if lines[i].strip().startswith("WZ"):
                tool_command = lines[i]
                operation_lines = [tool_command]
                i += 1

                # Collect lines until next tool command or end of file
                while i < len(lines) and not lines[i].strip().startswith("WZ"):
                    # Stop at EBENE0() at root level (signals end of operation)
                    if (
                        lines[i].strip() == "EBENE0()"
                        and i + 1 < len(lines)
                        and not lines[i + 1].strip().startswith("SAEGEN")
                    ):
                        break
                    operation_lines.append(lines[i])
                    i += 1

                self.operations.append(HopOperation(tool_command, operation_lines))
            else:
                i += 1


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
        # Assuming we're working with the first stock in the nesting data
        # Adjust if you need to handle multiple stocks
        stock = self.nesting_data["data"]["stocks"][0]
        stock_data = stock["data"]

        stock_info = {
            "length": stock_data["length"],
            "cross_section": stock_data["cross_section"],
            "elements": {},
        }

        # Extract element data (beams)
        for element_id, element_data in stock_data["element_data"].items():
            beam_key = element_data["key"]
            beam_length = element_data["length"]
            x_offset = element_data["frame"]["data"]["point"][0]

            stock_info["elements"][beam_key] = {
                "length": beam_length,
                "offset": x_offset,
            }

        return stock_info

    def _get_sorted_beam_keys(self) -> List[int]:
        """
        Get beam keys sorted by X-position (left to right in stock).

        Returns:
            List of beam keys sorted by position
        """
        sorted_items = sorted(
            self.stock_info["elements"].items(), key=lambda item: item[1]["offset"]
        )
        return [key for key, _ in sorted_items]

    def _auto_load_hop_files(self, directory: str):
        """
        Automatically discover and load .hop files, matching them to beams.

        Files are matched by:
        1. Sorting filenames alphabetically
        2. Sorting beam keys by X-position
        3. Pairing by index
        4. Validating dimensions match (with tolerance)

        Args:
            directory: Directory containing .hop files
        """
        hop_files = sorted(glob.glob(os.path.join(directory, "*.hop")))
        beam_keys = self._get_sorted_beam_keys()

        if len(hop_files) != len(beam_keys):
            raise ValueError(
                f"Mismatch: {len(hop_files)} .hop files but {len(beam_keys)} beams in nesting"
            )

        # Match by index and validate dimensions
        for hop_path, beam_key in zip(hop_files, beam_keys):
            hop_file = HopFile(hop_path)
            hop_dx = hop_file.dx
            beam_length = self.stock_info["elements"][beam_key]["length"]
            x_offset = self.stock_info["elements"][beam_key]["offset"]

            # Validate dimensions match (with tolerance)
            tolerance = 10  # mm
            if abs(hop_dx - beam_length) > tolerance:
                raise AssertionError(
                    f"Dimension mismatch for {os.path.basename(hop_path)}:\n"
                    f"  .hop DX = {hop_dx:.2f}mm\n"
                    f"  Nesting beam {beam_key} length = {beam_length:.2f}mm\n"
                    f"  Difference = {abs(hop_dx - beam_length):.2f}mm (tolerance: {tolerance}mm)"
                )

            self.hop_files.append((hop_file, x_offset, beam_key))
            print(
                f"✓ Matched {os.path.basename(hop_path)} → Beam {beam_key} (DX: {hop_dx:.2f}mm, Offset: {x_offset:.2f}mm)"
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
        tool_priority = {"WZF504": 0, "WZF503": 1, "WZS201": 2}  # Priority order
        all_operations.sort(
            key=lambda x: (
                tool_priority.get(x[0].tool_type, 99),  # Tool type priority
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
