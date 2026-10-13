"""vector_milling_calibration.py
================================
Write a small calibration program for vector (5-axis) milling with VSP / VG01 / VEP.

Open the result in HOPS on the machine PC, simulate it, and compare with the
expectations written as comments above every pass. Each pass checks one assumption
of FrameToolpathStrategies (origin, axis directions, tilt, rotation, continuous
interpolation, tool-tip reference).

Two files are written:

- ``vector_calibration.hop``      passes cut 2 mm into a 500 x 200 x 100 blank
- ``vector_calibration_air.hop``  same program moved 30 mm back along the tool axis,
                                  for a dry run on the machine without touching the part

Usage
-----
    python examples/vector_milling_calibration.py
    python examples/vector_milling_calibration.py --tool 405 --rpm 18000 --output-dir out/
"""

import argparse
import math
import os

from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Vector

from easyhops.hop_core import FinishedPart
from easyhops.hop_core import ParkPosition
from easyhops.hop_core import VarsDefinition
from easyhops.hop_core import hop_header
from easyhops.hop_job import HOPSJob
from easyhops.machining_commands import VectorMove
from easyhops.strategies.frames import FrameToolpathStrategies
from easyhops.tool_library import MachiningTool

DX, DY, DZ = 500.0, 200.0, 100.0
DEPTH = 2.0  # cutting depth along the tool axis
CLEARANCE = 15.0  # approach / exit distance along the tool axis
FEED_APPROACH, FEED_ENTRY, FEED_CUT = 5000, 1000, 2000


def tool_frame(point, tool_vector):
    """Frame with origin = tool tip and Z = tool vector (tip -> holder). X/Y are irrelevant."""
    z = Vector(*tool_vector)
    z.unitize()
    helper = Vector(1, 0, 0) if abs(z.x) < 0.9 else Vector(0, 1, 0)
    y = z.cross(helper)
    return Frame(Point(*point), y.cross(z), y)


def cut(points, vectors, retract=0.0):
    """Frames and feeds for one pass: approach in air -> cut points -> exit in air.

    ``retract`` moves the whole pass back along the tool axis (dry run).
    """
    frames, feeds = [], []
    unit = []
    for v in vectors:
        length = math.sqrt(sum(c * c for c in v))
        unit.append([c / length for c in v])

    def offset(p, n, d):
        return [p[i] + n[i] * (d + retract) for i in range(3)]

    frames.append(tool_frame(offset(points[0], unit[0], CLEARANCE), unit[0]))
    feeds.append(FEED_APPROACH)
    for p, n in zip(points, unit):
        frames.append(tool_frame(offset(p, n, 0.0), n))
        feeds.append(FEED_ENTRY if len(feeds) == 1 else FEED_CUT)
    frames.append(tool_frame(offset(points[-1], unit[-1], CLEARANCE), unit[-1]))
    feeds.append(FEED_APPROACH)
    return frames, feeds


