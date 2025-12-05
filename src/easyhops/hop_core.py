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
from enum import IntEnum
from typing import List
from typing import Optional

from .tool_library import ToolCallType


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


class EasySnapXY(IntEnum):
    """Corner snap mode for XY reference.

    Attributes:
    -----------
    DISABLED : 0
        Disabled
    BOTTOM_LEFT : 1
        Bottom-left corner
    BOTTOM_CENTER : 2
        Bottom-center
    BOTTOM_RIGHT : 3
        Bottom-right corner
    CENTER_RIGHT : 4
        Right-center
    TOP_RIGHT : 5
        Top-right corner
    TOP_CENTER : 6
        Top-center
    TOP_LEFT : 7
        Top-left corner
    CENTER_LEFT : 8
        Left-center
    CENTER : 9
        Center position
    """

    DISABLED = 0  # Disabled
    BOTTOM_LEFT = 1  # Bottom-left corner
    BOTTOM_CENTER = 2  # Bottom-center
    BOTTOM_RIGHT = 3  # Bottom-right corner
    CENTER_RIGHT = 4  # Right-center
    TOP_RIGHT = 5  # Top-right corner
    TOP_CENTER = 6  # Top-center
    TOP_LEFT = 7  # Top-left corner
    CENTER_LEFT = 8  # Left-center
    CENTER = 9  # Center position


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
    """

    def __init__(self, dx: float, dy: float, dz: float):
        self.dx = dx
        self.dy = dy
        self.dz = dz

    def __str__(self):
        return f"VARS\n   DX := {self.dx};\n   DY := {self.dy};\n   DZ := {self.dz};\nSTART"

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

        return cls(dx=dx, dy=dy, dz=dz)


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
        dx: Optional[float] = None,
        dy: Optional[float] = None,
        dz: Optional[float] = None,
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
        dx_str = f"{self.dx}" if self.dx is not None else "VARS DX"
        dy_str = f"{self.dy}" if self.dy is not None else "VARS DY"
        dz_str = f"{self.dz}" if self.dz is not None else "VARS DZ"
        comment_str = f"; {self.comment}" if self.comment else ""
        field_linking_str = "1" if self.field_linking else "0"
        activates_laser_str = "1" if self.activates_laser else "0"

        return (
            f"FERTIGTEIL({dx_str},{dy_str},{dz_str},"
            f"{self.rotation_flag},{self.empty_parameter},"
            f"{self.offset_x},{self.offset_y},{self.offset_z}"
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
            r"(?P<dx>[-+]?\d*\.?\d+|VARS DX)\s*,\s*"
            r"(?P<dy>[-+]?\d*\.?\d+|VARS DY)\s*,\s*"
            r"(?P<dz>[-+]?\d*\.?\d+|VARS DZ)\s*,\s*"
            r"(?P<rotation_flag>\d+)\s*,\s*"
            r"(?P<empty_parameter>\d+)\s*,\s*"
            r"(?P<offset_x>[-+]?\d*\.?\d+)\s*,\s*"
            r"(?P<offset_y>[-+]?\d*\.?\d+)\s*,\s*"
            r"(?P<offset_z>[-+]?\d*\.?\d+)"
            r"(?:\s*;\s*(?P<comment>[^,]+))?\s*,\s*"
            r"(?P<field_linking>[01])\s*,\s*"
            r"(?P<activates_laser>[01])\s*,\s*"
            r"(?P<stop_flag>\d+)\s*\)"
        )

        match = re.match(pattern, line)
        if match:
            dx_str = match.group("dx")
            dy_str = match.group("dy")
            dz_str = match.group("dz")

            dx = float(dx_str) if dx_str != "VARS DX" else None
            dy = float(dy_str) if dy_str != "VARS DY" else None
            dz = float(dz_str) if dz_str != "VARS DZ" else None

            return cls(
                dx=dx,
                dy=dy,
                dz=dz,
                rotation_flag=int(match.group("rotation_flag")),
                empty_parameter=int(match.group("empty_parameter")),
                offset_x=float(match.group("offset_x")),
                offset_y=float(match.group("offset_y")),
                offset_z=float(match.group("offset_z")),
                comment=match.group("comment") or "",
                field_linking=bool(int(match.group("field_linking"))),
                activates_laser=bool(int(match.group("activates_laser"))),
                stop_flag=int(match.group("stop_flag")),
            )
        else:
            raise ValueError(f"Invalid FERTIGTEIL line: {line}")


class ParkMode:
    """Represents the Park_V7 command for tool parking positions.

    Parameters:
    -----------
    mode : int
        Park mode value (typically 11 for standard parking)
    pos_x : float
        X position for parking (default 0)
    pos_y : float
        Y position for parking (default 0)
    """

    def __init__(self, mode: int = 11, pos_x: float = 0, pos_y: float = 0):
        self.mode = mode
        self.pos_x = pos_x
        self.pos_y = pos_y

    def __str__(self):
        return f"CALL Park_V7 ( VAL MODE:={self.mode},POSX:={self.pos_x},POSY:={self.pos_y})"

    @classmethod
    def from_hop_line(cls, line: str) -> "ParkMode":
        """Parse Park_V7 command from HOPS line.

        Parameters:
        -----------
        line : str
            Line starting with CALL Park_V7(...)

        Returns:
        --------
        ParkMode
            Parsed ParkMode object
        """
        pattern = r"CALL Park_V7\s*\(\s*VAL\s+MODE:=([-+]?\d+)\s*,\s*POSX:=([-+]?\d+\.?\d*)\s*,\s*POSY:=([-+]?\d+\.?\d*)\s*\)"

        match = re.match(pattern, line.strip())
        if match:
            return cls(mode=int(match.group(1)), pos_x=float(match.group(2)), pos_y=float(match.group(3)))
        raise ValueError(f"Invalid Park_V7 line: {line}")


# class HopOperation:
#     """Represents a single machining operation block in a HOPS file.

