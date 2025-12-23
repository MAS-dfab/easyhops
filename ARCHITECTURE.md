# EasyHops Architecture Overview

## Project Purpose

EasyHops is a Python library for parsing, manipulating, and generating HOPS machining files (.hop) used in CNC woodworking operations. It provides object-oriented abstractions for HOPS commands and enables programmatic creation and modification of machining programs.

---

## Module Structure

### Core Modules

```
easyhops/
├── base_commands.py         # Abstract base classes for all HOPS commands
├── hop_core.py              # Fundamental HOP file components and enums
├── hop_job.py               # Complete file parser and container
├── machining_commands.py    # Operation types (milling, sawing, drilling, moves)
├── tool_library.py          # Tool definitions and types
├── work_planes.py           # Work plane definitions
├── utility_commands.py      # Utility commands (feedrate override, stops, etc.)
├── btlx_processes.py        # BTLx file processing
├── parse_btlx.py            # BTLx XML parsing
├── writehops.py             # Legacy HOP file generation
└── merge_stock_hops.py      # Stock merging utilities
```

---

## Command Architecture

### Hierarchical Class Structure

All HOPS commands inherit from a unified base class hierarchy that enables:
- **Command chaining**: Add commands before/after other commands
- **Fluent API**: Method chaining for common modifications
- **Type safety**: Semantic grouping by command category
- **No circular dependencies**: Clean module separation

```
HOPSCommand (abstract base)
    │
    ├── OperationCommand (abstract)
    │   ├── MillingOperation
    │   ├── SawingOperation
    │   └── DrillingOperation
    │
    ├── MoveCommand (abstract)
    │   ├── StartPoint
    │   ├── G01
    │   ├── G02M
    │   ├── G03M
    │   └── EndPoint
    │
    ├── WorkPlaneCommand (abstract)
    │   ├── WorkPlane (enum-based)
    │   └── FreePlane
    │
    ├── ToolCommand (abstract)
    │   └── MachiningTool
    │
    └── UtilityCommand (abstract)
        ├── FeedrateOverride
        └── MachineStop
```

### Module Dependencies

Clean dependency hierarchy with no circular imports:

```
base_commands.py
     ↓ (imported by all)
┌────┴────┬────────────┬─────────────┬──────────────┐
│         │            │             │              │
tool_   work_      utility_    machining_      hop_core.py
library  planes     commands    commands
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

### 0. base_commands.py - Abstract Base Classes

The foundation for all HOPS commands, providing unified command manipulation interface.

#### **HOPSCommand (Abstract)**
Root base class for all HOPS commands with command chaining support.

```python
class HOPSCommand(ABC):
    def __init__(self):
        self._before_commands: List[HOPSCommand] = []
        self._after_commands: List[HOPSCommand] = []
    
    @abstractmethod
    def _to_hop_line(self) -> str:
        """Generate the core HOPS command line."""
        pass
    
    def add_before(self, command: HOPSCommand) -> HOPSCommand:
        """Add a command to execute before this command."""
        ...
    
    def add_after(self, command: HOPSCommand) -> HOPSCommand:
        """Add a command to execute after this command."""
        ...
    
    def __str__(self) -> str:
        """Generate complete output including before/after commands."""
        ...
```

**Usage**:
```python
# Chain commands together
sp = StartPoint(0, 0, 0)
sp.add_before(FeedrateOverride(3000))
sp.add_before(MachineStop("Check setup"))

# Output:
# CALL _Tvorschub_v5(VAL VORSCHUB:=3000)
# CALL MachineStop_V7(...)
# SP(0,0,0,...)
```

#### **OperationCommand (Abstract)**
Base for complete machining operations with operation-specific fluent API.

**Fluent Methods**:
- `.with_tool(tool)` - Add tool before operation
- `.with_workplane(workplane)` - Add workplane before operation
- `.with_feedrate(feedrate)` - Add feedrate override before operation
- `.with_stop(message, **kwargs)` - Add machine stop before operation

**Example**:
```python
from easyhops.tool_library import MachiningTool, ToolCallType
from easyhops.work_planes import FreePlane

