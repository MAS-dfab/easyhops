"""HopsJob - Complete HOP file parser and container.

This module provides a complete parser for HOP files, creating structured
representations of all machining operations with their associated tools and work planes.
"""

import warnings
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from .hop_core import FinishedPart
from .hop_core import ParkMode
from .hop_core import VarsDefinition
from .machining_commands import G01
from .machining_commands import DrillingOperation
from .machining_commands import EndPoint
from .machining_commands import Machining
from .machining_commands import MillingOperation
from .machining_commands import SawingOperation
from .machining_commands import StartPoint
from .tool_library import MachiningTool
from .work_planes import FreePlane
from .work_planes import WorkPlane


class HopsJob:
    """Represents a complete HOP file with all its components.

    A HopsJob contains:
    - Variable definitions (piece dimensions)
    - Finished part definition
    - Park mode settings
    - List of Machining instances (each with tool, work plane, and operation)

    Parameters:
    -----------
    vars : :class:`VarsDefinition`
        Variable definitions (DX, DY, DZ)
    finished_part : :class:`FinishedPart`
        Finished part definition
    park_mode : :class:`ParkMode`
        Park mode settings
    machinings : List[:class:`Machining`]
        List of all machining operations with their tools and work planes
    header : Optional[List[str]]
        Comment lines from the start of the file

    Example:
    --------
    >>> vars_def = VarsDefinition(dx=100.0, dy=200.0, dz=50.0)
    >>> finished_part = FinishedPart(dx=100.0, dy=200.0, dz=50.0)
    >>> park_mode = ParkMode(mode=11, pos_x=0, pos_y=0)
    >>> machinings = [Machining(tool, plane, operation)]
    >>> job = HopsJob(vars_def, finished_part, park_mode, machinings)

    Or parse from file:
    >>> job = HopsJob.from_hop_file("path/to/file.hop")
    >>> print(f"Piece dimensions: {job.vars.dx} x {job.vars.dy} x {job.vars.dz}")
    >>> for i, machining in enumerate(job.machinings):
    ...     print(f"Operation {i}: {machining.tool.tool_name} on {machining.work_plane}")
    """

    def __init__(
        self,
        vars: VarsDefinition,
        finished_part: FinishedPart,
        park_mode: ParkMode,
        machinings: List[Machining],
        header: Optional[List[str]] = None,
    ):
        self.vars = vars
        self.finished_part = finished_part
        self.park_mode = park_mode
        self.machinings = machinings
        self.header = header

    @classmethod
    def from_hop_file(cls, filepath: str) -> "HopsJob":
        """Parse a HOP file and create a HopsJob.

        Parameters:
        -----------
        filepath : str
            Path to the HOP file to parse

        Returns:
        --------
        HopsJob
            Parsed HopsJob object with all machinings

        Example:
        --------
        >>> job = HopsJob.from_hop_file("part.hop")
        >>> print(f"Found {len(job.machinings)} operations")
        """
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        # Initialize temporary parsing state
        vars_def: Optional[VarsDefinition] = None
        finished_part_def: Optional[FinishedPart] = None
        park_mode_def: Optional[ParkMode] = None
        machinings_list: List[Machining] = []
        unparsed_lines: List[Tuple[int, str]] = []
        warnings_list: List[str] = []
        header_lines: List[str] = []

        i = 0

        # Collect header comments
        while i < len(lines) and lines[i].strip().startswith(";"):
            header_lines.append(lines[i].rstrip())
            i += 1

        # Parse VARS section
        i, vars_def = cls._parse_vars_section(lines, i, unparsed_lines, warnings_list)

        # Parse FERTIGTEIL
        i, finished_part_def = cls._parse_finished_part(lines, i, unparsed_lines, warnings_list)

        # Parse Park mode
        i, park_mode_def = cls._parse_park_mode(lines, i, unparsed_lines, warnings_list)

        # Parse operations
        machinings_list = cls._parse_operations(lines, i, unparsed_lines, warnings_list)

        # Emit warnings for unparsed lines
        if unparsed_lines:
            msg = f"Skipped {len(unparsed_lines)} unparsed line(s) in {filepath}"
            warnings_list.append(msg)
            warnings.warn(msg, UserWarning)

        # Create job with parsed components
        job = cls(
            vars=vars_def or VarsDefinition(0.0, 0.0, 0.0),
            finished_part=finished_part_def or FinishedPart(None, None, None),
            park_mode=park_mode_def or ParkMode(),
            machinings=machinings_list,
            header=header_lines if header_lines else None,
        )

        return job

    @staticmethod
    def _parse_vars_section(lines: List[str], start_idx: int, unparsed_lines: List[Tuple[int, str]], warnings_list: List[str]) -> Tuple[int, Optional[VarsDefinition]]:
        """Parse VARS section (VARS...START).

        Returns:
        --------
        Tuple[int, Optional[VarsDefinition]]
            Index of the line after START and parsed VarsDefinition
        """
        vars_lines = []
        i = start_idx

        # Collect lines until START
        while i < len(lines):
            line = lines[i]
            vars_lines.append(line)
            if "START" in line:
                i += 1
                break
            i += 1

        # Parse VARS
        try:
            vars_def = VarsDefinition.from_hop_line(vars_lines)
            return i, vars_def
        except Exception as e:
            warnings_list.append(f"Failed to parse VARS section: {e}")
            unparsed_lines.extend([(start_idx + j, line) for j, line in enumerate(vars_lines)])
            return i, None

    @staticmethod
    def _parse_finished_part(lines: List[str], start_idx: int, unparsed_lines: List[Tuple[int, str]], warnings_list: List[str]) -> Tuple[int, Optional[FinishedPart]]:
        """Parse FERTIGTEIL line.

        Returns:
        --------
        Tuple[int, Optional[FinishedPart]]
            Index of the next line and parsed FinishedPart
        """
        i = start_idx

        # Look for FERTIGTEIL
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("FERTIGTEIL("):
                try:
                    finished_part = FinishedPart.from_hop_line(line)
                    return i + 1, finished_part
                except Exception as e:
                    warnings_list.append(f"Failed to parse FERTIGTEIL at line {i + 1}: {e}")
                    unparsed_lines.append((i, lines[i]))
                    return i + 1, None
            elif line and not line.startswith(";"):
                # Non-comment, non-FERTIGTEIL line
                break
            i += 1

        return i, None

    @staticmethod
    def _parse_park_mode(lines: List[str], start_idx: int, unparsed_lines: List[Tuple[int, str]], warnings_list: List[str]) -> Tuple[int, Optional[ParkMode]]:
        """Parse CALL Park_V7 line.

        Returns:
        --------
        Tuple[int, Optional[ParkMode]]
            Index of the next line and parsed ParkMode
        """
        i = start_idx

        # Look for Park_V7
        while i < len(lines):
            line = lines[i].strip()
            if "Park_V7" in line:
                try:
                    park_mode = ParkMode.from_hop_line(line)
                    return i + 1, park_mode
                except Exception as e:
                    warnings_list.append(f"Failed to parse Park_V7 at line {i + 1}: {e}")
                    unparsed_lines.append((i, lines[i]))
                    return i + 1, None
            elif line.startswith("WZ"):
                # Reached operations section
                break
            elif line and not line.startswith(";"):
                # Skip other initialization lines
                i += 1
            else:
                i += 1

        return i, None

    @staticmethod
    def _parse_operations(lines: List[str], start_idx: int, unparsed_lines: List[Tuple[int, str]], warnings_list: List[str]) -> List[Machining]:
        """Parse all machining operations (WZF/WZS blocks).

        Each operation consists of:
        - Tool command (WZF or WZS)
        - Work plane (EBENE or EBENEF)
        - Machining commands (SP+G01+EP, SAEGEN, or BOHR)
        """
        machinings = []
        i = start_idx

        while i < len(lines):
            line = lines[i].strip()

            # Tool change - start of new operation context
            if line.startswith("WZF(") or line.startswith("WZS("):
                try:
                    # Parse tool
                    tool = MachiningTool.from_hop_line(line)
                    i += 1

                    # Parse work plane
                    work_plane, i = HopsJob._parse_work_plane(lines, i, unparsed_lines, warnings_list)

                    # Parse machining operation(s) with this tool/plane
                    i = HopsJob._parse_machining_operations(lines, i, tool, work_plane, machinings, unparsed_lines, warnings_list)

                except Exception as e:
                    warnings_list.append(f"Failed to parse operation at line {i + 1}: {e}")
                    unparsed_lines.append((i, lines[i]))
                    i += 1
            else:
                i += 1

        return machinings

    @staticmethod
    def _parse_work_plane(lines: List[str], start_idx: int, unparsed_lines: List[Tuple[int, str]], warnings_list: List[str]) -> Tuple[Union[WorkPlane, FreePlane], int]:
        """Parse work plane definition.

        Returns:
        --------
        Tuple[Union[WorkPlane, FreePlane], int]
            Parsed work plane and index of next line
        """
        i = start_idx
        line = lines[i].strip()

        try:
            if line.startswith("EBENEF("):
                plane = FreePlane.from_hop_line(line)
                return plane, i + 1
            elif line.startswith("EBENE"):
                plane = WorkPlane.from_hop_line(line)
                return plane, i + 1
            else:
                warnings_list.append(f"Expected work plane at line {i + 1}, found: {line}")
                unparsed_lines.append((i, lines[i]))
                return None, i + 1
        except Exception as e:
            warnings_list.append(f"Failed to parse work plane at line {i + 1}: {e}")
            unparsed_lines.append((i, lines[i]))
            return None, i + 1

    @staticmethod
    def _parse_machining_operations(
        lines: List[str],
        start_idx: int,
        tool: MachiningTool,
        work_plane: Union[WorkPlane, FreePlane],
        machinings: List[Machining],
        unparsed_lines: List[Tuple[int, str]],
        warnings_list: List[str],
    ) -> int:
        """Parse machining operations until next tool change.

        Returns:
        --------
        int
            Index after parsing operations
        """
        i = start_idx

        while i < len(lines):
            line = lines[i].strip()

            # Stop at next tool change
            if line.startswith("WZF(") or line.startswith("WZS("):
                break

            # Skip comments and empty lines
            if not line or line.startswith(";"):
                i += 1
                continue

            # Parse specific operation types
            try:
                if line.startswith("SP("):
                    # Milling operation
                    operation, i = HopsJob._parse_milling_operation(lines, i, unparsed_lines, warnings_list)
                    if operation:
                        machining = Machining(tool, work_plane, operation)
                        machinings.append(machining)

                elif line.startswith("SAEGEN("):
                    # Sawing operation
                    operation = SawingOperation.from_hop_line(line)
                    machining = Machining(tool, work_plane, operation)
                    machinings.append(machining)
                    i += 1

                elif line.startswith("BOHR("):
                    # Drilling operation
                    operation = DrillingOperation.from_hop_line(line)
                    machining = Machining(tool, work_plane, operation)
                    machinings.append(machining)
                    i += 1

                elif line.startswith("CALL") or line.startswith("EBENE"):
                    # Skip feedrate calls and plane resets
                    i += 1

                else:
                    # Unrecognized line
                    unparsed_lines.append((i, lines[i]))
                    i += 1

            except Exception as e:
                warnings_list.append(f"Failed to parse operation at line {i + 1}: {e}")
                unparsed_lines.append((i, lines[i]))
                i += 1

        return i

    @staticmethod
    def _parse_milling_operation(lines: List[str], start_idx: int, unparsed_lines: List[Tuple[int, str]], warnings_list: List[str]) -> Tuple[Optional[MillingOperation], int]:
        """Parse a milling operation (SP + G01 moves + EP).

        Returns:
        --------
        Tuple[Optional[MillingOperation], int]
            Parsed MillingOperation and index after EP
        """
        i = start_idx

        try:
            # Parse SP
            start_point = StartPoint.from_hop_line(lines[i].strip())
            i += 1

            # Parse G01 moves
            moves = []
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith("G01("):
                    move = G01.from_hop_line(line)
                    moves.append(move)
                    i += 1
                elif line.startswith("EP("):
                    break
                elif line.startswith("CALL"):
                    # Skip feedrate commands
                    i += 1
                elif not line or line.startswith(";"):
                    # Skip empty lines and comments
                    i += 1
                else:
                    # Unexpected line
                    break

            # Parse EP
            if i < len(lines) and lines[i].strip().startswith("EP("):
                end_point = EndPoint.from_hop_line(lines[i].strip())
                i += 1

                # Create milling operation
                operation = MillingOperation(
                    start_point=start_point,
                    moves=moves,
                    end_point=end_point,
                )
                return operation, i
            else:
                warnings_list.append(f"Milling operation starting at line {start_idx + 1} has no EP")
                return None, i

        except Exception as e:
            warnings_list.append(f"Failed to parse milling operation at line {start_idx + 1}: {e}")
            return None, start_idx + 1

    def __repr__(self) -> str:
        """Return string representation."""
        return f"HopsJob(vars={self.vars}, machinings={len(self.machinings)})"

    def __str__(self) -> str:
        """Generate HOP file content from this job.

        Returns:
        --------
        str
            Complete HOP file content
        """
        lines = []

        # Header comments
        if self.header:
            lines.extend(self.header)
            lines.append("")

        # VARS section
        if self.vars:
            lines.append(str(self.vars))
            lines.append("")

        # FERTIGTEIL
        if self.finished_part:
            lines.append(str(self.finished_part))

        # Park mode
        if self.park_mode:
            lines.append(str(self.park_mode))
            lines.append("")

        # Machinings
        for machining in self.machinings:
            lines.append(str(machining))
            lines.append("")

        return "\n".join(lines)

    def to_hop_file(self, filepath: str):
        """Write this job to a HOP file.

        Parameters:
        -----------
        filepath : str
            Path to write the HOP file
        """
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(str(self))
