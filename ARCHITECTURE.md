# EasyHops Architecture Overview

## Project Purpose

EasyHops is a Python library for parsing, manipulating, and generating HOPS machining files (.hop) used in CNC woodworking operations. It provides object-oriented abstractions for HOPS commands and enables programmatic creation and modification of machining programs.

---

## Module Structure

### Core Modules

```
easyhops/
├── hop_core.py              # Fundamental HOP file components
├── hop_job.py               # Complete file parser and container
├── machining_commands.py    # Operation types (milling, sawing, drilling)
├── tool_library.py          # Tool definitions and types
├── work_planes.py           # Work plane definitions
├── btlx_processes.py        # BTLx file processing
├── parse_btlx.py            # BTLx XML parsing
├── writehops.py             # Legacy HOP file generation
└── merge_stock_hops.py      # Stock merging utilities
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         HOPSJob                             │
│  (Complete HOP file representation)                         │
├─────────────────────────────────────────────────────────────┤
│ • vars: VarsDefinition                                      │
│ • finished_part: FinishedPart                               │
│ • park_mode: ParkMode                                       │
│ • machinings: List[HOPSMachining]                           │
│ • header: List[str]                                         │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  │ contains multiple
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    HOPSMachining                            │
│  (Single machining operation with context)                  │
├─────────────────────────────────────────────────────────────┤
│ • tool: MachiningTool                                       │
│ • work_plane: WorkPlane | FreePlane                         │
│ • operations: List[MillingOperation | SawingOperation |     │
│              DrillingOperation]                             │
│ • feedrate_overrides: List[Tuple[...]]                      │
└──────┬──────────────┬─────────────────┬─────────────────────┘
       │              │                 │
       ▼              ▼                 ▼
┌──────────┐   ┌─────────────┐   ┌──────────────────┐
│  Tool    │   │ Work Plane  │   │   Operation      │
│          │   │             │   │                  │
│ WZF/WZS/ │   │ EBENE0-4    │   │ SP + G01 + EP    │
│ WZB      │   │ EBENEF      │   │ SAEGEN           │
│          │   │             │   │ BOHRUNG          │
└──────────┘   └─────────────┘   └──────────────────┘
```

---

## Core Components

### 1. hop_core.py - Fundamental Building Blocks

Contains the basic HOP file components that are independent of parsing logic.

#### **VarsDefinition**
Represents piece dimensions and variable declarations.

```python
VARS
   DX := 1000.0;
   DY := 500.0;
   DZ := 100.0;
START
```

**Class**: `VarsDefinition(dx, dy, dz)`

#### **FinishedPart**
Represents the FERTIGTEIL command with 12 parameters.

**Format**: `FERTIGTEIL(dx,dy,dz,rotation_flag,empty,offset_x,offset_y,offset_z,comment,field_linking,laser,stop)`

**Parameters**:
- `dx, dy, dz` - Piece dimensions (can be values or VARS references)
- `rotation_flag` - Rotation mode (0=none, 2=rotate)
- `empty_parameter` - Reserved parameter (always 0)
- `offset_x, offset_y, offset_z` - Position offsets
- `comment` - Quoted comment string (9th parameter)
- `field_linking` - Field linking flag (0/1)
- `activates_laser` - Laser activation flag (0/1)
- `stop_flag` - Stop mode flag

**Example**: `FERTIGTEIL(VARS DX,VARS DY,VARS DZ,0,0,0,0,0,'MyPart',0,0,0)`

#### **ParkMode**
Park position command settings.

**Format**: `CALL Park_V7 ( VAL MODE:=11,POSX:=0,POSY:=0)`

#### **EasySnapZ**
Enum for Z-axis reference modes:
- `TOP_EDGE = 0` - Reference from top
- `BOTTOM_EDGE = 1` - Reference from bottom
- `RELATIVE = 2` - Relative/incremental

---

### 2. tool_library.py - Tool Definitions

#### **ToolCallType (Enum)**
```python
ROUTER = "WZF"  # Milling/routing tool
SAW = "WZS"     # Sawing tool
DRILL = "WZB"   # Drilling tool
```

#### **MachiningTool**
Represents tool call commands (WZF/WZS/WZB).

