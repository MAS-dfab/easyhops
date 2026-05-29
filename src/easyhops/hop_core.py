# Core HOPS File OOP Implementation

# This module provides object-oriented abstractions for HOPS machining commands and file structure.
# These classes represent the fundamental building blocks of HOPS programs independent of any
# merging or batch processing logic.

# Classes:
#    WorkPlane: Enum for standard work plane definitions (EBENE0-4)
#    FreePlane: Parametric free view work plane (EBENEF)
#    StartPoint: Milling start point command (SP)
#    HopOperation: Single machining operation block
#    HopFile: Parser and container for .hop file structure

# Usage Example:
#    ```python
#    from hop_core import HopFile, FreePlane, WorkPlane

#    # Parse a .hop file
#    hop = HopFile('path/to/file.hop')

#    # Access operations
#    for op in hop.operations:
#        print(f"Tool: {op.tool_code}, Min X: {op.calculate_min_x()}")

#    # Create a free plane
#    plane = FreePlane(x=100, y=50, z=0, rotation_angle=45, tilt_angle=0)
#    print(str(plane))  # EBENEF(100,50,0,45,0)
#    ```


import re
from enum import Enum
from enum import IntEnum
from typing import List
from typing import Optional

# Module-level cache for HopsSystemVars numeric values (cannot live inside Enum class body)
_hops_system_vars_cache: dict = {}


class HopsSystemVars(str, Enum):
    """HOPS global system variables for tool parameters.

    These macro variables reference the CNC machine's configured default values.
    When used in HOPS commands, the machine substitutes them with current values
    from the tool manager during program execution.

    Parameters:
    -----------
    FEEDRATE : str
        Current feed rate from tool manager ("_V")
    LEAD_OUT_FEEDRATE : str
        Current lead out feed rate from tool manager ("_VA")
    LEAD_IN_FEEDRATE : str
        Current lead in feed rate from tool manager ("_VE")
    MOTOR_SPEED : str
        Current motor speed from tool manager ("_SD")
    LEAD_IN_OUT_FACTOR : str
        Current tool lead in and lead out factor from tool manager ("_ANF")
    TOOL_DIAMETER : str
        Current tool diameter from tool manager ("_WZD")
    TOOL_RADIUS : str
        Current tool radius from tool manager ("_WZR")
    SAW_WIDTH : str
        Current saw blade width from tool manager ("_SBB")
    """

    LEAD_IN_FEEDRATE = "_VE"  # Current lead in feed rate (tool manager)
    FEEDRATE = "_V"  # Current feed rate (tool manager)
    LEAD_OUT_FEEDRATE = "_VA"  # Current lead out feed rate (tool manager)
    MOTOR_SPEED = "_SD"  # Current motor speed (tool manager)
    LEAD_IN_OUT_FACTOR = "_ANF"  # Current tool lead in/out factor (tool manager)
    TOOL_DIAMETER = "_WZD"  # Current tool diameter (tool manager)
    TOOL_RADIUS = "_WZR"  # Current tool radius (tool manager)
    SAW_WIDTH = "_SBB"  # Current saw blade width (tool manager)
    X_DIM = "_RX"  # Part X dimension (beam length)
    Y_DIM = "_RY"  # Part Y dimension (beam width)
    Z_DIM = "_RZ"  # Part Z dimension (beam thickness)

    def __str__(self):
        return self.value

    def set(self, value):
        """Seed this variable with a numeric value for use in arithmetic.

        Once set, arithmetic operations (-, +, /, etc.) work on this variable while
        the macro string (e.g. '_WZD') is still used for HOPS file serialization.

        Part-dimension vars (X_DIM, Y_DIM, Z_DIM) are auto-seeded by HOPSJob.
        Tool-dimension vars (TOOL_DIAMETER, TOOL_RADIUS) are auto-seeded by HOPSMachining.
        """
        _hops_system_vars_cache[self.name] = float(value)

    def reset(self):
        """Remove the numeric value for this variable."""
        _hops_system_vars_cache.pop(self.name, None)

    @classmethod
    def reset_all(cls):
        """Clear all numeric values. Useful for test isolation or resetting between jobs."""
        _hops_system_vars_cache.clear()

    @property
    def numeric(self):
        """Return the numeric value for this variable.

        Raises:
        -------
        ValueError
            If no numeric value has been set. Either call .set(value) manually,
            or ensure a HOPSJob (for part dims) or HOPSMachining (for tool dims)
            has been instantiated first.
        """
        if self.name not in _hops_system_vars_cache:
            raise ValueError(
                f"HopsSystemVars.{self.name} ('{self.value}') has no numeric value. "
                f"Ensure a HOPSJob or HOPSMachining has been created, or call "
                f"HopsSystemVars.{self.name}.set(value) manually."
            )
        return _hops_system_vars_cache[self.name]

    def __neg__(self):
        return -self.numeric

    def __float__(self):
        return self.numeric

    def __int__(self):
        return int(self.numeric)

    def __add__(self, other):
        if isinstance(other, (int, float)):
            return self.numeric + other
        return str.__add__(self, other)  # fall back to string concatenation

    def __radd__(self, other):
        return float(other) + self.numeric

    def __sub__(self, other):
        return self.numeric - float(other)

    def __rsub__(self, other):
        return float(other) - self.numeric

    def __truediv__(self, other):
        return self.numeric / float(other)

    def __rtruediv__(self, other):
        return float(other) / self.numeric


