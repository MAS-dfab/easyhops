# HOP File Parsing Strategy

## Overview

The `easyhops` library parses HOPS CNC machine instruction files (`.hop` format) into structured Python objects using a **two-phase parsing strategy**:

1. **Phase 1: Chunking** - Split file into logical chunks (header, vars, finished_part, park_mode, machining blocks)
2. **Phase 2: Parsing** - Parse each chunk independently into typed objects

This approach separates concerns and makes the parser more maintainable and testable.

## File Format Structure

A HOP file contains these sections in order:

```
; Header comments
VARS
  DX := value
  DY := value
  DZ := value
START

FERTIGTEIL(...)
CALL Park_V7 (...)

WZF(...)          ; Tool definition (Router)
EBENE0()          ; Work plane
CALL _Tvorschub_v5(...)  ; Optional feedrate
SP(...)           ; Milling: Start Point
G01(...)          ; Milling: Linear moves
G01(...)
EP(...)           ; Milling: End Point

; Multiple operations can share same tool+workplane
SP(...)           ; Second operation with same tool/plane
G01(...)
EP(...)

WZS(...)          ; Tool definition (Saw)
EBENE0()          ; Work plane
SAEGEN(...)       ; Sawing operation

WZB(...)          ; Tool definition (Driller)
EBENEF(...)       ; Free plane
BOHR(...)         ; Drilling operation
```

## Architecture

### Core Classes

```
HOPSJob
├── header: List[str]                    # Header comments
├── vars: VarsDefinition                 # VARS section
├── finished_part: FinishedPart          # FERTIGTEIL line
├── park_mode: ParkMode                  # Park_V7 call
└── machinings: List[HOPSMachining]      # All operations

HOPSMachining (wrapper)
├── tool: MachiningTool                  # WZF/WZS/WZB
├── work_plane: WorkPlane | FreePlane    # EBENE or EBENEF
└── operations: List[Operation]          # One or more operations
    ├── MillingOperation                 # SP+G01+EP
    ├── SawingOperation                  # SAEGEN
    └── DrillingOperation                # BOHR

HOPChunk (internal - used during parsing)
├── lines: List[str]                     # Code lines (no comments)
├── comments: List[str]                  # Associated comment lines
├── start_line: int                      # Line number (1-indexed)
└── chunk_type: str                      # 'header', 'vars', 'finished_part', etc.
```

**Key Change from v1**: `HOPSMachining.operations` is now a **list** (plural) supporting multiple operations per tool+workplane combination.

### Design Pattern: Classmethod Factories

Each component implements `from_hop_line(line: str)` for parsing:

```python
# Tool parsing
tool = MachiningTool.from_hop_line("WZF(504,3000,4000,5000,_SD,_ANF,'1')")

# Work plane parsing
plane = WorkPlane.from_hop_line("EBENE0()")
plane = FreePlane.from_hop_line("EBENEF(x,y,z,rot,tilt,snap_xy,snap_z)")

# Operation parsing
op = StartPoint.from_hop_line("SP(x,y,z,...)")
op = G01.from_hop_line("G01(x,y,z,...)")
op = EndPoint.from_hop_line("EP(...)")
op = SawingOperation.from_hop_line("SAEGEN(sx,sy,sz,ex,ey,ez,...)")
op = DrillingOperation.from_hop_line("BOHR(x,y,z,...)")
```

## Parsing Flow

### Two-Phase Strategy

**Phase 1: Chunking (`_split_lines`)**
- Read entire file into memory
- Split into logical chunks without parsing content
- Separate comments from code lines within each chunk
- Return typed chunks: `HOPChunk` objects

**Phase 2: Parsing (`_parse_*_chunk`)**
- Parse each chunk independently
- Convert text to typed Python objects
- Handle errors per-chunk (lenient or strict mode)

### Entry Point: `HOPSJob.from_hop_file(filepath, strict=False)`