**Format**: `WZF(position,depth,diameter,processing_mode,direction,reference,comment)`

**Attributes**:
- `tool_type` - ToolCallType (ROUTER/SAW/DRILL)
- `position` - Tool position number
- `depth` - Processing depth
- `diameter` - Tool diameter
- `processing_mode` - Processing parameters
- `direction` - Feed direction
- `reference` - Reference point
- `comment` - Tool comment

**Example**: `WZF(504,3000,4000,5000,_SD,_ANF,'Birdsmouth tool')`

---

### 3. work_planes.py - Work Plane Definitions

#### **WorkPlane (Enum)**
Standard work planes mapped to face numbers:

```python
EBENE0 = 0  # TOP
EBENE1 = 1  # BOTTOM
EBENE2 = 2  # LEFT
EBENE3 = 3  # RIGHT
EBENE4 = 4  # FRONT
EBENE5 = 5  # BACK
```

**Aliases**: `TOP`, `BOTTOM`, `LEFT`, `RIGHT`, `FRONT`, `BACK`

#### **FreePlane**
Parametric free-view work plane with rotation.

**Format**: `EBENEF(x,y,z,rotation_angle,tilt_angle,slope_angle,aux_angle)`

**Attributes**:
- `x, y, z` - Plane origin coordinates
- `rotation_angle` - Primary rotation angle
- `tilt_angle` - Tilt angle (usually 0)
- `slope_angle` - Slope angle (usually 0)
- `aux_angle` - Auxiliary angle (usually 0)

**Example**: `EBENEF(1351.763,268.987,182.642,13.003,0,0,0)`

---

### 4. machining_commands.py - Operation Types

#### **Milling Operations**

**StartPoint (SP)**
```
SP(x,y,z,depth,ref_mode,direction,corr_side,approach,radius,...)
```

**G01 (Linear Move)**
```
G01(x,y,z,radius,feed_speed,...)
```

**EndPoint (EP)**
```
EP(z,ref_mode,direction,exit_mode,radius,...)
```

**MillingOperation**
Combines SP + list of G01 moves + EP into a complete milling path.

```python
MillingOperation(
    start_point: StartPoint,
    moves: List[G01],
    end_point: EndPoint
)
```

#### **Sawing Operations**

**SawingOperation**
Single sawing cut command.

**Format**: `SAEGEN(sx,sy,sz,ex,ey,ez,orientation,prep,kal,overcut,plunge,depth,ref,comment)`

**Attributes**:
- `sx, sy, sz` - Start coordinates
- `ex, ey, ez` - End coordinates
- `orientation` - Cut orientation
- `preparation` - Preparation mode
- `kalibrierung` - Calibration setting
- Other sawing-specific parameters

#### **Drilling Operations**

**DrillingOperation**
Drilling command.

**Format**: `BOHRUNG(x,y,depth,diameter,tolerance,direction,ref,comment)`

---

### 5. hop_job.py - Complete File Parser

The main orchestrator that parses entire HOP files using a **two-phase approach**.

#### **HOPSMachining**
Associates operations with their tool, work plane, and feedrate overrides.

```python
class HOPSMachining:
    tool: MachiningTool
    work_plane: Union[WorkPlane, FreePlane]
    operations: List[Union[MillingOperation, SawingOperation, DrillingOperation]]
    comments: List[str]
    feedrate_overrides: List[Tuple[Tuple[int, Optional[int]], FeedrateOverride]]
```

**Feedrate Override Tracking**:
- Stored as `((operation_idx, command_idx), FeedrateOverride)` tuples
- `command_idx=None` for sawing/drilling (override before the operation)
- `command_idx=0,1,2,...` for milling (before SP, moves, or EP respectively)

**Example**:
```python
# Tool: WZF(504,...)
# Plane: EBENEF(1351.763,268.987,182.642,13.003,0,0,0)
# Operations: [MillingOperation(SP+G01s+EP), MillingOperation(...)]
# Feedrate overrides: [((0, 0), FeedrateOverride(3000)), ((0, 3), FeedrateOverride(4000))]
machining = HOPSMachining(tool, work_plane, operations, feedrate_overrides=overrides)
```

#### **HOPSJob**
Container for complete HOP file.