class EasySnapZ(IntEnum):
    """Z reference mode for depth calculations.

    Attributes:
    -----------
    TOP_EDGE : 0
        Reference from top edge (absolute from top)
    BOTTOM_EDGE : 1
        Reference from bottom edge (absolute from bottom)
    RELATIVE : 2
        Relative/incremental Z (0 = maintain current depth, X/Y always absolute)
    """

    TOP_EDGE = 0  # Reference from top edge (absolute from top)
    BOTTOM_EDGE = 1  # Reference from bottom edge (absolute from bottom)
    RELATIVE = 2  # Relative/incremental Z (0 = maintain current depth, X/Y always absolute)

    TOP_SIDE = 2  # Reference from top side // SAEGEN
    CENTER = 1  # Reference from center // SAEGEN
    BOTTOM_SIDE = 0  # Reference from bottom side // SAEGEN

    def __str__(self):
        return str(self.value)


class EasySnapXY(IntEnum):
    """Corner snap mode for XY reference.

    Attributes:
    -----------
    DISABLED : 0
        Disabled
    FRONT_LEFT : 1
        Front-left corner
    FRONT_CENTER : 2
        Front-center
    FRONT_RIGHT : 3
        Front-right corner
    CENTER_RIGHT : 4
        Right-center
    REAR_RIGHT : 5
        Rear-right corner
    REAR_CENTER : 6
        Rear-center
    REAR_LEFT : 7
        Rear-left corner
    CENTER_LEFT : 8
        Left-center
    WORKPIECE_CENTER : 9
        Center position'
    RELATIVE : 10
        Relative/incremental (maintain current XY position)
    """

    DISABLED = 0  # Disabled
    FRONT_LEFT = 1  # Front-left corner
    FRONT_CENTER = 2  # Front-center
    FRONT_RIGHT = 3  # Front-right corner
    CENTER_RIGHT = 4  # Right-center
    REAR_RIGHT = 5  # Rear-right corner
    REAR_CENTER = 6  # Rear-center
    REAR_LEFT = 7  # Rear-left corner
    CENTER_LEFT = 8  # Left-center
    WORKPIECE_CENTER = 9  # Center position
    RELATIVE = 10  # Relative/incremental (maintain current XY position)

    def __str__(self):
        return str(self.value)


class ParkMode(IntEnum):
    """Park position modes for tool parking.

    Attributes:
    -----------
    WITHOUT : 0
        Without parking
    LEFT_REAR : 1
        Left rear position
    RIGHT_REAR : 2
        Right rear position
    MIDDLE_REAR : 3
        Middle rear position
    LEFT_FRONT : 4
        Left front position
    RIGHT_FRONT : 5
        Right front position
    MIDDLE_FRONT : 6
        Middle front position
    LEFT_MIDDLE : 7
        Left middle position
    RIGHT_MIDDLE : 8
        Right middle position
    MACHINE_CENTRE : 9
        Machine centre position
    MANUAL : 10
        Manual parking
    AUTOMATIC : 11
        Automatic parking
    """

    WITHOUT = 0
    LEFT_REAR = 1
    RIGHT_REAR = 2
    MIDDLE_REAR = 3
    LEFT_FRONT = 4
    RIGHT_FRONT = 5
    MIDDLE_FRONT = 6
    LEFT_MIDDLE = 7
    RIGHT_MIDDLE = 8
    MACHINE_CENTRE = 9
    MANUAL = 10
    AUTOMATIC = 11

    def __str__(self):
        return str(self.value)


