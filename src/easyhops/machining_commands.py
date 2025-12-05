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


# ==================== Machining Command Classes ====================


class MillingCommand:
    """Represents a milling path sequence (SP + G01 moves + EP).

    MillingCommand encapsulates a complete milling operation including the start point, moves, and end point.

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
    MillingCommand(
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
        return f"MillingCommand(start={self.start_point.x:.1f},{self.start_point.y:.1f}, moves={len(self.moves)})"

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


class SawingCommand:
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
    cutting_depth : float
        Cutting depth (z1) in negative value, based on reference height
    ex : float
        Ending position X-coordinate based on current reference point
    ey : float
        Ending position Y-coordinate based on current reference point
    reference_height : float
        Reference height (z2) based on current Z reference (top/bottom edge or in between)
    lead_in : float
        Extending the length of the sawing cut at the starting point (default: 0.0)
    lead_out : float
        Extending the length of the sawing cut at the ending point (default: 0.0)
    parallel_offset : float
        Parallel distance offset. Positive = right side (sawing direction), Negative = left side (default: 0.0)
    fit_in : int
        Saw blade fitting mode:
        0 = Regular cutting (saw blade deepest point touches ending coordinates)
        1 = Fitted cutting (first edge of saw blade reaches ending coordinates) (default: 0)
    tilt_angle : float
        C-axis tilt angle for beveled sawing in degrees:
        0 = vertical cut
        Positive = tip toward part
        Negative = tip away from part (default: 0.0)
    groove_position : int
        Position of saw blade on contour (in machining direction):
        0 = Center
        1 = Left
        2 = Right (default: 0)
    mode : int
        Cutting mode:
        0 = Climb cut
        1 = Conventional cut
        2 = Precut in climb, regular in conventional
        3 = Precut in conventional, regular in climb (default: 0)
    precut_depth : float
        Precut depth based on reference (negative value). Only active if precut mode selected (default: 0.0)
    precut_offset : float
        Precut offset. Positive = right, Negative = left (machining direction). Only active if precut mode selected (default: 0.0)
    param_16 : int
        Reserved parameter (position 16) (default: 0)
    param_17 : int
        Reserved parameter (position 17) (default: 0)
    """

    def __init__(
        self,
        sx: float,
        sy: float,
        cutting_depth: float,
        ex: float,
        ey: float,
        reference_height: float,
        lead_in: float = 0.0,
        lead_out: float = 0.0,
        parallel_offset: float = 0.0,
        fit_in: int = 0,
        tilt_angle: float = 0.0,
        groove_position: int = 0,
        mode: int = 0,
        precut_depth: float = 0.0,
        precut_offset: float = 0.0,
        param_16: int = 0,
        param_17: int = 0,
    ):
        self.sx = sx
        self.sy = sy
        self.cutting_depth = cutting_depth
        self.ex = ex
        self.ey = ey
        self.reference_height = reference_height
        self.lead_in = lead_in
        self.lead_out = lead_out
        self.parallel_offset = parallel_offset
        self.fit_in = fit_in
        self.tilt_angle = tilt_angle
        self.groove_position = groove_position
        self.mode = mode
        self.precut_depth = precut_depth
        self.precut_offset = precut_offset
        self.param_16 = param_16
        self.param_17 = param_17

    @classmethod
    def from_line(cls, line: str) -> "SawingCommand":
        """Parse SAEGEN command from HOPS line.

        Args:
            line: HOPS line starting with SAEGEN(...)

        Returns:
            SawingCommand instance
        """
        # Match all 17 parameters
        pattern = (
            r"SAEGEN\(([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),"
            r"([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),"
            r"([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),"
            r"([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),"
            r"([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),"
            r"([-+]?\d+\.?\d*),([-+]?\d+\.?\d*)\)"
        )

        match = re.match(pattern, line.strip())
        if match:
            params = [float(match.group(i)) for i in range(1, 18)]
            return cls(
                sx=params[0],
                sy=params[1],
                cutting_depth=params[2],
                ex=params[3],
                ey=params[4],
                reference_height=params[5],
                lead_in=params[6],
                lead_out=params[7],
                parallel_offset=params[8],
                fit_in=int(params[9]),
                tilt_angle=params[10],
                groove_position=int(params[11]),
                mode=int(params[12]),
                precut_depth=params[13],
                precut_offset=params[14],
                param_16=int(params[15]),
                param_17=int(params[16]),
            )
        raise ValueError(f"Invalid SAEGEN line: {line}")

    def to_line(self) -> str:
        """Generate HOPS SAEGEN command line.

        Returns:
            Formatted SAEGEN(...) command string
        """
        return (
            f"SAEGEN({self.sx},{self.sy},{self.cutting_depth},"
            f"{self.ex},{self.ey},{self.reference_height},"
            f"{self.lead_in},{self.lead_out},{self.parallel_offset},"
            f"{self.fit_in},{self.tilt_angle},"
            f"{self.groove_position},{self.mode},{self.precut_depth},"
            f"{self.precut_offset},{self.param_16},{self.param_17})"
        )

    def __repr__(self) -> str:
        return f"SawingCommand(from=({self.sx:.1f},{self.sy:.1f},{self.cutting_depth:.1f}), to=({self.ex:.1f},{self.ey:.1f},{self.reference_height:.1f}), tilt={self.tilt_angle}°)"


class DrillingCommand:
    """Represents a drilling operation.

    Drilling creates holes at specific points. The exact HOPS command format
    for drilling is TBD - need to find examples in actual .hop files.

    Typical drilling parameters:
    - Position (x, y, z)
    - Depth
    - Drill diameter
    - Feed rate

    Attributes:
        x, y, z: Drill position coordinates
        depth: Drilling depth
        diameter: Drill bit diameter
    """

    def __init__(self, x: float, y: float, z: float, depth: float, diameter: float):
        """Initialize drilling command.

        Args:
            x, y, z: Drill position
            depth: Drilling depth (mm)
            diameter: Drill bit diameter (mm)
        """
        self.x, self.y, self.z = x, y, z
        self.depth = depth
        self.diameter = diameter

    def __repr__(self) -> str:
        return f"DrillingCommand(pos=({self.x:.1f},{self.y:.1f},{self.z:.1f}), depth={self.depth}, ø={self.diameter})"
