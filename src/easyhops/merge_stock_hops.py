"""
Stock-Level HOPS Merger for Nested Beams

This module provides functionality for merging multiple .hop files (representing individual beams)
into a single .hop file for a timber stock, based on nesting information from a JSON file.

Filename Format:
    S<stock_idx>_R<stock_id>_<beam_key>(<flip>).hop
    - stock_idx: 0-based stock index in nesting JSON
    - stock_id: Stock identifier (e.g., "01", "02")
    - beam_key: Beam identifier number
    - flip: Optional (1) suffix indicating stock flip/rotation

The merger handles:
- Parsing filename to extract stock index, stock ID, beam key, and flip indicator
- Grouping files by stock index and flip
- Reading nesting data to determine beam positions within stock
- Offsetting X-coordinates of machining operations based on nesting positions
- Grouping and sorting operations by tool type (not by piece)
- Preserving comment headers with each machining block
- Generating merged HOPS files: S<idx>_R<id>.hop and S<idx>_R<id>(1).hop

Classes:
    StockHopsMerger: Main class for merging multiple beams into stocks

Usage Example:
    ```python
    from easyhops.merge_stock_hops import StockHopsMerger

    # Initialize merger with nesting JSON and hop files directory
    merger = StockHopsMerger(nesting_json_path="path/to/nesting.json", hop_directory="path/to/hop/files/")

    # Merge and write outputs (creates multiple stock files)
    merger.merge_all()
    ```

Coordinate System Notes:
    - EBENEF(x, y, z, theta, beta, ...): X-coordinate is offset based on nesting position
    - EBENE0(): Standard top view, subsequent operation coordinates are offset
    - SAEGEN(x1, y1, z1, x2, y2, z2, ...): Both x1 and x2 are offset
    - SP/G01/EP: X-coordinates are offset when following EBENE or EBENEF
    - Comments from original files are preserved in merged output
"""

import glob
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from .hop_core import FinishedPart
from .hop_core import ParkMode
from .hop_core import VarsDefinition
from .hop_job import HOPSJob
from .hop_job import HOPSMachining
from .machining_commands import G01
from .machining_commands import G02M
from .machining_commands import G03M
from .machining_commands import DrillingOperation
from .machining_commands import MillingOperation
from .machining_commands import SawingOperation
from .work_planes import FreePlane


@dataclass
class BeamFileInfo:
    """Information extracted from beam HOP filename.

    Attributes:
        filepath: Full path to the .hop file
        filename: Just the filename
        stock_idx: Stock index (0-based)
        stock_id: Stock identifier string (e.g., "01", "02")
        beam_key: Beam identifier number
        flip: Flip indicator (0 for normal, 1 for flipped)
    """

    filepath: str
    filename: str
    stock_idx: int
    stock_id: str
    beam_key: int
    flip: int


@dataclass
class OffsetMachining:
    """Container for a machining operation with its applied offset.

    Attributes:
        machining: The HOPSMachining object (tool + workplane + operations list)
        x_offset: The X-offset applied to this machining
        min_x: Minimum X coordinate after offset (for sorting)
        beam_key: Original beam key this machining came from
    """

    machining: HOPSMachining
    x_offset: float
    min_x: float
    beam_key: int