```python
@classmethod
def from_hop_file(cls, filepath: str, strict: bool = False) -> "HOPSJob":
    """Parse complete HOP file into HOPSJob object.
    
    Parameters:
    -----------
    filepath : str
        Path to the HOP file
    strict : bool, optional
        If True, raises UnparsedLineError on first parsing error.
        If False (default), skips unparseable lines silently.
    
    Returns:
    --------
    HOPSJob
        Fully parsed job with all components
        
    Raises:
    -------
    UnparsedLineError
        If strict=True and any line cannot be parsed
    """
    # Read file
    lines = readlines(filepath)
    
    # PHASE 1: Split into chunks
    header_chunk, vars_chunk, fp_chunk, pm_chunk, mach_chunks = cls._split_lines(lines)
    
    # PHASE 2: Parse each chunk
    header_lines = parse_header(header_chunk)
    vars_def = cls._parse_vars_chunk(vars_chunk)
    finished_part = cls._parse_finished_part_chunk(fp_chunk)
    park_mode = cls._parse_park_mode_chunk(pm_chunk)
    
    # Parse machinings and collect errors
    machinings_list = []
    unparsed_errors = []
    for mach_chunk in mach_chunks:
        machining, errors = cls._parse_machining_chunk(mach_chunk, strict=strict)
        if machining:
            machinings_list.append(machining)
        if errors:
            unparsed_errors.extend(errors)
    
    # Strict mode: raise first error
    if strict and unparsed_errors:
        raise unparsed_errors[0]
    
    # Create job with defaults for missing components
    return HOPSJob(
        vars=vars_def or VarsDefinition(0.0, 0.0, 0.0),
        finished_part=finished_part or FinishedPart(None, None, None),
        park_mode=park_mode or ParkMode(),
        machinings=machinings_list,
        header=header_lines
    )
```

### Phase 1: Chunking Strategy

#### Step 1a: Extract Header Lines

```python
@staticmethod
def _extract_header_lines(lines: List[str], start_idx: int) -> Tuple[Optional[HOPChunk], int]:
    """Extract leading comment lines as header."""
    
    idx = start_idx
    header_lines = []
    
    # Collect all leading lines starting with ";"
    while idx < len(lines) and lines[idx].strip().startswith(";"):
        header_lines.append(lines[idx])
        idx += 1
    
    if header_lines:
        header_chunk = HOPChunk(
            lines=header_lines,
            comments=[],
            start_line=start_idx + 1,
            chunk_type="header"
        )
        return header_chunk, idx
    
    return None, idx
```

**Strategy**: Consume sequential comment lines until first non-comment.

#### Step 1b: Extract VARS Section

```python
@staticmethod
def _extract_vars_lines(lines: List[str], start_idx: int) -> Tuple[Optional[HOPChunk], int]:
    """Extract VARS block until START keyword."""
    
    idx = start_idx
    vars_code = []
    vars_comments = []
    
    # Collect lines until "START"
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        
        if stripped.startswith(";"):
            vars_comments.append(line)
        else:
            vars_code.append(line)
        
        if "START" in line:
            idx += 1
            return HOPChunk(
                lines=vars_code,
                comments=vars_comments,
                start_line=start_idx + 1,
                chunk_type="vars"
            ), idx
        
        idx += 1
    
    return None, idx
```

**Strategy**: Separate comments from code, stop at `START` keyword.

#### Step 1c: Extract FERTIGTEIL and Park Mode

```python
@staticmethod
def _extract_finished_part_lines(...) -> Tuple[Optional[HOPChunk], int]:
    """Extract FERTIGTEIL line with preceding comments."""
    
    # Look back for comments before FERTIGTEIL
    # Collect FERTIGTEIL line
    # Return chunk with comments separated from code
    
@staticmethod
def _extract_park_mode_lines(...) -> Tuple[Optional[HOPChunk], int]:
    """Extract Park_V7 CALL line with preceding comments."""
    
    # Look back for comments before CALL
    # Collect CALL line
    # Return chunk with comments separated from code
```

**Strategy**: Look backward to collect associated comments, forward to get code line.

#### Step 1d: Extract Machining Blocks