class VarsDefinition:
    """Represents variable definitions in the VARS section of a HOPS file.

    Parameters:
    -----------
    dx : float
        Piece length (DX)
    dy : float
        Piece height (DY)
    dz : float
        Piece thickness (DZ)
    **kwargs : float or tuple
        Additional custom variables (optional). Can be:
        - Just a value: B1=6000
        - Tuple of (value, description): B1=(6000, "Beam width")

    Example:
    --------
    >>> # Explicit method approach (recommended for clarity)
    >>> vars_def = VarsDefinition(dx=1000, dy=60, dz=60)
    >>> vars_def.add_variable("B1", 6000, "Beam width")
    >>> vars_def.add_variable("K1", 500, "Offset parameter")
    >>> # Or with chaining:
    >>> vars_def = VarsDefinition(dx=1000, dy=60, dz=60).add_variable("B1", 6000, "Beam width").add_variable("K1", 500, "Offset parameter")
    >>> # Convenient shorthand with **kwargs:
    >>> vars_def = VarsDefinition(dx=1000, dy=60, dz=60, B1=(6000, "Beam width"), K1=500)  # Uses default description
    """

    def __init__(self, dx: float, dy: float, dz: float, **kwargs):
        self.dx = dx
        self.dy = dy
        self.dz = dz
        # Parse kwargs to handle (value, description) tuples
        self.custom_vars = {}
        for key, val in kwargs.items():
            if isinstance(val, tuple) and len(val) == 2:
                # (value, description) tuple
                self.custom_vars[key] = {"value": val[0], "desc": val[1]}
            else:
                # Just a value, use default description
                self.custom_vars[key] = {"value": val, "desc": "Custom Variable"}

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "dx" and isinstance(value, (int, float)):
            HopsSystemVars.X_DIM.set(value)
        elif name == "dy" and isinstance(value, (int, float)):
            HopsSystemVars.Y_DIM.set(value)
        elif name == "dz" and isinstance(value, (int, float)):
            HopsSystemVars.Z_DIM.set(value)

    def __str__(self):
        lines = ["VARS"]
        lines.append(f"   DX := {self.dx};*VAR* Piece Length")
        lines.append(f"   DY := {self.dy};*VAR* Piece Height")
        lines.append(f"   DZ := {self.dz};*VAR* Piece Thickness")

        # Add custom variables in sorted order for consistency
        for key in sorted(self.custom_vars.keys()):
            var_data = self.custom_vars[key]
            lines.append(f"   {key} := {var_data['value']};*VAR* {var_data['desc']}")

        lines.append("START")
        return "\n".join(lines)

    def add_variable(self, name: str, value: int, description: str) -> "VarsDefinition":
        """Add a custom variable with explicit name, value, and description.

        This is the recommended way to add variables when you need clear documentation.

        Parameters:
        -----------
        name : str
            Variable name (e.g., "B1", "K1")
        value : int
            Variable value
        description : str
            Description for the variable (appears in HOPS comments)

        Returns:
        --------
        VarsDefinition
            Self, for method chaining

        Example:
        --------
        >>> vars_def = VarsDefinition(dx=1000, dy=60, dz=60)
        >>> vars_def.add_variable("B1", 6000, "Beam width")
        >>> vars_def.add_variable("K1", 500, "Offset parameter")
        >>> # Or chain the calls:
        >>> vars_def = VarsDefinition(dx=1000, dy=60, dz=60).add_variable("B1", 6000, "Beam width").add_variable("K1", 500, "Offset parameter")
        """
        self.custom_vars[name] = {"value": int(value), "desc": description}
        return self

    @classmethod
    def from_hop_line(cls, line: List[str]) -> "VarsDefinition":
        """Parse VARS definition from HOPS lines.

        Parameters:
        -----------
        line : List[str]
            Lines from the VARS section of a HOPS file

        Returns:
        --------
        VarsDefinition
            Parsed VarsDefinition object
        """
        dx = dy = dz = 0.0
        custom_vars = {}

        for l in line:
            if "DX :=" in l:
                match = re.search(r"DX := ([-+]?\d+\.?\d*)", l)
                if match:
                    dx = float(match.group(1))
            elif "DY :=" in l:
                match = re.search(r"DY := ([-+]?\d+\.?\d*)", l)
                if match:
                    dy = float(match.group(1))
            elif "DZ :=" in l:
                match = re.search(r"DZ := ([-+]?\d+\.?\d*)", l)
                if match:
                    dz = float(match.group(1))
            else:
                # Try to parse custom variables with optional description
                # Format: "   B1 := 6000;*VAR* Beam width"
                match = re.search(r"([A-Z]\w*) := ([-+]?\d+\.?\d*)(?:;\*VAR\*\s*(.*))?", l)
                if match:
                    var_name = match.group(1)
                    var_value = float(match.group(2))
                    var_desc = match.group(3).strip() if match.group(3) else "Custom Variable"
                    # Exclude DX, DY, DZ if they appear again
                    if var_name not in ["DX", "DY", "DZ"]:
                        custom_vars[var_name] = (var_value, var_desc)

        return cls(dx=dx, dy=dy, dz=dz, **custom_vars)


