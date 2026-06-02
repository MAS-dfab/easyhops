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
from ..machining_commands import ContourPocketOperation
from ..machining_commands import EndPoint
from ..machining_commands import LeadInOutMode
from ..machining_commands import MillingOperation
from ..machining_commands import OpenPocketOperation
from ..machining_commands import SawingLengthAngleOperation
from ..machining_commands import StartPoint
from ..tool_library import BirdsmouthW41
from ..tool_library import CastorD61
from ..tool_library import MachiningTool
from ..tool_library import SaegeD350
from ..work_planes import FreePlane
from ..work_planes import WorkPlane

if TYPE_CHECKING:
    from compas_timber.fabrication import JackRafterCut

    from ..hop_job import HOPSMachining


class JackRafterCutStrategies:
    @staticmethod
    def _rotation_angle(jack_rafter_cut: "JackRafterCut", machine_ref_side_index: int) -> float:
        """Compute the EbeneF rotation angle for a JackRafterCut given the machine orientation plane.

        When the JRC and the machine orientation share the same reference plane,
        the natural angle is used.  When they are on opposite long faces (ref_side
        indices 1 and 3), the angle is negated to account for the mirror transform.
        """
        base_angle = jack_rafter_cut.angle if jack_rafter_cut.orientation == "start" else 180 - jack_rafter_cut.angle
        jrc_rsi = jack_rafter_cut.ref_side_index
        if jrc_rsi == machine_ref_side_index:
            return base_angle
        elif {jrc_rsi, machine_ref_side_index} == {1, 3}:
            return -base_angle
        else:
            raise NotImplementedError(f"JRC ref_side_index={jrc_rsi} with machine_ref_side_index={machine_ref_side_index} is not yet supported.")

    @staticmethod
    def sawing(jack_rafter_cut: "JackRafterCut", machine_ref_side_index: int = None, tool: Optional[MachiningTool] = None) -> "List[HOPSMachining]":
        """Create HOPSMachining instances for a sawing operation derived from a JackRafterCut processing.

        Parameters:
        -----------
        jack_rafter_cut : JackRafterCut
            The JackRafterCut processing containing the geometric information

        Returns:
        --------
        List[HOPSMachining]
            One or more HOPSMachining instances representing this sawing operation
        """
        from ..hop_job import HOPSMachining

        tool = tool or SaegeD350()
        work_plane = WorkPlane.TOP
        ref_side_index = jack_rafter_cut.ref_side_index

        if ref_side_index == machine_ref_side_index:
            sx = (
                jack_rafter_cut.start_x if jack_rafter_cut.orientation == "end" else HopsSystemVars.Y_DIM / math.tan(math.radians(jack_rafter_cut.angle)) + jack_rafter_cut.start_x
            )
            sy = jack_rafter_cut.start_y
            sz = jack_rafter_cut.start_depth
            angle = 180 - jack_rafter_cut.angle if jack_rafter_cut.orientation == "end" else jack_rafter_cut.angle
            radius_compensation = CompensationMode.RIGHT
            easy_snap_xy = EasySnapXY.FRONT_LEFT if jack_rafter_cut.orientation == "end" else EasySnapXY.REAR_LEFT
            length = HopsSystemVars.Y_DIM / math.sin(math.radians(angle)) if jack_rafter_cut.orientation == "end" else HopsSystemVars.Y_DIM / math.sin(math.radians(-angle))
            tilt_angle = 90 - jack_rafter_cut.inclination  # this needs to be always negative for a 5-axis sawing operation
        else:
            raise NotImplementedError(
                f"JackRafterCut sawing currently only supports when the JRC ref_side_index matches the machine_ref_side_index. Got JRC ref_side_index={ref_side_index} and machine_ref_side_index={machine_ref_side_index}."  # noqa: E501
            )

        sawing_operation = SawingLengthAngleOperation(
            sx=sx,
            sy=sy,
            sz=sz,
            length=length,
            angle=angle,
            z_level=-2.0,
            radius_compensation=radius_compensation,
            tilt_angle=tilt_angle,
            easy_snap_xy=easy_snap_xy,
            easy_snap_z=EasySnapZ.BOTTOM_SIDE,
        )

        return [
            HOPSMachining(
                tool=tool,
                work_plane=work_plane,
                operations=[sawing_operation],
                comments=["; ---------------------------------", ";JackRafterCut_Sawing", "; ---------------------------------"],
            )
        ]

    @staticmethod
    def milling(
        jack_rafter_cut: "JackRafterCut",
        machine_ref_side_index: int = None,
        tool: Optional[MachiningTool] = None,
    ) -> "List[HOPSMachining]":
        """Create a HOPSMachining instance for a contour milling operation derived from a JackRafterCut.

        Uses the same sx/angle derivation as sawing(), but produces a FreePlane +
        MillingOperation (SP/G01/EP) instead of a SAEGEN command.

        Parameters:
        -----------
        jack_rafter_cut : JackRafterCut
            The JackRafterCut processing containing the geometric information
        tool : Optional[MachiningTool]
            The tool to use. Defaults to BirdsmouthW41 (WZF504).

        Returns:
        --------
        List[HOPSMachining]
            A single HOPSMachining instance representing this milling operation
        """
        from ..hop_job import HOPSMachining

        if jack_rafter_cut.ref_side_index != 3:
            raise NotImplementedError(f"Unsupported ref_side_index {jack_rafter_cut.ref_side_index} for JackRafterCut milling. Expected 3.")

        tool = tool or BirdsmouthW41()

        sx = jack_rafter_cut.start_x
        sy = jack_rafter_cut.start_y
        sz = jack_rafter_cut.start_depth
        angle = jack_rafter_cut.angle if jack_rafter_cut.orientation == "start" else 180 - jack_rafter_cut.angle

        easy_snap_xy_sp = EasySnapXY.REAR_RIGHT if angle >= 90 else EasySnapXY.REAR_LEFT
        easy_snap_xy_g01 = EasySnapXY.FRONT_RIGHT if angle >= 90 else EasySnapXY.FRONT_LEFT

        work_plane = FreePlane(
            x=sx,
            y=sy,
            z=sz,
            tilt_angle=90,
            rotation_angle=angle,
            easy_snap_xy=EasySnapXY.FRONT_LEFT,
            easy_snap_z=EasySnapZ.RELATIVE,
            offset_z=0.0,
        )

        milling_operation = MillingOperation(
            start_point=StartPoint(
                radius_compensation=CompensationMode.CENTER,
                lead_in_mode=LeadInOutMode.LINEAR,
                easy_snap_xy=easy_snap_xy_sp,
                easy_snap_z=EasySnapZ.TOP_EDGE,
                start_correction_above=False,
                distance_to_view=0.5,
            ),
            moves=[G01(x=0.0, y=0.0, z=0.0, easy_snap_xy=easy_snap_xy_g01)],
            end_point=EndPoint(),
        )

        return [
            HOPSMachining(
                tool=tool,
                work_plane=work_plane,
                operations=[milling_operation],
                comments=["; ---------------------------------", ";JackRafterCut_Milling", "; ---------------------------------"],
            )
        ]

    @staticmethod
    def open_pocket(
        jack_rafter_cut: "JackRafterCut",
        machine_ref_side_index: int = None,
        tool: Optional[MachiningTool] = None,
    ) -> "List[HOPSMachining]":
        """Create a HOPSMachining instance for an open pocket roughing operation.

        Produces three passes (WZF + 3× EbeneF/CALL OpenPocket) that rough out the
        angled cut face.

        Parameters:
        -----------
        jack_rafter_cut : JackRafterCut
            The JackRafterCut processing containing the geometric information
        tool : Optional[MachiningTool]
            The tool to use. Defaults to BirdsmouthW41 (WZF504).

        Returns:
        --------
        List[HOPSMachining]
            A single HOPSMachining instance with three OpenPocketOperation passes
        """
        from ..hop_job import HOPSMachining

        if jack_rafter_cut.ref_side_index != 3:
            raise NotImplementedError(f"Unsupported ref_side_index {jack_rafter_cut.ref_side_index} for JackRafterCut open pocket. Expected 3.")

        tool = tool or BirdsmouthW41()

        sx = jack_rafter_cut.start_x
        angle = jack_rafter_cut.angle if jack_rafter_cut.orientation == "start" else 180 - jack_rafter_cut.angle

        corner = 2 if angle < 90 else 0
        length = f"_RY/SIN({angle})"
        width = f"ABS(_RY*SIN(90-{angle}))"

        operations = [
            OpenPocketOperation(
                sx=sx,
                rotation_angle=angle,
                z_expr=f"_RZ*{i}/3",
                corner=corner,
                length=length,
                width=width,
            )
            for i in range(1, 4)
        ]

        return [
            HOPSMachining(
                tool=tool,
                work_plane=None,
                operations=operations,
                comments=["; ---------------------------------", ";JackRafterCut_OpenPocket", "; ---------------------------------"],
            )
        ]

    @staticmethod
    def contour_pocket(
        jack_rafter_cut: "JackRafterCut",
        machine_ref_side_index: int,
        tool: Optional[MachiningTool] = None,
    ) -> "List[HOPSMachining]":
        """Create a HOPSMachining for a contour-buffer pocket roughing of a JackRafterCut.

        Produces a single EbeneF + KB/KG01×4/KG01ZuKB + CALL _ExecutePocket_V5 block.

        Parameters:
        -----------
        jack_rafter_cut : JackRafterCut
            The JackRafterCut processing.
        machine_ref_side_index : int
            ref_side_index of the processing that defines the machine orientation.
        tool : Optional[MachiningTool]
            Defaults to CastorD61 (WZF503).

        Returns:
        --------
        List[HOPSMachining]
            A single HOPSMachining with one ContourPocketOperation.
        """
        from ..hop_job import HOPSMachining

        if jack_rafter_cut.ref_side_index != machine_ref_side_index:
            raise NotImplementedError(
                f"JackRafterCut contour pocketing currently only supports when the JRC ref_side_index matches the machine_ref_side_index. Got JRC ref_side_index={jack_rafter_cut.ref_side_index} and machine_ref_side_index={machine_ref_side_index}."  # noqa: E501
            )

        tool = tool or CastorD61()
        rotation_angle = JackRafterCutStrategies._rotation_angle(jack_rafter_cut, machine_ref_side_index)

        operation = ContourPocketOperation(
            sx=jack_rafter_cut.start_x,
            sy=jack_rafter_cut.start_y,
            sz=jack_rafter_cut.start_depth,
            tilt_angle=jack_rafter_cut.inclination,
            rotation_angle=rotation_angle,
            easy_snap_xy=EasySnapXY.REAR_LEFT,
        )

        return [
            HOPSMachining(
                tool=tool,
                work_plane=None,
                operations=[operation],
                comments=["; ---------------------------------", ";JackRafterCut_ContourPocket", "; ---------------------------------"],
            )
        ]
