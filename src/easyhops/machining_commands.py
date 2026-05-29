from __future__ import annotations

import math
import re
from enum import IntEnum
from typing import TYPE_CHECKING
from typing import List
from typing import Optional
from typing import Union

from .base_commands import MoveCommand
from .base_commands import OperationCommand
from .contour_commands import CloseContour
from .contour_commands import ContourLine
from .contour_commands import ContourStart
from .hop_core import EasySnapXY
from .hop_core import EasySnapZ
from .hop_core import HopsSystemVars
from .hop_macros import FreeFormPocket

if TYPE_CHECKING:
    from compas_timber.fabrication import JackRafterCut


class CompensationMode(IntEnum):
    """Tool position relative to path.

    Attributes:
    -----------
    CENTER : int
        Centered on path (0)
    LEFT : int
        Left side of path (1)
    RIGHT : int
        Right side of path (2)

    """

    CENTER = 0
    LEFT = 1
    RIGHT = 2

    def __str__(self):
        return str(self.value)


class LeadInOutMode(IntEnum):
    """Lead in method.

    Attributes:
    -----------
    NONE : int
        Straight into part at starting point (0)
    LINEAR : int
        Tangential extension based on lead_in_factor (1)
    TANGENT : int
        Tangential extension with radius based on lead_in_factor (2)
    LATERAL : int
        Smooth lead in with Z interpolation (3)
    """

    NONE = 0
    LINEAR = 1
    TANGENT = 2
    LATERAL = 3

    def __str__(self):
        return str(self.value)


class ProcessMode(IntEnum):
    """Machining direction control.

    Attributes:
    -----------
    NO_CHANGE : int
        No change in machining direction (0)
    WITH_ROTATION : int
        With rotation (climb cut) (1)
    AGAINST_ROTATION : int
        Against rotation (conventional cut) (2)
    WITH_ROTATION_MIRROR : int
        With rotation using mirror tool (3)
    AGAINST_ROTATION_MIRROR : int
        Against rotation using mirror tool (4)
    """

    # TODO: SAEGEN and SP have different values for each mode, need to clarify

    NO_CHANGE = 0
    WITH_ROTATION = 1
    AGAINST_ROTATION = 2
    WITH_ROTATION_MIRROR = 3
    AGAINST_ROTATION_MIRROR = 4

    def __str__(self):
        return str(self.value)


class StartPoint(MoveCommand):
    """HOPS start point (SP) command definition.

    Represents a milling starting point with all associated parameters.

    Parameters:
    -----------
    x : float
        X-coordinate of the starting point
    y : float
        Y-coordinate of the starting point
    z : float
        Z-coordinate (milling depth), can reference top/bottom edge or relative
    radius_compensation : Optional[CompensationMode]
        Tool position relative to path. See CompensationMode enum for options. If None, defaults to CompensationMode.CENTER
        var: "rk"
    lead_in_mode : Optional[LeadInOutMode]
        Lead in mode. See LeadInOutMode enum for options. If None, defaults to LeadInOutMode.NONE
        var: "ab"
    lead_in_factor : Optional[float]
        Lead in factor. If None, defaults to _ANF variable from tool manager
        var: "ANF"
    distance_to_contour : Optional[float]
        Distance offset to contour in mm. Positive = outside, Negative = inside
        var: "dc"
    offset_angle : Optional[float]
        Machine-specific additive angle for correct C-axis positioning
        var: "Oa"
    tip_angle : Optional[float]
        Tip angle offset for beveled milling (based on vertical normal position)
        var: "Ta"
    easy_snap_xy : Optional[EasySnapXY]
        EasySnapXY corner snap mode for XY movement. See EasySnapXY enum for options. If None, defaults to EasySnapXY.DISABLED
        var: "Es"
    easy_snap_z : Optional[EasySnapZ]
        EasySnapZ Z-axis reference mode for depth calculations. See EasySnapZ enum for options. If None, defaults to EasySnapZ.RELATIVE
        var: "Esz"
    process_mode : Optional[ProcessMode]
        Machining direction control. See ProcessMode enum for options. If None, defaults to ProcessMode.NO_CHANGE
        var: "Pm"
    milling_steps : Optional[int]
        Number of milling steps to divide depth into multiple levels. If None, defaults to 1 (single pass)
        var: "Fm"
    depth_per_level : Optional[float]
        Depth per level when using multiple steps (overrides milling_steps if used)
        var: "Zs"
    excess_depth : Optional[float]
        Additional depth beyond programmed depth for exact chip cut. Only if tip_angle is not zero.
        var: "Us"
    interpolation_with_rot_axis : bool
        Enable smooth Z-axis lead in to starting point
        var: "Cm"
    activate_laser : bool
        If True, milling path is also used as laser path
        var: "I"
    start_correction_above : bool
        If True, radius compensation removed above milling depth (default)
    tilt_angle : Optional[float]
        C-axis tilt angle for beveled milling (based on vertical normal position)
        Positive = tip toward part, Negative = tip away from part
    excess_length : Optional[float]
        Depth influence in direction of tipped tool for exact chip cut
    axial_lead_in_out : bool
        If True, lead in/out movements occur on tilted plane
    axial_distance : float
        Retraction distance for axial lead in/out (divided by milling_steps)
    distance_to_view : float
        In the case of the interpolative Z infeed, the milling path begins at "Distance to view" above (positive value) the defined plane


    Example:
    ---------
    SP(68.0,-35.546,20,0,0,_ANF,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)
    SP(0,0,0,1,1,_ANF,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0.5)
    """

    def __init__(
        self,
        x: Optional[float] = 0.0,
        y: Optional[float] = 0.0,
        z: Optional[float] = 0.0,
        radius_compensation: Optional[CompensationMode] = CompensationMode.CENTER,
        lead_in_mode: Optional[LeadInOutMode] = LeadInOutMode.NONE,
        lead_in_factor: Optional[float] = HopsSystemVars.LEAD_IN_OUT_FACTOR,
        distance_to_contour: Optional[float] = 0.0,
        offset_angle: Optional[float] = 0.0,
        tip_angle: Optional[float] = 0.0,
        easy_snap_xy: Optional[EasySnapXY] = EasySnapXY.DISABLED,
        easy_snap_z: Optional[EasySnapZ] = EasySnapZ.RELATIVE,
        process_mode: Optional[ProcessMode] = ProcessMode.NO_CHANGE,
        milling_steps: Optional[int] = 0,
        depth_per_level: Optional[float] = 0.0,
        excess_depth: Optional[float] = 0.0,
        interpolation_with_rot_axis: Optional[bool] = False,
        activate_laser: Optional[bool] = False,
        start_correction_above: Optional[bool] = True,
        tilt_angle: Optional[float] = 0.0,
        excess_length: Optional[float] = 0.0,
        axial_lead_in_out: Optional[bool] = False,
        axial_distance: Optional[float] = 0.0,
        distance_to_view: Optional[float] = 0.0,
    ):
        super().__init__()
        self.x = x
        self.y = y
        self.z = z
        self.radius_compensation = radius_compensation
        self.lead_in_mode = lead_in_mode
        self.lead_in_factor = lead_in_factor
        self.distance_to_contour = distance_to_contour
        self.offset_angle = offset_angle
        self.tip_angle = tip_angle
        self.easy_snap_xy = easy_snap_xy
        self.easy_snap_z = easy_snap_z
        self.process_mode = process_mode
        self.milling_steps = milling_steps
        self.depth_per_level = depth_per_level
        self.excess_depth = excess_depth
        self.interpolation_with_rot_axis = interpolation_with_rot_axis
        self.activate_laser = activate_laser
        self.start_correction_above = start_correction_above
        self.tilt_angle = tilt_angle
        self.excess_length = excess_length
        self.axial_lead_in_out = axial_lead_in_out
        self.axial_distance = axial_distance
        self.distance_to_view = distance_to_view

    def _to_hop_line(self):
        lead_in_factor_str = self.lead_in_factor if self.lead_in_factor is not None else "_ANF"
        params = [
            self.x,
            self.y,
            self.z,
            self.radius_compensation,
            self.lead_in_mode,
            lead_in_factor_str,
            self.distance_to_contour,
            self.offset_angle,
            self.tip_angle,
            self.easy_snap_xy,
            self.easy_snap_z,
            self.process_mode,
            self.milling_steps,
            self.depth_per_level,
            self.excess_depth,
            int(self.interpolation_with_rot_axis),
            int(self.activate_laser),
            int(self.start_correction_above),
            self.tilt_angle,
            self.excess_length,
            int(self.axial_lead_in_out),
            self.axial_distance,
            self.distance_to_view,
        ]
        return f"SP({','.join(map(str, params))})"

    @classmethod
    def from_hop_line(cls, line: str) -> "StartPoint":
        """Parse SP command from HOPS line.

        Parameters:
        -----------
        line : str
            HOPS SP(...) command line

        Returns:
        -----------
        :class:`StartPoint`
            Parsed StartPoint instance
        """
        # Match 23 parameters, allowing optional whitespace after commas
        pattern = (
            r"SP\("
            r"([-+]?\d+\.?\d*),\s*"  # x
            r"([-+]?\d+\.?\d*),\s*"  # y
            r"([-+]?\d+\.?\d*),\s*"  # z
            r"([-+]?\d+),\s*"  # radius_compensation
            r"([-+]?\d+),\s*"  # lead_in_mode
            r"([-+]?\d+\.?\d*|_ANF),\s*"  # lead_in_factor
            r"([-+]?\d+\.?\d*),\s*"  # distance_to_contour
            r"([-+]?\d+\.?\d*),\s*"  # offset_angle
            r"([-+]?\d+\.?\d*),\s*"  # tip_angle
            r"([-+]?\d+),\s*"  # easy_snap_xy
            r"([-+]?\d+),\s*"  # easy_snap_z
            r"([-+]?\d+),\s*"  # process_mode
            r"([-+]?\d+),\s*"  # milling_steps
            r"([-+]?\d+\.?\d*),\s*"  # depth_per_level
            r"([-+]?\d+\.?\d*),\s*"  # excess_depth
            r"([-+]?\d+),\s*"  # interpolation_with_rot_axis
            r"([-+]?\d+),\s*"  # activate_laser
            r"([-+]?\d+),\s*"  # start_correction_above
            r"([-+]?\d+\.?\d*),\s*"  # tilt_angle
            r"([-+]?\d+\.?\d*),\s*"  # excess_length
            r"([-+]?\d+),\s*"  # axial_lead_in_out
            r"([-+]?\d+\.?\d*),\s*"  # axial_distance
            r"([-+]?\d+\.?\d*)"  # distance_to_view
            r"\)"
        )

        match = re.match(pattern, line.strip())
        if match:
            lead_in_factor = None if match.group(6) == "_ANF" else float(match.group(6))
            return cls(
                x=float(match.group(1)),
                y=float(match.group(2)),
                z=float(match.group(3)),
                radius_compensation=CompensationMode(int(match.group(4))),
                lead_in_mode=LeadInOutMode(int(match.group(5))),
                lead_in_factor=lead_in_factor,
                distance_to_contour=float(match.group(7)),
                offset_angle=float(match.group(8)),
                tip_angle=float(match.group(9)),
                easy_snap_xy=EasySnapXY(int(match.group(10))),
                easy_snap_z=EasySnapZ(int(match.group(11))),
                process_mode=ProcessMode(int(match.group(12))),
                milling_steps=int(match.group(13)),
                depth_per_level=float(match.group(14)),
                excess_depth=float(match.group(15)),
                interpolation_with_rot_axis=bool(int(match.group(16))),
                activate_laser=bool(int(match.group(17))),
                start_correction_above=bool(int(match.group(18))),
                tilt_angle=float(match.group(19)),
                excess_length=float(match.group(20)),
                axial_lead_in_out=bool(int(match.group(21))),
                axial_distance=float(match.group(22)),
                distance_to_view=float(match.group(23)),
            )
        raise ValueError(f"Invalid SP line: {line}")


