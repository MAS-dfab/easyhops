from __future__ import annotations

import math
from typing import TYPE_CHECKING
from typing import List
from typing import Optional

from ..hop_core import EasySnapXY
from ..hop_core import EasySnapZ
from ..machining_commands import G01
from ..machining_commands import CompensationMode
from ..machining_commands import EndPoint
from ..machining_commands import LeadInOutMode
from ..machining_commands import MillingOperation
from ..machining_commands import StartPoint
from ..tool_library import CastorD61
from ..tool_library import MachiningTool
from ..work_planes import FreePlane

if TYPE_CHECKING:
    from compas_timber.fabrication import Lap

    from ..hop_job import HOPSMachining


class LapStrategies:
    @staticmethod
    def milling(
        lap: "Lap",
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