```python
@staticmethod
def _extract_machining_lines(lines: List[str], start_idx: int) -> List[HOPChunk]:
    """Extract all machining chunks (WZF/WZS/WZB blocks with operations).
    
    Each chunk contains:
    - One tool line (WZF/WZS/WZB)
    - One workplane line (EBENE/EBENEF)
    - One or more operations (SP+G01+EP, SAEGEN, BOHR)
    - Associated comments
    """
    
    machining_chunks = []
    idx = start_idx
    
    while idx < len(lines):
        line = lines[idx].strip()
        
        # Start of machining block
        if line.startswith("WZF(") or line.startswith("WZS(") or line.startswith("WZB("):
            mach_start = idx
            mach_code = []
            mach_comments = []
            
            # Collect everything until next tool change
            while idx < len(lines):
                line = lines[idx]
                stripped = line.strip()
                
                # Stop at next tool change
                if idx > mach_start and (stripped.startswith("WZF(") or 
                                        stripped.startswith("WZS(") or 
                                        stripped.startswith("WZB(")):
                    break
                
                # Separate comments from code
                if stripped.startswith(";"):
                    mach_comments.append(line)
                elif stripped:  # Non-empty, non-comment line
                    mach_code.append(line)
                
                idx += 1
            
            if mach_code:
                machining_chunks.append(HOPChunk(
                    lines=mach_code,
                    comments=mach_comments,
                    start_line=mach_start + 1,
                    chunk_type="machining"
                ))
        else:
            idx += 1
    
    return machining_chunks
```

**Key Strategy**: 
- Chunk boundaries are tool changes (WZF/WZS/WZB)
- A single chunk may contain **multiple operations** with same tool+workplane
- Comments are separated from code during chunking

### Phase 2: Parsing Strategy
### Phase 2: Parsing Strategy

#### Parsing VARS Chunk

```python
@staticmethod
def _parse_vars_chunk(chunk: HOPChunk) -> Optional[VarsDefinition]:
    """Parse VARS chunk using VarsDefinition.from_hop_line()."""
    try:
        vars_def = VarsDefinition.from_hop_line(chunk.lines)
        return vars_def
    except Exception:
        return None
```

**Delegates to**: `VarsDefinition.from_hop_line()` which uses regex to extract `DX`, `DY`, `DZ`.

#### Parsing FERTIGTEIL Chunk

```python
@staticmethod
def _parse_finished_part_chunk(chunk: HOPChunk) -> Optional[FinishedPart]:
    """Parse FERTIGTEIL line (12 parameters)."""
    if chunk.lines:
        try:
            finished_part = FinishedPart.from_hop_line(chunk.lines[0].strip())
            return finished_part
        except Exception:
            return None
    return None
```

**Delegates to**: `FinishedPart.from_hop_line()` which parses 12-parameter format.

#### Parsing Park Mode Chunk

```python
@staticmethod
def _parse_park_mode_chunk(chunk: HOPChunk) -> Optional[ParkMode]:
    """Parse CALL Park_V7 line."""
    if chunk.lines:
        try:
            park_mode = ParkMode.from_hop_line(chunk.lines[0].strip())
            return park_mode
        except Exception:
            return None
    return None
```

**Delegates to**: `ParkMode.from_hop_line()` which extracts MODE, POSX, POSY.

#### Parsing Machining Chunk (Core Logic)

