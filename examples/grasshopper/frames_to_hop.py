#! python3
# venv: easyhops
# r: compas==2.15.1
"""Grasshopper: tool frames -> HOPS vector milling program (.hop).

Paste into a Rhino 8 "Script" component (Python 3) and create these parameters
(right-click a parameter to set its access and type hint):

Inputs
------
Frames      Tree Access, Plane   One branch per pass, in machining order: approach point in the
                                 air, cutting frames, exit point in the air.
                                 Plane origin = tool tip, plane Z = tool axis from tip to holder.
                                 Plane X/Y are ignored.
Feeds       Tree Access, float   Optional, mm/min. Per branch either one value (whole pass) or one
                                 value per frame. A single value applies to all passes.
                                 Empty: tool-manager feed (_V).
PartPlane   Item, Plane          Origin at the X=0/Y=0/Z=0 corner of the finished part (bottom face),
                                 X along DX, Y along DY, Z up on the machine table. Empty: World XY.
DX, DY, DZ  Item, float          Finished part size in mm.
ToolNo      Item, int            Tool position in the magazine, e.g. 404.
RPM         Item, float          Optional spindle speed. Empty: tool-manager value.
ZToHolder   Item, bool           Optional, default True. False if your plane Z points into the material.
MaxTilt     Item, float          Optional, default 90 (horizontal tool). A plane that tilts more is turned
                                 about its origin, towards PartPlane Z, to exactly MaxTilt, with a warning
                                 naming the branch and frame (first 10 on the component, all in Report).
Name        Item, str            Program name, also the file name. Default "toolpath".
Folder      Item, str            Output folder.
Write       Item, bool           Connect a Button: writes <Folder>/<Name>.hop.

Outputs
-------
Hop         The .hop program text.
Report      Read-back check of the written program against the input frames.
Stock       Box of the finished part: check that it sits where the part is on the machine.
ToolAxes    Tool-axis lines per pass, computed back from the written program.
TipPaths    Tool-tip polylines per pass, computed back from the written program.
FilePath    Path of the written file (after Write).

Setup: set EASYHOPS_SRC below to the src folder of your easyhops clone, see examples/grasshopper/README.md.
"""

import os
import sys

EASYHOPS_SRC = os.path.join(os.path.expanduser("~"), "Documents", "GitHub", "easyhops", "src")

# Use the easyhops code in your clone, re-imported on every run so a git pull or a fix
# takes effect with F5 in Grasshopper, without restarting Rhino.
if EASYHOPS_SRC not in sys.path:
    sys.path.insert(0, EASYHOPS_SRC)
for module_name in [m for m in sys.modules if m == "easyhops" or m.startswith("easyhops.")]:
    del sys.modules[module_name]

import Grasshopper  # noqa: E402
import Rhino.Geometry as rg  # noqa: E402
from compas.geometry import Frame  # noqa: E402
from compas.geometry import Point  # noqa: E402
from compas.geometry import Vector  # noqa: E402
from Grasshopper import DataTree  # noqa: E402
from Grasshopper.Kernel.Data import GH_Path  # noqa: E402

from easyhops.hop_core import FinishedPart  # noqa: E402
from easyhops.hop_core import ParkPosition  # noqa: E402
from easyhops.hop_core import VarsDefinition  # noqa: E402
from easyhops.hop_core import hop_header  # noqa: E402
from easyhops.hop_job import HOPSJob  # noqa: E402
from easyhops.strategies.frames import FrameToolpathStrategies  # noqa: E402
from easyhops.tool_library import MachiningTool  # noqa: E402

AXIS_LENGTH = 60.0  # length of the preview tool-axis lines in mm
MAX_MESSAGES = 10  # warnings shown on the component; Report lists all of them


def message(text, level="Warning"):
    ghenv.Component.AddRuntimeMessage(getattr(Grasshopper.Kernel.GH_RuntimeMessageLevel, level), text)  # noqa: F821


def to_frame(plane):
    o, x, y = plane.Origin, plane.XAxis, plane.YAxis
    return Frame(Point(o.X, o.Y, o.Z), Vector(x.X, x.Y, x.Z), Vector(y.X, y.Y, y.Z))


def tree_branches(tree):
    if tree is None:
        return []
    return [(path, [item for item in tree.Branch(path) if item is not None]) for path in tree.Paths]


def feeds_for_passes(feed_tree, frame_branches):
    """One entry per pass: None, a single feed, or a list with one feed per frame."""
    branches = [(path, values) for path, values in tree_branches(feed_tree) if values]
    if not branches:
        return None
    if len(branches) == 1 and len(branches[0][1]) == 1 and len(frame_branches) > 1:
        return float(branches[0][1][0])
    by_path = {str(path): values for path, values in branches}
    feeds = []
    for path, frames in frame_branches:
        values = by_path.get(str(path))
        if values is None:
            raise ValueError(f"Feeds has no branch {path}.")
        if len(values) == 1:
            feeds.append(float(values[0]))
        elif len(values) == len(frames):
            feeds.append([float(v) for v in values])
        else:
            raise ValueError(f"Feeds branch {path} has {len(values)} values for {len(frames)} frames (use 1 or {len(frames)}).")
    return feeds