def calibration_passes(retract=0.0):
    """Return a list of (comment lines, frames, feeds)."""
    top = DZ - DEPTH
    passes = []

    # 1. Vertical tool on the top face: checks the part origin and the Z reference.
    pts = [(x, 50.0, top) for x in range(40, 141, 20)]
    passes.append(
        (
            ["Pass 1: vertical tool (DW 0, KW 0) on the TOP face",
             "Expect: groove along X from X=40 to X=140 at Y=50, 2 mm deep, near the X=0/Y=0 corner"],
            *cut(pts, [(0, 0, 1)] * len(pts), retract),
        )
    )

    # 2. Constant 30 deg tilt, holder leaning towards -Y: checks the tilt direction.
    n = (0.0, -math.sin(math.radians(30)), math.cos(math.radians(30)))
    pts = [(x, 150.0, top) for x in range(40, 141, 20)]
    passes.append(
        (
            ["Pass 2: constant tilt KW 30, DW 0 on the TOP face",
             "Expect: groove along X at Y=150; spindle leans towards Y=0 (the -Y face)"],
            *cut(pts, [n] * len(pts), retract),
        )
    )

    # 3. Tilt sweep 0 -> 45 deg along the path: checks continuous KW interpolation.
    pts, vectors = [], []
    for i, t in enumerate(range(0, 46, 5)):
        pts.append((200.0 + 10 * i, 100.0, top))
        vectors.append((0.0, -math.sin(math.radians(t)), math.cos(math.radians(t))))
    passes.append(
        (
            ["Pass 3: tilt sweep KW 0 -> 45 (DW 0) on the TOP face",
             "Expect: one continuous groove X=200..290 at Y=100, tool tilting smoothly towards -Y, no stop"],
            *cut(pts, vectors, retract),
        )
    )

    # 4. RTCP check in the air: tip stays at one point while the axis moves.
    tip = (400.0, 100.0, DZ + 30.0)
    vectors = [(0.0, 0.0, 1.0)]
    vectors += [(0.0, -math.sin(math.radians(t)), math.cos(math.radians(t))) for t in range(5, 31, 5)]
    vectors += [VectorMove.vector_from_angles(dw, 30.0) for dw in range(15, 181, 15)]
    vectors += [VectorMove.vector_from_angles(dw, 30.0) for dw in range(165, -1, -15)]
    frames = [tool_frame([tip[i] + vectors[0][i] * retract for i in range(3)], v) for v in vectors]
    passes.append(
        (
            ["Pass 4: tool-tip test IN THE AIR at X=400 Y=100 Z=DZ+30",
             "Expect: tip stays on one point while KW goes 0->30 and DW 0->180->0 (no cutting)"],
            frames,
            [FEED_CUT] * len(frames),
        )
    )

    # 5. Horizontal tool on the front (-Y) face: checks DW 0 / KW 90 and Y=0 face position.
    pts = [(x, DEPTH, 50.0) for x in range(40, 141, 20)]
    passes.append(
        (
            ["Pass 5: horizontal tool (DW 0, KW 90) on the FRONT face Y=0",
             "Expect: groove along X at Z=50 on the Y=0 face, spindle outside the part on the -Y side"],
            *cut(pts, [(0, -1, 0)] * len(pts), retract),
        )
    )

    # 6. Horizontal tool turning around Z (flank-style, like the Grasshopper toolpath).
    pts, vectors = [], []
    for i, a in enumerate(range(10, 31, 4)):
        pts.append((200.0 + 15 * i, DEPTH, 50.0))
        vectors.append((math.sin(math.radians(a)), -math.cos(math.radians(a)), 0.0))
    passes.append(
        (
            ["Pass 6: horizontal tool on the FRONT face, DW turning 10 -> 30 (KW 90)",
             "Expect: groove along X at Z=50, spindle swinging continuously towards +X"],
            *cut(pts, vectors, retract),
        )
    )

    # 7. Mirror of pass 6 on the back (+Y) face.
    pts, vectors = [], []
    for i, a in enumerate(range(10, 31, 4)):
        pts.append((200.0 + 15 * i, DY - DEPTH, 50.0))
        vectors.append((math.sin(math.radians(a)), math.cos(math.radians(a)), 0.0))
    passes.append(
        (
            ["Pass 7: horizontal tool on the BACK face Y=DY, DW turning 170 -> 150 (KW 90)",
             "Expect: mirror of pass 6 on the opposite face"],
            *cut(pts, vectors, retract),
        )
    )
    return passes


def build_job(name, tool_no, rpm, retract):
    tool = MachiningTool(position=tool_no, motor_speed=rpm)
    machinings = []
    for comments, frames, feeds in calibration_passes(retract):
        machining = FrameToolpathStrategies.vector_milling([frames], tool, feedrates=[feeds], comment=comments[0])[0]
        machining.comments += [f"; {line}" for line in comments[1:]]
        machinings.append(machining)
    header = hop_header(name, info="easyhops vector milling calibration")
    job = HOPSJob(VarsDefinition(dx=DX, dy=DY, dz=DZ), FinishedPart(), ParkPosition(), machinings, header=header)
    report = FrameToolpathStrategies.check(job, [frames for _, frames, _ in calibration_passes(retract)])
    return job, report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tool", type=int, default=404, help="tool position in the magazine (default 404, SRSL D12)")
    parser.add_argument("--rpm", type=float, default=None, help="spindle speed; default uses the tool manager value")
    parser.add_argument("--output-dir", default=os.path.join(os.path.dirname(__file__), "..", "data", "calibration"))
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    for name, retract in (("vector_calibration", 0.0), ("vector_calibration_air", 30.0)):
        job, report = build_job(name, args.tool, args.rpm, retract)
        path = os.path.join(args.output_dir, name + ".hop")
        job.to_hop_file(path)
        print(f"{path}: {report['passes']} passes, {report['points']} points, "
              f"max position error {report['max_position_error']:.4f} mm, max axis error {report['max_axis_error_deg']:.4f} deg")
        for warning in report["warnings"]:
            print("  WARNING:", warning)


if __name__ == "__main__":
    main()