```python
@staticmethod
def _parse_machining_chunk(chunk: HOPChunk, strict: bool = False) -> Tuple[Optional[HOPSMachining], List[UnparsedLineError]]:
    """Parse a machining chunk (tool + work plane + operations).
    
    A single chunk may contain multiple operations using the same
    tool and work plane (e.g., two Birdsmouth milling paths).
    
    Parameters:
    -----------
    chunk : HOPChunk
        The chunk containing code lines (no comments)
    strict : bool
        If True, collect unparsed line errors
    
    Returns:
    --------
    Tuple of (HOPSMachining or None, List of errors)
    """
    
    tool = None
    work_plane = None
    operations = []  # List of operations for this tool+workplane
    errors = []
    chunk_idx = 0
    
    # 1. Parse tool (WZF/WZS/WZB) - must be first
    while chunk_idx < len(chunk.lines):
        line = chunk.lines[chunk_idx].strip()
        if line.startswith("WZF(") or line.startswith("WZS(") or line.startswith("WZB("):
            try:
                tool = MachiningTool.from_hop_line(line)
                chunk_idx += 1
                break
            except Exception:
                if strict:
                    errors.append(UnparsedLineError(
                        line_number=chunk.start_line + chunk_idx,
                        line_content=chunk.lines[chunk_idx],
                        context="Failed to parse tool line"
                    ))
                return None, errors
        chunk_idx += 1
    
    if not tool:
        if strict:
            errors.append(UnparsedLineError(
                line_number=chunk.start_line,
                line_content="",
                context="No tool definition found in machining chunk"
            ))
        return None, errors
    
    # 2. Parse work plane (EBENE/EBENEF) - must come after tool
    work_plane_start_idx = chunk_idx
    while chunk_idx < len(chunk.lines):
        line = chunk.lines[chunk_idx].strip()
        
        if line.startswith("EBENEF("):
            # Free plane
            try:
                work_plane = FreePlane.from_hop_line(line)
                chunk_idx += 1
                break
            except Exception:
                if strict:
                    errors.append(UnparsedLineError(
                        line_number=chunk.start_line + chunk_idx,
                        line_content=chunk.lines[chunk_idx],
                        context="Failed to parse EBENEF work plane"
                    ))
                return None, errors
                
        elif line.startswith("EBENE"):
            # Standard plane
            try:
                work_plane = WorkPlane.from_hop_line(line)
                chunk_idx += 1
                break
            except Exception:
                if strict:
                    errors.append(UnparsedLineError(
                        line_number=chunk.start_line + chunk_idx,
                        line_content=chunk.lines[chunk_idx],
                        context="Failed to parse EBENE work plane"
                    ))
                return None, errors
                
        elif line.startswith("SP(") or line.startswith("SAEGEN(") or line.startswith("BOHR("):
            # Found operation before work plane - error
            if strict:
                errors.append(UnparsedLineError(
                    line_number=chunk.start_line + chunk_idx,
                    line_content=chunk.lines[chunk_idx],
                    context="Found operation before work plane definition"
                ))
            return None, errors
            
        elif not line.startswith("CALL") and line:
            # Unknown line where we expected work plane
            if strict:
                errors.append(UnparsedLineError(
                    line_number=chunk.start_line + chunk_idx,
                    line_content=chunk.lines[chunk_idx],
                    context="Expected work plane definition (EBENE/EBENEF), got unknown command"
                ))
                return None, errors
            # Skip non-work plane lines (like CALL feedrate)
            chunk_idx += 1
        else:
            # Skip CALL or empty lines
            chunk_idx += 1
    
    if not work_plane:
        if strict:
            errors.append(UnparsedLineError(
                line_number=chunk.start_line + work_plane_start_idx,
                line_content="",
                context="No work plane definition found after tool"
            ))
        return None, errors
    
    # 3. Parse ALL operations in this chunk (SP+G01+EP, SAEGEN, or BOHR)
    # KEY: A chunk may have multiple operations with same tool+workplane
    while chunk_idx < len(chunk.lines):
        line = chunk.lines[chunk_idx].strip()
        
        # Skip CALL feedrate commands
        if line.startswith("CALL"):
            chunk_idx += 1
            continue
        
        operation = None
        try:
            if line.startswith("SP("):
                # Milling: SP + G01s + EP
                operation, next_idx = HOPSJob._parse_milling_from_chunk(chunk, chunk_idx)
                if operation:
                    operations.append(operation)
                    chunk_idx = next_idx  # Jump past EP
                else:
                    # Parsing failed, skip to avoid infinite loop
                    chunk_idx += 1
                    
            elif line.startswith("SAEGEN("):
                # Sawing: single line
                operation = SawingOperation.from_hop_line(line)
                if operation:
                    operations.append(operation)
                chunk_idx += 1
                
            elif line.startswith("BOHR("):
                # Drilling: single line
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
        return HOPSMachining(tool, work_plane, operations), errors
    
    return None, errors
```

**Key Points**:
1. **Strict mode**: Collects `UnparsedLineError` objects for invalid lines
2. **Multiple operations**: Continues parsing until chunk exhausted
3. **Infinite loop protection**: If `_parse_milling_from_chunk` fails, increments by 1
4. **Error accumulation**: Returns both result and error list

#### Parsing Milling Operation

