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
    from compas_timber.fabrication import DoubleCut

    from ..hop_job import HOPSMachining


class DoubleCutStrategies:
    @staticmethod
    def milling(
        double_cut: "DoubleCut",
        tool: Optional[MachiningTool] = None,
        first_cut: bool = True,
        engagement_ratio: float = 0.5,
    ) -> "List[HOPSMachining]":
        """Create HOPSMachining instances for a milling operation derived from a DoubleCut processing.

        When the required riser depth exceeds the tool's max depth, multiple passes are generated,
        each as a separate HOPSMachining with an incrementally deeper work plane offset.
        An additional area-based constraint ensures the triangular step cross-section never exceeds
        engagement_ratio of the tool's rectangular chip area (diameter × max_depth) per pass.

        Parameters:
        -----------
        double_cut : DoubleCut
            The DoubleCut processing containing the geometric information
        tool : MachiningTool, optional
            The machining tool to use; defaults to CastorD61
        first_cut : bool
            In case of 90 degree cuts, determines whether this is the first cut (True) or second cut (False)
        engagement_ratio : float
            Maximum fraction of the tool's chip area per pass. Defaults to 0.5.

        Returns:
        --------
        List[HOPSMachining]
            One or more HOPSMachining instances representing this milling operation
        """
        from ..hop_job import HOPSMachining

        tool = tool or CastorD61()

        if first_cut:
            angle = double_cut.angle_1
            inclination = double_cut.inclination_1
        else:
            angle = double_cut.angle_2
            inclination = double_cut.inclination_2

        angle = 0.0 if angle == 0.1 else angle  # NOTE: hack in BTLx export to avoid issues with 90 degree cuts

        riser_length = double_cut.user_attributes["riser_length"]
        tread_length = double_cut.user_attributes["tread_length"]

        step_area = 0.5 * riser_length * tread_length
        tool_area = tool.diameter * tool.max_depth
        n_z_passes = max(
            max(1, math.ceil(riser_length / tool.max_depth)),
            max(1, math.ceil(step_area / (engagement_ratio * tool_area))) if tool_area > 0 else 1,
        )
        depth_per_z_pass = riser_length / n_z_passes

        n_x_passes = max(1, math.ceil(tread_length / tool.diameter))
        x_step = tread_length / n_x_passes

        if double_cut.ref_side_index == 1:
            easy_snap_xy = EasySnapXY.REAR_LEFT
            rotation_angle = -angle if double_cut.orientation == "start" else angle
            radius_compensation = CompensationMode.RIGHT if double_cut.orientation == "start" else CompensationMode.LEFT
        elif double_cut.ref_side_index == 3:
            easy_snap_xy = EasySnapXY.FRONT_LEFT
            rotation_angle = 180 + angle if double_cut.orientation == "start" else 180 - angle
            radius_compensation = CompensationMode.LEFT if double_cut.orientation == "start" else CompensationMode.RIGHT
        else:
            raise NotImplementedError(f"Unsupported ref_side_index {double_cut.ref_side_index} for DoubleCut processing. Expected 1 or 3.")

        x_sign = 1 if radius_compensation == CompensationMode.LEFT else -1
        milling_operations = [
            MillingOperation(
                start_point=StartPoint(
                    x=x_sign * x_step * (n_x_passes - 1 - j),
                    radius_compensation=radius_compensation,
                    lead_in_mode=LeadInOutMode.LINEAR,
                ),
                moves=[G01(x=0.0, y="-_RZ", z=0.0, easy_snap_xy=EasySnapXY.RELATIVE)],
                end_point=EndPoint(lead_out_mode=LeadInOutMode.NONE, lead_out_factor=1.0),
            )
            for j in range(n_x_passes)
        ]

        n_passes = n_z_passes
        result = []
        for i in range(n_passes):
            comment = f"; ###### DoubleCut (Pass {i + 1}/{n_passes}) ######" if n_passes > 1 else "; ###### DoubleCut ######"
            work_plane = FreePlane(
                x=double_cut.start_x,
                y=double_cut.start_y,
                z=0.0,
                rotation_angle=rotation_angle,
                tilt_angle=inclination,
                easy_snap_xy=easy_snap_xy,
                easy_snap_z=EasySnapZ.RELATIVE,
                offset_z=depth_per_z_pass * (n_passes - 1 - i),
            )
            result.append(HOPSMachining(tool=tool, work_plane=work_plane, operations=milling_operations, comments=[comment]))
        return result