tool = MachiningTool(ToolCallType.ROUTER, position=505, depth=3000, diameter=10)
plane = FreePlane(x=100, y=50, z=0, rotation_angle=45, tilt_angle=0)

# Create operation with fluent API
operation = SawingOperation(
    sx=100, sy=200, sz=-50,
    ex=300, ey=400, ez=-50
).with_tool(tool).with_workplane(plane).with_feedrate(2000)

# Output includes tool, plane, feedrate override, then operation
print(str(operation))
```

#### **MoveCommand (Abstract)**
Base for individual movements with move-specific fluent API.

**Fluent Methods**:
- `.with_feedrate(feedrate)` - Add feedrate override before move
- `.with_stop(message, **kwargs)` - Add machine stop before move

**Example**:
```python
# Create move with feedrate override
g01 = G01(100, 100, 0).with_feedrate(4000).with_stop("Check alignment")

# Output:
# CALL _Tvorschub_v5(VAL VORSCHUB:=4000)
# CALL MachineStop_V7(...)
# G01(100,100,0,...)
```

#### **WorkPlaneCommand (Abstract)**
Base for work plane definitions (EBENE, EBENEF).

#### **ToolCommand (Abstract)**
Base for tool definitions (WZF, WZS, WZB).

#### **UtilityCommand (Abstract)**
Base for utility/modifier commands that enhance other commands.

---

### 1. utility_commands.py - Command Modifiers

#### **FeedrateOverride**
Standalone feedrate override command.

**Format**: `CALL _Tvorschub_v5(VAL VORSCHUB:={feedrate})`

**Usage**:
```python
override = FeedrateOverride(3000)
print(str(override))  # CALL _Tvorschub_v5(VAL VORSCHUB:=3000)
```

#### **MachineStop**
Machine stop/pause command with optional message and park position.

**Format**: `CALL MachineStop_V7 ( VAL MODE:={mode},PARKMODE:={park_mode},PARKPOSX:={park_pos_x:.3f},PARKPOSY:={park_pos_y},TYP:={typ},R6:={r6}, STR:='{message}',R7:={r7})`

**Parameters**:
- `message` - Optional message to display
- `mode` - Stop mode (default: 2)
- `park_mode` - Park mode (default: 0)
- `park_pos_x`, `park_pos_y` - Park position coordinates
- Additional machine-specific parameters

**Example**:
```python
stop = MachineStop("Flip workpiece", park_pos_x=1500.0, park_pos_y=800.0)
```

---

### 2. hop_core.py - Fundamental Building Blocks

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

### 3. tool_library.py - Tool Definitions

All tool classes inherit from `ToolCommand` base class.

#### **ToolCallType (Enum)**
```python
ROUTER = "WZF"  # Milling/routing tool
SAW = "WZS"     # Sawing tool
DRILL = "WZB"   # Drilling tool
```

#### **MachiningTool**
Represents tool call commands (WZF/WZS/WZB). Inherits from `ToolCommand`.

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

### 4. work_planes.py - Work Plane Definitions

All work plane classes inherit from `WorkPlaneCommand` base class.

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

### 5. machining_commands.py - Operation Types

All operation and move classes inherit from their respective base classes.

#### **Move Commands**

All move commands inherit from `MoveCommand` and support fluent API:
- `StartPoint` - Milling start point (SP)
- `G01` - Linear interpolation move
- `G02M` - Clockwise arc with center point
- `G03M` - Counter-clockwise arc with center point
- `EndPoint` - Milling end point (EP)

**StartPoint (SP)**
```
SP(x,y,z,depth,ref_mode,direction,corr_side,approach,radius,...)
```

**G01 (Linear Move)**
Linear interpolation movement. Inherits from `MoveCommand`.

```
G01(x,y,z,corner_radius,easy_snap_xy,easy_snap_z)
```

**Fluent API Example**:
```python
# Add feedrate override to specific move
g01 = G01(100, 100, -10, corner_radius=5).with_feedrate(4000)

