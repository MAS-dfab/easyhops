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
from ..work_planes import WorkPlane

if TYPE_CHECKING:
    from compas_timber.fabrication import StepJoint

    from ..hop_job import HOPSMachining


class StepJointStrategies:
    @staticmethod
    def milling(
        step_joint: "StepJoint",
        machine_ref_side_index: int,
        tool: Optional[MachiningTool] = None,
    ) -> "List[HOPSMachining]":
        """Create HOPSMachining instances for a StepJoint double-shape milling operation.

        Generates three cut groups:
        - Block 1 (EBENE1): riser face, tool left compensation
        - Block 2 (EBENEF): tread face, tool left compensation
        - Block 3 (EBENEF, n passes): heel face, tool right compensation

        The number of heel passes is determined by ``tool.max_depth`` vs the
        required displacement into the beam.

        Parameters
        ----------
        step_joint : StepJoint
            The StepJoint processing.
        machine_ref_side_index : int
            Reference side index of the machine setup.
        tool : MachiningTool, optional
            Defaults to CastorD61 (WZF503).

        Returns
        -------
        List[HOPSMachining]
            2 + n_passes HOPSMachining instances.
        """
        from ..hop_job import HOPSMachining

        tool = tool or CastorD61()

        if step_joint.step_shape != "double":
            raise NotImplementedError(f"Only 'double' step shape is supported, got '{step_joint.step_shape}'")

        heel_dx = step_joint.start_x + step_joint.heel_depth / math.sin(math.radians(180 - step_joint.strut_inclination))
        heel_dy = step_joint.heel_depth / math.cos(math.radians(180 - step_joint.strut_inclination))

        # ------------------------------------------------------------------ #
        # Block 1 — EBENE1 (standard front face), heel_cut                   #
        # ------------------------------------------------------------------ #
        heel_operation = MillingOperation(
            start_point=StartPoint(
                x=heel_dx,
                y=HopsSystemVars.Z_DIM,
                z=-heel_dy,
                radius_compensation=CompensationMode.LEFT,
                lead_in_mode=LeadInOutMode.LINEAR,
                easy_snap_xy=EasySnapXY.DISABLED,
                easy_snap_z=EasySnapZ.TOP_EDGE,
            ),
            moves=[
                G01(x=0.0, y=-HopsSystemVars.Z_DIM, z=0, easy_snap_xy=EasySnapXY.RELATIVE),
            ],
            end_point=EndPoint(lead_out_mode=LeadInOutMode.NONE),
        )

        block1 = HOPSMachining(
            tool=tool,
            work_plane=WorkPlane.FRONT,
            operations=[heel_operation],
            comments=[
                "; ---------------------------------",
                ";StepJoint_Heel",
                "; ---------------------------------",
            ],
        )

        # ------------------------------------------------------------------ #
        # Block 2 — EBENEF, step face (left compensation)                    #
        # ------------------------------------------------------------------ #
        step_operation = MillingOperation(
            start_point=StartPoint(
                radius_compensation=CompensationMode.LEFT,
                lead_in_mode=LeadInOutMode.LINEAR,
                easy_snap_xy=EasySnapXY.DISABLED,
                easy_snap_z=EasySnapZ.TOP_EDGE,
            ),
            moves=[
                G01(x=0, y=-HopsSystemVars.Z_DIM, z=0, easy_snap_xy=EasySnapXY.RELATIVE),
            ],
            end_point=EndPoint(lead_out_mode=LeadInOutMode.NONE),
        )

        block2 = HOPSMachining(
            tool=tool,
            work_plane=FreePlane(
                x=step_joint.start_x + HopsSystemVars.Y_DIM / math.tan(math.radians(180.0 - step_joint.strut_inclination)),
                y=0.0,
                z=0.0,
                tilt_angle=90.0,
                rotation_angle=(180.0 - step_joint.strut_inclination) / 2,
                easy_snap_xy=EasySnapXY.REAR_LEFT,
                easy_snap_z=EasySnapZ.TOP_SIDE,
            ),
            operations=[step_operation],
            comments=[
                "; ---------------------------------",
                ";StepJoint_Step",
                "; ---------------------------------",
            ],
        )

        # ------------------------------------------------------------------ #
        # Block 3 — EBENEF, heel face (right compensation), multi-pass        #
        # ------------------------------------------------------------------ #
        displacement_end = HopsSystemVars.Z_DIM / math.sin(math.radians(step_joint.strut_inclination))
        displacement_heel = step_joint.heel_depth / math.sin(math.radians(step_joint.strut_inclination))
        trans_len = math.tan(math.radians(step_joint.strut_inclination)) * displacement_heel
        heel_hyp = math.sqrt(trans_len**2 + displacement_heel**2)
        angle_heel = (
            step_joint.strut_inclination
            - 90.0
            + math.atan(step_joint.step_depth / (displacement_end - heel_hyp - step_joint.step_depth / math.tan(math.radians(step_joint.strut_inclination) / 2)))
        )

        heel_to_step_dx = (HopsSystemVars.Y_DIM - heel_dy - step_joint.step_depth) / math.cos(math.radians(angle_heel))
        n_passes = max(1, math.ceil(heel_to_step_dx / tool.max_depth))
        offset_per_pass = heel_to_step_dx / n_passes

        heel_operations = [
            MillingOperation(
                start_point=StartPoint(
                    y=HopsSystemVars.TOOL_DIAMETER,
                    z=offset_per_pass * j if j > 0 else (offset_per_pass if n_passes > 1 else 0),
                    radius_compensation=CompensationMode.RIGHT,
                    lead_in_mode=LeadInOutMode.LINEAR,
                    easy_snap_xy=EasySnapXY.DISABLED,
                    easy_snap_z=EasySnapZ.TOP_EDGE,
                ),
                moves=([G01(x=0, y=0, z=-offset_per_pass, easy_snap_xy=EasySnapXY.RELATIVE)] if j == 0 else []) + [G01(x=0, y=-HopsSystemVars.Z_DIM, z=0)],
                end_point=EndPoint(lead_out_mode=LeadInOutMode.LATERAL),
            )
            for j in reversed(range(n_passes))
        ]

        block3 = HOPSMachining(
            tool=tool,
            work_plane=FreePlane(
                x=heel_dx,
                y=heel_dy,
                z=0.0,
                tilt_angle=90.0,
                rotation_angle=180.0 - angle_heel,
                easy_snap_xy=EasySnapXY.FRONT_LEFT,
                easy_snap_z=EasySnapZ.TOP_SIDE,
            ),
            operations=heel_operations,
            comments=[
                "; ---------------------------------",
                ";StepJoint_Body",
                "; ---------------------------------",
            ],
        )
        return [block1, block2, block3]
