import re
from abc import ABC
from enum import IntEnum
from typing import List
from typing import Optional

from .hop_core import EasySnapXY
from .hop_core import EasySnapZ


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

    NO_CHANGE = 0
    WITH_ROTATION = 1
    AGAINST_ROTATION = 2
    WITH_ROTATION_MIRROR = 3
    AGAINST_ROTATION_MIRROR = 4


class MachiningCommand(ABC):
    """Abstract base class for machining commands.

    This class serves as a template for specific machining command implementations.

    Parameters:
    -----------
    feedrate : Optional[float]
        The feedrate for the machining command in mm/min, meant to override the default feedrate of the tool.
    """

    def __init__(self, feedrate: Optional[float] = None):
        self.feedrate = feedrate

    def __str__(self) -> str:
        """Return feedrate command line if feedrate is set."""
        if self.feedrate is not None:
            return f"CALL _Tvorschub_v5(VAL VORSCHUB:={self.feedrate})"
        return ""


class StartPoint(MachiningCommand):
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
    lead_in_mode : Optional[LeadInOutMode]
        Lead in mode. See LeadInOutMode enum for options. If None, defaults to LeadInOutMode.NONE
    lead_in_factor : Optional[float]
        Lead in factor. If None, defaults to _ANF variable from tool manager
    distance_to_contour : Optional[float]
        Distance offset to contour in mm. Positive = outside, Negative = inside
    offset_angle : Optional[float]
        Machine-specific additive angle for correct C-axis positioning
    tip_angle : Optional[float]
        Tip angle offset for beveled milling (based on vertical normal position)
    easy_snap_xy : Optional[EasySnapXY]
        EasySnapXY corner snap mode for XY movement. See EasySnapXY enum for options. If None, defaults to EasySnapXY.DISABLED
    easy_snap_z : Optional[EasySnapZ]
        EasySnapZ Z-axis reference mode for depth calculations. See EasySnapZ enum for options. If None, defaults to EasySnapZ.RELATIVE
    process_mode : Optional[ProcessMode]
        Machining direction control. See ProcessMode enum for options. If None, defaults to ProcessMode.NO_CHANGE
    milling_steps : Optional[int]
        Number of milling steps to divide depth into multiple levels. If None, defaults to 1 (single pass)
    depth_per_level : Optional[float]
        Depth per level when using multiple steps (overrides milling_steps if used)
    excess_depth : Optional[float]
        Additional depth beyond programmed depth for exact chip cut. Only if tip_angle is not zero.
    interpolation_with_rot_axis : bool
        Enable smooth Z-axis lead in to starting point
    activate_laser : bool
        If True, milling path is also used as laser path

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
    feedrate : Optional[float]
        Feedrate for the milling operation in mm/min (overrides tool default)

    Example:
    ---------
    SP(68.807,-35.546,20,0,0,_ANF,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)
    """

    def __init__(
        self,
        x: float,
        y: float,
        z: float,
        radius_compensation: Optional[CompensationMode] = CompensationMode.CENTER,
        lead_in_mode: Optional[LeadInOutMode] = LeadInOutMode.NONE,
        lead_in_factor: Optional[float] = None,
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
        start_correction_above: Optional[bool] = False,
        tilt_angle: Optional[float] = 0.0,
        excess_length: Optional[float] = 0.0,
        axial_lead_in_out: Optional[bool] = False,
        axial_distance: Optional[float] = 0.0,
        param_23: Optional[float] = 0.0,  # TODO: figure out what this is
        feedrate: Optional[float] = None,
    ):
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
        self.param_23 = param_23
        super().__init__(feedrate=feedrate)

    def __str__(self):
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
            self.param_23,
        ]
        parent_str = super().__str__()
        sp_str = f"SP({','.join(map(str, params))})"
        return f"{parent_str}\n{sp_str}" if parent_str else sp_str

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
            r"([-+]?\d+\.?\d*)"  # param_23
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
                param_23=float(match.group(23)),
            )
        raise ValueError(f"Invalid SP line: {line}")


class G01(MachiningCommand):
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
    feedrate : Optional[float]
        Feedrate for the movement in mm/min (overrides tool default)

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
        feedrate: Optional[float] = None,
    ):
        self.x = x
        self.y = y
        self.z = z
        self.corner_radius = corner_radius
        self.easy_snap_xy = easy_snap_xy
        self.easy_snap_z = easy_snap_z
        super().__init__(feedrate=feedrate)

    def __str__(self):
        parent_str = super().__str__()
        g01_str = f"G01({self.x},{self.y},{self.z},{self.corner_radius},{self.easy_snap_xy},{int(self.easy_snap_z)})"
        return f"{parent_str}\n{g01_str}" if parent_str else g01_str

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


class EndPoint(MachiningCommand):
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
    feedrate : Optional[float]
        Feedrate for the end point movement in mm/min (overrides tool default)

    Example:
    -----------
    EP(3,3.000,0)
    """

    def __init__(
        self,
        lead_out_mode: Optional[LeadInOutMode] = LeadInOutMode.NONE,
        lead_out_factor: Optional[float] = None,
        reverse_direction: bool = False,
        feedrate: Optional[float] = None,
    ):
        self.lead_out_mode = lead_out_mode
        self.lead_out_factor = lead_out_factor
        self.reverse_direction = reverse_direction
        super().__init__(feedrate=feedrate)

    def __str__(self):
        parent_str = super().__str__()
        lead_out_factor_str = self.lead_out_factor if self.lead_out_factor is not None else "_ANF"
        ep_str = f"EP({self.lead_out_mode},{lead_out_factor_str},{self.reverse_direction})"
        return f"{parent_str}\n{ep_str}" if parent_str else ep_str

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