class G01(MoveCommand):
    """HOPS G01 linear interpolation movement command.

    Represents a single G01 movement with all associated parameters.

    Parameters:
    -----------
    x : float
        X-coordinate of the target point (absolute)
    y : float
        Y-coordinate of the target point (absolute)
    z : float
        Z-coordinate/milling depth. Interpretation depends on z_reference_mode:
        - TOP_EDGE: Reference from top edge
        - BOTTOM_EDGE: Reference from bottom edge
        - RELATIVE: Relative/incremental (0 = no Z change, maintain current depth)
    corner_radius : float
        Corner radius in mm for rounded transitions (0 = sharp corner)
    easy_snap_xy : EasySnapXY
        Corner snap mode for XY movement. See EasySnapXY enum for options. If None, defaults to EasySnapXY.DISABLED
    easy_snap_z : EasySnapZ
        Z-axis reference mode for depth calculations. See EasySnapZ enum for options. If None, defaults to EasySnapZ.RELATIVE

    Example:
    ---------
    G01(1028.902,-157.471,-59.321,0,0,2)  # Plunge 59.321mm down (relative Z)
    G01(1028.902,-152.471,0,0,0,2)        # Move in XY, Z=0 means keep current depth
    G01(155,137.805,0,0,0,2)              # Move in XY at same depth
    G01(155,137.805,5,5,0,2)              # Move in XY, rise 5mm, with 5mm corner radius
    """

    def __init__(
        self,
        x: float,
        y: float,
        z: float,
        corner_radius: Optional[float] = 0,
        easy_snap_xy: Optional[EasySnapXY] = EasySnapXY.DISABLED,
        easy_snap_z: Optional[EasySnapZ] = EasySnapZ.RELATIVE,
    ):
        super().__init__()
        self.x = x
        self.y = y
        self.z = z
        self.corner_radius = corner_radius
        self.easy_snap_xy = easy_snap_xy
        self.easy_snap_z = easy_snap_z

    def _to_hop_line(self):
        return f"G01({self.x},{self.y},{self.z},{self.corner_radius},{self.easy_snap_xy},{int(self.easy_snap_z)})"

    @classmethod
    def from_hop_line(cls, line: str) -> "G01":
        """Parse G01 command from HOPS line.

        Parameters:
        -----------
        line : str
            HOPS G01(...) command line

        Returns:
        -----------
        :class:`G01`
            Parsed G01 instance
        """
        # Match 6 parameters, allowing optional whitespace after commas
        pattern = (
            r"G01\("
            r"([-+]?\d+\.?\d*),\s*"  # x
            r"([-+]?\d+\.?\d*),\s*"  # y
            r"([-+]?\d+\.?\d*),\s*"  # z
            r"([-+]?\d+\.?\d*),\s*"  # corner_radius
            r"([-+]?\d+),\s*"  # easy_snap_xy
            r"([-+]?\d+)"  # easy_snap_z
            r"\)"
        )

        match = re.match(pattern, line.strip())
        if match:
            return cls(
                x=float(match.group(1)),
                y=float(match.group(2)),
                z=float(match.group(3)),
                corner_radius=float(match.group(4)),
                easy_snap_xy=EasySnapXY(int(match.group(5))),
                easy_snap_z=EasySnapZ(int(match.group(6))),
            )
        raise ValueError(f"Invalid G01 line: {line}")


class G02M(MoveCommand):
    """HOPS G02M clockwise arc with center point command.

    Represents a clockwise arc movement (G2) with explicit center point specification.
    The 'M' suffix indicates the arc is defined using a center point rather than radius.

    Parameters:
    -----------
    x : float
        X-coordinate of arc end point (absolute)
    y : float
        Y-coordinate of arc end point (absolute)
    z : float
        Z-coordinate/milling depth at end point
    mx : float
        X-coordinate of arc center point
    my : float
        Y-coordinate of arc center point
    corner_radius : float
        Corner radius in mm for transition to next element (0 = sharp corner)
    easy_snap_xy : EasySnapXY
        Corner snap mode for XY movement. See EasySnapXY enum for options. If None, defaults to EasySnapXY.DISABLED
    easy_snap_z : EasySnapZ
        Z-axis reference mode for depth calculations. See EasySnapZ enum for options. If None, defaults to EasySnapZ.RELATIVE
    easy_snap_center : int
        Easy snap mode for center point X/Y (0 = disabled)

    Example:
    ---------
    G02M(89.001,22.91,0,96.638,22.91,0,0,2,0)  # Clockwise arc to (89.001,22.91) with center at (96.638,22.91)
    """

    def __init__(
        self,
        x: float,
        y: float,
        z: float,
        mx: float,
        my: float,
        corner_radius: Optional[float] = 0,
        easy_snap_xy: Optional[EasySnapXY] = EasySnapXY.DISABLED,
        easy_snap_z: Optional[EasySnapZ] = EasySnapZ.RELATIVE,
        easy_snap_center: Optional[int] = 0,
    ):
        super().__init__()
        self.x = x
        self.y = y
        self.z = z
        self.mx = mx
        self.my = my
        self.corner_radius = corner_radius
        self.easy_snap_xy = easy_snap_xy
        self.easy_snap_z = easy_snap_z
        self.easy_snap_center = easy_snap_center

    def _to_hop_line(self):
        return f"G02M({self.x},{self.y},{self.z},{self.mx},{self.my},{self.corner_radius},{int(self.easy_snap_xy)},{int(self.easy_snap_z)},{self.easy_snap_center})"

    @classmethod
    def from_hop_line(cls, line: str) -> "G02M":
        """Parse G02M command from HOPS line.

        Parameters:
        -----------
        line : str
            HOPS G02M(...) command line

        Returns:
        -----------
        :class:`G02M`
            Parsed G02M instance
        """
        # Match 9 parameters, allowing optional whitespace after commas
        pattern = (
            r"G02M\("
            r"([-+]?\d+\.?\d*),\s*"  # x
            r"([-+]?\d+\.?\d*),\s*"  # y
            r"([-+]?\d+\.?\d*),\s*"  # z
            r"([-+]?\d+\.?\d*),\s*"  # mx
            r"([-+]?\d+\.?\d*),\s*"  # my
            r"([-+]?\d+\.?\d*),\s*"  # corner_radius
            r"([-+]?\d+),\s*"  # easy_snap_xy
            r"([-+]?\d+),\s*"  # easy_snap_z
            r"([-+]?\d+)"  # easy_snap_center
            r"\)"
        )

        match = re.match(pattern, line.strip())
        if match:
            return cls(
                x=float(match.group(1)),
                y=float(match.group(2)),
                z=float(match.group(3)),
                mx=float(match.group(4)),
                my=float(match.group(5)),
                corner_radius=float(match.group(6)),
                easy_snap_xy=EasySnapXY(int(match.group(7))),
                easy_snap_z=EasySnapZ(int(match.group(8))),
                easy_snap_center=int(match.group(9)),
            )
        raise ValueError(f"Invalid G02M line: {line}")


class G03M(MoveCommand):
    """HOPS G03M counter-clockwise arc with center point command.

    Represents a counter-clockwise arc movement (G3) with explicit center point specification.
    The 'M' suffix indicates the arc is defined using a center point rather than radius.

    Parameters:
    -----------
    x : float
        X-coordinate of arc end point (absolute)
    y : float
        Y-coordinate of arc end point (absolute)
    z : float
        Z-coordinate/milling depth at end point
    mx : float
        X-coordinate of arc center point
    my : float
        Y-coordinate of arc center point
    corner_radius : float
        Corner radius in mm for transition to next element (0 = sharp corner)
    easy_snap_xy : EasySnapXY
        Corner snap mode for XY movement. See EasySnapXY enum for options. If None, defaults to EasySnapXY.DISABLED
    easy_snap_z : EasySnapZ
        Z-axis reference mode for depth calculations. See EasySnapZ enum for options. If None, defaults to EasySnapZ.RELATIVE
    easy_snap_center : int
        Easy snap mode for center point X/Y (0 = disabled)

    Example:
    ---------
    G03M(104.274,7.637,0,96.638,7.637,0,0,2,0)  # Counter-clockwise arc to (104.274,7.637) with center at (96.638,7.637)
    """

    def __init__(
        self,
        x: float,
        y: float,
        z: float,
        mx: float,
        my: float,
        corner_radius: Optional[float] = 0,
        easy_snap_xy: Optional[EasySnapXY] = EasySnapXY.DISABLED,
        easy_snap_z: Optional[EasySnapZ] = EasySnapZ.RELATIVE,
        easy_snap_center: Optional[int] = 0,
    ):
        super().__init__()
        self.x = x
        self.y = y
        self.z = z
        self.mx = mx
        self.my = my
        self.corner_radius = corner_radius
        self.easy_snap_xy = easy_snap_xy
        self.easy_snap_z = easy_snap_z
        self.easy_snap_center = easy_snap_center

    def _to_hop_line(self):
        return f"G03M({self.x},{self.y},{self.z},{self.mx},{self.my},{self.corner_radius},{int(self.easy_snap_xy)},{int(self.easy_snap_z)},{self.easy_snap_center})"

    @classmethod
    def from_hop_line(cls, line: str) -> "G03M":
        """Parse G03M command from HOPS line.

        Parameters:
        -----------
        line : str
            HOPS G03M(...) command line

        Returns:
        -----------
        :class:`G03M`
            Parsed G03M instance
        """
        # Match 9 parameters, allowing optional whitespace after commas
        pattern = (
            r"G03M\("
            r"([-+]?\d+\.?\d*),\s*"  # x
            r"([-+]?\d+\.?\d*),\s*"  # y
            r"([-+]?\d+\.?\d*),\s*"  # z
            r"([-+]?\d+\.?\d*),\s*"  # mx
            r"([-+]?\d+\.?\d*),\s*"  # my
            r"([-+]?\d+\.?\d*),\s*"  # corner_radius
            r"([-+]?\d+),\s*"  # easy_snap_xy
            r"([-+]?\d+),\s*"  # easy_snap_z
            r"([-+]?\d+)"  # easy_snap_center
            r"\)"
        )

        match = re.match(pattern, line.strip())
        if match:
            return cls(
                x=float(match.group(1)),
                y=float(match.group(2)),
                z=float(match.group(3)),
                mx=float(match.group(4)),
                my=float(match.group(5)),
                corner_radius=float(match.group(6)),
                easy_snap_xy=EasySnapXY(int(match.group(7))),
                easy_snap_z=EasySnapZ(int(match.group(8))),
                easy_snap_center=int(match.group(9)),
            )
        raise ValueError(f"Invalid G03M line: {line}")


