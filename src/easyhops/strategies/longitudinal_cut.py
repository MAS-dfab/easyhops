from __future__ import annotations

import math
from typing import TYPE_CHECKING
from typing import List
from typing import Optional

from ..hop_core import EasySnapXY
from ..hop_core import EasySnapZ
from ..hop_core import HopsSystemVars
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
    from compas_timber.fabrication import LongitudinalCut

    from ..hop_job import HOPSMachining


class LongitudinalCutStrategies:
    @staticmethod
    def contouring(
        longitudinal_cut: "LongitudinalCut",
        machine_ref_side_index: int,
        tool: Optional[MachiningTool] = None,
        engagement_ratio: float = 0.5,
    ) -> "List[HOPSMachining]":
        """Create HOPSMachining instances for a milling operation derived from a Longitudinal processing with a contouring strategy.

        Parameters:
        -----------
        longitudinal_cut : LongitudinalCut
            The LongitudinalCut processing containing the geometric information
        machine_ref_side_index : int
            The index of the reference side on the machine (0-3), used to determine the orientation of the milling operation
        tool : MachiningTool, optional
            The machining tool to use; defaults to CastorD61
        engagement_ratio : float
            Maximum fraction of the tool's chip area per pass. Defaults to 0.5.

        Returns:
        --------
        List[HOPSMachining]
            One or more HOPSMachining instances representing this milling operation
        """
        from ..hop_job import HOPSMachining

        tool = tool or CastorD61()

        if (longitudinal_cut.ref_side_index - machine_ref_side_index) % 4 in (1, 3):
            x = 0
            y = 0
            z = HopsSystemVars.Y_DIM - longitudinal_cut.start_y
            rotation_angle = 180
            tilt_angle = abs(longitudinal_cut.inclination)
            easy_snap_xy = EasySnapXY.FRONT_LEFT
            easy_snap_z = EasySnapZ.TOP_SIDE

        full_depth = HopsSystemVars.Y_DIM / math.sin(abs(longitudinal_cut.inclination))
        depth_per_pass = tool.max_depth * engagement_ratio
        n_passes = math.ceil(full_depth / depth_per_pass)

        milling_operations = []
        for i in range(n_passes):
            z_pass = min((i + 1) * depth_per_pass, full_depth)
            milling_operations.append(
                MillingOperation(
                    start_point=StartPoint(
                        x=-HopsSystemVars.TOOL_DIAMETER,
                        y=-HopsSystemVars.TOOL_DIAMETER,
                        z=z_pass,
                        radius_compensation=CompensationMode.LEFT,
                        lead_in_mode=LeadInOutMode.LINEAR,
                    ),
                    moves=[
                        G01(x=0.0, y=-HopsSystemVars.TOOL_DIAMETER, z=0.0, easy_snap_xy=EasySnapXY.RELATIVE),  # Vertical Lead-in move
                        G01(x=-HopsSystemVars.TOOL_DIAMETER, y=0.0, z=0.0, easy_snap_xy=EasySnapXY.REAR_RIGHT),  # Contouring move
                        G01(x=0.0, y=HopsSystemVars.TOOL_DIAMETER, z=0.0, easy_snap_xy=EasySnapXY.RELATIVE),  # Vertical Lead-out move
                    ],
                    end_point=EndPoint(lead_out_mode=LeadInOutMode.LINEAR),
                )
            )

        comment_label = f"LongitudinalCut_Contouring ({n_passes} passes)" if n_passes > 1 else "LongitudinalCut_Contouring"
        comment = "\n".join(["; ---------------------------------", f";{comment_label}", "; ---------------------------------"])
        work_plane = FreePlane(
            x=x,
            y=y,
            z=z,
            rotation_angle=rotation_angle,
            tilt_angle=tilt_angle,
            easy_snap_xy=easy_snap_xy,
            easy_snap_z=easy_snap_z,
        )
        return [HOPSMachining(tool=tool, work_plane=work_plane, operations=milling_operations, comments=[comment])]