class FinishedPart:
    """Represents the finished part definition in a HOPS file.

    Parameters:
    -----------
    x : Optional[float]
        Work piece dimension in X direction. If None, VARS DX is used.
    y : Optional[float]
        Work piece dimension in Y direction. If None, VARS DY is used.
    z : Optional[float]
        Work piece dimension in Z direction. If None, VARS DZ is used.
    rotation_flag : Optional[int]
        Rotation flag (0 = no rotation, 1 = rotate 90 degrees, 2 = rotate 180 degrees, 3 = rotate 270 degrees)
    empty_parameter : Optional[int] # TODO: figure this out
        Empty parameter, always set to 0.
    offset_x : Optional[float]
        X offset of the finished part
    offset_y : Optional[float]
        Y offset of the finished part
    offset_z : Optional[float]
        Z offset of the finished part
    comment : Optional[str]
        Optional comment for the finished part
    field_linking : Optional[bool]
        Field linking flag (True = enabled, False = disabled)
    activates_laser : Optional[bool]
        Laser activation flag (True = activates laser, False = does not activate laser)
    stop_flag : Optional[int]
        Stop situation 0: LU, 1:RU , 2:RO, 3:LO stop flag # TODO: figure this out

    """

    def __init__(
        self,
        dx: Optional[float] = HopsSystemVars.X_DIM,
        dy: Optional[float] = HopsSystemVars.Y_DIM,
        dz: Optional[float] = HopsSystemVars.Z_DIM,
        rotation_flag: Optional[int] = 0,
        empty_parameter: Optional[int] = 0,
        offset_x: Optional[float] = 0,
        offset_y: Optional[float] = 0,
        offset_z: Optional[float] = 0,
        comment: Optional[str] = "",
        field_linking: Optional[bool] = False,
        activates_laser: Optional[bool] = False,
        stop_flag: Optional[int] = 0,
    ):
        self.dx = dx
        self.dy = dy
        self.dz = dz
        self.rotation_flag = rotation_flag
        self.empty_parameter = empty_parameter
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.offset_z = offset_z
        self.comment = comment
        self.field_linking = field_linking
        self.activates_laser = activates_laser
        self.stop_flag = stop_flag

    def __str__(self):
        dx_str = f"{self.dx}" if self.dx is not None else "DX"
        dy_str = f"{self.dy}" if self.dy is not None else "DY"
        dz_str = f"{self.dz}" if self.dz is not None else "DZ"
        # Comment should be quoted if non-empty, or empty string
        comment_str = f"'{self.comment}'" if self.comment else "''"
        field_linking_str = "1" if self.field_linking else "0"
        activates_laser_str = "1" if self.activates_laser else "0"

        return (
            f"FERTIGTEIL({dx_str},{dy_str},{dz_str},"
            f"{self.rotation_flag},{self.empty_parameter},"
            f"{self.offset_x:.3f},{self.offset_y:.3f},{self.offset_z:.3f},"
            f"{comment_str},{field_linking_str},{activates_laser_str},{self.stop_flag})\n"
        )

    @classmethod
    def from_hop_line(cls, line: str) -> "FinishedPart":
        """Parse FERTIGTEIL definition from HOPS line.

        Parameters:
        -----------
        line : str
            Line starting with FERTIGTEIL(...)

        Returns:
        --------
        FinishedPart
            Parsed FinishedPart object
        """
        pattern = (
            r"FERTIGTEIL\(\s*"
            r"(?P<dx>[-+]?\d*\.?\d+|VARS DX|DX)\s*,\s*"
            r"(?P<dy>[-+]?\d*\.?\d+|VARS DY|DY)\s*,\s*"
            r"(?P<dz>[-+]?\d*\.?\d+|VARS DZ|DZ)\s*,\s*"
            r"(?P<rotation_flag>\d+)\s*,\s*"
            r"(?P<empty_parameter>\d+)\s*,\s*"
            r"(?P<offset_x>[-+]?\d*\.?\d+)\s*,\s*"
            r"(?P<offset_y>[-+]?\d*\.?\d+)\s*,\s*"
            r"(?P<offset_z>[-+]?\d*\.?\d+)\s*,\s*"
            r"(?P<comment>'[^']*'|[^,]*)\s*,\s*"
            r"(?P<field_linking>[01])\s*,\s*"
            r"(?P<activates_laser>[01])\s*,\s*"
            r"(?P<stop_flag>\d+)\s*\)"
        )

        match = re.match(pattern, line)
        if match:
            dx_str = match.group("dx")
            dy_str = match.group("dy")
            dz_str = match.group("dz")

            dx = float(dx_str) if dx_str not in ("VARS DX", "DX") else None
            dy = float(dy_str) if dy_str not in ("VARS DY", "DY") else None
            dz = float(dz_str) if dz_str not in ("VARS DZ", "DZ") else None

            # Parse comment - strip quotes if present
            comment_str = match.group("comment") or ""
            if comment_str.startswith("'") and comment_str.endswith("'"):
                comment_str = comment_str[1:-1]

            return cls(
                dx=dx,
                dy=dy,
                dz=dz,
                rotation_flag=int(match.group("rotation_flag")),
                empty_parameter=int(match.group("empty_parameter")),
                offset_x=float(match.group("offset_x")),
                offset_y=float(match.group("offset_y")),
                offset_z=float(match.group("offset_z")),
                comment=comment_str,
                field_linking=bool(int(match.group("field_linking"))),
                activates_laser=bool(int(match.group("activates_laser"))),
                stop_flag=int(match.group("stop_flag")),
            )
        else:
            raise ValueError(f"Invalid FERTIGTEIL line: {line}")


