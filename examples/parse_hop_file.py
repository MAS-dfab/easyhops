"""Example: Parse a HOP file and print its contents.

This example demonstrates how to:
1. Load a HOP file
2. Access its components (vars, finished part, park mode)
3. Iterate through machining operations
4. Print details about each operation
"""

import os
import sys

# Add src to path so we can import easyhops
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from easyhops.hop_job import HOPSJob
from easyhops.machining_commands import DrillingOperation
from easyhops.machining_commands import MillingOperation
from easyhops.machining_commands import SawingOperation
from easyhops.work_planes import FreePlane
from easyhops.work_planes import WorkPlane

# Path to your HOP file - using absolute path from this file
HOP_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "test.hop")


def main():
    """Parse and print HOP file contents."""

    print("=" * 70)
    print("HOP FILE PARSER EXAMPLE")
    print("=" * 70)

    # Parse the HOP file
    print(f"\nParsing: {HOP_FILE}")
    job = HOPSJob.from_hop_file(HOP_FILE)

    # Print header comments
    print("\n" + "-" * 70)
    print("HEADER COMMENTS")
    print("-" * 70)
    if job.header:
        for line in job.header:
            print(line.rstrip())
    else:
        print("(no header comments)")

    # Print variables
    print("\n" + "-" * 70)
    print("PIECE DIMENSIONS")
    print("-" * 70)
    print(f"DX (Length): {job.vars.dx} mm")
    print(f"DY (Width):  {job.vars.dy} mm")
    print(f"DZ (Height): {job.vars.dz} mm")

    # Print finished part
    print("\n" + "-" * 70)
    print("FINISHED PART")
    print("-" * 70)
    print(f"Dimensions: {job.finished_part.dx} x {job.finished_part.dy} x {job.finished_part.dz}")
    if job.finished_part.comment:
        print(f"Comment: {job.finished_part.comment}")
    print(f"Rotation flag: {job.finished_part.rotation_flag}")
    print(f"Offsets: X={job.finished_part.offset_x}, Y={job.finished_part.offset_y}, Z={job.finished_part.offset_z}")

    # Print park mode
    print("\n" + "-" * 70)
    print("PARK MODE")
    print("-" * 70)
    print(f"Mode: {job.park_mode.mode}")
    print(f"Position: X={job.park_mode.pos_x}, Y={job.park_mode.pos_y}")

    # Print machining operations
    print("\n" + "-" * 70)
    print(f"MACHINING OPERATIONS ({len(job.machinings)} total)")
    print("-" * 70)

    for i, machining in enumerate(job.machinings, 1):
        print(f"\n{'=' * 70}")
        print(f"OPERATION #{i}")
        print(f"{'=' * 70}")

        # Tool information
        print(f"\nTool: {machining.tool.tool_type.value}")
        print(f"  Position: {machining.tool.position}")
        if machining.tool.feedrate:
            print(f"  Feedrate: {machining.tool.feedrate}")
        if machining.tool.motor_speed:
            print(f"  Motor speed: {machining.tool.motor_speed}")
        if machining.tool.name:
            print(f"  Name: {machining.tool.name}")

        # Work plane information
        print(f"\nWork Plane: {type(machining.work_plane).__name__}")
        if isinstance(machining.work_plane, FreePlane):
            print(f"  Origin: ({machining.work_plane.x}, {machining.work_plane.y}, {machining.work_plane.z})")
            print(f"  Rotation angle: {machining.work_plane.rotation_angle}°")
        elif isinstance(machining.work_plane, WorkPlane):
            print(f"  Face: {machining.work_plane.name}")

        # Operation information
        print(f"\nOperations in this machining: {len(machining.operations)}")

        for op_idx, operation in enumerate(machining.operations, 1):
            if len(machining.operations) > 1:
                print(f"\n  --- Sub-operation {op_idx} ---")

            print(f"\nOperation Type: {type(operation).__name__}")

            if isinstance(operation, MillingOperation):
                print(f"  Start Point: ({operation.start_point.x}, {operation.start_point.y}, {operation.start_point.z})")
                print(f"  Number of moves: {len(operation.moves)}")
                print(f"  End Point: lead_out_mode={operation.end_point.lead_out_mode}")

                # Print first few moves
                if operation.moves:
                    print(f"\n  First moves:")
                    for j, move in enumerate(operation.moves[:3], 1):
                        print(f"    {j}. G01 → ({move.x}, {move.y}, {move.z})")
                    if len(operation.moves) > 3:
                        print(f"    ... and {len(operation.moves) - 3} more moves")

            elif isinstance(operation, SawingOperation):
                print(f"  Start: ({operation.sx}, {operation.sy}, {operation.sz})")
                print(f"  End: ({operation.ex}, {operation.ey}, {operation.ez})")
                if operation.tilt_angle:
                    print(f"  Tilt angle: {operation.tilt_angle}°")

            elif isinstance(operation, DrillingOperation):
                print(f"  Position: ({operation.x}, {operation.y}, {operation.z})")
                print(f"  Depth: {operation.depth}")
                if operation.diameter:
                    print(f"  Diameter: {operation.diameter}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    # Count operation types - note: operations is now a list
    milling_count = sum(len([op for op in m.operations if isinstance(op, MillingOperation)]) for m in job.machinings)
    sawing_count = sum(len([op for op in m.operations if isinstance(op, SawingOperation)]) for m in job.machinings)
    drilling_count = sum(len([op for op in m.operations if isinstance(op, DrillingOperation)]) for m in job.machinings)

    total_operations = sum(len(m.operations) for m in job.machinings)

    print(f"Total machining blocks: {len(job.machinings)}")
    print(f"Total operations: {total_operations}")
    print(f"  - Milling: {milling_count}")
    print(f"  - Sawing: {sawing_count}")
    print(f"  - Drilling: {drilling_count}")

    # Count work plane types
    freeplane_count = sum(1 for m in job.machinings if isinstance(m.work_plane, FreePlane))
    workplane_count = sum(1 for m in job.machinings if isinstance(m.work_plane, WorkPlane))

    print(f"\nWork planes:")
    print(f"  - Free planes (EBENEF): {freeplane_count}")
    print(f"  - Standard planes (EBENE): {workplane_count}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