class MillingOperation:
    """Represents a milling path sequence (SP + G01 moves + EP).

    MillingOperation encapsulates a complete milling operation including the start point, moves, and end point.

    Parameters:
    -----------
    start_point : :class:`StartPoint`
        StartPoint instance with milling parameters
    moves : List[:class:`G01`]
        List of G01 instances representing linear interpolation movements
    end_point : :class:`EndPoint`
        EndPoint instance with lead out parameters

    Example:
    ---------
    MillingOperation(
        SP(300,-301.264,-27.229,1,3,3.000,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
        [G01(500.123,-100.456,-25.000,0,0,2),
        G01(800.456,-200.789,-25.000,0,0,2)],
        EP(3,3.000,0)
    )
    """

    def __init__(self, start_point: StartPoint, moves: List[G01], end_point: EndPoint):
        self.start_point = start_point
        self.moves = moves
        self.end_point = end_point

    def __repr__(self) -> str:
        return f"MillingOperation(start={self.start_point.x:.1f},{self.start_point.y:.1f}, moves={len(self.moves)})"

    def __str__(self):
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


class SawingOperation:
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

    def __init__(
        self,
        sx: float,
        sy: float,
        sz: float,
        ex: float,
        ey: float,
        ez: float,
        radius_compensation: Optional[CompensationMode] = CompensationMode.CENTER,
        fit_in: Optional[bool] = True,
        lead_in_out: Optional[float] = 0.0,
        process_mode: Optional[ProcessMode] = ProcessMode.NO_CHANGE,
        tilt_angle: Optional[float] = 0.0,
        z_level: Optional[float] = 0.0,
        easy_snap_xy_start: Optional[EasySnapXY] = EasySnapXY.DISABLED,
        easy_snap_xy_end: Optional[EasySnapXY] = EasySnapXY.DISABLED,
        easy_snap_z: Optional[EasySnapZ] = EasySnapZ.RELATIVE,
    ):
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

    def __str__(self) -> str:
        """Return HOPS SAEGEN command line."""
        return self._to_line()

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
            raise TypeError(f"lead_in_out must be a number, got {type(value).__name__}")
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

        if not 0 <= value <= 9:
            raise ValueError(f"easy_snap_xy_end must be between 0 and 9, got {value}")

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
            # Note: Some parameters in the file format may not match the docstring 1:1
            # This parser maintains compatibility with existing .hop files
            return cls(
                sx=params[0],
                sy=params[1],
                sz=params[2],
                ex=params[3],
                ey=params[4],
                ez=params[5],
                lead_in_out=params[6],  # lead_in in file
                # params[7] is lead_out - not used in new API
                # params[8] is parallel_offset - not used in new API
                fit_in=bool(int(params[9])),
                tilt_angle=params[10],
                # params[11] is groove_position - maps to z_level
                z_level=params[11],
                process_mode=ProcessMode(int(params[12])),
                # params[13-16] are additional saw parameters not in main API
            )
        raise ValueError(f"Invalid SAEGEN line: {line}")

    def _to_line(self) -> str:
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
            f"{fmt(self.lead_in_out)},{fmt(self.lead_in_out)},{fmt(0)},"  # lead_in, lead_out, parallel_offset
            f"{fmt(self.fit_in)},{fmt(self.tilt_angle)},"
            f"{fmt(self.z_level)},{fmt(self.process_mode)},{fmt(0)},"  # z_level as groove_position, mode, precut_depth
            f"{fmt(0)},{fmt(self.easy_snap_xy_start)},{fmt(self.easy_snap_xy_end)})"  # precut_offset, snap params
        )


class DrillingOperation:
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

    def __str__(self):
        """Return HOPS BOHR command line."""
        return self._to_line()

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
        """Parse BOHR command from HOPS line.

        Parameters:
        -----------
        line : str
            HOPS line starting with BOHR(...)

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
        raise ValueError(f"Invalid BOHR line: {line}")

    def _to_line(self) -> str:
        """Generate HOPS BOHR command line.

        Returns:
            Formatted BOHR(...) command string
        """

        def fmt(val):
            if isinstance(val, (int, float)):
                return str(int(val)) if val == int(val) else f"{val:.3f}"
            return str(val)

        diameter_str = fmt(self.diameter) if self.diameter is not None else "_WZD"
        return f"BOHR({fmt(self.x)},{fmt(self.y)},{fmt(self.z)},{diameter_str},{fmt(self.depth)},{self.drilling_flags},{fmt(self.rotation)},{fmt(self.tilt)},{self.easy_snap_xy},{int(self.easy_snap_z)})"