```python
class HOPSJob:
    vars: VarsDefinition
    finished_part: FinishedPart
    park_mode: ParkMode
    machinings: List[HOPSMachining]
    header: Optional[List[str]]
```

**Usage**:
```python
# Parse from file
job = HOPSJob.from_hop_file("part.hop")

# Access components
print(f"Dimensions: {job.vars.dx} x {job.vars.dy} x {job.vars.dz}")
print(f"Operations: {len(job.machinings)}")

# Iterate through machinings
for machining in job.machinings:
    print(f"Tool: {machining.tool.tool_type.value}@{machining.tool.position}")
    print(f"Plane: {machining.work_plane}")
    print(f"Operations: {len(machining.operations)}")
    
    # Access feedrate overrides
    for (op_idx, cmd_idx), override in machining.feedrate_overrides:
        if cmd_idx is None:
            print(f"  Feedrate {override.feedrate} before operation {op_idx}")
        else:
            print(f"  Feedrate {override.feedrate} at op {op_idx}, command {cmd_idx}")
```

---

## Two-Phase Parsing Strategy

The parser uses a two-phase approach to separate structural analysis from content parsing.

### **Phase 1: Chunking** (`_split_lines`)

Identifies logical blocks in the file without parsing their content.

**Input**: Raw file lines  
**Output**: List of `HOPChunk` objects

```python
@dataclass
class HOPChunk:
    lines: List[str]           # Code lines (no comments)
    comments: List[str]        # Associated comments
    start_line: int            # Line number in original file
    chunk_type: str            # 'header', 'vars', 'finished_part', etc.
```

**Chunk Types**:
1. **Header** - Leading comment lines (starting with `;`)
2. **VARS** - Variable definitions (`VARS...START` block)
3. **Finished Part** - Single `FERTIGTEIL(...)` line
4. **Park Mode** - Single `CALL Park_V7(...)` line
5. **Machining** - Tool + work plane + operation(s)

**Chunking Rules**:
- Machining chunks break at **new tool calls** (WZF/WZS/WZB)
- Comments are separated from code lines
- Each chunk tracks its position in original file

**Example**:
```
File lines:
; Header comment
VARS DX := 1000; START
FERTIGTEIL(...)
WZF(504,...)
EBENEF(...)
SP(...) EP(...)
WZS(201,...)
EBENE0()
SAEGEN(...)

Chunks created:
[Header chunk: "; Header comment"]
[VARS chunk: "VARS DX := 1000; START"]
[FinishedPart chunk: "FERTIGTEIL(...)"]
[Machining chunk #1: "WZF(504,...)", "EBENEF(...)", "SP(...) EP(...)"]
[Machining chunk #2: "WZS(201,...)", "EBENE0()", "SAEGEN(...)"]
```

### **Phase 2: Parsing** (`_parse_*_chunk`)

Each chunk is independently parsed into typed objects.

```python
# Parse VARS chunk
vars_def = VarsDefinition.from_hop_line(vars_chunk.lines)

# Parse FinishedPart chunk
finished_part = FinishedPart.from_hop_line(fp_chunk.lines[0])

# Parse ParkMode chunk
park_mode = ParkMode.from_hop_line(pm_chunk.lines[0])

# Parse each machining chunk
for chunk in machining_chunks:
    machining = _parse_machining_chunk(chunk)
    # Returns HOPSMachining(tool, work_plane, operation)
```

**Machining Chunk Parsing Flow**:
```
1. Extract tool line (WZF/WZS/WZB)
   → Parse into MachiningTool

2. Extract work plane line (EBENE/EBENEF)
   → Parse into WorkPlane or FreePlane

3. Extract operation lines:
   - If SP(...) → Parse MillingOperation (SP + G01s + EP)
   - If SAEGEN(...) → Parse SawingOperation
   - If BOHR(...) → Parse DrillingOperation

4. Combine into HOPSMachining(tool, work_plane, operation)
```

**Benefits**:
- ✅ Clean separation of concerns
- ✅ Easy to test each phase independently
- ✅ Preserves line numbers for error reporting
- ✅ Comments tracked with their relevant chunks
- ✅ Robust to formatting variations

---

## File Format Specifications