class ParkPosition:
    """Represents the Park_V7 command for tool parking positions.

    Parameters:
    -----------
    mode : Optional[ParkMode]
        Park mode position setting (default AUTOMATIC)
    pos_x : Optional[float]
        X position for parking (default 0)
    pos_y : Optional[float]
        Y position for parking (default 0)
    """

    def __init__(self, mode: ParkMode = ParkMode.AUTOMATIC, pos_x: float = 0, pos_y: float = 0):
        self.mode = mode
        self.pos_x = pos_x
        self.pos_y = pos_y

    def __str__(self):
        return f"CALL Park_V7 ( VAL MODE:={self.mode.value},POSX:={self.pos_x},POSY:={self.pos_y})"

    @classmethod
    def from_hop_line(cls, line: str) -> "ParkPosition":
        """Parse Park_V7 command from HOPS line.

        Parameters:
        -----------
        line : str
            Line starting with CALL Park_V7(...)

        Returns:
        --------
        ParkPosition
            Parsed ParkPosition object
        """
        pattern = r"CALL Park_V7\s*\(\s*VAL\s+MODE:=([-+]?\d+)\s*,\s*POSX:=([-+]?\d+\.?\d*)\s*,\s*POSY:=([-+]?\d+\.?\d*)\s*\)"

        match = re.match(pattern, line.strip())
        if match:
            return cls(mode=ParkMode(int(match.group(1))), pos_x=float(match.group(2)), pos_y=float(match.group(3)))
        raise ValueError(f"Invalid Park_V7 line: {line}")