class EndPoint(MoveCommand):
    """HOPS end point (EP) command definition.

    Represents the end of a milling path with associated parameters.

    Parameters:
    -----------
    lead_out_mode : Optional[LeadInOutMode]
        Lead out method. If None, defaults to LeadInOutMode.NONE
    lead_out_factor : float
        Lead out factor. If None, defaults to _ANF variable from tool manager
    reverse_direction : bool
        If True, reverses the machining direction at the end point

    Example:
    -----------
    EP(3,3.000,0)
    """

    def __init__(
        self,
        lead_out_mode: Optional[LeadInOutMode] = LeadInOutMode.NONE,
        lead_out_factor: Optional[float] = HopsSystemVars.LEAD_IN_OUT_FACTOR,
        reverse_direction: bool = False,
    ):
        super().__init__()
        self.lead_out_mode = lead_out_mode
        self.lead_out_factor = lead_out_factor
        self.reverse_direction = reverse_direction

    def _to_hop_line(self):
        return f"EP({self.lead_out_mode},{self.lead_out_factor},{int(self.reverse_direction)})"

    @classmethod
    def from_hop_line(cls, line: str) -> "EndPoint":
        """Parse EP command from HOPS line.

        Parameters:
        -----------
        line : str
            HOPS EP(...) command line

        Returns:
        -----------
        :class:`EndPoint`
            Parsed EndPoint instance
        """
        # Match 3 parameters, allowing optional whitespace after commas
        pattern = (
            r"EP\("
            r"([-+]?\d+),\s*"  # lead_out_mode
            r"([-+]?\d+\.?\d*|_ANF),\s*"  # lead_out_factor
            r"([-+]?\d+)"  # reverse_direction
            r"\)"
        )

        match = re.match(pattern, line.strip())
        if match:
            lead_out_factor = None if match.group(2) == "_ANF" else float(match.group(2))
            return cls(
                lead_out_mode=LeadInOutMode(int(match.group(1))),
                lead_out_factor=lead_out_factor,
                reverse_direction=bool(int(match.group(3))),
            )
        raise ValueError(f"Invalid EP line: {line}")


# ==================== Machining Command Classes ====================


class MillingOperation(OperationCommand):
    """Represents a milling path sequence (SP + moves + EP).

    MillingOperation encapsulates a complete milling operation including the start point, moves, and end point.
    Moves can be linear (G01) or arc movements (G02M, G03M).

    Parameters:
    -----------
    start_point : :class:`StartPoint`
        StartPoint instance with milling parameters
    moves : List[Union[:class:`G01`, :class:`G02M`, :class:`G03M`]]
        List of move instances representing linear interpolation or arc movements
    end_point : :class:`EndPoint`
        EndPoint instance with lead out parameters

    Example:
    ---------
    MillingOperation(
        SP(300,-301.264,-27.229,1,3,3.000,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
        [G01(500.123,-100.456,-25.000,0,0,2),
        G02M(89.001,22.91,0,96.638,22.91,0,0,2,0),
        G03M(104.274,7.637,0,96.638,7.637,0,0,2,0)],
        EP(3,3.000,0)
    )
    """

    OPERATION_TYPE = "MILLING"

    def __init__(self, start_point: StartPoint, moves: List[Union[G01, G02M, G03M]], end_point: EndPoint):
        super().__init__()
        self.start_point = start_point
        self.moves = moves
        self.end_point = end_point

    def __repr__(self) -> str:
        return f"MillingOperation(start={self.start_point.x:.1f},{self.start_point.y:.1f}, moves={len(self.moves)})"

    def _to_hop_line(self) -> str:
        """Generate HOPS command lines for the milling operation.

        Returns the complete milling path as a multi-line string containing
        the start point, all moves, and the end point.
        """
        return "\n".join(self._to_lines())

    def _to_lines(self) -> List[str]:
        """Generate HOPS command lines for the milling operation."""
        lines = [str(self.start_point)]
        if not isinstance(self.moves, list):
            self.moves = [self.moves]
        for move in self.moves:
            lines.append(str(move))
        lines.append(str(self.end_point))
        return lines

    @classmethod
    def from_polyline(
        cls,
        points: List[tuple],
        radius_compensation: Optional[CompensationMode] = CompensationMode.CENTER,
        lead_in_mode: Optional[LeadInOutMode] = LeadInOutMode.NONE,
        lead_in_factor: Optional[float] = None,
        lead_out_mode: Optional[LeadInOutMode] = LeadInOutMode.NONE,
        lead_out_factor: Optional[float] = None,
        easy_snap_z: Optional[EasySnapZ] = EasySnapZ.RELATIVE,
    ) -> "MillingOperation":
        """Create a MillingOperation from a sequence of (x, y, z) points.

        The first point becomes the StartPoint (SP), each subsequent point
        becomes a G01 linear move, and the operation is closed with an
        EndPoint (EP).

        Parameters:
        -----------
        points : List[tuple]
            Sequence of (x, y, z) coordinate tuples. Must contain at least
            two points. Coordinates are in the active work-plane frame.
        radius_compensation : CompensationMode
            Tool offset mode applied at the StartPoint. Defaults to CENTER.
        lead_in_mode : LeadInOutMode
            Lead-in strategy for the StartPoint. Defaults to NONE.
        lead_in_factor : Optional[float]
            Lead-in factor. None serializes as _ANF (tool-manager default).
        lead_out_mode : LeadInOutMode
            Lead-out strategy for the EndPoint. Defaults to NONE.
        lead_out_factor : Optional[float]
            Lead-out factor. None serializes as _ANF (tool-manager default).
        easy_snap_z : EasySnapZ
            Z-axis reference mode applied to every move command. Defaults to RELATIVE.

        Returns:
        --------
        MillingOperation
        """
        if len(points) < 2:
            raise ValueError("from_polyline requires at least 2 points (start + one move).")

        x0, y0, z0 = points[0]
        start = StartPoint(
            x=x0,
            y=y0,
            z=z0,
            radius_compensation=radius_compensation,
            lead_in_mode=lead_in_mode,
            lead_in_factor=lead_in_factor,
            easy_snap_z=easy_snap_z,
        )

        moves = [G01(x=x, y=y, z=z, easy_snap_z=easy_snap_z) for x, y, z in points[1:]]

        end = EndPoint(lead_out_mode=lead_out_mode, lead_out_factor=lead_out_factor)

        return cls(start_point=start, moves=moves, end_point=end)