### HOP File Structure

```
; Header comments
; INFO: Project details
; BILD: Image references

VARS
   DX := 1000.0;
   DY := 500.0;
   DZ := 100.0;
START

FERTIGTEIL(VARS DX,VARS DY,VARS DZ,0,0,0,0,0,'Part Name',0,0,0)

CALL Park_V7 ( VAL MODE:=11,POSX:=0,POSY:=0)

; Machining Operation 1
WZF(504,3000,4000,5000,_SD,_ANF,'Tool 1')
EBENEF(1351.763,268.987,182.642,13.003,0,0,0)
SP(0.0,0.0,0.0,10,_ANF,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)
G01(10.0,0.0,0.0,0,4000,0,0,0,0,0,0,0,0,0,0,0,0)
G01(10.0,10.0,0.0,0,4000,0,0,0,0,0,0,0,0,0,0,0,0)
EP(0,_ANF,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)

; Machining Operation 2
WZS(201,1000,500,_SD,_ANF,'Saw 1')
EBENE0()
SAEGEN(100,100,-50,100,200,-50,0,0,0,0,0,0,_ANF,'')

; More operations...
```

---

## Data Flow

### Parsing Flow

```
HOP File (text)
    ↓
[Phase 1: Chunking]
    ↓
HOPChunk objects
    ↓
[Phase 2: Parsing]
    ↓
Typed Python objects
    ↓
HOPSJob instance
```

### Serialization Flow

```
HOPSJob instance
    ↓
job.__str__() or job.to_hop_file()
    ↓
Reconstruct HOP format
    ↓
HOP File (text)
```

---

## Key Design Patterns

### 1. **Dataclass Pattern**
Most classes use `@dataclass` for concise definitions and automatic `__init__`.

### 2. **Factory Pattern**
Each class has a `from_hop_line(line: str)` class method for parsing.

```python
tool = MachiningTool.from_hop_line("WZF(504,3000,4000,5000,_SD,_ANF,'Tool')")
plane = WorkPlane.from_hop_line("EBENE0()")
```

### 3. **String Serialization**
Each class implements `__str__()` to generate valid HOP commands.

```python
str(tool)   # → "WZF(504,3000,4000,5000,_SD,_ANF,'Tool')"
str(plane)  # → "EBENE0()"
```

### 4. **Enum Pattern**
Enums for standardized values with string representations.

```python
ToolCallType.ROUTER  # → "WZF"
WorkPlane.TOP        # → EBENE0
```

### 5. **Two-Phase Parsing**
Separate chunking from parsing for robustness and testability.

---

## Current Limitations

### 1. **Multiple Operations Per Chunk**
If the same tool and work plane are used for multiple operations (e.g., two consecutive milling paths with the same WZF and EBENEF), only the **first operation is parsed**.

**Example**:
```
WZF(504,...)
EBENEF(...)
SP(...) ... EP(...)  ← Parsed ✓
SP(...) ... EP(...)  ← Skipped ✗
```

**Impact**: Files with repeated tool+plane combinations will have incomplete operation lists.

### 2. **Strict Mode Not Implemented**
The `strict=True` parameter exists in `from_hop_file()` but doesn't currently raise errors on unparseable lines. All parsing is currently lenient.

### 3. **Round-Trip Imperfect**
Parsing → Serializing → Re-parsing may lose some operations due to limitation #1.

### 4. **Comment Preservation**
Inline comments and formatting are not fully preserved during round-trip operations.

---

## Testing Architecture

### Test Files

```
tests/
├── test_hop_core.py          # ✅ 36/36 passing
├── test_hop_job_objects.py   # HOPSJob basic tests
├── test_machining_commands.py # Operation parsing tests
├── test_tool_library.py       # Tool parsing tests
├── test_work_planes.py        # Work plane tests
└── test_*.py                  # Other module tests
```

### Test Coverage

- ✅ **FinishedPart**: All 12 parameters tested
- ✅ **VarsDefinition**: Parsing and serialization
- ✅ **Tool parsing**: WZF/WZS/WZB commands
- ✅ **Work planes**: EBENE and EBENEF
- ✅ **Operations**: Milling, sawing, drilling
- ⚠️ **Complete file parsing**: Tests need recreation