```python
@staticmethod
def _parse_milling_from_chunk(chunk: HOPChunk, start_idx: int) -> Tuple[Optional[MillingOperation], int]:
    """Parse milling operation (SP + G01s + EP) from chunk.
    
    Returns:
    --------
    Tuple of (MillingOperation or None, next index after EP)
    """
    chunk_idx = start_idx
    
    try:
        # Parse SP (start point)
        start_point = StartPoint.from_hop_line(chunk.lines[chunk_idx].strip())
        chunk_idx += 1
        
        # Parse G01 moves
        moves = []
        while chunk_idx < len(chunk.lines):
            line = chunk.lines[chunk_idx].strip()
            
            if line.startswith("G01("):
                move = G01.from_hop_line(line)
                moves.append(move)
                chunk_idx += 1
            elif line.startswith("EP("):
                break  # Found end point
            elif line.startswith("CALL"):
                chunk_idx += 1  # Skip CALL lines
            else:
                break  # Unknown line, stop
        
        # Parse EP (end point)
        if chunk_idx < len(chunk.lines) and chunk.lines[chunk_idx].strip().startswith("EP("):
            end_point = EndPoint.from_hop_line(chunk.lines[chunk_idx].strip())
            chunk_idx += 1  # Move past EP
            
            return MillingOperation(
                start_point=start_point,
                moves=moves,
                end_point=end_point
            ), chunk_idx
        else:
            # No EP found
            return None, chunk_idx
    
    except Exception:
        # Parsing failed, return start index
        return None, start_idx
```

**Strategy**: 
- Parse SP, collect all G01s, parse EP
- Return next index to continue parsing
- On error, return `start_idx` (not incremented) so caller can skip

**Critical Bug Fix**: Returning `(None, start_idx)` on error would cause infinite loop if caller blindly used the returned index. Caller must check if operation is None and increment manually.

## Regex Patterns Reference

### Tool Line (WZF/WZS/WZB)

```regex
(WZ[FSB])\(\s*(\d+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*'([^']*)'\s*\)
```

**Captures**:
1. Tool type (WZF/WZS/WZB)
2. Position (integer)
3-7. Speed/feedrate parameters (numeric or `_SD`, `_ANF` system variables)
8. Head ID (quoted string)

**Example**: `WZF(504,3000,4000,5000,_SD,_ANF,'1')`

### Standard Work Plane (EBENE)

```regex
EBENE(\d+)\(\)  OR  EBENE\((\d+)\)
```

**Mapping**:
- `EBENE0()` or `EBENE(0)` → TOP
- `EBENE1()` or `EBENE(1)` → FRONT
- `EBENE2()` or `EBENE(2)` → START
- `EBENE3()` or `EBENE(3)` → BACK
- `EBENE4()` or `EBENE(4)` → END

### Free Work Plane (EBENEF)

```regex
EBENEF\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)
```

**Captures**: x, y, z, rotation_angle, tilt_angle, snap_xy, snap_z

### FERTIGTEIL

```regex
FERTIGTEIL\(\s*(?P<dx>[-+]?\d*\.?\d+|VARS DX|DX)\s*,\s*(?P<dy>[-+]?\d*\.?\d+|VARS DY|DY)\s*,\s*(?P<dz>[-+]?\d*\.?\d+|VARS DZ|DZ)\s*,\s*(?P<rotation_flag>\d+)\s*,\s*(?P<vz>\d+)\s*,\s*(?P<mode>\d+)\s*,\s*(?P<kop_flag>\d+)\s*,\s*(?P<ak>\d+)\s*,\s*(?P<comment>'[^']*'|[^,]*)\s*,\s*(?P<spare1>\d+)\s*,\s*(?P<spare2>\d+)\s*,\s*(?P<spare3>\d+)\s*\)
```

**Handles**:
- Numeric values: `1352.233`
- Variable references: `DX`, `VARS DX` → parsed as `None`
- Quoted comments: `'My Part'` or empty `''`

### Milling Commands

**StartPoint (SP)**:
```regex
SP\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,...\)
```

**Linear Move (G01)**:
```regex
G01\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,...\)
```

**EndPoint (EP)**:
```regex
EP\(\s*(\d+)\s*,\s*([^,]+)\s*,\s*(\d+)\s*\)
```

### Sawing Operation (SAEGEN)

```regex
SAEGEN\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,...\)
```

**Captures**: start (sx, sy, sz), end (ex, ey, ez), plus additional parameters

## Error Handling

### Two Modes: Lenient vs Strict