def lines_tree(passes, length):
    tree = DataTree[object]()
    for index, moves in enumerate(passes):
        path = GH_Path(index)
        for point, vector in moves:
            start = rg.Point3d(*point)
            tree.Add(rg.Line(start, start + rg.Vector3d(*vector) * length), path)
    return tree


def paths_tree(passes):
    tree = DataTree[object]()
    for index, moves in enumerate(passes):
        tree.Add(rg.PolylineCurve([rg.Point3d(*point) for point, _ in moves]), GH_Path(index))
    return tree


def format_report(report):
    lines = [
        f"passes: {report['passes']}, points: {report['points']}",
        f"max position error: {report['max_position_error']:.4f} mm",
        f"max tool-axis error: {report['max_axis_error_deg']:.4f} deg",
    ]
    if report["tilt_range_deg"]:
        lines.append("tilt KW: {:.2f} .. {:.2f} deg".format(*report["tilt_range_deg"]))
    lines.append(f"largest rotation DW step: {report['max_rotation_step_deg']:.2f} deg")
    lines += [f"WARNING: {w}" for w in report["warnings"]]
    return "\n".join(lines)


Hop = Report = Stock = ToolAxes = TipPaths = FilePath = None

try:
    frame_branches = [(path, items) for path, items in tree_branches(Frames) if items]  # noqa: F821
    if not frame_branches:
        raise ValueError("Connect Frames (Tree Access, Plane).")
    if None in (DX, DY, DZ):  # noqa: F821
        raise ValueError("Set DX, DY and DZ.")
    if ToolNo is None:  # noqa: F821
        raise ValueError("Set ToolNo.")
    for path, items in frame_branches:
        if len(items) < 2:
            raise ValueError(f"Branch {path} has {len(items)} frame(s); a pass needs at least 2.")

    part_plane = PartPlane if PartPlane is not None else rg.Plane.WorldXY  # noqa: F821
    part_frame = to_frame(part_plane)
    z_to_holder = True if ZToHolder is None else bool(ZToHolder)  # noqa: F821
    max_tilt = 90.0 if MaxTilt is None else float(MaxTilt)  # noqa: F821
    name = Name or "toolpath"  # noqa: F821

    # Frames tilting more than MaxTilt are turned about the tool tip, towards PartPlane Z, to exactly MaxTilt.
    passes = [[to_frame(plane) for plane in items] for _, items in frame_branches]
    passes, tilt_changes = FrameToolpathStrategies.limit_tilt(passes, max_tilt, part_frame=part_frame, z_to_holder=z_to_holder)
    tilt_warnings = [
        f"Branch {frame_branches[p][0]}, frame {f}: tilt {tilt:.3f} deg exceeds MaxTilt {max_tilt} deg, plane turned to {max_tilt} deg."
        for p, f, tilt in tilt_changes
    ]

    machinings = FrameToolpathStrategies.vector_milling(
        passes,
        MachiningTool(position=int(ToolNo), motor_speed=RPM),  # noqa: F821
        part_frame=part_frame,
        feedrates=feeds_for_passes(Feeds, frame_branches),  # noqa: F821
        z_to_holder=z_to_holder,
        max_tilt=max_tilt,
        comment=name,
    )
    job = HOPSJob(
        VarsDefinition(dx=float(DX), dy=float(DY), dz=float(DZ)),  # noqa: F821
        FinishedPart(),
        ParkPosition(),
        machinings,
        header=hop_header(name, info="easyhops vector milling from Grasshopper"),
    )

    Hop = str(job)
    report = FrameToolpathStrategies.check(job, passes, part_frame=part_frame, z_to_holder=z_to_holder)
    report["warnings"] = tilt_warnings + report["warnings"]
    Report = format_report(report)
    for warning in report["warnings"][:MAX_MESSAGES]:
        message(warning)
    if len(report["warnings"]) > MAX_MESSAGES:
        message(f"{len(report['warnings']) - MAX_MESSAGES} more warnings, see Report.")

    written = FrameToolpathStrategies.read_back(job, part_frame=part_frame)
    ToolAxes = lines_tree(written, AXIS_LENGTH)
    TipPaths = paths_tree(written)
    Stock = rg.Box(part_plane, rg.Interval(0, float(DX)), rg.Interval(0, float(DY)), rg.Interval(0, float(DZ)))  # noqa: F821

    if Write:  # noqa: F821
        if not Folder:  # noqa: F821
            raise ValueError("Set Folder before writing.")
        FilePath = os.path.join(Folder, name + ".hop")  # noqa: F821
        job.to_hop_file(FilePath)
        message(f"Written {FilePath}", "Remark")

except Exception as error:  # show every problem on the component instead of failing silently
    message(str(error), "Error")