class StockHopsMerger:
    """
    Merges multiple .hop files (beams) into a single .hop file (stock) based on nesting data.

    The merger:
    1. Loads nesting JSON to determine beam positions in stock
    2. Auto-discovers .hop files and matches them to beams by dimension validation
    3. Applies X-offsets to all operations based on nesting positions
    4. Groups operations by tool type (not by piece)
    5. Sorts operations by tool+workplane and position (left to right)
    6. Generates merged HOPS file for the stock

    Attributes:
        nesting_data (dict): Loaded nesting JSON data
        stock_info (dict): Extracted stock dimensions and element positions
        hop_jobs (List[Tuple[HOPSJob, float, int]]): List of (HOPSJob, x_offset, beam_key) tuples
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
        self.hop_jobs = []
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
                print(f"Found matching stock (index {stock_idx}) containing beams: {sorted(hop_beam_keys)}")
                break

        if matching_stock is None:
            raise ValueError(
                f"No stock found containing all beam keys from .hop files: {sorted(hop_beam_keys)}\n"
                f"Available stocks have these beam keys:\n"
                + "\n".join([f"  Stock {i}: {sorted([e['key'] for e in s['data']['element_data'].values()])}" for i, s in enumerate(stocks[:5])])
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
        hop_files = [f for f in all_hop_files if re.search(r"R_?0{2}", os.path.basename(f))]

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
        hop_files = [f for f in all_hop_files if re.search(r"R_?0{2}", os.path.basename(f))]

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
                print(f"⚠ Skipping {filename}: Beam {beam_key} not found in nesting data")
                continue

            # Parse HOP file using new architecture
            hop_job = HOPSJob.from_hop_file(hop_path)
            x_offset = self.stock_info["elements"][beam_key]["offset"]

            self.hop_jobs.append((hop_job, x_offset, beam_key))
            print(f"✓ Matched {filename} → Beam {beam_key} (Offset: {x_offset:.2f}mm, {len(hop_job.machinings)} machinings)")

        if len(self.hop_jobs) != len(available_beam_keys):
            raise ValueError(f"Incomplete match: Found {len(self.hop_jobs)} matching .hop files but {len(available_beam_keys)} beams in nesting")

    @staticmethod
    def _offset_free_plane(plane: FreePlane, x_offset: float) -> FreePlane:
        """Apply X-offset to a FreePlane (EBENEF).

        Args:
            plane: Original FreePlane
            x_offset: X-offset to apply

        Returns:
            New FreePlane with offset applied
        """
        return FreePlane(
            x=plane.x + x_offset,
            y=plane.y,
            z=plane.z,
            rotation_angle=plane.rotation_angle,
            tilt_angle=plane.tilt_angle,
            easy_snap_xy=plane.easy_snap_xy,
            easy_snap_z=plane.easy_snap_z,
        )

    @staticmethod
    def _offset_milling_operation(operation: MillingOperation, x_offset: float) -> MillingOperation:
        """Apply X-offset to a MillingOperation (SP + G01s + EP).

        Args:
            operation: Original MillingOperation
            x_offset: X-offset to apply

        Returns:
            New MillingOperation with offset applied to all coordinates
        """
        from .machining_commands import StartPoint

        # Offset start point
        new_sp = StartPoint(
            x=operation.start_point.x + x_offset,
            y=operation.start_point.y,
            z=operation.start_point.z,
            radius_compensation=operation.start_point.radius_compensation,
            lead_in_mode=operation.start_point.lead_in_mode,
            lead_in_factor=operation.start_point.lead_in_factor,
            distance_to_contour=operation.start_point.distance_to_contour,
            offset_angle=operation.start_point.offset_angle,
            tip_angle=operation.start_point.tip_angle,
            easy_snap_xy=operation.start_point.easy_snap_xy,
            easy_snap_z=operation.start_point.easy_snap_z,
            process_mode=operation.start_point.process_mode,
            milling_steps=operation.start_point.milling_steps,
            depth_per_level=operation.start_point.depth_per_level,
            excess_depth=operation.start_point.excess_depth,
            interpolation_with_rot_axis=operation.start_point.interpolation_with_rot_axis,
            activate_laser=operation.start_point.activate_laser,
            start_correction_above=operation.start_point.start_correction_above,
            tilt_angle=operation.start_point.tilt_angle,
            excess_length=operation.start_point.excess_length,
            axial_lead_in_out=operation.start_point.axial_lead_in_out,
            axial_distance=operation.start_point.axial_distance,
            param_23=operation.start_point.param_23,
            feedrate=operation.start_point.feedrate,
        )

        # Offset all moves (G01, G02M, G03M)
        new_moves = []
        for move in operation.moves:
            if isinstance(move, G01):
                new_moves.append(
                    G01(
                        x=move.x + x_offset,
                        y=move.y,
                        z=move.z,
                        corner_radius=move.corner_radius,
                        easy_snap_xy=move.easy_snap_xy,
                        easy_snap_z=move.easy_snap_z,
                        feedrate=move.feedrate,
                    )
                )
            elif isinstance(move, G02M):
                new_moves.append(
                    G02M(
                        x=move.x + x_offset,
                        y=move.y,
                        z=move.z,
                        mx=move.mx + x_offset,
                        my=move.my,
                        corner_radius=move.corner_radius,
                        easy_snap_xy=move.easy_snap_xy,
                        easy_snap_z=move.easy_snap_z,
                        easy_snap_center=move.easy_snap_center,
                        feedrate=move.feedrate,
                    )
                )
            elif isinstance(move, G03M):
                new_moves.append(
                    G03M(
                        x=move.x + x_offset,
                        y=move.y,
                        z=move.z,
                        mx=move.mx + x_offset,
                        my=move.my,
                        corner_radius=move.corner_radius,
                        easy_snap_xy=move.easy_snap_xy,
                        easy_snap_z=move.easy_snap_z,
                        easy_snap_center=move.easy_snap_center,
                        feedrate=move.feedrate,
                    )
                )

        # End point doesn't have coordinates, just copy
        new_ep = operation.end_point

        return MillingOperation(start_point=new_sp, moves=new_moves, end_point=new_ep)

    @staticmethod
    def _offset_sawing_operation(operation: SawingOperation, x_offset: float) -> SawingOperation:
        """Apply X-offset to a SawingOperation (SAEGEN).

        Args:
            operation: Original SawingOperation
            x_offset: X-offset to apply

        Returns:
            New SawingOperation with offset applied to both start and end X
        """
        return SawingOperation(
            sx=operation.sx + x_offset,
            sy=operation.sy,
            sz=operation.sz,
            ex=operation.ex + x_offset,
            ey=operation.ey,
            ez=operation.ez,
            radius_compensation=operation.radius_compensation,
            fit_in=operation.fit_in,
            lead_in_out=operation.lead_in_out,
            process_mode=operation.process_mode,
            tilt_angle=operation.tilt_angle,
            z_level=operation.z_level,
            easy_snap_xy_start=operation.easy_snap_xy_start,
            easy_snap_xy_end=operation.easy_snap_xy_end,
            easy_snap_z=operation.easy_snap_z,
        )

    @staticmethod
    def _offset_drilling_operation(operation: DrillingOperation, x_offset: float) -> DrillingOperation:
        """Apply X-offset to a DrillingOperation (BOHR).

        Args:
            operation: Original DrillingOperation
            x_offset: X-offset to apply

        Returns:
            New DrillingOperation with offset applied to X coordinate
        """
        return DrillingOperation(
            x=operation.x + x_offset,
            y=operation.y,
            z=operation.z,
            depth=operation.depth,
            diameter=operation.diameter,
            drilling_flags=operation.drilling_flags,
            rotation=operation.rotation,
            tilt=operation.tilt,
            easy_snap_xy=operation.easy_snap_xy,
            easy_snap_z=operation.easy_snap_z,
        )

    @staticmethod
    def _offset_machining(machining: HOPSMachining, x_offset: float, beam_key: int) -> OffsetMachining:
        """Apply X-offset to a complete HOPSMachining (tool + workplane + operations).

        Args:
            machining: Original HOPSMachining
            x_offset: X-offset to apply
            beam_key: Beam key for tracking

        Returns:
            OffsetMachining with offset applied to workplane and all operations
        """
        # Offset workplane if it's a FreePlane
        if isinstance(machining.work_plane, FreePlane):
            new_work_plane = StockHopsMerger._offset_free_plane(machining.work_plane, x_offset)
        else:
            # Standard WorkPlane (EBENE0-4) doesn't need offsetting
            new_work_plane = machining.work_plane

        # Offset all operations in the list
        new_operations = []
        for operation in machining.operations:
            if isinstance(operation, MillingOperation):
                new_operations.append(StockHopsMerger._offset_milling_operation(operation, x_offset))
            elif isinstance(operation, SawingOperation):
                new_operations.append(StockHopsMerger._offset_sawing_operation(operation, x_offset))
            elif isinstance(operation, DrillingOperation):
                new_operations.append(StockHopsMerger._offset_drilling_operation(operation, x_offset))
            else:
                # Unknown operation type, keep original
                new_operations.append(operation)

        # Create new machining with offset coordinates, preserving comments
        new_machining = HOPSMachining(tool=machining.tool, work_plane=new_work_plane, operations=new_operations, comments=machining.comments)

        # Calculate min_x for sorting (from first operation's first coordinate)
        min_x = x_offset  # Default to offset if no operations
        if new_operations:
            first_op = new_operations[0]
            if isinstance(first_op, MillingOperation):
                min_x = first_op.start_point.x
            elif isinstance(first_op, SawingOperation):
                min_x = min(first_op.sx, first_op.ex)
            elif isinstance(first_op, DrillingOperation):
                min_x = first_op.x
            elif isinstance(new_work_plane, FreePlane):
                min_x = new_work_plane.x

        return OffsetMachining(machining=new_machining, x_offset=x_offset, min_x=min_x, beam_key=beam_key)

    def _calculate_tool_sort_key(self, machining: HOPSMachining) -> Tuple[int, int]:
        """Calculate sort key for grouping operations by tool.

        Args:
            machining: The machining to calculate key for

        Returns:
            Tuple of (tool_type_priority, tool_position)
        """
        return (machining.tool.tool_type.value, machining.tool.position)

    def merge(self, output_path: str):
        """
        Merge all .hop files into a single stock .hop file.

        Process:
        1. Collect all machinings from all beams
        2. Apply X-offsets based on nesting positions
        3. Group and sort operations by tool type (not by piece)
        4. Sort within each tool group by position along stock
        5. Generate merged file with stock dimensions

        Args:
            output_path: Path for the output merged .hop file
        """
        print(f"\n🔧 Merging {len(self.hop_jobs)} beams into stock...")

        # Collect all machinings with offsets applied
        all_offset_machinings: List[OffsetMachining] = []
        total_operations = 0

        for hop_job, x_offset, beam_key in self.hop_jobs:
            for machining in hop_job.machinings:
                offset_machining = StockHopsMerger._offset_machining(machining, x_offset, beam_key)
                all_offset_machinings.append(offset_machining)
                total_operations += len(machining.operations)

        print(f"📊 Collected {len(all_offset_machinings)} machining blocks ({total_operations} total operations)")

        # Sort by tool type first, then by position along stock
        # This groups all operations for the same tool together
        all_offset_machinings.sort(
            key=lambda om: (
                self._calculate_tool_sort_key(om.machining),  # Group by tool
                om.min_x,  # Then by position
            )
        )

        print("✅ Sorted by tool type and position (operations grouped by tool, not by piece)")

        # Generate merged file
        self._write_merged_file(output_path, all_offset_machinings)
        print(f"✅ Merged file written to: {output_path}")

    def _write_merged_file(self, output_path: str, offset_machinings: List[OffsetMachining]):
        """
        Write the merged HOPS file.

        Args:
            output_path: Output file path
            offset_machinings: List of OffsetMachining objects (already sorted)
        """
        # Get stock dimensions
        stock_length = self.stock_info["length"]
        stock_width, stock_height = self.stock_info["cross_section"]

        # Create stock job components
        vars_def = VarsDefinition(dx=stock_length, dy=stock_width, dz=stock_height)
        finished_part = FinishedPart(comment="MERGED STOCK")
        park_mode = ParkMode(mode=4, pos_x=0, pos_y=0)

        # Header comments
        header = [
            ";MERGED STOCK FILE",
            ";Generated by merge_stock_hops.py",
            ";",
            f";Stock dimensions: {stock_length:.1f} x {stock_width:.1f} x {stock_height:.1f} mm",
            f";Beams merged: {len(self.hop_jobs)}",
            f";Total machining blocks: {len(offset_machinings)}",
            ";",
            ";Merged beam files:",
        ]

        # Add each merged beam info
        for hop_job, x_offset, beam_key in self.hop_jobs:
            beam_info = self.stock_info["elements"][beam_key]
            beam_filename = f"R_00_{beam_key}.hop"
            header.append(f";  - {beam_filename} (Beam {beam_key}): offset={x_offset:.2f}mm, length={beam_info['length']:.2f}mm")

        header.append(";")
        header.append(";MASCHINE=HOLZHER")

        # Extract machinings from OffsetMachining objects
        machinings = [om.machining for om in offset_machinings]

        # Create merged job
        merged_job = HOPSJob(vars=vars_def, finished_part=finished_part, park_mode=park_mode, machinings=machinings, header=header)

        # Write to file
        merged_job.to_hop_file(output_path)

        # Print summary by tool type
        print("\n📋 Machining summary by tool:")
        from collections import defaultdict

        tool_counts = defaultdict(int)
        for om in offset_machinings:
            tool_key = f"{om.machining.tool.tool_type.name} (pos {om.machining.tool.position})"
            tool_counts[tool_key] += 1

        for tool_name, count in sorted(tool_counts.items()):
            print(f"  {tool_name}: {count} machining blocks")

    @staticmethod
    def parse_filename(filename: str) -> Optional[BeamFileInfo]:
        """Parse filename in format: S<stock_idx>_R<stock_id>_<beam_key>(<flip>).hop

        Args:
            filename: Filename to parse (with or without path)

        Returns:
            BeamFileInfo object or None if filename doesn't match pattern

        Examples:
            S0_R01_117.hop -> stock_idx=0, stock_id="01", beam_key=117, flip=0
            S0_R01_117(1).hop -> stock_idx=0, stock_id="01", beam_key=117, flip=1
            S1_44.hop -> stock_idx=1, stock_id="", beam_key=44, flip=0
            S1_44(1).hop -> stock_idx=1, stock_id="", beam_key=44, flip=1
        """
        base_name = os.path.basename(filename)

        # Pattern: S<stock_idx>_R<stock_id>_<beam_key>(<flip>).hop
        # or: S<stock_idx>_<beam_key>(<flip>).hop (without R part)
        pattern = r"S(\d+)_(?:R(\w+)_)?(\d+)(?:\((\d+)\))?\.hop"
        match = re.match(pattern, base_name)

        if not match:
            return None

        stock_idx = int(match.group(1))
        stock_id = match.group(2) or ""  # May be None if no R part
        beam_key = int(match.group(3))
        flip = int(match.group(4)) if match.group(4) else 0

        return BeamFileInfo(filepath=filename, filename=base_name, stock_idx=stock_idx, stock_id=stock_id, beam_key=beam_key, flip=flip)

    @staticmethod
    def group_files_by_stock(hop_directory: str) -> Dict[Tuple[int, int], List[BeamFileInfo]]:
        """Group HOP files by (stock_idx, flip).

        Args:
            hop_directory: Directory containing .hop files

        Returns:
            Dictionary mapping (stock_idx, flip) -> list of BeamFileInfo objects
        """
        all_files = glob.glob(os.path.join(hop_directory, "*.hop"))
        groups = defaultdict(list)

        for filepath in all_files:
            info = StockHopsMerger.parse_filename(filepath)
            if info:
                key = (info.stock_idx, info.flip)
                groups[key].append(info)

        return dict(groups)

    @staticmethod
    def merge_by_filename_pattern(nesting_json_path: str, hop_directory: str, output_directory: Optional[str] = None):
        """Merge HOP files based on filename pattern (S<idx>_R<id>_<beam>(<flip>).hop).

        This method:
        1. Parses all filenames to extract stock index, stock ID, beam key, and flip
        2. Groups files by (stock_idx, flip)
        3. For each group, merges beams into a stock HOP file
        4. Outputs files named: S<idx>_R<id>.hop and S<idx>_R<id>(1).hop

        Args:
            nesting_json_path: Path to nesting JSON file
            hop_directory: Directory containing input .hop files
            output_directory: Output directory (defaults to same as hop_directory)
        """
        if output_directory is None:
            output_directory = hop_directory

        # Load nesting data
        with open(nesting_json_path, "r", encoding="utf-8") as f:
            nesting_data = json.load(f)
        stocks = nesting_data["data"]["stocks"]

        # Group files
        file_groups = StockHopsMerger.group_files_by_stock(hop_directory)

        print(f"\n📂 Found {len(file_groups)} stock groups to merge:")
        for (stock_idx, flip), files in sorted(file_groups.items()):
            flip_str = f"(1)" if flip == 1 else ""
            beam_keys = sorted([f.beam_key for f in files])
            print(f"  Stock {stock_idx}{flip_str}: {len(files)} beams - keys: {beam_keys}")

        # Print nesting data beam keys for debugging
        print(f"\n📊 Nesting data contains {len(stocks)} stocks:")
        for idx, stock in enumerate(stocks[:5]):  # Show first 5
            beam_keys = sorted([elem["key"] for elem in stock["data"]["element_data"].values()])
            print(f"  Stock {idx}: {len(beam_keys)} beams - keys: {beam_keys}")

        # Process each group
        for (stock_idx, flip), beam_files in sorted(file_groups.items()):
            # Get stock data
            if stock_idx >= len(stocks):
                print(f"\n⚠ Warning: Stock index {stock_idx} not found in nesting data (only {len(stocks)} stocks available)")
                continue

            stock_data = stocks[stock_idx]["data"]
            stock_length = stock_data["length"]
            stock_width, stock_height = stock_data["cross_section"]

            # Extract stock ID from first file
            stock_id = beam_files[0].stock_id
            flip_suffix = "(1)" if flip == 1 else ""
            output_filename = f"S{stock_idx}_R{stock_id}{flip_suffix}.hop" if stock_id else f"S{stock_idx}{flip_suffix}.hop"
            output_path = os.path.join(output_directory, output_filename)

            print(f"\n{'=' * 70}")
            print(f"Processing Stock {stock_idx}{flip_suffix} (R{stock_id})")
            print(f"{'=' * 70}")
            print(f"Stock dimensions: {stock_length:.1f} x {stock_width:.1f} x {stock_height:.1f} mm")
            print(f"Beams to merge: {len(beam_files)}")

            # Load and offset each beam's machinings
            all_offset_machinings = []

            for beam_file in beam_files:
                beam_key = beam_file.beam_key

                # Find beam in nesting data
                beam_offset = None
                beam_length = None
                for element_data in stock_data["element_data"].values():
                    if element_data["key"] == beam_key:
                        beam_offset = element_data["frame"]["data"]["point"][0]
                        beam_length = element_data["length"]
                        break

                if beam_offset is None:
                    print(f"  ⚠ Warning: Beam {beam_key} not found in stock {stock_idx} nesting data, skipping")
                    continue

                # Load HOP file
                try:
                    hop_job = HOPSJob.from_hop_file(beam_file.filepath)
                    print(f"  ✓ Loaded {beam_file.filename}: Beam {beam_key} at offset {beam_offset:.2f}mm ({len(hop_job.machinings)} machining blocks)")

                    # Offset all machinings
                    for machining in hop_job.machinings:
                        # Use static method to offset
                        offset_machining = StockHopsMerger._offset_machining(machining, beam_offset, beam_key)
                        all_offset_machinings.append(offset_machining)

                except Exception as e:
                    print(f"  ✗ Error loading {beam_file.filename}: {e}")
                    continue

            if not all_offset_machinings:
                print(f"  ⚠ No machinings to merge for stock {stock_idx}{flip_suffix}")
                continue

            # Create a map from beam_key to its x_offset from the nesting data
            beam_x_offset_map = {element_data["key"]: element_data["frame"]["data"]["point"][0] for element_data in stock_data["element_data"].values()}

            # Sort by tool type then position
            # For milling and drilling, we preserve the beam order based on their X-position in the nesting data.
            # For sawing, we sort by X-position (min_x) to optimize cuts.
            all_offset_machinings.sort(
                key=lambda om: (
                    om.machining.tool.tool_type.value,
                    om.machining.tool.position,
                    beam_x_offset_map.get(om.beam_key) if isinstance(om.machining.operations[0], (MillingOperation, DrillingOperation)) else om.min_x,
                )
            )

            # Create header
            header = [
                ";MERGED STOCK FILE",
                ";Generated by merge_stock_hops.py",
                ";",
                f";Stock {stock_idx}{flip_suffix} (R{stock_id})" if stock_id else f";Stock {stock_idx}{flip_suffix}",
                f";Dimensions: {stock_length:.1f} x {stock_width:.1f} x {stock_height:.1f} mm",
                f";Beams merged: {len(beam_files)}",
                f";Total machining blocks: {len(all_offset_machinings)}",
                ";",
                ";Merged beam files:",
            ]

            for beam_file in sorted(beam_files, key=lambda bf: bf.beam_key):
                header.append(f";  - {beam_file.filename}")

            header.append(";")
            header.append(";MASCHINE=HOLZHER")

            # Create merged job
            vars_def = VarsDefinition(dx=stock_length, dy=stock_width, dz=stock_height)
            finished_part = FinishedPart(comment=f"STOCK {stock_idx}{flip_suffix}")
            park_mode = ParkMode(mode=4, pos_x=0, pos_y=0)
            machinings = [om.machining for om in all_offset_machinings]

            merged_job = HOPSJob(vars=vars_def, finished_part=finished_part, park_mode=park_mode, machinings=machinings, header=header)

            # Write output
            merged_job.to_hop_file(output_path)
            print(f"  ✅ Merged file written: {output_path}")

            # Print summary
            from collections import defaultdict as dd

            tool_counts = dd(int)
            for om in all_offset_machinings:
                tool_key = f"{om.machining.tool.tool_type.name} (pos {om.machining.tool.position})"
                tool_counts[tool_key] += 1

            print(f"\n  📋 Machining summary by tool:")
            for tool_name, count in sorted(tool_counts.items()):
                print(f"    {tool_name}: {count} blocks")

        print(f"\n{'=' * 70}")
        print(f"✅ All stocks merged successfully!")
        print(f"{'=' * 70}")