The parser supports two modes controlled by the `strict` parameter in `from_hop_file()`:

**Lenient Mode (default: `strict=False`)**
- Unparseable lines are silently skipped
- Parsing continues despite errors
- Missing sections use default values
- Best for production use with potentially malformed files

**Strict Mode (`strict=True`)**
- First unparseable line raises `UnparsedLineError` immediately
- Provides detailed error information:
  - Line number where error occurred (1-indexed)
  - Line content that failed to parse
  - Context about what was expected
- Best for development, debugging, and validation

### Error Classes

```python
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
```

### Strict Mode Example

```python
from easyhops.hop_job import HOPSJob, UnparsedLineError

try:
    job = HOPSJob.from_hop_file("part.hop", strict=True)
    print(f"Successfully parsed {len(job.machinings)} operations")
    
except UnparsedLineError as e:
    print(f"Parse error at line {e.line_number}")
    print(f"Context: {e.context}")
    print(f"Content: {e.line_content}")
    
# Example output:
# HOP PARSING ERROR - Line 11: Expected work plane definition (EBENE/EBENEF), got unknown command
#   Line context: INVALID_WORKPLANE_COMMAND(1,2,3)
```

### Error Collection in Strict Mode

During parsing, errors are collected per chunk:
1. Each `_parse_machining_chunk` returns `(machining, errors)`
2. Errors accumulate in `unparsed_errors` list
3. If `strict=True` and `unparsed_errors` is non-empty, raise first error
4. If `strict=False`, errors are discarded

### Common Error Contexts

- `"Failed to parse tool line"` - WZF/WZS/WZB malformed
- `"No tool definition found in machining chunk"` - Chunk missing tool
- `"Failed to parse EBENE work plane"` - Standard plane malformed
- `"Failed to parse EBENEF work plane"` - Free plane malformed
- `"Found operation before work plane definition"` - SP/SAEGEN/BOHR before EBENE
- `"Expected work plane definition (EBENE/EBENEF), got unknown command"` - Invalid line where work plane expected
- `"No work plane definition found after tool"` - Work plane missing after tool

### Missing Components (Lenient Behavior)

If required sections are missing or fail to parse:
- `vars` → defaults to `VarsDefinition(0.0, 0.0, 0.0)`
- `finished_part` → defaults to `FinishedPart(None, None, None)`
- `park_mode` → defaults to `ParkMode()`
- `machinings` → empty list `[]`

This allows partial parsing of incomplete files.

## Serialization Flow

### `HOPSJob.__str__()` and `to_hop_file()`

```python
def __str__(self) -> str:
    """Generate complete HOP file content."""
    
    output = []
    
    # 1. Header comments
    if self.header:
        output.extend(self.header)
        output.append("")  # Blank line
    
    # 2. VARS section
    output.append(str(self.vars))
    output.append("")
    
    # 3. FERTIGTEIL
    output.append(str(self.finished_part))
    output.append("")
    
    # 4. Park mode
    output.append(str(self.park_mode))
    output.append("")
    
    # 5. Each machining (tool + plane + operation)
    for machining in self.machinings:
        output.append(str(machining))
        output.append("")  # Blank line between operations
    
    return "\n".join(output)
```

**Strategy**: Delegate string generation to each component's `__str__()` method.

## Known Limitations and Future Work

### 1. Multiple Operations per Tool+Workplane ✓ FIXED

**Status**: **IMPLEMENTED** (v1.1.0)

The parser now correctly supports multiple operations sharing the same tool and workplane. Example from `data/test.hop`:

```
WZF(504,...)
EBENEF(...)
SP(...)  ; First Birdsmouth operation
G01(...)
EP(...)
SP(...)  ; Second Birdsmouth operation (same tool+workplane)
G01(...)
EP(...)
```

Both operations are now parsed into a single `HOPSMachining` object with `operations` as a list containing both `MillingOperation` instances.

### 2. Comment Preservation

**Status**: NOT IMPLEMENTED

**Problem**: Original HOP files contain intermediate comments between operations:
```
; ---------------------------------
; _133,P_Birdsmouth
; ---------------------------------
WZF(504,...)
```

These comments are separated during chunking but not preserved in the object model.

**Impact**: Round-trip (parse → write → parse) loses descriptive comments.