# Output:
# CALL _Tvorschub_v5(VAL VORSCHUB:=4000)
# G01(100,100,-10,5,0,2)

# Chain multiple modifiers
g01 = (G01(100, 100, -10)
    .with_feedrate(4000)
    .with_stop(mode=1, message="Check workpiece"))
```

**G02M / G03M (Arc Moves)**
Clockwise (G02M) and counter-clockwise (G03M) arc movements with center point.
Both inherit from `MoveCommand`.

**EndPoint (EP)**
Milling end point. Inherits from `MoveCommand`.

```
EP(lead_out_mode,lead_out_factor,reverse_direction)
```

#### **Operation Commands**

All operations inherit from `OperationCommand` and support fluent API.

#### **MillingOperation**
Composite operation combining SP + list of moves + EP into a complete milling path.
Inherits from `OperationCommand` for unified interface and fluent API support.

```python
class MillingOperation(OperationCommand):
    def __init__(
        self,
        start_point: StartPoint,
        moves: List[Union[G01, G02M, G03M]],
        end_point: EndPoint
    ):
        super().__init__()
        self.start_point = start_point
        self.moves = moves
        self.end_point = end_point
```

**Fluent API Support**:
```python
from easyhops.tool_library import MachiningTool, ToolCallType
from easyhops.work_planes import FreePlane

# Create milling operation with fluent API
tool = MachiningTool(ToolCallType.ROUTER, position=505, depth=3000, diameter=10)
plane = FreePlane(x=100, y=50, z=0, rotation_angle=45, tilt_angle=0)

operation = MillingOperation(
    start_point=StartPoint(0, 0, -10),
    moves=[G01(100, 0, -10), G01(100, 100, -10)],
    end_point=EndPoint()
).with_tool(tool).with_workplane(plane).with_feedrate(3000)

# Tool, workplane, and feedrate override are automatically added before the operation

# Or add commands to individual moves
operation = MillingOperation(
    start_point=StartPoint(0, 0, -10).with_stop(mode=1),
    moves=[
        G01(100, 0, -10).with_feedrate(4000),
        G01(100, 100, -10).with_feedrate(5000)
    ],
    end_point=EndPoint()
)
```

#### **SawingOperation**
Single sawing cut command. Inherits from `OperationCommand`.

**Format**: `SAEGEN(sx,sy,sz,ex,ey,ez,radius_compensation,fit_in,lead_in_out,process_mode,tilt_angle,z_level,easy_snap_xy_start,easy_snap_xy_end,easy_snap_z,p16,p17)`

**Attributes**:
- `sx, sy, sz` - Start coordinates
- `ex, ey, ez` - End coordinates
- `radius_compensation` - Tool position relative to path
- `fit_in` - Saw blade fitting mode
- `tilt_angle` - C-axis tilt angle for beveled cuts
- Other sawing-specific parameters

**Fluent API Example**:
```python
saw = SawingOperation(
    sx=100, sy=200, sz=-50,
    ex=300, ey=400, ez=-50,
    tilt_angle=-7.5
).with_tool(saw_tool).with_workplane(WorkPlane.TOP).with_feedrate(1500)
```

#### **DrillingOperation**
Drilling command. Inherits from `OperationCommand`.

**Format**: `BOHRUNG(x,y,z,diameter,depth,drilling_flags,rotation,tilt,easy_snap_xy,easy_snap_z)`

---

### 6. hop_job.py - Complete File Parser

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

### 1. **Hierarchical Command Architecture**
Two-level inheritance provides category-specific APIs while maintaining unified base.

```
HOPSCommand (root)
    ↓