---

## Future Enhancements

### Planned Improvements

1. **Multi-operation chunks**: Parse all operations in a single tool+plane chunk
2. **Strict mode**: Implement error handling for malformed lines
3. **Comment preservation**: Retain inline comments and formatting
4. **Validation**: Add semantic validation (e.g., dimension checks)
5. **Optimization**: Detect and merge redundant operations
6. **Export formats**: Support export to other CNC formats

### Extensibility Points

- **New operation types**: Add new `Operation` subclasses
- **Custom tools**: Extend `MachiningTool` for custom tools
- **Preprocessing**: Add hooks in chunking phase
- **Post-processing**: Transform operations after parsing

---

## Usage Examples

### Basic Parsing

```python
from easyhops.hop_job import HOPSJob

# Parse HOP file
job = HOPSJob.from_hop_file("part.hop")

# Access job properties
print(f"Piece: {job.vars.dx} x {job.vars.dy} x {job.vars.dz}")
print(f"Total operations: {len(job.machinings)}")

# Iterate operations
for i, m in enumerate(job.machinings):
    print(f"\nOperation {i+1}:")
    print(f"  Tool: {m.tool.tool_type.value} position {m.tool.position}")
    print(f"  Plane: {m.work_plane}")
    print(f"  Type: {type(m.operation).__name__}")
```

### Creating HOP File Programmatically

```python
from easyhops.hop_core import VarsDefinition, FinishedPart, ParkMode
from easyhops.hop_job import HOPSJob, HOPSMachining
from easyhops.tool_library import MachiningTool, ToolCallType
from easyhops.work_planes import WorkPlane
from easyhops.machining_commands import SawingOperation

# Define piece
vars_def = VarsDefinition(dx=1000.0, dy=500.0, dz=100.0)
finished_part = FinishedPart(dx=1000.0, dy=500.0, dz=100.0, comment="MyPart")
park_mode = ParkMode(mode=11, pos_x=0, pos_y=0)

# Define a sawing operation
tool = MachiningTool(
    tool_type=ToolCallType.SAW,
    position=201,
    depth=1000,
    diameter=500,
    comment="Saw blade"
)
plane = WorkPlane.TOP
operation = SawingOperation(
    sx=0, sy=0, sz=-50,
    ex=100, ey=0, ez=-50,
    comment="Cut edge"
)

# Create machining
machining = HOPSMachining(tool, plane, operation)

# Create job
job = HOPSJob(
    vars=vars_def,
    finished_part=finished_part,
    park_mode=park_mode,
    machinings=[machining]
)

# Write to file
job.to_hop_file("output.hop")
```

### Filtering Operations

```python
from easyhops.hop_job import HOPSJob
from easyhops.machining_commands import MillingOperation, SawingOperation
from easyhops.work_planes import FreePlane

job = HOPSJob.from_hop_file("part.hop")

# Get all milling operations
milling_ops = [m for m in job.machinings 
               if isinstance(m.operation, MillingOperation)]

# Get operations on free planes
freeplane_ops = [m for m in job.machinings 
                 if isinstance(m.work_plane, FreePlane)]

# Get sawing operations
sawing_ops = [m for m in job.machinings 
              if isinstance(m.operation, SawingOperation)]

print(f"Milling: {len(milling_ops)}")
print(f"Free planes: {len(freeplane_ops)}")
print(f"Sawing: {len(sawing_ops)}")
```

---

## Version History

### Current Version
- Two-phase parsing architecture
- 12-parameter FERTIGTEIL format
- Complete operation type support
- 36/36 core tests passing

### Recent Changes
- Fixed FERTIGTEIL comment parameter position (9th parameter)
- Fixed infinite loop in machining chunk parsing
- Updated tests for 12-parameter format
- Improved comment handling and serialization

---

## Contributing

When adding new features:

1. **Follow the factory pattern**: Add `from_hop_line()` class methods
2. **Implement `__str__()`**: Ensure round-trip serialization works
3. **Write tests**: Add tests to appropriate test file
4. **Update this doc**: Document new classes/functionality
5. **Consider two phases**: Does your change affect chunking or parsing?

---

## License

[Include your license information here]
