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
from ..hop_macros import FreeFormPocket
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
    def pocketing(
        double_cut: "DoubleCut",
        machine_ref_side_index: int,
        tool: Optional[MachiningTool] = None,
        first_cut: bool = False,
        overlap: int = 60,
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

        if first_cut:
            angle = double_cut.angle_1
            inclination = double_cut.inclination_1
        else:
            angle = double_cut.angle_2
            inclination = double_cut.inclination_2

        angle = 0.0 if angle == 0.1 else angle  # BTLx export hack for 90-degree cuts

        ridge_length = double_cut.user_attributes["ridge_length"]
        ridge_angle = double_cut.user_attributes["ridge_angle"]
        # Auto-calculate passes: how many tool.max_depth increments fit in ridge_length
        n_z_passes = max(1, math.ceil(ridge_length / tool.max_depth))

        if double_cut.ref_side_index == machine_ref_side_index:
            easy_snap_xy = EasySnapXY.REAR_LEFT
            rotation_angle = -angle if double_cut.orientation == "start" else angle
            # KG01 approach: x = -TAN(ridge_angle)/_WZR (towards REAR), y = _WZR
            kg01_x = f"-TAN({ridge_angle:.3f})/_WZR"
        elif double_cut.ref_side_index == (machine_ref_side_index + 2) % 4:  # Opposite side
            easy_snap_xy = EasySnapXY.FRONT_LEFT
            rotation_angle = 180 + angle if double_cut.orientation == "start" else 180 - angle
            # KG01 approach: x = +TAN(supplement)/_WZR, y = _WZR
            supplement = 180 - ridge_angle
            kg01_x = f"TAN({supplement:.3f})/_WZR"
        else:
            raise NotImplementedError(
                f"Unsupported ref_side_index {double_cut.ref_side_index} for DoubleCut. Expected {machine_ref_side_index} or {(machine_ref_side_index + 2) % 4}."
            )  # noqa: E501

        # The angled line length covers the ridge + one tool diameter of clearance
        kw_length = f"{ridge_length:.3f}+_WZD"
        kw_angle = f"-{ridge_angle:.3f}"

        contour_name = "K1"

        finishing_contour_name = "K2"

        class _DoubleCutPocketOp:
            """Serialises as: pocket contour + _ExecutePocket_ETH, then finishing EBENEF + ridge contour."""

            def __str__(self_op):
                lines = [
                    # ---- roughing pocket ----
                    str(ContourStart(contour_name, x="-_WZR", y="-_WZR", easy_snap_xy=EasySnapXY.REAR_LEFT)),
                    str(ContourLine("L_start", x=kg01_x, y="_WZR", z=0, easy_snap_xy=EasySnapXY.RELATIVE)),
                    f"CALL _KWGerade_V5 ( VAL NAME:='L_main',LAENGE:={kw_length},WINKEL:={kw_angle},Z:=0,INFO:='',ESD:=2)",
                    str(ContourLine("L_end", x="-_WZR", y="-_WZR", z=0, easy_snap_xy=EasySnapXY.FRONT_LEFT)),
                    str(CloseContour()),
                    str(
                        FreeFormPocket(
                            contour_name=contour_name,
                            distance_to_contour=0,
                            overlap=overlap,
                            mode=0,
                            depth=ridge_length,
                            count=n_z_passes,
                            outside_in=0,
                            flying_plunge=0,
                            max_plunge_length=60,
                        )
                    ),
                    # ---- finishing pass (same work plane, no new tool call) ----
                    "; ---------------------------------",
                    ";DoubleCut_Finishing",
                    "; ---------------------------------",
                    str(work_plane),  # repeat EBENEF without WZF
                    str(ContourStart(finishing_contour_name, x=0, y=0, z=0, easy_snap_xy=EasySnapXY.DISABLED)),
                    f"CALL _KWGerade_V5 ( VAL NAME:='',LAENGE:={kw_length},WINKEL:={kw_angle},Z:=0,INFO:='',ESD:=2)",
                    "KSP ('???','???',0,2,1,_ANF,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)",
                    f"KonturFraesen ('{finishing_contour_name}','KSP','KEP',0,0,0,0,0,0,0,0,0,90,0,0.5,0)",
                    "EP (1,_ANF,0)",
                ]
                return "\n".join(lines)

        work_plane = FreePlane(
            x=double_cut.start_x,
            y=double_cut.start_y,
            z=0.0,
            rotation_angle=rotation_angle,
            tilt_angle=inclination,
            easy_snap_xy=easy_snap_xy,
            easy_snap_z=EasySnapZ.RELATIVE,
            offset_z=0.0,
        )

        machining = HOPSMachining(
            tool=tool,
            work_plane=work_plane,
            operations=[_DoubleCutPocketOp()],
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
                end_point=EndPoint(lead_out_mode=LeadInOutMode.NONE, lead_out_factor=1.0),
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
