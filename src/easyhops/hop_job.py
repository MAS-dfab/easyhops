"""HOPSJob - Complete HOP file parser and container.

This module provides a complete parser for HOP files, creating structured
representations of all machining operations with their associated tools and work planes.
"""

import os
from dataclasses import dataclass
from dataclasses import field
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from .generate_jlx import JLXGenerator
from .hop_core import EasySnapXY
from .hop_core import EasySnapZ
from .hop_core import FinishedPart
from .hop_core import ParkMode
from .hop_core import ParkPosition
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
from .utility_commands import FeedrateOverride
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
    feedrate_overrides : List[Tuple[Tuple[int, Optional[int]], FeedrateOverride]]
        List of ((operation_idx, command_idx), FeedrateOverride) tuples.
        - operation_idx: index of the operation in self.operations
        - command_idx: None for sawing/drilling, or index within milling operation
          (0=before SP, 1=before first move, 2=before second move, ..., n+1=before EP)

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
        feedrate_overrides: Optional[List[Tuple[Tuple[int, Optional[int]], FeedrateOverride]]] = None,
    ):
        self.tool = tool
        self.work_plane = work_plane
        # Ensure operations is always a list
        if isinstance(operations, list):
            self.operations = operations
        else:
            self.operations = [operations]
        self.comments = comments or []
        self.feedrate_overrides = feedrate_overrides or []

    def __repr__(self) -> str:
        """Return string representation."""
        op_count = len(self.operations)
        return f"Machining(tool={self.tool.tool_type.value}@{self.tool.position}, plane={self.work_plane}, ops={op_count}x{type(self.operations[0]).__name__ if self.operations else 'None'})"  # noqa: E501

    def __str__(self) -> str:
        """Generate HOPS commands for this machining.

        Returns comments, tool, work plane, feedrate overrides, and all operations on separate lines.
        Feedrate overrides are inserted at their correct positions, including within milling operations.
        """
        lines = []
        # Add comments first
        if self.comments:
            lines.extend(self.comments)
        lines.extend([str(self.tool), str(self.work_plane)])

        # Add operations with feedrate overrides in the correct positions
        for op_idx, operation in enumerate(self.operations):
            if isinstance(operation, MillingOperation):
                # For milling operations, insert feedrate overrides within the operation
                op_lines = self._milling_operation_with_feedrates(op_idx, operation)
                lines.extend(op_lines)
            else:
                # For sawing/drilling, check for feedrate override before the operation
                for (o_idx, cmd_idx), override in self.feedrate_overrides:
                    if o_idx == op_idx and cmd_idx is None:
                        lines.append(str(override))
                        break
                lines.append(str(operation))

        return "\n".join(lines)

    def _milling_operation_with_feedrates(self, op_idx: int, operation: MillingOperation) -> List[str]:
        """Generate lines for a milling operation with feedrate overrides inserted at correct positions."""
        # Build a map of command indices to feedrate overrides for this operation
        feedrate_map = {}
        for (o_idx, cmd_idx), override in self.feedrate_overrides:
            if o_idx == op_idx and cmd_idx is not None:
                feedrate_map[cmd_idx] = override

        lines = []
        cmd_idx = 0

        # Before SP
        if cmd_idx in feedrate_map:
            lines.append(str(feedrate_map[cmd_idx]))
        lines.append(str(operation.start_point))
        cmd_idx += 1

        # Before each move
        for move in operation.moves:
            if cmd_idx in feedrate_map:
                lines.append(str(feedrate_map[cmd_idx]))
            lines.append(str(move))
            cmd_idx += 1

        # Before EP
        if cmd_idx in feedrate_map:
            lines.append(str(feedrate_map[cmd_idx]))
        lines.append(str(operation.end_point))

        return lines


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

    def to_hop_file(self, filepath: str):
        """Write this job to a HOP file.

        Parameters:
        -----------
        filepath : str
            Path to write the HOP file
        """
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(str(self))

    def to_layout_file(
        self,
        filepath: str,
        hop_path: str = "",
        machine_id: str = "7235C_219",
        placement: Tuple[float, float, float] = (0, 0, 0),
    ):
        """Generate JLX layout file from this HOP job.

        Automatically extracts:
        - Dimensions (DX, DY, DZ) from vars
        - Bar positions (K1-K6) from custom variables (consoles)
        - HOP filename derived from JLX filepath (e.g., "S0_R01.jlx" → "S0_R01.hop")

        Parameters:
        -----------
        filepath : str
            Path to write the JLX file (e.g., "S0_R01.jlx" or "output_layout.jlx")
        hop_path : str, optional
            Path to HOP file directory, default empty string
        machine_id : str, optional
            Machine identifier, default "7235C_219"
        placement : Tuple[float, float, float], optional
            Workpiece placement (X, Y, Z), default (0, 0, 0)

        Raises:
        -------
        ValueError
            If custom variables don't contain exactly 6 bar positions (K1-K6)

        Example:
        --------
        >>> # Parse HOP file with K1-K6 custom variables
        >>> job = HOPSJob.from_hop_file("S0_R01.hop")
        >>> # Generate layout file - everything extracted automatically
        >>> job.to_layout_file("S0_R01.jlx")
        """

        # Extract bar positions from custom variables (K1, K2, K3, K4, K5, K6)
        bar_positions = []
        for i in range(1, 7):  # K1 through K6
            key = f"K{i}"
            if key not in self.vars.custom_vars:
                raise ValueError(f"Missing bar position variable '{key}' in custom variables. Expected K1-K6, found: {list(self.vars.custom_vars.keys())}")
            bar_positions.append(self.vars.custom_vars[key]["value"])

        # Derive HOP filename from JLX filepath
        hop_filename = os.path.basename(filepath).replace(".jlx", ".hop")

        # Create JLX generator
        generator = JLXGenerator(machine_id=machine_id)

        # Add workpiece with extracted dimensions and bar positions
        generator.add_workpiece(
            hop_filename=hop_filename,
            hop_path=hop_path,
            bar_positions=bar_positions,
            dimensions=(self.vars.dx, self.vars.dy, self.vars.dz),
            placement=placement,
        )

        # Write JLX file
        generator.write_jlx(filepath)

    @classmethod
    def from_hop_string(cls, hop_content: str, strict: bool = False) -> "HOPSJob":
        """Parse a HOP string and create a HOPSJob.

        Parameters:
        -----------
        hop_content : str
            Content of the HOP file as a string
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
        >>> job = HOPSJob.from_hop_string(hop_content)
        >>> print(f"Found {len(job.machinings)} operations")

        >>> # Strict mode - raises on any parsing error
        >>> try:
        ...     job = HOPSJob.from_hop_string(hop_content, strict=True)
        ... except UnparsedLineError as e:
        ...     print(f"Parse error at line {e.line_number}: {e.context}")
        """
        # PHASE 1: Split file into chunks
        lines = hop_content.splitlines(True)  # Split string into a list of lines
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
            park_mode=park_mode_def or ParkPosition(),
            machinings=machinings_list,
            header=header_lines if header_lines else None,
        )

        return job

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

        return cls.from_hop_string("".join(lines), strict=strict)

    @classmethod
    def from_timber_element(cls, element, tool: MachiningTool) -> "HOPSJob":
        """Create a HOPSJob from a TimberModel element.

        This method extracts machining information from the given TimberModel element,
        including its reference planes and associated machining operations, and constructs
        a HOPSJob with appropriate VarsDefinition, FinishedPart, ParkMode, and HOPSMachining instances.

        Parameters:
        -----------
        element : TimberElement
            The TimberModel element containing machining information
        tool : MachiningTool
            The tool to assign to all generated machining operations

        Returns:
        --------
        HOPSJob
            A HOPSJob instance representing the machining operations for the given element

        Example:
        --------
        >>> job = HOPSJob.from_timber_element(timber_element, tool)
        >>> print(f"Generated HOPSMachining for {len(job.machinings)} operations")
        """
        vars = VarsDefinition(dx=element.blank_length, dy=element.width, dz=element.height)
        finished_part = FinishedPart(dx=element.blank_length, dy=element.width, dz=element.height)
        park_mode = ParkPosition(mode=ParkMode.RIGHT_MIDDLE)
        machinings = []

        for processing in element.features:
            print(f"Processing feature with type '{processing.name}' and ref_side_index {processing.ref_side_index}")
            if processing.name == "FreeContour":
                # get contour polyline
                contour_polyline = processing.contour_param_object.polyline
                milling_operation = MillingOperation.from_polyline(contour_polyline)
                # get working plane
                if processing.ref_side_index >= 100:
                    ref_frame = element.get_user_ref_plane(processing.ref_side_index)
                else:
                    ref_frame = element.ref_sides[processing.ref_side_index]

                ref_frame_local = ref_frame.transformed(element.transformation_to_local())
                work_plane = FreePlane.from_frame(ref_frame_local, easy_snap_xy=EasySnapXY.CENTER_LEFT, easy_snap_z=EasySnapZ.BOTTOM_EDGE)

                machinings.append(HOPSMachining(tool=tool, work_plane=work_plane, operations=[milling_operation]))

        return cls(vars=vars, finished_part=finished_part, park_mode=park_mode, machinings=machinings)

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
    def _filter_verbose_comments(comments: List[str]) -> List[str]:
        """Filter out verbose machine-generated comments, keeping only meaningful operation names.

        Removes comments like:
        - "; Tool Selection"
        - "; Work Plane Definition: ..."
        - "; Compensation (Par...): ..."
        - "; ######## END MACH TYPE = ..."
        - "; Type LeadOut (Par...): ..."

        Keeps comments with operation names like:
        - "; S14_446,C_Birdsmouth_LongCut"
        - "; ---------------------------------"
        """
        filtered = []
        for comment in comments:
            stripped = comment.strip()
            # Keep separator lines and operation name comments
            if stripped == "; ---------------------------------":
                filtered.append(comment)
            # Skip verbose machine-generated comments
            elif any(
                pattern in stripped
                for pattern in [
                    "; Tool Selection",
                    "; Work Plane Definition:",
                    "; Compensation (Par",
                    "; ######## END MACH TYPE",
                    "; Type LeadOut (Par",
                    "; Type LeadIn (Par",
                ]
            ):
                continue
            # Keep other comments (like operation names)
            else:
                filtered.append(comment)
        return filtered

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

                # Filter out verbose machine-generated comments
                mach_comments = HOPSJob._filter_verbose_comments(mach_comments)

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
        """Parse a machining chunk (tool + work plane + operations + feedrate overrides).

        A single chunk may contain multiple operations using the same
        tool and work plane (e.g., multiple milling paths), along with
        feedrate override commands at various positions.

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
        feedrate_overrides = []  # Store (operation_index, FeedrateOverride) tuples
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
        # Also collect feedrate overrides and track their positions
        while chunk_idx < len(chunk.lines):
            line = chunk.lines[chunk_idx].strip()

            # Check if this might be the start of a milling operation
            # Milling can start with CALL _Tvorschub_v5 or directly with SP
            if line.startswith("CALL _Tvorschub_v5(") or line.startswith("SP("):
                # Look ahead to determine if this is a milling operation
                lookahead_idx = chunk_idx
                while lookahead_idx < len(chunk.lines):
                    lookahead_line = chunk.lines[lookahead_idx].strip()
                    if lookahead_line.startswith("SP("):
                        # This is a milling operation, parse it (including any preceding CALL commands)
                        operation, milling_feedrates, next_idx = HOPSJob._parse_milling_from_chunk(chunk, chunk_idx)
                        if operation:
                            # Add milling operation
                            op_idx = len(operations)
                            operations.append(operation)

                            # Add feedrate overrides for this milling operation with (op_idx, cmd_idx)
                            for cmd_idx, override in milling_feedrates:
                                feedrate_overrides.append(((op_idx, cmd_idx), override))

                            chunk_idx = next_idx
                        else:
                            # Parsing failed, skip this line to avoid infinite loop
                            chunk_idx += 1
                        break
                    elif lookahead_line.startswith("CALL"):
                        # Keep looking
                        lookahead_idx += 1
                    else:
                        # Not a milling operation, this CALL is for sawing/drilling
                        if line.startswith("CALL _Tvorschub_v5("):
                            try:
                                feedrate_override = FeedrateOverride.from_hop_line(line)
                                feedrate_overrides.append(((len(operations), None), feedrate_override))
                            except Exception:
                                pass
                        chunk_idx += 1
                        break
                else:
                    # Reached end of chunk without finding SP
                    chunk_idx += 1

            elif line.startswith("CALL"):
                # Other CALL commands, skip them
                chunk_idx += 1
            elif line.startswith("CALL"):
                # Other CALL commands, skip them
                chunk_idx += 1
            elif line.startswith("SAEGEN("):
                try:
                    operation = SawingOperation.from_hop_line(line)
                    if operation:
                        operations.append(operation)
                except Exception:
                    pass
                chunk_idx += 1
            elif line.startswith("BOHR("):
                try:
                    operation = DrillingOperation.from_hop_line(line)
                    if operation:
                        operations.append(operation)
                except Exception:
                    pass
                chunk_idx += 1
            else:
                # Unknown line, skip it
                chunk_idx += 1

        # Return machining with all collected operations and feedrate overrides
        if operations:
            return HOPSMachining(tool, work_plane, operations, comments=chunk.comments, feedrate_overrides=feedrate_overrides), errors

        return None, errors

    @staticmethod
    def _parse_milling_from_chunk(chunk: HOPChunk, start_idx: int) -> Tuple[Optional[MillingOperation], List[Tuple[int, FeedrateOverride]], int]:
        """Parse milling operation from chunk lines starting at start_idx.

        Returns:
        --------
        Tuple[Optional[MillingOperation], List[Tuple[int, FeedrateOverride]], int]
            Tuple of (parsed MillingOperation or None, list of (command_idx, FeedrateOverride), next index after EP)
            command_idx is relative to the milling operation (0=before SP, 1=before first move, etc.)
        """
        chunk_idx = start_idx
        feedrate_overrides = []  # (command_idx, FeedrateOverride)
        cmd_idx = 0  # Track position within milling operation

        try:
            # Find StartPoint (SP), checking for feedrate override before it
            while chunk_idx < len(chunk.lines):
                line = chunk.lines[chunk_idx].strip()

                if line.startswith("CALL _Tvorschub_v5("):
                    # Feedrate override before SP
                    try:
                        override = FeedrateOverride.from_hop_line(line)
                        feedrate_overrides.append((cmd_idx, override))
                    except Exception:
                        pass
                    chunk_idx += 1
                elif line.startswith("SP("):
                    start_point = StartPoint.from_hop_line(line)
                    chunk_idx += 1
                    cmd_idx += 1  # Increment to position for first move
                    break
                elif line.startswith("CALL"):
                    # Other CALL commands, skip
                    chunk_idx += 1
                else:
                    chunk_idx += 1
            else:
                return None, [], start_idx  # No SP found

            # Parse moves (G01, G02M, G03M), checking for feedrate overrides before each
            moves = []
            while chunk_idx < len(chunk.lines):
                line = chunk.lines[chunk_idx].strip()

                if line.startswith("CALL _Tvorschub_v5("):
                    # Feedrate override before next move or EP
                    try:
                        override = FeedrateOverride.from_hop_line(line)
                        feedrate_overrides.append((cmd_idx, override))
                    except Exception:
                        pass
                    chunk_idx += 1
                elif line.startswith("G01("):
                    moves.append(G01.from_hop_line(line))
                    chunk_idx += 1
                    cmd_idx += 1
                elif line.startswith("G02M("):
                    moves.append(G02M.from_hop_line(line))
                    chunk_idx += 1
                    cmd_idx += 1
                elif line.startswith("G03M("):
                    moves.append(G03M.from_hop_line(line))
                    chunk_idx += 1
                    cmd_idx += 1
                elif line.startswith("EP("):
                    break
                elif line.startswith("CALL"):
                    # Other CALL commands, skip
                    chunk_idx += 1
                else:
                    chunk_idx += 1  # Skip unknown lines

            # Parse EndPoint (EP), checking for feedrate override before it
            while chunk_idx < len(chunk.lines):
                line = chunk.lines[chunk_idx].strip()

                if line.startswith("CALL _Tvorschub_v5("):
                    # Feedrate override before EP
                    try:
                        override = FeedrateOverride.from_hop_line(line)
                        feedrate_overrides.append((cmd_idx, override))
                    except Exception:
                        pass
                    chunk_idx += 1
                elif line.startswith("EP("):
                    end_point = EndPoint.from_hop_line(line)
                    chunk_idx += 1
                    return MillingOperation(start_point=start_point, moves=moves, end_point=end_point), feedrate_overrides, chunk_idx
                elif line.startswith("CALL"):
                    # Other CALL commands, skip
                    chunk_idx += 1
                else:
                    chunk_idx += 1

            return None, [], start_idx  # No EP found
        except Exception:
            return None, [], start_idx

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