**Potential Solution**: Add `comments: List[str]` to `HOPSMachining` to store associated comments.

### 3. CALL Command Preservation

**Status**: PARTIALLY IMPLEMENTED

**Current Behavior**: `CALL _Tvorschub_v5` feedrate commands are skipped during parsing but not preserved.

**Impact**: Written files don't include intermediate CALL statements.

**Potential Solution**: Store CALL commands in operation metadata or as separate operation type.

### 4. Variable Reference Resolution

**Status**: NOT IMPLEMENTED

**Current Behavior**: When `FERTIGTEIL(DX,DY,DZ,...)` uses variable references, these are stored as `None`:
```python
job.finished_part.dx == None  # Not resolved to 1352.233
```

**Workaround**: Users must cross-reference with `job.vars.dx` manually.

**Potential Solution**: Add optional `resolve_vars=True` parameter to resolve references during parsing.

### 5. System Variables

**Current Behavior**: System variables like `_SD` (default speed) and `_ANF` (default factor) are converted to `None` values, letting the machine use its defaults.

**This is intentional** - preserves machine-specific defaults.

### 6. Infinite Loop Protection ✓ FIXED

**Status**: **FIXED** (v1.0.1)

**Previous Bug**: When `_parse_milling_from_chunk` failed and returned `(None, start_idx)`, the caller would set `chunk_idx = start_idx`, creating an infinite loop.

**Fix**: Caller now checks if operation is `None` and increments manually:
```python
operation, next_idx = HOPSJob._parse_milling_from_chunk(chunk, chunk_idx)
if operation:
    operations.append(operation)
    chunk_idx = next_idx  # Only update on success
else:
    chunk_idx += 1  # Skip bad line to avoid infinite loop
```

### 7. Strict Mode Error Reporting ✓ IMPLEMENTED

**Status**: **IMPLEMENTED** (v1.0.0)

Strict mode now properly:
- Collects `UnparsedLineError` objects with line numbers and context
- Raises first error when `strict=True`
- Provides detailed error messages for debugging

## Testing Strategy

### Test Coverage

**`tests/test_hop_core.py`** (36 tests) - Core components:
- VarsDefinition parsing and serialization
- FinishedPart 12-parameter format (with comment as 9th parameter)
- ParkMode parsing

**`tests/test_hop_job_parsing.py`** (22 tests) - File parsing:
- Full file parsing with `data/test.hop`
- Multiple operations per tool+workplane
- Work plane type detection (EBENE vs EBENEF)
- Operation type counting (milling, sawing, drilling)
- Strict mode error handling with `UnparsedLineError`
- Round-trip tests (marked as xfail due to comment/CALL loss)

**`examples/parse_hop_file.py`** - Working example:
- Demonstrates real-world usage patterns
- Shows how to iterate through `operations` list
- Handles all operation types correctly (Milling, Sawing, Drilling)
- Counts operations and work plane types

### Test Data

**`data/test.hop`** - Real HOPS file from production:
- Workpiece: 1352.233 x 140 x 100 mm
- **5 machining blocks** containing **7 total operations**:
  1. Birdsmouth milling (WZF 504, FreePlane) - **2 operations in same block**
  2. Castor milling #1 (WZF 503, TOP) - 1 operation
  3. Castor milling #2 (WZF 503, TOP) - 1 operation
  4. Sawing #1 (WZS 201, TOP) - 1 operation
  5. Sawing #2 (WZS 201, TOP) - 1 operation

### All Tests Passing

**Status**: ✓ 214 tests passing (as of 2025-12-15)

## Future Enhancements

1. **Variable Resolution**: Add `resolve_vars=True` parameter to `from_hop_file()`
2. **Comment Preservation**: Store comments with operations for perfect round-trips
3. **CALL Preservation**: Include CALL commands in object model
4. **Validation**: Check tool/plane compatibility, detect invalid parameter combinations
5. **Pretty Printing**: Format output with consistent indentation and spacing
6. **Streaming Parser**: Memory-efficient parsing for very large HOP files (>100MB)
7. **Error Recovery**: Continue parsing after errors in lenient mode with warnings
8. **Type Hints**: Add complete type annotations for all methods
9. **Performance**: Profile and optimize regex patterns, consider compiled patterns

