"""HOPSJob - Complete HOP file parser and container.

This module provides a complete parser for HOP files, creating structured
representations of all machining operations with their associated tools and work planes.
"""

import warnings
from dataclasses import dataclass
from dataclasses import field
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from .hop_core import FinishedPart
from .hop_core import ParkMode
from .hop_core import VarsDefinition
from .machining_commands import G01
from .machining_commands import G02M
from .machining_commands import G03M
from .machining_commands import DrillingOperation
from .machining_commands import EndPoint
from .machining_commands import MillingOperation
from .machining_commands import SawingOperation
from .machining_commands import StartPoint
from .tool_library import MachiningTool
from .work_planes import FreePlane
from .work_planes import WorkPlane


class HOPParsingError(Exception):
    """Base exception for HOP file parsing errors."""

    pass


class UnparsedLineError(HOPParsingError):
    """Exception for lines that couldn't be parsed.

    Attributes:
        line_number: Line number in the file (1-indexed)
        line_content: The actual line content
        context: Additional context about what was expected
    """

    def __init__(self, line_number: int, line_content: str, context: str = ""):
        self.line_number = line_number
        self.line_content = line_content
        self.context = context
        message = f"HOP PARSING ERROR - Line {line_number}: {context}\n  Line context: {line_content.strip()}"
        super().__init__(message)


@dataclass
class HOPChunk:
    """Represents a logical chunk of HOP file lines.

    Attributes:
        lines: The code lines for this chunk (without comments)
        comments: Associated comment lines (usually header comments)
        start_line: Line number where chunk starts (1-indexed)
        chunk_type: Type of chunk ('header', 'vars', 'finished_part', 'park_mode', 'machining')
    """

    lines: List[str]
    comments: List[str] = field(default_factory=list)
    start_line: int = 0
    chunk_type: str = ""


class HOPSMachining:
    """Represents machining operations with their tool and work plane.

    This class associates one or more machining operations (milling, sawing, or drilling)
    with the tool and work plane used for those operations. A single tool+workplane
    combination can have multiple operations (e.g., multiple milling paths).

    Attributes:
    -----------
    tool : MachiningTool
        The machining tool used for these operations
    work_plane : Union[WorkPlane, FreePlane]
        The work plane on which these operations are performed
    operations : List[Union[MillingOperation, SawingOperation, DrillingOperation]]
        The actual machining operations (one or more)

    Example:
    --------
    >>> from .tool_library import MachiningTool
    >>> from .work_planes import WorkPlane
    >>> tool = MachiningTool.from_hop_line("WZF(1,10,0,0)")
    >>> plane = WorkPlane.from_hop_line("EBENE(1)")
    >>> op1 = MillingOperation(SP(...), [G01(...)], EP(...))
    >>> op2 = MillingOperation(SP(...), [G01(...)], EP(...))
    >>> machining = HOPSMachining(tool, plane, [op1, op2])
    """

    def __init__(
        self,
        tool: MachiningTool,
        work_plane: Union[WorkPlane, FreePlane],
        operations: List[Union[MillingOperation, SawingOperation, DrillingOperation]],
        comments: Optional[List[str]] = None,
    ):
        self.tool = tool
        self.work_plane = work_plane
        # Ensure operations is always a list
        if isinstance(operations, list):
            self.operations = operations
        else:
            self.operations = [operations]
        self.comments = comments or []

    def __repr__(self) -> str:
        """Return string representation."""
        op_count = len(self.operations)
        return f"Machining(tool={self.tool.tool_type.value}@{self.tool.position}, plane={self.work_plane}, ops={op_count}x{type(self.operations[0]).__name__ if self.operations else 'None'})"

    def __str__(self) -> str:
        """Generate HOPS commands for this machining.

        Returns comments, tool, work plane, and all operations on separate lines.
        """
        lines = []
        # Add comments first
        if self.comments:
            lines.extend(self.comments)
        lines.extend([str(self.tool), str(self.work_plane)])
        for operation in self.operations:
            lines.append(str(operation))
        return "\n".join(lines)