class SawingOperation(OperationCommand):
    """Represents a saw cutting operation (SAEGEN).

    Sawing cuts a straight line from point 1 to point 2 with full control over
    cutting parameters including lead in/out, offsets, tilt angles, and precuts.

    SAEGEN format (17 parameters):
        SAEGEN(sx,sy,z1, ex,ey,z2, lead_in,lead_out,parallel_offset, fit_in,tilt_angle, groove_pos,mode,precut_depth, precut_offset,p16,p17)

    Example:
        SAEGEN(852.354,-0.428,-70.735, 849.565,139.941,-70.735, 0,0,0, 1,-7.57, 0,0,0, 2,0,0)

    Parameters:
    -----------
    sx : float
        Starting position X-coordinate based on current reference point
    sy : float
        Starting position Y-coordinate based on current reference point
    sz : float
        Starting position Z-coordinate based on current reference point
    ex : float
        Ending position X-coordinate based on current reference point
    ey : float
        Ending position Y-coordinate based on current reference point
    ez : float
        Ending position Z-coordinate based on current reference point'
    radius_compensation : Optional[CompensationMode]
        Tool position relative to path. See CompensationMode enum for options. If None, defaults to CompensationMode.CENTER
    fit_in : Optional[Obool]
        Saw blade fitting mode:
        True = Fit saw blade into contour (default)
        False = Do not fit saw blade into contour
    lead_in_out : Optional[float]
        Extending the length of the sawing cut before and after the contour
    process_mode : Optional[ProcessMode]
        Machining direction control. See ProcessMode enum for options. If None, defaults to ProcessMode.NO_CHANGE
    tilt_angle : Optional[float]
        C-axis tilt angle for beveled sawing in degrees:
        0 = vertical cut
        Positive = tip toward part
        Negative = tip away from part (default: 0.0)
    z_level : Optional[float]
        Reference height offset for sawing operation
    easy_snap_xy_start : Optional[EasySnapXY]
        Corner snap mode for XY movement at start point. See EasySnapXY enum for options. If None, defaults to EasySnapXY.DISABLED
    easy_snap_xy_end : Optional[EasySnapXY]
        Corner snap mode for XY movement at end point. See EasySnapXY enum for options. If None, defaults to EasySnapXY.DISABLED
    easy_snap_z : Optional[EasySnapZ]
        Z-axis reference mode for depth calculations. See EasySnapZ enum for options. If None, defaults to EasySnapZ.RELATIVE
    """

    OPERATION_TYPE = "SAWING"

    def __init__(
        self,
        sx: float,
        sy: float,
        sz: float,
        ex: float,
        ey: float,
        ez: float,
        radius_compensation: Optional[CompensationMode] = CompensationMode.CENTER,
        fit_in: Optional[bool] = False,
        lead_in_out: Optional[float] = HopsSystemVars.TOOL_RADIUS,
        process_mode: Optional[ProcessMode] = ProcessMode.WITH_ROTATION,
        tilt_angle: Optional[float] = 0.0,
        z_level: Optional[float] = 0.0,
        easy_snap_xy_start: Optional[EasySnapXY] = EasySnapXY.DISABLED,
        easy_snap_xy_end: Optional[EasySnapXY] = EasySnapXY.DISABLED,
        easy_snap_z: Optional[EasySnapZ] = EasySnapZ.RELATIVE,
    ):
        super().__init__()
        self._sx = None
        self._sy = None
        self._sz = None
        self._ex = None
        self._ey = None
        self._ez = None
        self._radius_compensation = None
        self._fit_in = None
        self._lead_in_out = None
        self._process_mode = None
        self._tilt_angle = None
        self._z_level = None
        self._easy_snap_xy_start = None
        self._easy_snap_xy_end = None
        self._easy_snap_z = None

        self.sx = sx
        self.sy = sy
        self.sz = sz
        self.ex = ex
        self.ey = ey
        self.ez = ez
        self.radius_compensation = radius_compensation
        self.fit_in = fit_in
        self.lead_in_out = lead_in_out
        self.process_mode = process_mode
        self.tilt_angle = tilt_angle
        self.z_level = z_level
        self.easy_snap_xy_start = easy_snap_xy_start
        self.easy_snap_xy_end = easy_snap_xy_end
        self.easy_snap_z = easy_snap_z

    def __repr__(self) -> str:
        return f"SawingOperation(from=({self.sx:.1f},{self.sy:.1f},{self.sz:.1f}), to=({self.ex:.1f},{self.ey:.1f},{self.ez:.1f}), tilt={self.tilt_angle}°)"

    @property
    def sx(self) -> float:
        """Starting position X-coordinate."""
        return self._sx

    @sx.setter
    def sx(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"sx must be a number, got {type(value).__name__}")
        self._sx = float(value)

    @property
    def sy(self) -> float:
        """Starting position Y-coordinate."""
        return self._sy

    @sy.setter
    def sy(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"sy must be a number, got {type(value).__name__}")
        self._sy = float(value)

    @property
    def sz(self) -> float:
        """Starting position Z-coordinate."""
        return self._sz

    @sz.setter
    def sz(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"sz must be a number, got {type(value).__name__}")
        self._sz = float(value)

    @property
    def ex(self) -> float:
        """Ending position X-coordinate."""
        return self._ex

    @ex.setter
    def ex(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"ex must be a number, got {type(value).__name__}")
        self._ex = float(value)

    @property
    def ey(self) -> float:
        """Ending position Y-coordinate."""
        return self._ey

    @ey.setter
    def ey(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"ey must be a number, got {type(value).__name__}")
        self._ey = float(value)

    @property
    def ez(self) -> float:
        """Ending position Z-coordinate."""
        return self._ez

    @ez.setter
    def ez(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"ez must be a number, got {type(value).__name__}")
        self._ez = float(value)

    @property
    def radius_compensation(self) -> CompensationMode:
        """Tool position relative to path."""
        return self._radius_compensation

    @radius_compensation.setter
    def radius_compensation(self, value: Optional[CompensationMode]):
        if isinstance(value, CompensationMode):
            value = value.value
        elif not isinstance(value, int):
            raise TypeError(f"radius_compensation must be CompensationMode enum or int, got {type(value).__name__}")

        if not 0 <= value <= 2:
            raise ValueError(f"radius_compensation must be between 0 and 2, got {value}")

        self._radius_compensation = CompensationMode(value)

    @property
    def fit_in(self) -> bool:
        """Saw blade fitting mode."""
        return self._fit_in

    @fit_in.setter
    def fit_in(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError(f"fit_in must be bool, got {type(value).__name__}")
        self._fit_in = value

    @property
    def lead_in_out(self) -> float:
        """Extending the length of the sawing cut before and after the contour."""
        return self._lead_in_out

    @lead_in_out.setter
    def lead_in_out(self, value: float):
        if not isinstance(value, (int, float)):
            # raise TypeError(f"lead_in_out must be a number, got {type(value).__name__}")
            self._lead_in_out = value
        else:
            self._lead_in_out = float(value)

    @property
    def process_mode(self) -> ProcessMode:
        """Machining direction control."""
        return self._process_mode

    @process_mode.setter
    def process_mode(self, value: Optional[ProcessMode]):
        if isinstance(value, ProcessMode):
            value = value.value
        elif not isinstance(value, int):
            raise TypeError(f"process_mode must be ProcessMode enum or int, got {type(value).__name__}")

        if not 0 <= value <= 4:
            raise ValueError(f"process_mode must be between 0 and 4, got {value}")

        self._process_mode = ProcessMode(value)

    @property
    def tilt_angle(self) -> float:
        """C-axis tilt angle for beveled sawing in degrees."""
        return self._tilt_angle

    @tilt_angle.setter
    def tilt_angle(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"tilt_angle must be a number, got {type(value).__name__}")
        self._tilt_angle = float(value)

    @property
    def z_level(self) -> float:
        """Reference height offset for sawing operation."""
        return self._z_level

    @z_level.setter
    def z_level(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"z_level must be a number, got {type(value).__name__}")
        self._z_level = float(value)

    @property
    def easy_snap_xy_start(self) -> int:
        """Corner snap mode for XY movement at start point (0-9)."""
        return self._easy_snap_xy_start

    @easy_snap_xy_start.setter
    def easy_snap_xy_start(self, value):
        if isinstance(value, EasySnapXY):
            value = value.value
        elif not isinstance(value, int):
            raise TypeError(f"easy_snap_xy_start must be EasySnapXY enum or int, got {type(value).__name__}")

        if not 0 <= value <= 9:
            raise ValueError(f"easy_snap_xy_start must be between 0 and 9, got {value}")

        self._easy_snap_xy_start = value

    @property
    def easy_snap_xy_end(self) -> int:
        """Corner snap mode for XY movement at end point (0-9)."""
        return self._easy_snap_xy_end

    @easy_snap_xy_end.setter
    def easy_snap_xy_end(self, value):
        if isinstance(value, EasySnapXY):
            value = value.value
        elif not isinstance(value, int):
            raise TypeError(f"easy_snap_xy_end must be EasySnapXY enum or int, got {type(value).__name__}")

        if not 0 <= value <= 10:
            raise ValueError(f"easy_snap_xy_end must be between 0 and 10, got {value}")

        self._easy_snap_xy_end = value

    @property
    def easy_snap_z(self) -> int:
        """Z-axis reference mode for depth calculations (0-2)."""
        return self._easy_snap_z

    @easy_snap_z.setter
    def easy_snap_z(self, value):
        if isinstance(value, EasySnapZ):
            value = value.value
        elif not isinstance(value, int):
            raise TypeError(f"easy_snap_z must be EasySnapZ enum or int, got {type(value).__name__}")

        if not 0 <= value <= 2:
            raise ValueError(f"easy_snap_z must be between 0 and 2, got {value}")

        self._easy_snap_z = value

    @classmethod
    def from_hop_line(cls, line: str) -> "SawingOperation":
        """Parse SAEGEN command from HOPS line.

        Parameters:
        -----------
        line : str
            HOPS SAEGEN(...) command line

        Returns:
        -----------
        :class:`SawingOperation`
            Parsed SawingOperation instance
        """
        # Match all 17 parameters (allow optional spaces after commas)
        pattern = (
            r"SAEGEN\(([-+]?\d+\.?\d*),\s*([-+]?\d+\.?\d*),\s*([-+]?\d+\.?\d*),\s*"
            r"([-+]?\d+\.?\d*),\s*([-+]?\d+\.?\d*),\s*([-+]?\d+\.?\d*),\s*"
            r"([-+]?\d+\.?\d*),\s*([-+]?\d+\.?\d*),\s*([-+]?\d+\.?\d*),\s*"
            r"([-+]?\d+\.?\d*),\s*([-+]?\d+\.?\d*),\s*([-+]?\d+\.?\d*),\s*"
            r"([-+]?\d+\.?\d*),\s*([-+]?\d+\.?\d*),\s*([-+]?\d+\.?\d*),\s*"
            r"([-+]?\d+\.?\d*),\s*([-+]?\d+\.?\d*)\)"
        )

        match = re.match(pattern, line.strip())
        if match:
            params = [float(match.group(i)) for i in range(1, 18)]
            return cls(
                sx=params[0],
                sy=params[1],
                sz=params[2],
                ex=params[3],
                ey=params[4],
                ez=params[5],
                radius_compensation=CompensationMode(int(params[6])),
                fit_in=bool(int(params[7])),
                lead_in_out=params[8],
                process_mode=ProcessMode(int(params[9])),
                tilt_angle=params[10],
                z_level=params[11],
                easy_snap_xy_start=EasySnapXY(int(params[12])),
                easy_snap_xy_end=EasySnapXY(int(params[13])),
                easy_snap_z=EasySnapZ(int(params[14])),
            )
        raise ValueError(f"Invalid SAEGEN line: {line}")

    def _to_hop_line(self) -> str:
        """Generate HOPS SAEGEN command line.

        Returns:
            Formatted SAEGEN(...) command string
        """

        # Format with intelligent number formatting (integers without decimals, floats with 3)
        def fmt(val):
            if isinstance(val, bool):
                return "1" if val else "0"
            if isinstance(val, (CompensationMode, ProcessMode)):
                return str(val.value)
            if isinstance(val, (int, float)):
                return str(int(val)) if val == int(val) else f"{val:.3f}"
            return str(val)

        return (
            f"SAEGEN({fmt(self.sx)},{fmt(self.sy)},{fmt(self.sz)},"
            f"{fmt(self.ex)},{fmt(self.ey)},{fmt(self.ez)},"
            f"{fmt(self.radius_compensation)},{fmt(self.fit_in)},{fmt(self.lead_in_out)},"
            f"{fmt(self.process_mode)},{fmt(self.tilt_angle)},{fmt(self.z_level)},"
            f"{fmt(self.easy_snap_xy_start)},{fmt(self.easy_snap_xy_end)},{fmt(self.easy_snap_z)},"
            f"{fmt(0)},{fmt(0)})"
        )

    @classmethod
    def from_jack_rafter_cut(cls, jack_rafter_cut: JackRafterCut):
        """Create a SawingOperation from a JackRafterCut instance.

        Parameters:
        -----------
        jack_rafter_cut : JackRafterCut
            JackRafterCut instance containing parameters for the sawing operation

        Returns:
        --------
        SawingOperation
        """
        # define reference side index for JackRafterCut
        ref_side_index = jack_rafter_cut.ref_side_index

        # This would probably work with only this reference side, but we can add more cases if needed
        if ref_side_index == 3:
            sx = jack_rafter_cut.start_x
            sy = jack_rafter_cut.start_y
            sz = jack_rafter_cut.start_depth

            angle = jack_rafter_cut.angle
            tilt_angle = jack_rafter_cut.inclination

            ex = sx + abs(sx) / math.tan(angle)
            ey = sy + abs(sx)
            ez = sz

            radius_compensation = CompensationMode.LEFT if jack_rafter_cut.orientation == "start" else CompensationMode.RIGHT
            easy_snap_xy_start = EasySnapXY.FRONT_LEFT

        return cls(
            sx=sx,
            sy=sy,
            sz=sz,
            ex=ex,
            ey=ey,
            ez=ez,
            radius_compensation=radius_compensation,
            fit_in=False,
            lead_in_out=HopsSystemVars.TOOL_RADIUS,
            process_mode=ProcessMode.WITH_ROTATION,
            tilt_angle=tilt_angle,
            z_level=-2.0,
            easy_snap_xy_start=easy_snap_xy_start,
            easy_snap_xy_end=EasySnapXY.RELATIVE,
            easy_snap_z=EasySnapZ.BOTTOM_EDGE,
        )


class SawingLengthAngleOperation(OperationCommand):
    """Represents a saw cut defined by start point, length, and angle using the HOPS macro call format.

    Serializes as:
        CALL _saege_lae_wi_V7 ( VAL SX:=...,SY:=...,SZ:=...,LAENGE:=...,SCHNITTWINKEL:=...,
            EZ:=...,BL:=...,EINPASSEN:=...,EL:=...,AL:=...,PARALLEL:=...,K:=...,KW:=...,
            BH:=0,RITZVERSATZ:=0,ESZ:=...,ESXY1:=...)

    Example:
        CALL _saege_lae_wi_V7 ( VAL SX:=-62.82,SY:=0,SZ:=-0,LAENGE:=ABS(-62/SIN(65.86)),
            SCHNITTWINKEL:=65.86,EZ:=-2,BL:=1,EINPASSEN:=0,EL:=_WZR,AL:=_WZR,
            PARALLEL:=0,K:=0,KW:=0,BH:=0,RITZVERSATZ:=0,ESZ:=0,ESXY1:=1)

    Parameters:
    -----------
    sx : float
        Starting X-coordinate (SX)
    sy : float
        Starting Y-coordinate (SY)
    sz : float
        Starting Z-coordinate (SZ)
    length : Union[float, str]
        Length of the cut in mm, or a HOPS formula string e.g. "ABS(-62/SIN(65.86))" (LAENGE)
    angle : float
        Cut angle in degrees (SCHNITTWINKEL)
    z_level : float
        Z depth at end of cut (EZ)
    radius_compensation : CompensationMode
        Blade side / tool position relative to path (BL). Defaults to LEFT.
    fit_in : bool
        Fit saw blade into contour (EINPASSEN). Default False.
    lead_in : Union[float, str]
        Lead-in length. Defaults to _WZR tool radius (EL).
    lead_out : Union[float, str]
        Lead-out length. Defaults to _WZR tool radius (AL).
    parallel_distance : float
        Parallel offset distance (PARALLEL).
    process_mode : int
        Mode / groove position (K).
    tilt_angle : float
        Tilt angle / Kippwinkel in degrees (KW).
    easy_snap_z : EasySnapZ
        Z-axis reference mode (ESZ).
    easy_snap_xy : EasySnapXY
        Corner snap mode for XY movement at start point (ESXY1).
    precut_depth : float
        Depth of the scoring blade pre-cut (BH). Default 0.
    precut_offset : float
        Lateral offset of the scoring blade relative to the main blade (RITZVERSATZ). Default 0.
    """

    OPERATION_TYPE = "SAWING"
    _MACRO_NAME = "_saege_lae_wi_V7"

    def __init__(
        self,
        sx: float,
        sy: float,
        sz: float,
        length: float,
        angle: float,
        z_level: Optional[float] = -2.0,
        radius_compensation: Optional[CompensationMode] = CompensationMode.LEFT,
        fit_in: Optional[bool] = False,
        lead_in: Optional[float] = HopsSystemVars.TOOL_RADIUS,
        lead_out: Optional[float] = HopsSystemVars.TOOL_RADIUS,
        parallel_distance: Optional[float] = 0.0,
        process_mode: Optional[ProcessMode] = ProcessMode.NO_CHANGE,
        tilt_angle: Optional[float] = 0.0,
        easy_snap_z: Optional[EasySnapZ] = EasySnapZ.TOP_EDGE,
        easy_snap_xy: Optional[EasySnapXY] = EasySnapXY.FRONT_LEFT,
        precut_depth: float = 0.0,
        precut_offset: float = 0.0,
    ):
        super().__init__()
        self.sx = sx
        self.sy = sy
        self.sz = sz
        self.length = length
        self.angle = angle
        self.z_level = z_level
        self.radius_compensation = radius_compensation
        self.fit_in = fit_in
        self.lead_in = lead_in
        self.lead_out = lead_out
        self.parallel_distance = parallel_distance
        self.process_mode = process_mode
        self.tilt_angle = tilt_angle
        self.easy_snap_z = easy_snap_z
        self.easy_snap_xy = easy_snap_xy
        self.precut_depth = precut_depth
        self.precut_offset = precut_offset

    def __repr__(self) -> str:
        return f"SawingLengthAngleOperation(sx={self.sx:.3f}, sy={self.sy:.3f}, sz={self.sz:.3f}, length={self.length}, angle={self.angle}°)"

    def _fmt(self, val) -> str:
        if isinstance(val, str):
            return val
        if isinstance(val, (EasySnapXY, EasySnapZ)):
            return str(int(val))
        if isinstance(val, CompensationMode):
            return str(val.value)
        if isinstance(val, bool):
            return "1" if val else "0"
        if isinstance(val, (int, float)):
            i = int(val)
            return str(i) if val == i else f"{val:.3f}"
        return str(val)

    def _to_hop_line(self) -> str:
        f = self._fmt
        return (
            f"CALL {self._MACRO_NAME} ( VAL "
            f"SX:={f(self.sx)},"
            f"SY:={f(self.sy)},"
            f"SZ:={f(self.sz)},"
            f"LAENGE:={f(self.length)},"
            f"SCHNITTWINKEL:={f(self.angle)},"
            f"EZ:={f(self.z_level)},"
            f"BL:={f(self.radius_compensation)},"
            f"EINPASSEN:={f(self.fit_in)},"
            f"EL:={f(self.lead_in)},"
            f"AL:={f(self.lead_out)},"
            f"PARALLEL:={f(self.parallel_distance)},"
            f"K:={f(self.process_mode)},"
            f"KW:={f(self.tilt_angle)},"
            f"BH:={f(self.precut_depth)},"
            f"RITZVERSATZ:={f(self.precut_offset)},"
            f"ESZ:={f(self.easy_snap_z)},"
            f"ESXY1:={f(self.easy_snap_xy)})"
        )

    @classmethod
    def from_hop_line(cls, line: str) -> "SawingLengthAngleOperation":
        """Parse a CALL _saege_lae_wi_V7 line into a SawingLengthAngleOperation."""

        def _get(name: str, s: str) -> str:
            m = re.search(rf"{name}:=([^,)]+)", s)
            if not m:
                raise ValueError(f"Missing parameter '{name}' in line: {s}")
            return m.group(1).strip()

        def _float(name: str, s: str) -> float:
            return float(_get(name, s))

        def _int(name: str, s: str) -> int:
            return int(float(_get(name, s)))

        s = line.strip()
        if not re.match(rf"CALL\s+{re.escape(cls._MACRO_NAME)}", s):
            raise ValueError(f"Not a {cls._MACRO_NAME} line: {line}")

        laenge_raw = _get("LAENGE", s)
        try:
            length: Union[float, str] = float(laenge_raw)
        except ValueError:
            length = laenge_raw

        def _lead(name: str, s: str) -> Union[float, str]:
            raw = _get(name, s)
            try:
                return float(raw)
            except ValueError:
                return raw

        return cls(
            sx=_float("SX", s),
            sy=_float("SY", s),
            sz=_float("SZ", s),
            length=length,
            angle=_float("SCHNITTWINKEL", s),
            z_level=_float("EZ", s),
            radius_compensation=CompensationMode(_int("BL", s)),
            fit_in=bool(_int("EINPASSEN", s)),
            lead_in=_lead("EL", s),
            lead_out=_lead("AL", s),
            parallel_distance=_float("PARALLEL", s),
            process_mode=_int("K", s),
            tilt_angle=_float("KW", s),
            easy_snap_z=EasySnapZ(_int("ESZ", s)),
            easy_snap_xy=EasySnapXY(_int("ESXY1", s)),
            precut_depth=_float("BH", s),
            precut_offset=_float("RITZVERSATZ", s),
        )


class DrillingOperation(OperationCommand):
    """Represents a horizontal drilling operation.

    Drilling creates holes at specific points.

    Parameters:
    -----------
    x : float
        X-coordinate of the drill position
    y : float
        Y-coordinate of the drill position
    z : float
        Z-coordinate of the drill position
    depth : float
        Drilling depth in mm. Positive or negative values depending on Z reference mode.
    diameter : float
        Drill bit diameter in mm. If None, defaults to tool diameter of the active tool (_WZD)
    drilling_flags : Optional[int]
        Additional drilling options as bitwise flags (not implemented)
    rotation : Optional[float]
        Rotation angle for angled drilling. Angle should be from 0 < rotation < 180 degrees
    tilt : Optional[float]
        Tilt angle for angled drilling. Angle should be from 0 < tilt < 90 degrees
    easy_snap_xy : Optional[EasySnapXY]
        EasySnapXY corner snap mode for XY movement. See EasySnapXY enum for options. If None, defaults to EasySnapXY.DISABLED
    easy_snap_z : Optional[EasySnapZ]
        EasySnapZ Z-axis reference mode for depth calculations. See EasySnapZ enum for options. If None, defaults to EasySnapZ.RELATIVE
    """

    OPERATION_TYPE = "DRILLING"

    def __init__(
        self,
        x: float,
        y: float,
        z: float,
        depth: Optional[float] = 0.0,
        diameter: Optional[float] = None,
        drilling_flags: Optional[int] = 0,
        rotation: Optional[float] = 0.0,
        tilt: Optional[float] = 0.0,
        easy_snap_xy: Optional[EasySnapXY] = EasySnapXY.DISABLED,
        easy_snap_z: Optional[EasySnapZ] = EasySnapZ.RELATIVE,
    ):
        super().__init__()
        self._x = None
        self._y = None
        self._z = None
        self._diameter = None
        self._depth = None
        self._drilling_flags = None
        self._rotation = None
        self._tilt = None
        self._easy_snap_xy = None
        self._easy_snap_z = None

        self.x = x
        self.y = y
        self.z = z
        self.diameter = diameter
        self.depth = depth
        self.drilling_flags = drilling_flags
        self.rotation = rotation
        self.tilt = tilt
        self.easy_snap_xy = easy_snap_xy
        self.easy_snap_z = easy_snap_z

    def __repr__(self) -> str:
        return f"DrillingOperation(pos=({self.x:.1f},{self.y:.1f},{self.z:.1f}), depth={self.depth}, ø={self.diameter})"

    @property
    def x(self) -> float:
        """X-coordinate of the drill position."""
        return self._x

    @x.setter
    def x(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"x must be a number, got {type(value).__name__}")
        self._x = float(value)

    @property
    def y(self) -> float:
        """Y-coordinate of the drill position."""
        return self._y

    @y.setter
    def y(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"y must be a number, got {type(value).__name__}")
        self._y = float(value)

    @property
    def z(self) -> float:
        """Z-coordinate of the drill position."""
        return self._z

    @z.setter
    def z(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"z must be a number, got {type(value).__name__}")
        self._z = float(value)

    @property
    def diameter(self) -> Optional[float]:
        """Drill bit diameter in mm."""
        return self._diameter

    @diameter.setter
    def diameter(self, value: Optional[float]):
        if value is not None:
            if not isinstance(value, (int, float)):
                raise TypeError(f"diameter must be a number or None, got {type(value).__name__}")
            if value <= 0:
                raise ValueError(f"diameter must be positive, got {value}")
        self._diameter = float(value) if value is not None else None

    @property
    def depth(self) -> float:
        """Drilling depth in mm."""
        return self._depth

    @depth.setter
    def depth(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"depth must be a number, got {type(value).__name__}")
        self._depth = float(value)

    @property
    def drilling_flags(self) -> int:
        """Additional drilling options as bitwise flags."""
        return self._drilling_flags

    @drilling_flags.setter
    def drilling_flags(self, value: int):
        if not isinstance(value, int):
            raise TypeError(f"drilling_flags must be int, got {type(value).__name__}")
        self._drilling_flags = value

    @property
    def rotation(self) -> float:
        """Rotation angle for angled drilling (0 < rotation < 180 degrees)."""
        return self._rotation

    @rotation.setter
    def rotation(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"rotation must be a number, got {type(value).__name__}")
        if not 0 <= value <= 180:
            raise ValueError(f"rotation must be between 0 and 180 degrees, got {value}")
        self._rotation = float(value)

    @property
    def tilt(self) -> float:
        """Tilt angle for angled drilling (0 < tilt < 90 degrees)."""
        return self._tilt

    @tilt.setter
    def tilt(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"tilt must be a number, got {type(value).__name__}")
        if not -90 <= value <= 90:
            raise ValueError(f"tilt must be between -90 and 90 degrees, got {value}")
        self._tilt = float(value)

    @property
    def easy_snap_xy(self) -> int:
        """Corner snap mode for XY movement (0-9)."""
        return self._easy_snap_xy

    @easy_snap_xy.setter
    def easy_snap_xy(self, value):
        if isinstance(value, EasySnapXY):
            value = value.value
        elif not isinstance(value, int):
            raise TypeError(f"easy_snap_xy must be EasySnapXY enum or int, got {type(value).__name__}")

        if not 0 <= value <= 9:
            raise ValueError(f"easy_snap_xy must be between 0 and 9, got {value}")

        self._easy_snap_xy = value

    @property
    def easy_snap_z(self) -> int:
        """Z-axis reference mode for depth calculations (0-2)."""
        return self._easy_snap_z

    @easy_snap_z.setter
    def easy_snap_z(self, value):
        if isinstance(value, EasySnapZ):
            value = value.value
        elif not isinstance(value, int):
            raise TypeError(f"easy_snap_z must be EasySnapZ enum or int, got {type(value).__name__}")

        if not 0 <= value <= 2:
            raise ValueError(f"easy_snap_z must be between 0 and 2, got {value}")

        self._easy_snap_z = value

    @classmethod
    def from_hop_line(cls, line: str) -> "DrillingOperation":
        """Parse BOHRUNG command from HOPS line.

        Parameters:
        -----------
        line : str
            HOPS line starting with BOHRUNG(...)

        Returns:
        --------
        :class:`DrillingOperation`
            Parsed DrillingOperation instance

        """
        # Match BOHR with 10 parameters (x, y, z, diameter, depth, flags, rotation, tilt, snap_xy, snap_z)
        # Diameter can be a number or _WZD
        pattern = (
            r"BOHR\(([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*|_WZD),([-+]?\d+\.?\d*),([-+]?\d+),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+),([-+]?\d+)\)"
        )

        match = re.match(pattern, line.strip())
        if match:
            x = float(match.group(1))
            y = float(match.group(2))
            z = float(match.group(3))
            diameter_str = match.group(4)
            diameter = None if diameter_str == "_WZD" else float(diameter_str)
            depth = float(match.group(5))
            drilling_flags = int(match.group(6))
            rotation = float(match.group(7))
            tilt = float(match.group(8))
            easy_snap_xy = EasySnapXY(int(match.group(9)))
            easy_snap_z = EasySnapZ(int(match.group(10)))

            return cls(
                x=x,
                y=y,
                z=z,
                depth=depth,
                diameter=diameter,
                drilling_flags=drilling_flags,
                rotation=rotation,
                tilt=tilt,
                easy_snap_xy=easy_snap_xy,
                easy_snap_z=easy_snap_z,
            )
        raise ValueError(f"Invalid BOHRUNG line: {line}")

    def _to_hop_line(self) -> str:
        """Generate HOPS BOHRUNG command line.

        Returns:
            Formatted BOHRUNG(...) command string
        """

        def fmt(val):
            if isinstance(val, (int, float)):
                return str(int(val)) if val == int(val) else f"{val:.3f}"
            return str(val)

        diameter_str = fmt(self.diameter) if self.diameter is not None else "_WZD"
        return f"BOHRUNG({fmt(self.x)},{fmt(self.y)},{fmt(self.z)},{diameter_str},{fmt(self.depth)},{self.drilling_flags},{fmt(self.rotation)},{fmt(self.tilt)},{self.easy_snap_xy},{int(self.easy_snap_z)})"  # noqa: E501


class OpenPocketOperation(OperationCommand):
    """Represents one pass of an open pocket roughing operation (EbeneF + CALL OpenPocket).

    Each pass serializes as two lines::

        EbeneF ({sx:.3f},0,{z_expr},0,{rotation_angle:.3f},{snap_xy},2,0)
        CALL OpenPocket ( VAL ECKE:={corner},DIM_X:={length},DIM_Y:={width},...)

    Parameters:
    -----------
    sx : float
        X origin of the free work plane for this pass
    rotation_angle : float
        Rotation angle in degrees for the EbeneF plane (and OpenPocket formula basis)
    z_expr : str
        HOPS expression for this pass Z depth, e.g. ``"_RZ*1/3"``
    corner : int
        ECKE — pocket reference corner/edge position (0-8, see CNC dialog)
    length : Union[float, str]
        DIM_X (L1) — pocket length, may be a HOPS formula string e.g. ``"_RY/SIN(63.41)"``
    width : Union[float, str]
        DIM_Y (L2) — pocket width, may be a HOPS formula string e.g. ``"ABS(_RY*SIN(90-63.41))"``
    radius : float
        RAD — corner radius of the pocket
    pos_x : float
        POSX — tool approach position X offset
    pos_y : float
        POSY — tool approach position Y offset
    easy_snap_x : int
        ESX — easy snap mode for X
    easy_snap_y : int
        ESY — easy snap mode for Y
    direction : int
        ANGLE_SWITCH — milling direction: 0 = horizontal, 1 = vertical
    dist : float
        DIST — additional offset distance
    overlap : int
        UEBERLAPPUNG — path overlap percentage (e.g. 67 = 67%)
    roughing : int
        SCHRUP — roughing mode flag (1 = roughing pass)
    depth : float
        TIEFE — absolute pocket depth override (0 = use plane depth)
    count : int
        ANZAHL — number of depth passes (0 = auto)
    max_z : float
        MAXZ — maximum Z depth limit
    easy_snap_md : int
        ESMD — easy snap mode for depth direction
    direct : int
        DIRECT — direct approach flag
    finish_mill : int
        MILL_FIN — finishing mill pass flag
    finish_mill_smooth : int
        MILL_FIN_GL — finishing mill smooth mode
    finish_mill_dist : float
        MILL_FIN_DIST — finishing mill offset distance
    finish_mill_depth : float
        MILL_FIN_DEPTH — finishing mill depth
    finish_mill_count : int
        MILL_FIN_COUNT — finishing mill pass count
    finish_mill_max_z : float
        MILL_FIN_MAXZ — finishing mill max Z
    finish_easy_snap_md : int
        MILL_ESMD — finishing mill easy snap mode for depth
    laser_path : int
        MILL_LASER — laser path flag (1 = also use as laser path)
    """

    OPERATION_TYPE = "ROUGHING"
    _MACRO_NAME = "OpenPocket"

    def __init__(
        self,
        sx: float,
        rotation_angle: float,
        z_expr: str,
        corner: int = 0,
        length: Union[float, str] = 0.0,
        width: Union[float, str] = 0.0,
        radius: float = 0.0,
        pos_x: float = 400.0,
        pos_y: float = 300.0,
        easy_snap_x: int = 0,
        easy_snap_y: int = 0,
        direction: int = 0,
        dist: float = 0.0,
        overlap: int = 67,
        roughing: int = 1,
        depth: float = 0.0,
        count: int = 0,
        max_z: float = 0.0,
        easy_snap_md: int = 0,
        direct: int = 0,
        finish_mill: int = 0,
        finish_mill_smooth: int = 0,
        finish_mill_dist: float = 0.0,
        finish_mill_depth: float = 0.0,
        finish_mill_count: int = 0,
        finish_mill_max_z: float = 0.0,
        finish_easy_snap_md: int = 0,
        laser_path: int = 0,
    ):
        super().__init__()
        self.sx = sx
        self.rotation_angle = rotation_angle
        self.z_expr = z_expr
        self.corner = corner
        self.length = length
        self.width = width
        self.radius = radius
        self.pos_x = pos_x
        self.pos_y = pos_y
        self.easy_snap_x = easy_snap_x
        self.easy_snap_y = easy_snap_y
        self.direction = direction
        self.dist = dist
        self.overlap = overlap
        self.roughing = roughing
        self.depth = depth
        self.count = count
        self.max_z = max_z
        self.easy_snap_md = easy_snap_md
        self.direct = direct
        self.finish_mill = finish_mill
        self.finish_mill_smooth = finish_mill_smooth
        self.finish_mill_dist = finish_mill_dist
        self.finish_mill_depth = finish_mill_depth
        self.finish_mill_count = finish_mill_count
        self.finish_mill_max_z = finish_mill_max_z
        self.finish_easy_snap_md = finish_easy_snap_md
        self.laser_path = laser_path

    def __repr__(self) -> str:
        return f"OpenPocketOperation(sx={self.sx:.3f}, angle={self.rotation_angle:.3f}, z={self.z_expr}, corner={self.corner})"

    def _fmt(self, val) -> str:
        if isinstance(val, str):
            return val
        if isinstance(val, bool):
            return "1" if val else "0"
        if isinstance(val, (int, float)):
            i = int(val)
            return str(i) if val == i else f"{val:.3f}"
        return str(val)

    def _to_hop_line(self) -> str:
        f = self._fmt
        easy_snap_xy_plane = 1 if self.rotation_angle < 90 else 0
        plane = f"EbeneF ({f(self.sx)},0,{self.z_expr},0,{f(self.rotation_angle)},{easy_snap_xy_plane},2,0)"
        pocket = (
            f"CALL {self._MACRO_NAME} ( VAL "
            f"ECKE:={self.corner},"
            f"DIM_X:={f(self.length)},"
            f"DIM_Y:={f(self.width)},"
            f"RAD:={f(self.radius)},"
            f"POSX:={f(self.pos_x)},"
            f"POSY:={f(self.pos_y)},"
            f"ESX:={self.easy_snap_x},"
            f"ESY:={self.easy_snap_y},"
            f"ANGLE_SWITCH:={self.direction},"
            f"DIST:={f(self.dist)},"
            f"UEBERLAPPUNG:={self.overlap},"
            f"SCHRUP:={self.roughing},"
            f"TIEFE:={f(self.depth)},"
            f"ANZAHL:={self.count},"
            f"MAXZ:={f(self.max_z)},"
            f"ESMD:={self.easy_snap_md},"
            f"DIRECT:={self.direct},"
            f"MILL_FIN:={self.finish_mill},"
            f"MILL_FIN_GL:={self.finish_mill_smooth},"
            f"MILL_FIN_DIST:={f(self.finish_mill_dist)},"
            f"MILL_FIN_DEPTH:={f(self.finish_mill_depth)},"
            f"MILL_FIN_COUNT:={self.finish_mill_count},"
            f"MILL_FIN_MAXZ:={f(self.finish_mill_max_z)},"
            f"MILL_ESMD:={self.finish_easy_snap_md},"
            f"MILL_LASER:={self.laser_path})"
        )
        return f"{plane}\n{pocket}"


class ContourPocketOperation(OperationCommand):
    """Represents a contour-buffer pocket roughing operation for an angled end cut.

    Serialises as a single EbeneF work-plane definition, a fixed 4-corner rectangle
    written into a named contour buffer, and a ``CALL _ExecutePocket_V5`` macro::

        EBENEF ({sx},{sy},{sz},{tilt_angle},{rotation_angle},{easy_snap_xy},2,0)
        KB ('{contour_name}','',-_WZR,-_WZR,0,'',7,0)
        KG01 ('',0,0,0,'',10,2)
        KG01 ('',-_WZR,-_WZR,0,'',1,2)
        KG01 ('',-_WZR,-_WZR,0,'',3,2)
        KG01 ('',-_WZR,-_WZR,0,'',5,2)
        KG01ZuKB()
        CALL _ExecutePocket_V5 ( VAL NAMEN:='{contour_name}',AA:=-_WZR,...)

    The 4-corner rectangle is always defined relative to the tool radius (``_WZR``)
    and uses the fixed EasySnapXY corners RELATIVE → FRONT_LEFT → FRONT_RIGHT → REAR_RIGHT.

    Parameters
    ----------
    sx, sy, sz : Union[float, str]
        Origin of the EbeneF work plane.
    tilt_angle : Union[float, str]
        Tilt angle of the EbeneF plane (maps to inclination of the cut).
    rotation_angle : Union[float, str]
        Rotation angle of the EbeneF plane.  Negative values indicate that the
        part is oriented from the opposite face to the JRC reference plane.
    easy_snap_xy : int
        Corner snap mode for the EbeneF origin (default: REAR_LEFT = 7).
    contour_name : str
        Name of the contour buffer, shared between KB and _ExecutePocket_V5.
    overlap : int
        ``UEBERLAPPUNG`` — path overlap as % of tool diameter.
    mode : int
        ``MODE`` — pocket fill strategy (2 = Parallel, default).
    max_z : Union[float, str]
        ``MAXZ`` — maximum depth per pass (default: ``'_AT_MAXDEPTH'``).
    outside_in : int
        ``RD`` — 1 = mill outside-to-inside.
    flying_plunge : int
        ``FLIEGENDEINTAUCHEN`` — helical plunge flag.
    max_plunge_length : Union[float, str]
        ``MAXEINTAUCHLAENGE`` — maximum plunge segment length in mm.
    """

    OPERATION_TYPE = "CONTOUR_POCKET"

    def __init__(
        self,
        sx: Union[float, str],
        sy: Union[float, str] = 0,
        sz: Union[float, str] = 0,
        tilt_angle: Union[float, str] = 0,
        rotation_angle: Union[float, str] = 0,
        easy_snap_xy: int = EasySnapXY.REAR_LEFT,
        contour_name: str = "K0",
        overlap: int = 15,
        mode: int = 2,
        max_z: Union[float, str] = "_AT_MAXDEPTH",
        outside_in: int = 0,
        flying_plunge: int = 0,
        max_plunge_length: Union[float, str] = 20,
    ):
        super().__init__()
        self.sx = sx
        self.sy = sy
        self.sz = sz
        self.tilt_angle = tilt_angle
        self.rotation_angle = rotation_angle
        self.easy_snap_xy = easy_snap_xy
        self.contour_name = contour_name
        self.overlap = overlap
        self.mode = mode
        self.max_z = max_z
        self.outside_in = outside_in
        self.flying_plunge = flying_plunge
        self.max_plunge_length = max_plunge_length

    def __repr__(self) -> str:
        return f"ContourPocketOperation(sx={self.sx}, tilt={self.tilt_angle}, rot={self.rotation_angle})"

    @staticmethod
    def _fmt(val) -> str:
        if isinstance(val, str):
            return val
        if isinstance(val, bool):
            return "1" if val else "0"
        if isinstance(val, (int, float)):
            i = int(val)
            return str(i) if val == i else f"{val:.3f}"
        return str(val)

    def _to_hop_line(self) -> str:
        f = self._fmt
        plane = f"EBENEF ({f(self.sx)},{f(self.sy)},{f(self.sz)},{f(self.tilt_angle)},{f(self.rotation_angle)},{f(self.easy_snap_xy)},2,0)"
        contour_lines = [
            str(ContourStart(self.contour_name, x="-_WZR", y="-_WZR")),
            str(ContourLine("", x="-_WZR", y="-_WZR", z=0, easy_snap_xy=EasySnapXY.FRONT_LEFT, easy_snap_z=EasySnapZ.RELATIVE)),
            str(ContourLine("", x="-_WZR", y="-_WZR", z=0, easy_snap_xy=EasySnapXY.FRONT_RIGHT, easy_snap_z=EasySnapZ.RELATIVE)),
            str(ContourLine("", x="-_WZR", y="-_WZR", z=0, easy_snap_xy=EasySnapXY.REAR_RIGHT, easy_snap_z=EasySnapZ.RELATIVE)),
            str(CloseContour()),
        ]
        pocket = str(
            FreeFormPocket(
                contour_name=self.contour_name,
                overlap=self.overlap,
                mode=self.mode,
                max_z=self.max_z,
                outside_in=self.outside_in,
                flying_plunge=self.flying_plunge,
                max_plunge_length=self.max_plunge_length,
            )
        )
        return "\n".join([plane] + contour_lines + [pocket])


class SawYOperation(OperationCommand):
    """Represents a Y-direction saw cut using the HOPS macro call format.

    Serializes as::

        CALL _saege_y_V7 ( VAL SX:=0,SY:=0,SZ:=-3,EY:=0,EZ:=-2,BL:=1,
            EINPASSEN:=0,EL:=_WZR,AL:=_WZR,PARALLEL:=0,K:=0,KW:=0,
            BH:=0,RITZVERSATZ:=0.05,ESZ:=0,ESXY1:=0,ESY:=5)

    Parameters
    ----------
    sx : Union[float, str], optional
        X position of the cut. Accepts a float or a HOPS expression such as ``'_RX'``. Defaults to ``0.0``.
    sy : Union[float, str], optional
        Starting Y-coordinate (SY).
    sz : Union[float, str], optional
        Starting Z depth — negative = into material (SZ).
    ey : Union[float, str], optional
        Ending Y-coordinate (EY).
    ez : Union[float, str], optional
        Ending Z depth (EZ).
    radius_compensation : CompensationMode
        Blade side: LEFT (1) = blade left of cut, RIGHT (2) = blade right of cut (BL).
    fit_in : bool
        Fit saw blade into contour (EINPASSEN). Default False.
    lead_in : Union[float, str]
        Lead-in extension length. Defaults to ``_WZR`` (EL).
    lead_out : Union[float, str]
        Lead-out extension length. Defaults to ``_WZR`` (AL).
    parallel_distance : float
        Parallel offset distance (PARALLEL).
    process_mode : int
        Groove position / process mode (K).
    tilt_angle : float
        Tilt angle in degrees (KW).
    precut_depth : float
        Scoring blade pre-cut depth (BH).
    precut_offset : float
        Scoring blade lateral offset (RITZVERSATZ).
    easy_snap_z : EasySnapZ
        Z-axis reference mode (ESZ).
    easy_snap_xy : EasySnapXY
        Corner snap mode for XY at start point (ESXY1).
    easy_snap_y : int
        Easy-snap mode for the Y axis (ESY).
    """

    OPERATION_TYPE = "SAWING"
    _MACRO_NAME = "_saege_y_V7"

    def __init__(
        self,
        sx: Union[float, str] = 0.0,
        sy: Union[float, str] = 0.0,
        sz: Union[float, str] = -3.0,
        ey: Union[float, str] = 0.0,
        ez: Union[float, str] = -2.0,
        radius_compensation: Optional[CompensationMode] = CompensationMode.LEFT,
        fit_in: Optional[bool] = False,
        lead_in: Union[float, str] = HopsSystemVars.TOOL_RADIUS,
        lead_out: Union[float, str] = HopsSystemVars.TOOL_RADIUS,
        parallel_distance: float = 0.0,
        process_mode: int = 0,
        tilt_angle: float = 0.0,
        precut_depth: float = 0.0,
        precut_offset: float = 0.05,
        easy_snap_z: int = 0,
        easy_snap_xy: int = 0,
        easy_snap_y: int = 5,
    ):
        super().__init__()
        self.sx = sx
        self.sy = sy
        self.sz = sz
        self.ey = ey
        self.ez = ez
        self.radius_compensation = radius_compensation
        self.fit_in = fit_in
        self.lead_in = lead_in
        self.lead_out = lead_out
        self.parallel_distance = parallel_distance
        self.process_mode = process_mode
        self.tilt_angle = tilt_angle
        self.precut_depth = precut_depth
        self.precut_offset = precut_offset
        self.easy_snap_z = easy_snap_z
        self.easy_snap_xy = easy_snap_xy
        self.easy_snap_y = easy_snap_y

    def __repr__(self) -> str:
        return f"SawYOperation(sx={self.sx}, sz={self.sz}, ez={self.ez}, bl={self.radius_compensation.value})"

    def _fmt(self, val) -> str:
        if isinstance(val, str):
            return val
        if isinstance(val, (EasySnapXY, EasySnapZ)):
            return str(int(val))
        if isinstance(val, CompensationMode):
            return str(val.value)
        if isinstance(val, bool):
            return "1" if val else "0"
        if isinstance(val, (int, float)):
            i = int(val)
            return str(i) if val == i else f"{val:.3f}"
        return str(val)

    def _to_hop_line(self) -> str:
        f = self._fmt
        return (
            f"CALL {self._MACRO_NAME} ( VAL "
            f"SX:={f(self.sx)},"
            f"SY:={f(self.sy)},"
            f"SZ:={f(self.sz)},"
            f"EY:={f(self.ey)},"
            f"EZ:={f(self.ez)},"
            f"BL:={f(self.radius_compensation)},"
            f"EINPASSEN:={f(self.fit_in)},"
            f"EL:={f(self.lead_in)},"
            f"AL:={f(self.lead_out)},"
            f"PARALLEL:={f(self.parallel_distance)},"
            f"K:={f(self.process_mode)},"
            f"KW:={f(self.tilt_angle)},"
            f"BH:={f(self.precut_depth)},"
            f"RITZVERSATZ:={f(self.precut_offset)},"
            f"ESZ:={f(self.easy_snap_z)},"
            f"ESXY1:={f(self.easy_snap_xy)},"
            f"ESY:={f(self.easy_snap_y)})"
        )

    @classmethod
    def from_hop_line(cls, line: str) -> "SawYOperation":
        """Parse a CALL _saege_y_V7 line into a SawYOperation."""

        def _get(name: str, s: str) -> str:
            m = re.search(rf"{name}:=([^,)]+)", s)
            if not m:
                raise ValueError(f"Missing parameter '{name}' in line: {s}")
            return m.group(1).strip()

        def _float(name: str, s: str) -> float:
            return float(_get(name, s))

        def _int(name: str, s: str) -> int:
            return int(float(_get(name, s)))

        def _num_or_str(name: str, s: str) -> Union[float, str]:
            raw = _get(name, s)
            try:
                return float(raw)
            except ValueError:
                return raw

        s = line.strip()
        if not re.match(rf"CALL\s+{re.escape(cls._MACRO_NAME)}", s):
            raise ValueError(f"Not a {cls._MACRO_NAME} line: {line}")

        return cls(
            sx=_num_or_str("SX", s),
            sy=_float("SY", s),
            sz=_float("SZ", s),
            ey=_float("EY", s),
            ez=_float("EZ", s),
            radius_compensation=CompensationMode(_int("BL", s)),
            fit_in=bool(_int("EINPASSEN", s)),
            lead_in=_num_or_str("EL", s),
            lead_out=_num_or_str("AL", s),
            parallel_distance=_float("PARALLEL", s),
            process_mode=_int("K", s),
            tilt_angle=_float("KW", s),
            precut_depth=_float("BH", s),
            precut_offset=_float("RITZVERSATZ", s),
            easy_snap_z=_int("ESZ", s),
            easy_snap_xy=_int("ESXY1", s),
            easy_snap_y=_int("ESY", s),
        )


class DrillingPocketOperation(OperationCommand):
    """Represents a circular pocket operation using the HOPS macro call format.

    Serializes as::

        CALL _Kreistasche_V5_1 ( VAL X_MITTE:=566.409,Y_MITTE:=50,RADIUS:=20.5/2,
            TIEFE:=-40,ZUSTELLUNG:=10,AB:=2,ABF:=_ANF,INTERPOL:=1,UMKEHREN:=1,
            UW:=67,ESXY:=1,ESMD:=0,LASER:=0)

    Parameters
    ----------
    mx : float
        X-coordinate of the pocket center (X_MITTE).
    my : float
        Y-coordinate of the pocket center (Y_MITTE).
    radius : Union[float, str]
        Pocket radius in mm. Accepts a float or a HOPS expression such as ``'20.5/2'`` (RADIUS).
    depth : float
        Milling depth — negative = into material (TIEFE).
    step_depth : float
        Maximum depth per pass in mm (ZUSTELLUNG).
    lead_out_mode : int
        Lead-out type: 0 = without, 1 = linear, 2 = radial (AB). Defaults to 2.
    lead_out_factor : Union[float, str]
        Lead-out factor. ``None`` serializes as ``_ANF`` (ABF).
    interpolate_z : bool
        Interpolate Z at the centre circle for smooth plunge (INTERPOL). Defaults to True.
    reverse_direction : bool
        Reverse the milling direction (UMKEHREN). Defaults to True.
    overlap : int
        Tool overlap between passes as a percentage of the tool diameter (UW). Defaults to 67.
    easy_snap_xy : int
        EasySnap XY mode (ESXY). Defaults to 0.
    easy_snap_z : int
        EasySnap depth mode (ESZ). Defaults to 0.
    laser : bool
        Also execute as a laser path (LASER). Defaults to False.
    """

    OPERATION_TYPE = "DRILLING"
    _MACRO_NAME = "_Kreistasche_V5_1"

    def __init__(
        self,
        mx: float,
        my: float,
        radius: float,
        depth: float,
        step_depth: float,
        lead_out_mode: LeadInOutMode.NONE,
        lead_out_factor: Union[float, str] = HopsSystemVars.LEAD_IN_OUT_FACTOR,
        interpolate_z: bool = True,
        reverse_direction: bool = True,
        overlap: float = 67.0,
        easy_snap_xy: EasySnapXY = EasySnapXY.FRONT_LEFT,
        easy_snap_z: EasySnapZ = EasySnapZ.TOP_SIDE,
        laser: bool = False,
    ):
        super().__init__()
        self.mx = mx
        self.my = my
        self.radius = radius
        self.depth = depth
        self.step_depth = step_depth
        self.lead_out_mode = lead_out_mode
        self.lead_out_factor = lead_out_factor
        self.interpolate_z = interpolate_z
        self.reverse_direction = reverse_direction
        self.overlap = overlap
        self.easy_snap_xy = easy_snap_xy
        self.easy_snap_z = easy_snap_z
        self.laser = laser

    def __repr__(self) -> str:
        return f"DrillingPocketOperation(center=({self.mx:.3f},{self.my:.3f}), radius={self.radius}, depth={self.depth})"

    def _fmt(self, val) -> str:
        if isinstance(val, str):
            return val
        if isinstance(val, bool):
            return "1" if val else "0"
        if isinstance(val, (int, float)):
            i = int(val)
            return str(i) if val == i else f"{val:.3f}"
        return str(val)

    def _to_hop_line(self) -> str:
        f = self._fmt
        abf = self.lead_out_factor if self.lead_out_factor is not None else "_ANF"
        return (
            f"CALL {self._MACRO_NAME} ( VAL "
            f"X_MITTE:={f(self.mx)},"
            f"Y_MITTE:={f(self.my)},"
            f"RADIUS:={f(self.radius)},"
            f"TIEFE:={f(self.depth)},"
            f"ZUSTELLUNG:={f(self.step_depth)},"
            f"AB:={f(self.lead_out_mode)},"
            f"ABF:={f(abf)},"
            f"INTERPOL:={f(self.interpolate_z)},"
            f"UMKEHREN:={f(self.reverse_direction)},"
            f"UW:={f(self.overlap)},"
            f"ESXY:={f(self.easy_snap_xy)},"
            f"ESZ:={f(self.easy_snap_z)},"
            f"LASER:={f(self.laser)})"
        )

    @classmethod
    def from_hop_line(cls, line: str) -> "DrillingPocketOperation":
        """Parse a ``CALL _Kreistasche_V5_1`` line into a :class:`DrillingPocketOperation`.

        Parameters
        ----------
        line : str
            Raw HOPS line starting with ``CALL _Kreistasche_V5_1 ( VAL ...)``.

        Returns
        -------
        :class:`DrillingPocketOperation`
        """

        def _get(name: str, s: str) -> str:
            m = re.search(rf"{name}:=([^,)]+)", s)
            if not m:
                raise ValueError(f"Missing parameter '{name}' in line: {s}")
            return m.group(1).strip()

        def _float(name: str, s: str) -> float:
            return float(_get(name, s))

        def _int(name: str, s: str) -> int:
            return int(float(_get(name, s)))

        def _num_or_str(name: str, s: str) -> Union[float, str]:
            raw = _get(name, s)
            try:
                return float(raw)
            except ValueError:
                return raw

        s = line.strip()
        if not re.match(rf"CALL\s+{re.escape(cls._MACRO_NAME)}", s):
            raise ValueError(f"Not a {cls._MACRO_NAME} line: {line}")

        abf_raw = _get("ABF", s)
        lead_out_factor: Union[float, str] = None if abf_raw == "_ANF" else float(abf_raw)

        return cls(
            mx=_float("X_MITTE", s),
            my=_float("Y_MITTE", s),
            radius=_num_or_str("RADIUS", s),
            depth=_float("TIEFE", s),
            step_depth=_float("ZUSTELLUNG", s),
            lead_out_mode=_int("AB", s),
            lead_out_factor=lead_out_factor,
            interpolate_z=bool(_int("INTERPOL", s)),
            reverse_direction=bool(_int("UMKEHREN", s)),
            overlap=_int("UW", s),
            easy_snap_xy=_int("ESXY", s),
            easy_snap_z=_int("ESZ", s),
            laser=bool(_int("LASER", s)),
        )
