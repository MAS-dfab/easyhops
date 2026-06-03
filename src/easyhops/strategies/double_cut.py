from __future__ import annotations

import math
from typing import TYPE_CHECKING
from typing import List
from typing import Optional

from ..contour_commands import CloseContour
from ..contour_commands import ContourLine
from ..contour_commands import ContourStart
from ..hop_core import EasySnapXY
from ..hop_core import EasySnapZ
from ..hop_core import HopsSystemVars
from ..hop_macros import AngledLine
from ..machining_commands import G01
from ..machining_commands import CompensationMode
from ..machining_commands import EndPoint
from ..machining_commands import LeadInOutMode
from ..machining_commands import MillingContour
from ..machining_commands import MillingContourStart
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
    def pocketing(
        double_cut: "DoubleCut",
        machine_ref_side_index: int,
        tool: Optional[MachiningTool] = None,
        first_cut: bool = False,
    ) -> "List[HOPSMachining]":
        """Create a HOPSMachining for a DoubleCut pocket operation.

        Produces a single EbeneF + KB / KG01 / _KWGerade_V5 / KG01 / KG01ZuKB
        + CALL _ExecutePocket_ETH block — mirroring the hand-written hop files.

        Parameters:
        -----------
        double_cut : DoubleCut
            The DoubleCut processing containing the geometric information.
        machine_ref_side_index : int
            The reference side index of the machine setup, used to determine the correct work plane orientation.
        tool : MachiningTool, optional
            Defaults to CastorD61 (WZF503).
        first_cut : bool
            True = first cut face (angle_1/inclination_1), False = second (angle_2/inclination_2).
        overlap : int
            Pocket path overlap as % of tool diameter.  Default 60.

        Returns:
        --------
        List[HOPSMachining]
            A single HOPSMachining instance.
        """
        from ..hop_job import HOPSMachining

        tool = tool or CastorD61()
        tool_max_depth = tool.max_depth / 3

        if first_cut:
            angle = double_cut.angle_1
            inclination = double_cut.inclination_1
        else:
            angle = double_cut.angle_2
            inclination = double_cut.inclination_2

        angle = 0.0 if angle == 0.1 else angle  # BTLx export hack for 90-degree cuts

        ridge_length = double_cut.user_attributes["ridge_length"] * 1000
        ridge_angle = double_cut.user_attributes["ridge_angle"]

        if double_cut.ref_side_index == (machine_ref_side_index + 2) % 4:  # Opposite side
            easy_snap_xy = EasySnapXY.REAR_LEFT
            rotation_angle = -angle if double_cut.orientation == "start" else angle
        elif double_cut.ref_side_index == machine_ref_side_index:
            easy_snap_xy = EasySnapXY.FRONT_LEFT
            rotation_angle = 180 + angle if double_cut.orientation == "start" else 180 - angle
            inclination = 180 - inclination
        else:
            raise NotImplementedError(
                f"Unsupported ref_side_index {double_cut.ref_side_index} for DoubleCut. Expected {machine_ref_side_index} or {(machine_ref_side_index + 2) % 4}."
            )  # noqa: E501

        # Auto-calculate passes: how many tool.max_depth increments are needed to reach the full depth
        depth = math.sin(math.radians(inclination)) * double_cut.start_x
        n_passes = max(1, math.ceil(depth / (tool.max_depth * 0.5)))  # hack since the depth is calculated without considering any roughing cuts.

        work_plane = FreePlane(
            x=double_cut.start_x,
            y=double_cut.start_y,
            z=0.0,
            rotation_angle=rotation_angle,
            tilt_angle=inclination,
            easy_snap_xy=easy_snap_xy,
            easy_snap_z=EasySnapZ.TOP_SIDE,
            offset_z=0.0,
        )

        contour_name = str(double_cut.guid)[:4]  # use first 4 chars of the guid as a short identifier for the contour name
        contours = [
            ContourStart(contour_name, x=-HopsSystemVars.TOOL_RADIUS / math.sin(math.radians(ridge_angle)), easy_snap_xy=EasySnapXY.DISABLED),
            AngledLine(name="ridge_line", length=-ridge_length, angle=ridge_angle),
            ContourLine("bottom_corner", easy_snap_xy=EasySnapXY.FRONT_LEFT),
            ContourLine("top_corner", easy_snap_xy=EasySnapXY.REAR_LEFT),
            CloseContour(),
        ]

        milling_contours = [
            MillingOperation(
                start_point=MillingContourStart(z=tool_max_depth * j, radius_compensation=CompensationMode.CENTER, easy_snap_z=EasySnapZ.TOP_EDGE),
                moves=[MillingContour(contour_name=contour_name)],
                end_point=EndPoint(lead_out_mode=LeadInOutMode.NONE),
            )
            for j in reversed(range(n_passes))
        ]

        machining = HOPSMachining(
            tool=tool,
            work_plane=work_plane,
            operations=contours + milling_contours,
            comments=["; ---------------------------------", ";DoubleCut_Pocketing", "; ---------------------------------"],
        )
        return [machining]

    @staticmethod
    def milling(
        double_cut: "DoubleCut",
        machine_ref_side_index: int,
        tool: Optional[MachiningTool] = None,
        first_cut: bool = True,
        engagement_ratio: float = 0.5,
        avoid_splintering: bool = False,
    ) -> "List[HOPSMachining]":
        """Create HOPSMachining instances for a milling operation derived from a DoubleCut processing.

        When the required riser depth exceeds the tool's max depth, multiple passes are generated,
        each as a separate HOPSMachining with an incrementally deeper work plane offset.
        An additional area-based constraint ensures the triangular step cross-section never exceeds
        engagement_ratio of the tool's rectangular chip area (diameter x max_depth) per pass.

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
        avoid_splintering : bool
            When True, a scoring pre-pass is added before the main passes at the final (deepest)
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

        if first_cut:
            angle = double_cut.angle_1
            inclination = double_cut.inclination_1
        else:
            angle = double_cut.angle_2
            inclination = double_cut.inclination_2

        angle = 0.0 if angle == 0.1 else angle  # NOTE: hack in BTLx export to avoid issues with 90 degree cuts

        riser_length = double_cut.user_attributes["riser_length"] * 1000
        tread_length = double_cut.user_attributes["tread_length"] * 1000

        step_area = 0.5 * riser_length * tread_length
        tool_area = tool.diameter * tool.max_depth
        n_z_passes = max(
            max(1, math.ceil(riser_length / tool.max_depth)),
            max(1, math.ceil(step_area / (engagement_ratio * tool_area))) if tool_area > 0 else 1,
        )
        depth_per_z_pass = riser_length / n_z_passes

        n_x_passes = max(1, math.ceil(tread_length / tool.diameter))
        x_step = tread_length / n_x_passes

        if double_cut.ref_side_index == machine_ref_side_index:
            easy_snap_xy = EasySnapXY.FRONT_LEFT
            rotation_angle = 180 + angle if double_cut.orientation == "start" else 180 - angle
            radius_compensation = CompensationMode.RIGHT if double_cut.orientation == "start" else CompensationMode.LEFT
        else:
            if double_cut.ref_side_index == (machine_ref_side_index + 2) % 4:  # Opposite side
                easy_snap_xy = EasySnapXY.REAR_LEFT
                rotation_angle = -angle if double_cut.orientation == "start" else angle
                radius_compensation = CompensationMode.LEFT if double_cut.orientation == "start" else CompensationMode.RIGHT
            else:
                raise NotImplementedError(
                    f"Unsupported ref_side_index {double_cut.ref_side_index} for DoubleCut processing. The ref_side_index must match either the machine_ref_side_index or its opposite."
                )

        x_sign = 1 if radius_compensation == CompensationMode.LEFT else -1
        pre_pass_compensation = CompensationMode.RIGHT if radius_compensation == CompensationMode.LEFT else CompensationMode.LEFT

        # add a pre-pass to score the wood fibers and reduce splintering on the final pass, if requested
        pre_pass_operation = MillingOperation(
            start_point=StartPoint(
                x=0.0,
                y=-HopsSystemVars.Z_DIM,
                radius_compensation=pre_pass_compensation,
                lead_in_mode=LeadInOutMode.LINEAR,
            ),
            moves=[G01(x=0.0, y=HopsSystemVars.TOOL_RADIUS, z=0.0, easy_snap_xy=EasySnapXY.RELATIVE)],
            end_point=EndPoint(lead_out_mode=LeadInOutMode.NONE),
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
            comment_label = f"DoubleCut_Milling (Pass {i + 1}/{n_passes})" if n_passes > 1 else "DoubleCut_Milling"
            comment = "\n".join(["; ---------------------------------", f";{comment_label}", "; ---------------------------------"])
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
            is_final_pass = i == n_passes - 1
            operations = [pre_pass_operation] + milling_operations if (avoid_splintering and is_final_pass) else milling_operations
            result.append(HOPSMachining(tool=tool, work_plane=work_plane, operations=operations, comments=[comment]))
        return result