class HOPSJob:
    """Represents a complete HOP file with all its components.

    A HOPSJob contains:
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
    machinings : List[:class:`HOPSMachining`]
        List of all machining operations with their tools and work planes
    header : Optional[List[str]]
        Comment lines from the start of the file

    Example:
    --------
    >>> vars_def = VarsDefinition(dx=100.0, dy=200.0, dz=50.0)
    >>> finished_part = FinishedPart(dx=100.0, dy=200.0, dz=50.0)
    >>> park_mode = ParkMode(mode=11, pos_x=0, pos_y=0)
    >>> machinings = [HOPSMachining(tool, plane, operation)]
    >>> job = HOPSJob(vars_def, finished_part, park_mode, machinings)

    Or parse from file:
    >>> job = HOPSJob.from_hop_file("path/to/file.hop")
    >>> print(f"Piece dimensions: {job.vars.dx} x {job.vars.dy} x {job.vars.dz}")
    >>> for i, machining in enumerate(job.machinings):
    ...     print(f"Operation {i}: {machining.tool.tool_name} on {machining.work_plane}")
    """

    def __init__(
        self,
        vars: VarsDefinition,
        finished_part: FinishedPart,
        park_mode: ParkMode,
        machinings: List[HOPSMachining],
        header: Optional[List[str]] = None,
    ):
        self.vars = vars
        self.finished_part = finished_part
        self.park_mode = park_mode
        self.machinings = machinings
        self.header = header

    def __repr__(self) -> str:
        """Return string representation."""
        return f"HOPSJob(vars={self.vars}, machinings={len(self.machinings)})"

    def __str__(self) -> str:
        """Generate HOP file content from this job.

        Returns:
        --------
        str
            Complete HOP file content
        """
        return self._to_hop_lines()

    @staticmethod
    def _extract_header_lines(lines: List[str], start_idx: int) -> Tuple[Optional[HOPChunk], int]:
        """Extract header comment lines from the beginning of the file.

        Returns:
        --------
        Tuple of (header_chunk, next_index)
        """
        idx = start_idx
        header_lines = []

        while idx < len(lines) and lines[idx].strip().startswith(";"):
            header_lines.append(lines[idx])
            idx += 1

        if header_lines:
            header_chunk = HOPChunk(lines=header_lines, comments=[], start_line=start_idx + 1, chunk_type="header")
            return header_chunk, idx

        return None, idx

    @staticmethod
    def _extract_vars_lines(lines: List[str], start_idx: int) -> Tuple[Optional[HOPChunk], int]:
        """Extract VARS section lines (VARS...START), separating code from comments.

        Returns:
        --------
        Tuple of (vars_chunk, next_index)
        """
        if start_idx >= len(lines):
            return None, start_idx

        idx = start_idx
        vars_start = idx
        vars_code = []
        vars_comments = []

        # Collect lines until START
        while idx < len(lines):
            line = lines[idx]
            stripped = line.strip()

            if stripped.startswith(";"):
                vars_comments.append(line)
            else:
                vars_code.append(line)

            if "START" in line:
                idx += 1
                vars_chunk = HOPChunk(lines=vars_code, comments=vars_comments, start_line=vars_start + 1, chunk_type="vars")
                return vars_chunk, idx

            idx += 1

        return None, idx

    @staticmethod
    def _extract_finished_part_lines(lines: List[str], start_idx: int) -> Tuple[Optional[HOPChunk], int]:
        """Extract FERTIGTEIL line with any preceding comments.

        Returns:
        --------
        Tuple of (finished_part_chunk, next_index)
        """
        idx = start_idx

        # Skip lines until FERTIGTEIL
        while idx < len(lines):
            if lines[idx].strip().startswith("FERTIGTEIL("):
                break
            idx += 1

        if idx >= len(lines):
            return None, idx

        fp_line_idx = idx

        # Look back for any preceding comments
        comment_start = fp_line_idx
        while comment_start > 0 and lines[comment_start - 1].strip().startswith(";"):
            comment_start -= 1

        # Collect comments
        fp_comments = []
        for i in range(comment_start, fp_line_idx):
            if lines[i].strip().startswith(";"):
                fp_comments.append(lines[i])

        fp_code = [lines[fp_line_idx]]

        finished_part_chunk = HOPChunk(lines=fp_code, comments=fp_comments, start_line=comment_start + 1, chunk_type="finished_part")

        return finished_part_chunk, fp_line_idx + 1

    @staticmethod
    def _extract_park_mode_lines(lines: List[str], start_idx: int) -> Tuple[Optional[HOPChunk], int]:
        """Extract Park_V7 line with any preceding comments.

        Returns:
        --------
        Tuple of (park_mode_chunk, next_index)
        """
        idx = start_idx

        # Look for Park_V7
        while idx < len(lines):
            line = lines[idx].strip()

            if "Park_V7" in line:
                pm_line_idx = idx

                # Look back for preceding comments
                comment_start = pm_line_idx
                while comment_start > 0 and lines[comment_start - 1].strip().startswith(";"):
                    comment_start -= 1

                # Collect comments
                pm_comments = []
                for i in range(comment_start, pm_line_idx):
                    if lines[i].strip().startswith(";"):
                        pm_comments.append(lines[i])

                pm_code = [lines[pm_line_idx]]

                park_mode_chunk = HOPChunk(lines=pm_code, comments=pm_comments, start_line=comment_start + 1, chunk_type="park_mode")

                return park_mode_chunk, pm_line_idx + 1

            elif line.startswith("WZ"):
                # Reached machining section
                break

            idx += 1

        return None, idx

    @staticmethod
    def _extract_machining_lines(lines: List[str], start_idx: int) -> List[HOPChunk]:
        """Extract all machining chunks (WZF/WZS/WZB blocks with operations).

        Returns:
        --------
        List of machining chunks
        """
        machining_chunks = []
        idx = start_idx

        while idx < len(lines):
            line = lines[idx].strip()

            # Start of machining block - collect preceding comments
            if line.startswith("WZF(") or line.startswith("WZS(") or line.startswith("WZB("):
                # Look back to collect comments immediately before this tool definition
                comment_start = idx - 1
                mach_comments = []

                # Collect comments going backwards until we hit non-comment
                while comment_start >= start_idx:
                    prev_line = lines[comment_start].strip()
                    if prev_line.startswith(";"):
                        mach_comments.insert(0, lines[comment_start])
                        comment_start -= 1
                    elif not prev_line:  # Empty line - keep going back
                        comment_start -= 1
                    else:
                        # Hit non-comment code, stop
                        break

                mach_start = idx
                mach_code = []

                # Collect everything until next tool change
                while idx < len(lines):
                    line = lines[idx]
                    stripped = line.strip()

                    # Stop at next tool change
                    if idx > mach_start and (stripped.startswith("WZF(") or stripped.startswith("WZS(") or stripped.startswith("WZB(")):
                        break

                    # Only collect non-comment, non-empty lines for code
                    if not stripped.startswith(";") and stripped:
                        mach_code.append(line)

                    idx += 1

                if mach_code:
                    machining_chunks.append(
                        HOPChunk(
                            lines=mach_code,
                            comments=mach_comments,
                            start_line=mach_start + 1,
                            chunk_type="machining",
                        )
                    )
            else:
                idx += 1

        return machining_chunks

    @staticmethod
    def _split_lines(
        lines: List[str],
    ) -> Tuple[Optional[HOPChunk], Optional[HOPChunk], Optional[HOPChunk], Optional[HOPChunk], List[HOPChunk]]:
        """Split HOP file lines into logical chunks.

        Phase 1 of parsing: identify logical blocks without parsing content.
        Separates comments from code lines for each chunk.

        Returns:
        --------
        Tuple of (header_chunk, vars_chunk, finished_part_chunk, park_mode_chunk, machining_chunks)
        """
        idx = 0

        # Extract each section sequentially
        header_chunk, idx = HOPSJob._extract_header_lines(lines, idx)
        vars_chunk, idx = HOPSJob._extract_vars_lines(lines, idx)
        finished_part_chunk, idx = HOPSJob._extract_finished_part_lines(lines, idx)
        park_mode_chunk, idx = HOPSJob._extract_park_mode_lines(lines, idx)
        machining_chunks = HOPSJob._extract_machining_lines(lines, idx)

        return header_chunk, vars_chunk, finished_part_chunk, park_mode_chunk, machining_chunks

    @classmethod
    def from_hop_file(cls, filepath: str, strict: bool = False) -> "HOPSJob":
        """Parse a HOP file and create a HOPSJob.

        Parameters:
        -----------
        filepath : str
            Path to the HOP file to parse
        strict : bool, optional
            If True, raises UnparsedLineError for any unparseable lines.
            If False (default), collects unparsed lines as warnings.

        Returns:
        --------
        HOPSJob
            Parsed HOPSJob object with all machinings

        Raises:
        -------
        HOPParsingError
            If strict=True and parsing encounters errors

        Example:
        --------
        >>> job = HOPSJob.from_hop_file("part.hop")
        >>> print(f"Found {len(job.machinings)} operations")

        >>> # Strict mode - raises on any parsing error
        >>> try:
        ...     job = HOPSJob.from_hop_file("part.hop", strict=True)
        ... except UnparsedLineError as e:
        ...     print(f"Parse error at line {e.line_number}: {e.context}")
        """
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        # PHASE 1: Split file into chunks
        header_chunk, vars_chunk, fp_chunk, pm_chunk, mach_chunks = cls._split_lines(lines)

        # PHASE 2: Parse each chunk independently
        # Parse header
        header_lines = None
        if header_chunk:
            header_lines = [line.rstrip() for line in header_chunk.lines]

        # Parse VARS
        vars_def = None
        if vars_chunk:
            vars_def = cls._parse_vars_chunk(vars_chunk)

        # Parse FERTIGTEIL
        finished_part_def = None
        if fp_chunk:
            finished_part_def = cls._parse_finished_part_chunk(fp_chunk)

        # Parse Park Mode
        park_mode_def = None
        if pm_chunk:
            park_mode_def = cls._parse_park_mode_chunk(pm_chunk)

        # Parse machining chunks
        machinings_list = []
        unparsed_errors = []
        for mach_chunk in mach_chunks:
            machining, errors = cls._parse_machining_chunk(mach_chunk, strict=strict)
            if machining:
                machinings_list.append(machining)
            if errors:
                unparsed_errors.extend(errors)

        # In strict mode, raise if there were any unparsed lines
        if strict and unparsed_errors:
            # Raise the first error
            raise unparsed_errors[0]

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
    def _parse_vars_chunk(chunk: HOPChunk) -> Optional[VarsDefinition]:
        """Parse VARS chunk.

        Returns:
        --------
        Optional[VarsDefinition]
            Parsed VarsDefinition or None if parsing failed
        """
        try:
            vars_def = VarsDefinition.from_hop_line(chunk.lines)
            return vars_def
        except Exception:
            return None

    @staticmethod
    def _parse_finished_part_chunk(chunk: HOPChunk) -> Optional[FinishedPart]:
        """Parse FERTIGTEIL chunk.

        Returns:
        --------
        Optional[FinishedPart]
            Parsed FinishedPart or None if parsing failed
        """
        # chunk.lines contains only code lines (no comments)
        if chunk.lines:
            try:
                finished_part = FinishedPart.from_hop_line(chunk.lines[0].strip())
                return finished_part
            except Exception:
                return None
        return None

    @staticmethod
    def _parse_park_mode_chunk(chunk: HOPChunk) -> Optional[ParkMode]:
        """Parse Park Mode chunk.

        Returns:
        --------
        Optional[ParkMode]
            Parsed ParkMode or None if parsing failed
        """
        # chunk.lines contains only code lines (no comments)
        if chunk.lines:
            try:
                park_mode = ParkMode.from_hop_line(chunk.lines[0].strip())
                return park_mode
            except Exception:
                return None
        return None

    @staticmethod
    def _parse_machining_chunk(chunk: HOPChunk, strict: bool = False) -> Tuple[Optional[HOPSMachining], List[UnparsedLineError]]:
        """Parse a machining chunk (tool + work plane + operations).

        A single chunk may contain multiple operations using the same
        tool and work plane (e.g., multiple milling paths).

        Parameters:
        -----------
        chunk : HOPChunk
            The chunk to parse
        strict : bool
            If True, collect unparsed line errors

        Returns:
        --------
        Tuple[Optional[HOPSMachining], List[UnparsedLineError]]
            Tuple of (parsed HOPSMachining with list of operations or None, list of errors)
        """

        # Find tool line (first non-comment line)
        tool = None
        work_plane = None
        operations = []
        errors = []

        chunk_idx = 0

        # Parse tool (WZF/WZS/WZB)
        while chunk_idx < len(chunk.lines):
            line = chunk.lines[chunk_idx].strip()
            if line.startswith("WZF(") or line.startswith("WZS(") or line.startswith("WZB("):
                try:
                    tool = MachiningTool.from_hop_line(line)
                    chunk_idx += 1
                    break
                except Exception:
                    if strict:
                        errors.append(UnparsedLineError(line_number=chunk.start_line + chunk_idx, line_content=chunk.lines[chunk_idx], context="Failed to parse tool line"))
                    return None, errors
            chunk_idx += 1

        if not tool:
            if strict:
                errors.append(UnparsedLineError(line_number=chunk.start_line, line_content="", context="No tool definition found in machining chunk"))
            return None, errors

        # Parse work plane (EBENE/EBENEF) - chunk.lines has no comments
        work_plane_start_idx = chunk_idx
        while chunk_idx < len(chunk.lines):
            line = chunk.lines[chunk_idx].strip()

            if line.startswith("EBENEF("):
                try:
                    work_plane = FreePlane.from_hop_line(line)
                    chunk_idx += 1
                    break
                except Exception:
                    if strict:
                        errors.append(
                            UnparsedLineError(line_number=chunk.start_line + chunk_idx, line_content=chunk.lines[chunk_idx], context="Failed to parse EBENEF work plane")
                        )
                    return None, errors
            elif line.startswith("EBENE"):
                try:
                    work_plane = WorkPlane.from_hop_line(line)
                    chunk_idx += 1
                    break
                except Exception:
                    if strict:
                        errors.append(UnparsedLineError(line_number=chunk.start_line + chunk_idx, line_content=chunk.lines[chunk_idx], context="Failed to parse EBENE work plane"))
                    return None, errors
            elif line.startswith("SP(") or line.startswith("SAEGEN(") or line.startswith("BOHR("):
                # Found operation before work plane - this is an error
                if strict:
                    errors.append(
                        UnparsedLineError(line_number=chunk.start_line + chunk_idx, line_content=chunk.lines[chunk_idx], context="Found operation before work plane definition")
                    )
                return None, errors
            elif not line.startswith("CALL") and line:
                # Unknown line where we expected work plane
                if strict:
                    errors.append(
                        UnparsedLineError(
                            line_number=chunk.start_line + chunk_idx,
                            line_content=chunk.lines[chunk_idx],
                            context="Expected work plane definition (EBENE/EBENEF), got unknown command",
                        )
                    )
                    return None, errors
                # Skip non-work plane lines (like CALL feedrate)
                chunk_idx += 1
            else:
                # Skip CALL or empty lines
                chunk_idx += 1

        if not work_plane:
            if strict:
                errors.append(UnparsedLineError(line_number=chunk.start_line + work_plane_start_idx, line_content="", context="No work plane definition found after tool"))
            return None, errors

        # Parse ALL operations in this chunk (SP+G01+EP, SAEGEN, or BOHR)
        while chunk_idx < len(chunk.lines):
            line = chunk.lines[chunk_idx].strip()

            # Skip CALL feedrate commands
            if line.startswith("CALL"):
                chunk_idx += 1
                continue

            operation = None
            try:
                if line.startswith("SP("):
                    # Parse milling and get next index
                    operation, next_idx = HOPSJob._parse_milling_from_chunk(chunk, chunk_idx)
                    if operation:
                        operations.append(operation)
                        chunk_idx = next_idx
                    else:
                        # Parsing failed, skip this line to avoid infinite loop
                        chunk_idx += 1
                    # chunk_idx already advanced past EP
                elif line.startswith("SAEGEN("):
                    operation = SawingOperation.from_hop_line(line)
                    if operation:
                        operations.append(operation)
                    chunk_idx += 1
                elif line.startswith("BOHR("):
                    operation = DrillingOperation.from_hop_line(line)
                    if operation:
                        operations.append(operation)
                    chunk_idx += 1
                else:
                    # Unknown line, skip it
                    chunk_idx += 1
            except Exception:
                # Error parsing operation, skip this line
                chunk_idx += 1

        # Return machining with all collected operations
        if operations:
            return HOPSMachining(tool, work_plane, operations, comments=chunk.comments), errors

        return None, errors

    @staticmethod
    def _parse_milling_from_chunk(chunk: HOPChunk, start_idx: int) -> Tuple[Optional[MillingOperation], int]:
        """Parse milling operation from chunk lines starting at start_idx.

        Returns:
        --------
        Tuple[Optional[MillingOperation], int]
            Tuple of (parsed MillingOperation or None, next index after EP)
        """
        chunk_idx = start_idx

        try:
            # Parse SP
            start_point = StartPoint.from_hop_line(chunk.lines[chunk_idx].strip())
            chunk_idx += 1

            # Parse G01 moves - chunk.lines has no comments
            moves = []
            while chunk_idx < len(chunk.lines):
                line = chunk.lines[chunk_idx].strip()
                if line.startswith("G01("):
                    move = G01.from_hop_line(line)
                    moves.append(move)
                    chunk_idx += 1
                elif line.startswith("G02M("):
                    move = G02M.from_hop_line(line)
                    moves.append(move)
                    chunk_idx += 1
                elif line.startswith("G03M("):
                    move = G03M.from_hop_line(line)
                    moves.append(move)
                    chunk_idx += 1
                elif line.startswith("EP("):
                    break
                elif line.startswith("CALL"):
                    chunk_idx += 1
                else:
                    break

            # Parse EP
            if chunk_idx < len(chunk.lines) and chunk.lines[chunk_idx].strip().startswith("EP("):
                end_point = EndPoint.from_hop_line(chunk.lines[chunk_idx].strip())
                chunk_idx += 1  # Move past EP

                return MillingOperation(
                    start_point=start_point,
                    moves=moves,
                    end_point=end_point,
                ), chunk_idx
            else:
                return None, chunk_idx

        except Exception:
            return None, start_idx

    def _to_hop_lines(self) -> str:
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
