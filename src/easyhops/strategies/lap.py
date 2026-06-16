from __future__ import annotations

import math
from typing import TYPE_CHECKING
from typing import List
from typing import Optional

from compas.tolerance import TOL

from ..hop_core import EasySnapXY
from ..hop_core import EasySnapZ
from ..hop_core import HopsSystemVars
from ..machining_commands import G01
from ..machining_commands import AngledLine
from ..machining_commands import CompensationMode
from ..machining_commands import EndPoint
from ..machining_commands import LeadInOutMode
from ..machining_commands import MillingOperation
from ..machining_commands import ProcessMode
from ..machining_commands import StartPoint
from ..tool_library import CastorD61
from ..tool_library import MachiningTool
from ..work_planes import FreePlane
from ..work_planes import WorkPlane

if TYPE_CHECKING:
    from compas_timber.fabrication import Lap

    from ..hop_job import HOPSMachining


class LapStrategies:
    @staticmethod
    def milling(
        lap: "Lap",
        machine_ref_side_index: int,
        tool: Optional[MachiningTool] = None,
    ) -> "List[HOPSMachining]":
        """Create a HOPSMachining for a contour milling operation derived from a Lap processing.

        Generates an EBENEF work plane with a single SP/G01/EP pass that mills
        the flat lap surface at the given depth, angle, inclination, and slope.

        The work plane origin is at (start_x, start_y, 0), tilted by ``90 - inclination``
        and rotated by ``180 - angle``.  The StartPoint plunges to the corrected depth
        ``-depth / cos(tilt_angle)`` and the G01 sweeps the full joint width, applying the
        slope as a Z ramp: ``z = -tan(slope) * x``.

        Supports ref_side_index 0 (top face) and 2 (bottom face).

        Parameters
        ----------
        lap : Lap
            The Lap processing containing the geometric information.
        tool : MachiningTool, optional
            Defaults to CastorD61 (WZF503).

        Returns
        -------
        List[HOPSMachining]
            A single HOPSMachining instance.
        """
        from ..hop_job import HOPSMachining

        tool = tool or CastorD61()

        rotation_angle = 180.0 - lap.angle
        tilt_angle = 90.0 - lap.inclination
        sweep_direction = 1

        # If the face is tilted in the opposite direction (negative inclination), flip the rotation by 180 degrees and take the absolute value of the tilt, so that the tool approaches from the correct side of the joint.
        if tilt_angle < 0.0:
            rotation_angle += 180.0
            tilt_angle = abs(tilt_angle)
            sweep_direction = -1

        work_plane = FreePlane(
            x=lap.start_x,
            y=lap.start_y,
            z=0.0,
            tilt_angle=tilt_angle,
            rotation_angle=rotation_angle,
            easy_snap_xy=EasySnapXY.FRONT_LEFT,
            easy_snap_z=EasySnapZ.RELATIVE,
            offset_z=0.0,
        )

        # Depth corrected for tilt: plunge further when the face is angled
        sp_z = round(-lap.depth / math.cos(math.radians(tilt_angle)), 3)

        # G01 sweep: x covers the full joint width projected along the angle,
        # z ramps by the slope over that horizontal distance
        g01_x = lap.width / math.sin(math.radians(lap.angle)) * sweep_direction
        g01_z = -math.tan(math.radians(lap.slope)) * g01_x

        # Number of passes needed to cover the lap width with the given tool
        num_passes = max(1, math.ceil(lap.width / tool.diameter))
        step_x = lap.width / num_passes

        if num_passes == 1:
            # Tool wider than the lap: center it by offsetting the sweep start
            tool_offset = max(0.0, (tool.diameter - lap.width) / 2)
            sp_x_list = [round(tool_offset, 3)]
        else:
            sp_x_list = [round(j * step_x, 3) for j in range(num_passes)]

        milling_operations = [
            MillingOperation(
                start_point=StartPoint(
                    x=sp_x_list[j],
                    y=0.0,
                    z=sp_z,
                    radius_compensation=CompensationMode.RIGHT,
                    lead_in_mode=LeadInOutMode.LINEAR,
                    lead_in_factor=None,
                    easy_snap_xy=EasySnapXY.DISABLED,
                    easy_snap_z=EasySnapZ.TOP_EDGE,
                ),
                moves=[
                    G01(
                        x=round(g01_x, 3),
                        y=0.0,
                        z=round(g01_z, 3),
                        easy_snap_xy=EasySnapXY.RELATIVE,
                        easy_snap_z=EasySnapZ.RELATIVE,
                    )
                ],
                end_point=EndPoint(),
            )
            for j in range(num_passes)
        ]

        return [
            HOPSMachining(
                tool=tool,
                work_plane=work_plane,
                operations=milling_operations,
                comments=[
                    "; ---------------------------------",
                    ";Lap_Milling",
                    "; ---------------------------------",
                ],
            )
        ]

    @staticmethod
    def pocketing(
        lap: "Lap",
        machine_ref_side_index: int,
        tool: Optional[MachiningTool] = None,
    ) -> "List[HOPSMachining]":
        """Create a HOPSMachining for a pocket milling operation derived from a Lap processing.

        Generates an EBENEF work plane and a single _ExecutePocket_ETH macro call that mills
        the lap surface as a pocket with the given depth, angle, inclination, and slope.

        The work plane origin is at (start_x, start_y, 0), tilted by ``90 - inclination``
        and rotated by ``180 - angle``.

        Supports ref_side_index 0 (top face) and 2 (bottom face).

        Parameters
        ----------
        lap : Lap
            The Lap processing containing the geometric information.
        machine_ref_side_index : int
            The index of the reference side on the machine (used for orientation).
        tool : MachiningTool, optional
            Defaults to CastorD61 (WZF503).

        Returns
        -------
        List[HOPSMachining]
            A single HOPSMachining instance.
        """
        from ..hop_job import HOPSMachining

        tool = tool or CastorD61()

        # assert lap.inclination == 90.0 and lap.slope == 0.0, (
        #     f"Lap milling is only supported for vertical laps (90° inclination and 0° slope). got inclination={lap.inclination} and slope={lap.slope}"
        # )

        # check the ref_side of the lap
        diff = (lap.ref_side_index - machine_ref_side_index) % 4
        angle = 180 - lap.angle if lap.orientation == "start" else lap.angle
        length = abs(HopsSystemVars.Z_DIM / math.cos(math.radians(angle)))
        if TOL.is_close(angle, 90.0):
            length = HopsSystemVars.Z_DIM  # avoid numerical issues with cos(90) = 0 and resulting infinite length

        if diff == 0:  # same side
            work_plane = WorkPlane.TOP
            easy_snap_xy = EasySnapXY.FRONT_LEFT
            length = abs(HopsSystemVars.Y_DIM / math.sin(math.radians(angle)))
            process_mode = ProcessMode.WITH_ROTATION if angle >= 90.0 else ProcessMode.NO_CHANGE
            if TOL.is_close(angle, 90.0):
                length = HopsSystemVars.Y_DIM  # avoid numerical issues with cos(90) = 0 and resulting infinite length
        elif diff == 1:  # front side
            work_plane = WorkPlane.FRONT
            easy_snap_xy = EasySnapXY.FRONT_LEFT
            if TOL.is_positive(angle - 90.0):
                length = abs(HopsSystemVars.Z_DIM / math.sin(math.radians(angle)))
            elif TOL.is_negative(angle - 90.0):
                length = abs(HopsSystemVars.Z_DIM / math.sin(math.radians(180 - angle)))
            else:
                length = HopsSystemVars.Z_DIM  # avoid numerical issues with sin(90) = 1 and resulting length equal to Z_DIM, which is correct but we set it explicitly for clarity

            process_mode = ProcessMode.WITH_ROTATION if angle >= 90.0 else ProcessMode.NO_CHANGE
        elif diff == 3:  # back side
            work_plane = WorkPlane.BACK
            easy_snap_xy = EasySnapXY.REAR_RIGHT
            length = -length
            process_mode = ProcessMode.NO_CHANGE
        else:
            raise NotImplementedError(
                f"Unsupported ref_side_index {lap.ref_side_index} for Lap milling. "
                f"Expected {(machine_ref_side_index + 1) % 4} (front) or {(machine_ref_side_index - 1) % 4} (back)."
            )

        num_passes = max(1, math.ceil(lap.length / tool.diameter))
        tool_offset = lap.length - num_passes * tool.diameter  # this should always be negative or zero, since num_passes is the ceiling of length/diameter
        assert tool_offset <= 0, (
            f"Unexpected positive offset {tool_offset} for lap length {lap.length} and tool diameter {tool.diameter}. This should not happen since num_passes is calculated as the ceiling of length/diameter."
        )
        dx = (tool.diameter + tool_offset) / math.sin(math.radians(180 - lap.angle))

        # length = -length if lap.orientation == "start" else length
        milling_operations = [
            MillingOperation(
                start_point=StartPoint(
                    x=lap.start_x + round(j * dx, 3),
                    y=lap.start_y,
                    z=-lap.depth,
                    radius_compensation=CompensationMode.RIGHT if lap.orientation == "start" else CompensationMode.LEFT,
                    lead_in_mode=LeadInOutMode.LINEAR,
                    easy_snap_xy=easy_snap_xy,
                    easy_snap_z=EasySnapZ.TOP_EDGE,
                    process_mode=process_mode,
                    # lead_in_factor=str(HopsSystemVars.LEAD_IN_OUT_FACTOR) + "*2",
                ),
                moves=[AngledLine(length=length, angle=angle, z=0.0, corner_radius=0.0, easy_snap_z=EasySnapZ.RELATIVE)],
                end_point=EndPoint(
                    lead_out_mode=LeadInOutMode.LINEAR,
                    # lead_out_factor=str(HopsSystemVars.LEAD_IN_OUT_FACTOR) + "*2"
                ),
            )
            for j in range(num_passes)
        ]

        return [
            HOPSMachining(
                tool=tool,
                work_plane=work_plane,
                operations=milling_operations,
                comments=[
                    "; ---------------------------------",
                    ";Lap_Pocketing",
                    "; ---------------------------------",
                ],
            )
        ]