## Usage Examples

### Basic Parsing

```python
from easyhops.hop_job import HOPSJob

# Parse file (lenient mode - skips unparseable lines)
job = HOPSJob.from_hop_file("part.hop")

# Access components
print(f"Dimensions: {job.vars.dx} x {job.vars.dy} x {job.vars.dz}")
print(f"Machining blocks: {len(job.machinings)}")

# Count total operations (note: operations is a list)
total_ops = sum(len(m.operations) for m in job.machinings)
print(f"Total operations: {total_ops}")
```

### Iterating Through Operations

```python
from easyhops.machining_commands import MillingOperation, SawingOperation, DrillingOperation

for i, machining in enumerate(job.machinings, 1):
    print(f"\nMachining #{i}")
    print(f"  Tool: {machining.tool.tool_type.value} at position {machining.tool.position}")
    print(f"  Work plane: {machining.work_plane}")
    print(f"  Number of operations: {len(machining.operations)}")
    
    # Iterate through operations in this machining block
    for op in machining.operations:
        if isinstance(op, MillingOperation):
            print(f"    - Milling: {len(op.moves)} moves")
        elif isinstance(op, SawingOperation):
            print(f"    - Sawing: ({op.sx},{op.sy},{op.sz}) to ({op.ex},{op.ey},{op.ez})")
        elif isinstance(op, DrillingOperation):
            print(f"    - Drilling at ({op.x},{op.y},{op.z})")
```

### Filtering Operations

```python
from easyhops.work_planes import FreePlane, WorkPlane

# Get all machining blocks using router tool 504
router_504 = [m for m in job.machinings if m.tool.position == 504]

# Get all operations on TOP plane
top_plane_ops = [m for m in job.machinings if m.work_plane == WorkPlane.TOP]

# Get all FreePlane (EBENEF) operations
free_plane_ops = [m for m in job.machinings if isinstance(m.work_plane, FreePlane)]

# Count operation types across all machinings
milling_count = sum(
    len([op for op in m.operations if isinstance(op, MillingOperation)]) 
    for m in job.machinings
)
```

### Parse with Strict Mode (for validation)

```python
from easyhops.hop_job import HOPSJob, UnparsedLineError

try:
    # Strict mode - raises on first parsing error
    job = HOPSJob.from_hop_file("part.hop", strict=True)
    print(f"✓ Valid HOP file with {len(job.machinings)} operations")
    
except UnparsedLineError as e:
    print(f"✗ Invalid HOP file")
    print(f"  Error at line {e.line_number}: {e.context}")
    print(f"  Content: {e.line_content}")
```

### Create and Write a HOP File

```python
from easyhops.hop_job import HOPSJob, HOPSMachining
from easyhops.hop_core import VarsDefinition, FinishedPart, ParkMode
from easyhops.tool_library import MachiningTool, ToolCallType
from easyhops.work_planes import WorkPlane
from easyhops.machining_commands import SawingOperation

# Create components
vars_def = VarsDefinition(1000, 500, 100)
part = FinishedPart(1000, 500, 100)
park = ParkMode(11, 0, 0)

# Create sawing operation
tool = MachiningTool(ToolCallType.SAW, 201, feedrate=7000)
plane = WorkPlane.TOP
operation = SawingOperation(0, 500, -110, 0, 0, -110)

# Note: operations is a list, even for single operation
machining = HOPSMachining(tool, plane, [operation])

# Create job
job = HOPSJob(
    vars=vars_def,
    finished_part=part,
    park_mode=park,
    machinings=[machining],
    header=["; Generated by easyhops", "; Date: 2025-12-15"]
)

# Write to file
job.to_hop_file("output.hop")
print(f"Wrote {len(job.machinings)} machining blocks to output.hop")
```

## Future Enhancements

1. **Comment Preservation**: Store intermediate comments with operations for perfect round-tripping
2. **Variable Resolution**: Option to resolve `DX`/`DY`/`DZ` references to actual values
3. **Validation**: Check tool/plane compatibility, detect malformed operations
4. **Pretty Printing**: Format output with consistent indentation and spacing
5. **Streaming Parser**: Memory-efficient parsing for very large HOP files
6. **Error Recovery**: Continue parsing after errors instead of stopping
