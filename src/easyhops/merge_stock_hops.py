"""
Stock-Level HOPS Merger for Nested Beams

This module provides functionality for merging multiple .hop files (representing individual beams)
into a single .hop file for a timber stock, based on nesting information from a JSON file.

The merger handles:
- Reading nesting data to determine beam positions within stock
- Offsetting X-coordinates of machining operations based on nesting positions
- Grouping and sorting operations by tool type (not by piece)
- Generating a merged HOPS file for the entire stock

Classes:
    StockHopsMerger: Main class for merging multiple beams into a stock

Usage Example:
    ```python
    from easyhops.merge_stock_hops import StockHopsMerger

    # Initialize merger with nesting JSON and hop files directory
    merger = StockHopsMerger(nesting_json_path="path/to/nesting.json", hop_directory="path/to/hop/files/")

    # Merge and write output
    merger.merge("output_merged.hop")
    ```

Coordinate System Notes:
    - EBENEF(x, y, z, theta, beta, ...): X-coordinate is offset based on nesting position
    - EBENE0(): Standard top view, subsequent operation coordinates are offset
    - SAEGEN(x1, y1, z1, x2, y2, z2, ...): Both x1 and x2 are offset
    - SP/G01/EP: X-coordinates are offset when following EBENE or EBENEF
    - Operations are grouped by tool+workplane, maintaining the operations list structure
"""

import glob
import json
import os
import re
from dataclasses import dataclass
from typing import List
from typing import Tuple

from .hop_core import FinishedPart
from .hop_core import ParkMode
from .hop_core import VarsDefinition
from .hop_job import HOPSJob
from .hop_job import HOPSMachining
from .machining_commands import G01
from .machining_commands import DrillingOperation
from .machining_commands import MillingOperation
from .machining_commands import SawingOperation
from .work_planes import FreePlane


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

    def _offset_free_plane(self, plane: FreePlane, x_offset: float) -> FreePlane:
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

    def _offset_milling_operation(self, operation: MillingOperation, x_offset: float) -> MillingOperation:
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

        # Offset all G01 moves
        new_moves = [
            G01(
                x=move.x + x_offset,
                y=move.y,
                z=move.z,
                corner_radius=move.corner_radius,
                easy_snap_xy=move.easy_snap_xy,
                easy_snap_z=move.easy_snap_z,
                feedrate=move.feedrate,
            )
            for move in operation.moves
        ]

        # End point doesn't have coordinates, just copy
        new_ep = operation.end_point

        return MillingOperation(start_point=new_sp, moves=new_moves, end_point=new_ep)

    def _offset_sawing_operation(self, operation: SawingOperation, x_offset: float) -> SawingOperation:
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

    def _offset_drilling_operation(self, operation: DrillingOperation, x_offset: float) -> DrillingOperation:
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

    def _offset_machining(self, machining: HOPSMachining, x_offset: float, beam_key: int) -> OffsetMachining:
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
            new_work_plane = self._offset_free_plane(machining.work_plane, x_offset)
        else:
            # Standard WorkPlane (EBENE0-4) doesn't need offsetting
            new_work_plane = machining.work_plane

        # Offset all operations in the list
        new_operations = []
        for operation in machining.operations:
            if isinstance(operation, MillingOperation):
                new_operations.append(self._offset_milling_operation(operation, x_offset))
            elif isinstance(operation, SawingOperation):
                new_operations.append(self._offset_sawing_operation(operation, x_offset))
            elif isinstance(operation, DrillingOperation):
                new_operations.append(self._offset_drilling_operation(operation, x_offset))
            else:
                # Unknown operation type, keep original
                new_operations.append(operation)

        # Create new machining with offset coordinates
        new_machining = HOPSMachining(tool=machining.tool, work_plane=new_work_plane, operations=new_operations)

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
                offset_machining = self._offset_machining(machining, x_offset, beam_key)
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
        finished_part = FinishedPart(dx=stock_length, dy=stock_width, dz=stock_height, rotation_flag=0, offset_x=0, offset_y=0, offset_z=0, comment="MERGED STOCK")
        park_mode = ParkMode(mode=11, pos_x=0, pos_y=0)

        # Header comments
        header = [
            ";MERGED STOCK FILE",
            ";Generated by merge_stock_hops.py",
            f";Stock: {stock_length:.1f} x {stock_width:.1f} x {stock_height:.1f} mm",
            f";Beams merged: {len(self.hop_jobs)}",
            f";Total machining blocks: {len(offset_machinings)}",
            ";MASCHINE=HOLZHER",
        ]

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