#     An operation consists of:
#     - Tool command (WZF or WZS)
#     - Work plane definition (EBENEF or EBENE0/EBENE1/EBENE3)
#     - Set of Feedrate (CALL _Tvorschub_v5(VAL VORSCHUB:=3000))
#     - Machining commands (SP, G01, EP for milling; SAEGEN for sawing)
#     - Associated comment lines

#     Attributes:
#         tool_command : str
#             Full tool command line (e.g., "WZS(201,10000,7000,20000,_SD,_ANF,'1')")
#         holder_type : ToolHolderType
#             Extracted tool holder type (CASSETTE or BLADE)
#         tool_code : str
#             Full tool code string (e.g., "WZS201", "WZF504")
#         lines : List[str]
#             All lines comprising this operation
#         has_ebenef : bool
#             True if operation uses EBENEF work plane
#         min_x : Optional[float]
#             Minimum X-coordinate for sorting purposes (calculated on demand)
#     """

#     def __init__(self, tool_command: str, lines: List[str]):
#         """Initialize HopOperation.

#         Args:
#             tool_command: The tool selection command line
#             lines: All lines belonging to this operation block
#         """
#         self.tool_command = tool_command
#         self.lines = lines
#         self.holder_type, self.tool_code = self._extract_tool_info()
#         self.has_ebenef = self._check_ebenef()
#         self.min_x: Optional[float] = None

#     def _extract_tool_info(self) -> tuple[ToolCallType, str]:
#         """Extract tool holder type and code from tool command.

#         Returns:
#             Tuple of (ToolCallType, tool code string)
#         """
#         match = re.match(r"(WZ[SF])\((\d+)", self.tool_command)
#         if match:
#             tool_prefix = match.group(1)
#             tool_position = match.group(2)
#             tool_code = f"{tool_prefix}{tool_position}"

#             if tool_prefix == "WZF":
#                 holder_type = ToolCallType.CASSETTE
#             elif tool_prefix == "WZS":
#                 holder_type = ToolCallType.BLADE
#             else:
#                 holder_type = ToolCallType.UNKNOWN
#             return holder_type, tool_code

#         return ToolCallType.UNKNOWN, "UNKNOWN"

