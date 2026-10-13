from __future__ import annotations

import math
from typing import TYPE_CHECKING
from typing import List
from typing import Optional

from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Transformation
from compas.geometry import Vector

from ..machining_commands import VectorMillingOperation
from ..machining_commands import VectorMove
from ..tool_library import MachiningTool

if TYPE_CHECKING:
    from ..hop_job import HOPSJob
    from ..hop_job import HOPSMachining


_TILT_TOLERANCE = 1e-6  # degrees


class FrameToolpathStrategies:
    """Convert tool frames (e.g. from Grasshopper) into vector (5-axis) milling.

    Each frame gives one tool position: its origin is the tool tip and its Z axis the
    tool direction. The frame's X/Y axes are ignored, because HOPS controls only the
    tool axis (two angles), not the spindle's rotation around it.

    Every pass becomes one ``VSP / VG01... / VEP`` block with the tool orientation set
    per point, so all five axes interpolate continuously. HOPS links consecutive passes
    itself; a pass should start and end with the tool clear of the material.
    """

    @staticmethod
    def vector_milling(
        passes: List[List[Frame]],
        tool: MachiningTool,
        part_frame: Optional[Frame] = None,
        feedrates=None,
        z_to_holder: bool = True,
        max_tilt: float = 90.0,
        comment: str = "Vector milling",
    ) -> "List[HOPSMachining]":
        """Create one HOPSMachining with one vector milling operation per pass.

        Parameters
        ----------
        passes : list of list of :class:`compas.geometry.Frame`
            Tool frames per continuous pass, in machining order.
        tool : :class:`MachiningTool`
            Tool used for all passes.
        part_frame : :class:`compas.geometry.Frame`, optional
            Origin at the X=0/Y=0/Z=0 corner of the finished part (bottom face), X along DX,
            Y along DY, Z up on the machine table. Frames are converted into this system.
            Defaults to the world XY frame (frames already in part coordinates).
        feedrates : None, float, str or list, optional
            ``None`` uses the tool-manager feed ``_V``. A single value applies to every move.
            A list gives one entry per pass; each entry is a single value or a list with
            one feed per frame.
        z_to_holder : bool, optional
            True (default) if the frame Z axis points from the tool tip to the holder,
            False if it points into the material.
        max_tilt : float, optional
            Largest allowed tilt from vertical in degrees. 90 = horizontal tool.
        comment : str, optional
            Comment written above the tool call.

        Returns
        -------
        List[HOPSMachining]
            A single HOPSMachining (tool, no work plane, one operation per pass).
        """
        from ..hop_job import HOPSMachining

        if not passes:
            raise ValueError("No passes given.")
        pass_feeds = FrameToolpathStrategies._feeds_per_pass(feedrates, len(passes))

        operations = []
        for index, (frames, feeds) in enumerate(zip(passes, pass_feeds)):
            points, vectors = FrameToolpathStrategies._to_part(frames, part_frame, z_to_holder)
            for point_index, vector in enumerate(vectors):
                tilt = VectorMove.angles_from_vector(vector)[1]
                if tilt > max_tilt + _TILT_TOLERANCE:
                    raise ValueError(f"Pass {index}, frame {point_index}: tilt {tilt:.3f} deg exceeds max_tilt {max_tilt} deg.")
            operations.append(VectorMillingOperation.from_points(points, vectors, feeds))

        return [
            HOPSMachining(
                tool=tool,
                work_plane=None,
                operations=operations,
                comments=["; ---------------------------------", f";{comment}", "; ---------------------------------"],
            )
        ]

    @staticmethod
    def limit_tilt(
        passes: List[List[Frame]],
        max_tilt: float,
        part_frame: Optional[Frame] = None,
        z_to_holder: bool = True,
    ) -> tuple:
        """Turn frames whose tool axis tilts more than ``max_tilt`` back to exactly ``max_tilt``.

        The tilt is measured from the part's Z axis (the machine vertical). A frame that
        tilts too far is rotated about its origin (the tool tip), in the plane of its tool
        axis and the part Z axis, so the tool tip and the rotation angle DW stay the same.
        A tool pointing straight down is turned about its own X axis.

        Parameters
        ----------
        passes : list of list of :class:`compas.geometry.Frame`
            Tool frames per pass, as given to :meth:`vector_milling`.
        max_tilt : float
            Largest allowed tilt from vertical in degrees (0..180).
        part_frame : :class:`compas.geometry.Frame`, optional
            Part frame as in :meth:`vector_milling`; defaults to the world XY frame.
        z_to_holder : bool, optional
            True if the frame Z axis points from the tool tip to the holder.

        Returns
        -------
        tuple
            ``(passes, changes)``: the passes with limited frames (unchanged frames are the
            same objects), and one ``(pass_index, frame_index, original_tilt)`` per change.
        """
        if not 0.0 <= max_tilt <= 180.0:
            raise ValueError(f"max_tilt {max_tilt} must be between 0 and 180 deg.")
        up = part_frame.zaxis if part_frame is not None else Vector(0, 0, 1)
        limited, changes = [], []
        for pass_index, frames in enumerate(passes):
            new_frames = []
            for frame_index, frame in enumerate(frames):
                axis = frame.zaxis if z_to_holder else -frame.zaxis
                tilt = math.degrees(axis.angle(up))
                if tilt > max_tilt + _TILT_TOLERANCE:
                    hinge = axis.cross(up)
                    if hinge.length < 1e-9:  # straight down: any axis perpendicular to the tool works
                        hinge = frame.xaxis
                    frame = frame.transformed(Rotation.from_axis_and_angle(hinge, math.radians(tilt - max_tilt), point=frame.point))
                    changes.append((pass_index, frame_index, tilt))
                new_frames.append(frame)
            limited.append(new_frames)
        return limited, changes

    @staticmethod
    def check(job: "HOPSJob", passes: List[List[Frame]], part_frame: Optional[Frame] = None, z_to_holder: bool = True) -> dict:
        """Read the job's HOP text back and compare every VG01 with the input frames.

        Returns a report with the largest position error (mm), the largest tool-axis
        error (degrees), the tilt range, the largest rotation (DW) step between two
        moves, and a list of warnings to look at in the HOPS simulation.
        """
        operations = FrameToolpathStrategies._vector_operations(job)
        report = {
            "passes": len(operations),
            "points": 0,
            "max_position_error": 0.0,
            "max_axis_error_deg": 0.0,
            "tilt_range_deg": None,
            "max_rotation_step_deg": 0.0,
            "warnings": [],
        }
        if len(operations) != len(passes):
            report["warnings"].append(f"File has {len(operations)} vector passes, input has {len(passes)}.")
            return report

        tilts = []
        for index, (operation, frames) in enumerate(zip(operations, passes)):
            points, vectors = FrameToolpathStrategies._to_part(frames, part_frame, z_to_holder)
            if len(operation.moves) != len(points):
                report["warnings"].append(f"Pass {index}: {len(operation.moves)} moves for {len(points)} frames.")
                continue
            previous = None
            for move, point, vector in zip(operation.moves, points, vectors):
                report["points"] += 1
                error = math.dist((move.x, move.y, move.z), point)
                report["max_position_error"] = max(report["max_position_error"], error)
                written = move.tool_vector
                length = math.sqrt(sum(c * c for c in vector))
                dot = sum(a * b / length for a, b in zip(written, vector))
                report["max_axis_error_deg"] = max(report["max_axis_error_deg"], math.degrees(math.acos(max(-1.0, min(1.0, dot)))))
                tilts.append(move.tilt_angle)
                if previous is not None and move.tilt_angle > 0 and previous.tilt_angle > 0:
                    step = abs(move.rotation_angle - previous.rotation_angle)
                    report["max_rotation_step_deg"] = max(report["max_rotation_step_deg"], step)
                    if step > 180.0:
                        report["warnings"].append(
                            f"Pass {index}: rotation DW jumps {previous.rotation_angle:.3f} -> {move.rotation_angle:.3f} (crosses 0/360); "
                            "check in the simulation that the head does not turn the long way round."
                        )
                previous = move

        if tilts:
            report["tilt_range_deg"] = (min(tilts), max(tilts))
            if max(tilts) > 90.0 + 1e-6:
                report["warnings"].append(f"Tilt up to {max(tilts):.3f} deg: tool points below horizontal (undercut).")
        return report

    @staticmethod
    def read_back(job: "HOPSJob", part_frame: Optional[Frame] = None) -> List[List[tuple]]:
        """Return what the job's HOP text says, per vector pass, in world coordinates.

        Each pass is a list of ``(point, vector)`` tuples: the tool tip and the unit tool
        vector (tip -> holder) of every VG01, computed back from the written DW/KW angles.
        Use it to preview the file (e.g. as tool-axis lines in Rhino) instead of the input.
        """
        to_world = Transformation.from_frame(part_frame) if part_frame is not None else None
        passes = []
        for operation in FrameToolpathStrategies._vector_operations(job):
            moves = []
            for move in operation.moves:
                point = Point(move.x, move.y, move.z)
                vector = Vector(*move.tool_vector)
                if to_world is not None:
                    point = point.transformed(to_world)
                    vector = vector.transformed(to_world)
                moves.append(((point.x, point.y, point.z), (vector.x, vector.y, vector.z)))
            passes.append(moves)
        return passes

    @staticmethod
    def _vector_operations(job: "HOPSJob") -> List[VectorMillingOperation]:
        from ..hop_job import HOPSJob

        parsed = HOPSJob.from_hop_string(str(job))
        return [op for m in parsed.machinings for op in m.operations if isinstance(op, VectorMillingOperation)]

    @staticmethod
    def _to_part(frames: List[Frame], part_frame: Optional[Frame], z_to_holder: bool):
        to_part = Transformation.from_change_of_basis(Frame.worldXY(), part_frame) if part_frame is not None else None
        points, vectors = [], []
        for frame in frames:
            if to_part is not None:
                frame = frame.transformed(to_part)
            axis = frame.zaxis if z_to_holder else -frame.zaxis
            points.append((frame.point.x, frame.point.y, frame.point.z))
            vectors.append((axis.x, axis.y, axis.z))
        return points, vectors

    @staticmethod
    def _feeds_per_pass(feedrates, count: int) -> list:
        if feedrates is None or isinstance(feedrates, (int, float, str)):
            return [feedrates] * count
        feedrates = list(feedrates)
        if len(feedrates) != count:
            raise ValueError(f"Got {count} passes but {len(feedrates)} feedrate entries.")
        return feedrates