Category Abstract Classes (OperationCommand, MoveCommand, etc.)
    ↓
Concrete Implementations
```

**Benefits**:
- Category-specific fluent methods (`.with_tool()` only on operations)
- Type safety and semantic grouping
- Extensible without modifying base classes
- No circular dependencies

### 2. **Fluent API Pattern**
Method chaining for intuitive command composition.

```python
operation = SawingOperation(...) \
    .with_tool(tool) \
    .with_workplane(plane) \
    .with_feedrate(2000) \
    .with_stop("Check alignment")
```

### 3. **Command Chaining Pattern**
Generic `add_before()` and `add_after()` for arbitrary command composition.

```python
sp = StartPoint(0, 0, -10)
sp.add_before(FeedrateOverride(3000))
sp.add_before(MachineStop("Ready?"))
# Outputs feedrate override, then stop, then start point
```

### 4. **Dataclass Pattern**
Most classes use `@dataclass` for concise definitions and automatic `__init__`.

### 5. **Factory Pattern**
Each class has a `from_hop_line(line: str)` class method for parsing.

```python
tool = MachiningTool.from_hop_line("WZF(504,3000,4000,5000,_SD,_ANF,'Tool')")
plane = WorkPlane.from_hop_line("EBENE0()")
saw = SawingOperation.from_hop_line("SAEGEN(...)")
```

### 6. **Abstract Method Pattern**
All command classes implement `_to_hop_line()` for serialization.

```python
class MyCommand(HOPSCommand):
    def _to_hop_line(self) -> str:
        return f"MYCMD({self.param1},{self.param2})"
```

The base `__str__()` method automatically combines `_before_commands`, `_to_hop_line()`, and `_after_commands`.

### 7. **Enum Pattern**
Enums for standardized values with string representations.

```python
ToolCallType.ROUTER  # → "WZF"
WorkPlane.TOP        # → EBENE0
```

### 8. **Two-Phase Parsing**
Separate chunking from parsing for robustness and testability.

---

## Design Decisions

### Why Two-Level Abstract Hierarchy?

**Question**: Why not just one `HOPSCommand` base class with all methods?

**Answer**: The two-level hierarchy provides:

1. **Category-Specific APIs**:
   - `OperationCommand.with_tool()`, `.with_workplane()` - Makes sense for operations
   - `MoveCommand.with_feedrate()` - Makes sense for moves
   - Not all commands need all methods

2. **Type Safety**:
   - Functions can accept `OperationCommand` → knows it's a complete operation
   - Functions can accept `MoveCommand` → knows it's a single move
   - Better than generic `HOPSCommand`

3. **Semantic Grouping**:
   - Clear categorization of command types
   - Easy to understand what operations are available
   - Natural extension point for new command categories

4. **Future Extensibility**:
   - Easy to add category-specific methods without polluting base class
   - Can create new categories (e.g., `CommentCommand`, `VariableCommand`)

**Trade-off**: Slightly more complex hierarchy vs. simpler flat structure with unnecessary methods on all classes.

**Conclusion**: Two-level provides meaningful organization without significant complexity cost.

### Why Separate base_commands.py Module?

**Question**: Why not keep abstract classes in their respective modules?

**Answer**: Circular dependency avoidance:

**Before** (Circular Dependencies):
```
machining_commands.py → tool_library.py (for MachiningTool)
tool_library.py → hop_core.py (for HOPSCommand)
machining_commands.py → hop_core.py (for HOPSCommand)
utility_commands.py ← machining_commands.py (runtime imports)
```

**After** (Clean Hierarchy):
```
base_commands.py (no dependencies)
    ↓
All modules import from base_commands.py
No circular dependencies!
```

**Benefits**:
- ✅ Modules can be imported in any order
- ✅ No runtime imports in methods (only in base_commands fluent API)
- ✅ Clear dependency direction
- ✅ Easy to test and maintain

### 9. **Two-Phase Parsing**
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