#     def _check_ebenef(self) -> bool:
#         """Check if this operation uses EBENEF work plane definition."""
#         return any("EBENEF" in line for line in self.lines)

#     def calculate_min_x(self) -> float:
#         """Calculate minimum X-coordinate in this operation for sorting.

#         Returns:
#             Minimum X-coordinate found in operation commands
#         """
#         x_coords = []

#         for line in self.lines:
#             # Extract X from EBENEF
#             if "EBENEF" in line:
#                 match = re.search(r"EBENEF\(([-+]?\d+\.?\d*)", line)
#                 if match:
#                     x_coords.append(float(match.group(1)))

#             # Extract X from SP
#             elif line.strip().startswith("SP("):
#                 match = re.search(r"SP\(([-+]?\d+\.?\d*)", line)
#                 if match:
#                     x_coords.append(float(match.group(1)))

#             # Extract X from SAEGEN
#             elif "SAEGEN" in line:
#                 match = re.search(r"SAEGEN\(([-+]?\d+\.?\d*)", line)
#                 if match:
#                     x_coords.append(float(match.group(1)))

#         self.min_x = min(x_coords) if x_coords else 0.0
#         return self.min_x

#     def apply_offset(self, x_offset: float) -> List[str]:
#         """Apply X-offset to all coordinates in this operation.

#         Offsetting rules:
#         - EBENEF: Only first parameter (X-coordinate)
#         - SP, G01 (after EBENE0): First parameter (X-coordinate)
#         - SAEGEN: Parameters 1 and 4 (X1 and X2)

#         Args:
#             x_offset: Distance to offset X-coordinates (mm)

#         Returns:
#             List of offset lines for this operation
#         """
#         offset_lines = []
#         in_ebene0_block = False

#         for line in self.lines:
#             # Check if we're entering an EBENE0 block
#             if "EBENE0()" in line or "EBENE1()" in line or "EBENE3()" in line:
#                 in_ebene0_block = True
#                 offset_lines.append(line)
#                 continue

#             # EBENEF: offset only first parameter (X)
#             if "EBENEF" in line:
#                 in_ebene0_block = False
#                 offset_lines.append(self._offset_ebenef(line, x_offset))

#             # SAEGEN: offset parameters 1 and 4 (X1, X2)
#             elif "SAEGEN" in line:
#                 offset_lines.append(self._offset_saegen(line, x_offset))

#             # SP, G01: offset first parameter (X) if in EBENE0 block
#             elif (line.strip().startswith("SP(") or line.strip().startswith("G01(")) and in_ebene0_block:
#                 offset_lines.append(self._offset_coordinate_line(line, x_offset))

#             # All other lines pass through unchanged
#             else:
#                 offset_lines.append(line)

#         return offset_lines

#     def _offset_ebenef(self, line: str, x_offset: float) -> str:
#         """Offset X-coordinate (first parameter) in EBENEF command."""
#         match = re.match(r"EBENEF\(([-+]?\d+\.?\d*)(,.*)", line)
#         if match:
#             x_val = float(match.group(1)) + x_offset
#             return f"EBENEF({x_val:.4f}{match.group(2)}\n"
#         return line

#     def _offset_saegen(self, line: str, x_offset: float) -> str:
#         """Offset X1 and X2 (parameters 1 and 4) in SAEGEN command."""
#         # SAEGEN(x1, y1, z1, x2, y2, z2, ...)
#         match = re.match(
#             r"SAEGEN\(([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*)(,.*)",
#             line,
#         )
#         if match:
#             x1 = float(match.group(1)) + x_offset
#             y1 = float(match.group(2))
#             z1 = float(match.group(3))
#             x2 = float(match.group(4)) + x_offset
#             y2 = float(match.group(5))
#             z2 = float(match.group(6))
#             rest = match.group(7)
#             return f"SAEGEN({x1:.3f},{y1:.3f},{z1:.3f},{x2:.3f},{y2:.3f},{z2:.3f}{rest}\n"
#         return line

