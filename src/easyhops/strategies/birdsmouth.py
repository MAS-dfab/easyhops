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
    from compas_timber.fabrication import BirdsMouth

    from ..hop_job import HOPSMachining


class BirdsMouthStrategies:
    @staticmethod
    def milling(
        birdsmouth: "BirdsMouth",
        machine_ref_side_index: int,
        tool: Optional[MachiningTool] = None,
        first_cut: bool = False,
        engagement_ratio: float = 0.5,
        avoid_splintering: bool = False,
    ) -> "List[HOPSMachining]":
        """Create HOPSMachining instances for a milling operation derived from a BirdsMouth processing.

        Parameters:
        -----------
        birdsmouth : BirdsMouth
            The BirdsMouth processing containing the geometric information
        tool : MachiningTool, optional
            The machining tool to use; defaults to CastorD61
        first_cut : bool
            Selects between inclination_1 (True) and inclination_2 (False) for the rotation angle
        engagement_ratio : float
            Maximum fraction of the tool's chip area per pass. Defaults to 0.5.
        avoid_splintering : bool
            When True, a scoring pre-pass is added before each main pass at the final (deepest)
            Z-level. The pre-pass approaches from the exit edge in the opposite direction and
            bites in by one tool radius (_WZR), severing wood fibers before the main cut.
            Defaults to False.

        Returns:
        --------
        List[HOPSMachining]
            One or more HOPSMachining instances representing this milling operation
        """
        from ..hop_job import HOPSMachining

        tool = tool or CastorD61()

        inclination = birdsmouth.inclination_1 if first_cut else 180 + birdsmouth.inclination_2

        if birdsmouth.ref_side_index == (machine_ref_side_index + 1) % 4:  # Clockwise adjacent side
            easy_snap_xy = EasySnapXY.FRONT_LEFT
            rotation_angle = -inclination if birdsmouth.orientation == "start" else inclination
            radius_compensation = CompensationMode.LEFT if birdsmouth.orientation == "start" else CompensationMode.RIGHT
        elif birdsmouth.ref_side_index == (machine_ref_side_index - 1) % 4:  # Opposite side
            easy_snap_xy = EasySnapXY.REAR_LEFT
            rotation_angle = 180 + inclination if birdsmouth.orientation == "start" else 180 - inclination
            radius_compensation = CompensationMode.RIGHT if birdsmouth.orientation == "start" else CompensationMode.LEFT
        else:
            raise NotImplementedError(
                f"Unsupported ref_side_index {birdsmouth.ref_side_index} for BirdsMouth processing. Expected {machine_ref_side_index} or {(machine_ref_side_index + 2) % 4}."
            )

        if not first_cut:
            radius_compensation = CompensationMode.RIGHT if radius_compensation == CompensationMode.LEFT else CompensationMode.LEFT

        riser_length = birdsmouth.user_attributes["riser_length"] * 1000
        tread_length = birdsmouth.user_attributes["tread_length"] * 1000

        step_area = 0.5 * riser_length * tread_length
        tool_area = tool.diameter * tool.max_depth
        n_z_passes = max(
            max(1, math.ceil(riser_length / tool.max_depth)),
            max(1, math.ceil(step_area / (engagement_ratio * tool_area))) if tool_area > 0 else 1,
        )
        depth_per_z_pass = riser_length / n_z_passes

        pass_length = tread_length if first_cut else riser_length
        n_x_passes = max(1, math.ceil(pass_length / tool.diameter))
        x_step = pass_length / n_x_passes

        x_sign = 1 if radius_compensation == CompensationMode.LEFT else -1

        # add a pre-pass to score the wood fibers and reduce splintering on the final pass, if requested
        pre_pass_operation = MillingOperation(
            start_point=StartPoint(
                x=0.0,
                y=-HopsSystemVars.Z_DIM,
                radius_compensation=CompensationMode.RIGHT if radius_compensation == CompensationMode.LEFT else CompensationMode.LEFT,
                lead_in_mode=LeadInOutMode.LINEAR,
            ),
            moves=[G01(x=0.0, y=HopsSystemVars.TOOL_RADIUS, z=0.0, easy_snap_xy=EasySnapXY.RELATIVE)],
            end_point=EndPoint(lead_out_mode=LeadInOutMode.LATERAL),
        )

        milling_operations = [
            MillingOperation(
                start_point=StartPoint(
                    x=x_sign * x_step * (n_x_passes - 1 - j),
                    radius_compensation=radius_compensation,
                    lead_in_mode=LeadInOutMode.LINEAR,
                ),
                moves=[G01(x=0.0, y="-_RZ", z=0.0, easy_snap_xy=EasySnapXY.RELATIVE)],
                end_point=EndPoint(lead_out_mode=LeadInOutMode.NONE),
            )
            for j in range(n_x_passes)
        ]

        n_passes = n_z_passes
        result = []
        for i in range(n_passes):
            comment_label = f"BirdsMouth_Milling (Pass {i + 1}/{n_passes})" if n_passes > 1 else "BirdsMouth_Milling"
            comment = "\n".join(["; ---------------------------------", f";{comment_label}", "; ---------------------------------"])
            work_plane = FreePlane(
                x=birdsmouth.start_x,
                y=birdsmouth.start_depth,
                z=birdsmouth.start_y,
                rotation_angle=rotation_angle,
                tilt_angle=birdsmouth.angle,
                easy_snap_xy=easy_snap_xy,
                easy_snap_z=EasySnapZ.RELATIVE,
                offset_z=depth_per_z_pass * (n_passes - 1 - i),
            )
            is_final_pass = i == n_passes - 1
            operations = [pre_pass_operation] + milling_operations if (avoid_splintering and is_final_pass) else milling_operations
            result.append(HOPSMachining(tool=tool, work_plane=work_plane, operations=operations, comments=[comment]))
        return result