#     def _offset_coordinate_line(self, line: str, x_offset: float) -> str:
#         """Offset X-coordinate (first parameter) in SP or G01 command."""
#         # SP(x, y, z, ...) or G01(x, y, z, ...)
#         match = re.match(r"(SP|G01)\(([-+]?\d+\.?\d*)(,.*)", line)
#         if match:
#             command = match.group(1)
#             x_val = float(match.group(2)) + x_offset
#             rest = match.group(3)
#             return f"{command}({x_val:.3f}{rest}\n"
#         return line

#     def __repr__(self) -> str:
#         """Return string representation for debugging."""
#         return f"HopOperation(tool={self.tool_code}, lines={len(self.lines)}, has_ebenef={self.has_ebenef})"


# class HopFile:
#     """Represents and parses a single .hop file.

#     Parses the file into:
#     - Header comments (lines starting with ';')
#     - VARS section (variable definitions)
#     - Operations (machining command blocks)

#     Attributes:
#         filepath : str
#             Path to the .hop file
#         header : List[str]
#             Comment lines at top of file
#         vars_section : List[str]
#             VARS...START section
#         operations : List[HopOperation]
#             Parsed machining operations
#         dx : Optional[float]
#             Piece length extracted from VARS section
#         dy : Optional[float]
#             Piece height
#         dz : Optional[float]
#             Piece thickness
#     """

#     def __init__(self, filepath: str):
#         """Initialize HopFile parser.

#         Args:
#             filepath: Path to the .hop file
#         """
#         self.filepath = filepath
#         self.header: List[str] = []
#         self.vars_section: List[str] = []
#         self.operations: List[HopOperation] = []
#         self.dx: Optional[float] = None
#         self.dy: Optional[float] = None
#         self.dz: Optional[float] = None
#         self._parse()

#     def _parse(self):
#         """Parse the .hop file into header, vars, and operations."""
#         with open(self.filepath, "r", encoding="utf-8", errors="ignore") as f:
#             lines = f.readlines()

#         # Extract header comments
#         i = 0
#         while i < len(lines) and lines[i].startswith(";"):
#             self.header.append(lines[i])
#             i += 1

#         # Extract VARS section (up to START)
#         while i < len(lines) and "START" not in lines[i]:
#             self.vars_section.append(lines[i])
#             # Extract DX, DY, DZ values
#             if "DX :=" in lines[i]:
#                 match = re.search(r"DX := ([-+]?\d+\.?\d*)", lines[i])
#                 if match:
#                     self.dx = float(match.group(1))
#             elif "DY :=" in lines[i]:
#                 match = re.search(r"DY := ([-+]?\d+\.?\d*)", lines[i])
#                 if match:
#                     self.dy = float(match.group(1))
#             elif "DZ :=" in lines[i]:
#                 match = re.search(r"DZ := ([-+]?\d+\.?\d*)", lines[i])
#                 if match:
#                     self.dz = float(match.group(1))
#             i += 1

#         # Add START line
#         if i < len(lines):
#             self.vars_section.append(lines[i])
#             i += 1

#         # Skip FERTIGTEIL and Park lines (part of initialization, not operations)
#         while i < len(lines) and not (lines[i].strip().startswith("WZ")):
#             i += 1

#         # Parse operations (WZF/WZS blocks)
#         while i < len(lines):
#             if lines[i].strip().startswith("WZ"):
#                 tool_command = lines[i]
#                 operation_lines = [tool_command]
#                 i += 1

#                 # Collect lines until next tool command or end of file
#                 while i < len(lines) and not lines[i].strip().startswith("WZ"):
#                     # Stop at EBENE0() at root level (signals end of operation)
#                     if lines[i].strip() == "EBENE0()" and i + 1 < len(lines) and not lines[i + 1].strip().startswith("SAEGEN"):
#                         break
#                     operation_lines.append(lines[i])
#                     i += 1

#                 self.operations.append(HopOperation(tool_command, operation_lines))
#             else:
#                 i += 1

#     def __repr__(self) -> str:
#         """Return string representation for debugging."""
#         return f"HopFile(filepath='{self.filepath}', operations={len(self.operations)}, dx={self.dx}, dy={self.dy}, dz={self.dz})"
