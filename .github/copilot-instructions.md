# EasyHops AI Agent Instructions

## Project Overview

EasyHops is a Python library for parsing, manipulating, and generating HOPS (.hop) CNC machining files used in timber fabrication. **The core focus is the object-oriented approach that serves as a Python wrapper for HOPS**, enabling programmatic creation and modification of machining programs for woodworking CNC machines.

**Legacy Code**: The modules `writehops.py`, `parse_btlx.py`, and `btlx_processes.py` are deprecated legacy code. A similar BTLx workflow is planned for this package but its implementation is still to be defined. These modules remain in the codebase temporarily but should not be used as reference for new development.

## Architecture Fundamentals

### Command Hierarchy (Critical)

All HOPS commands inherit from `HOPSCommand` base class in [base_commands.py](../src/easyhops/base_commands.py). The hierarchy is:

```
HOPSCommand (abstract)
├── OperationCommand (full operations: milling, sawing, drilling)
├── MoveCommand (individual moves: SP, G01, G02M, G03M, EP)
├── WorkPlaneCommand (EBENE, EBENEF)
├── ToolCommand (WZF, WZS, WZB)
└── UtilityCommand (feedrate override, machine stops)
```

**Key Pattern**: Every command implements `_to_hop_line()` for serialization and `from_hop_line(line: str)` classmethod for parsing. Commands support `add_before()` and `add_after()` for chaining.

### Two-Phase Parsing Strategy

Parser in [hop_job.py](../src/easyhops/hop_job.py) uses two phases:
1. **Chunking**: Split file into logical blocks (`HOPChunk` objects) without parsing content
2. **Parsing**: Convert each chunk independently into typed Python objects

**Why**: Separates structural analysis from content parsing for maintainability and preserves line numbers for error reporting. See [PARSING_STRATEGY.md](../docs/PARSING_STRATEGY.md) for details.

### Module Dependencies (No Circular Imports)

```
base_commands.py (root)
    ↓
tool_library.py, work_planes.py, utility_commands.py, hop_core.py
    ↓
machining_commands.py
    ↓
hop_job.py
```

**Critical**: Never import from child modules in parent modules. All commands import from `base_commands.py` only.

## Development Workflows

### Running Tests

```bash
# Run all tests with coverage
pytest tests/ --cov=src/easyhops

# Run specific test file
pytest tests/test_hop_job_parsing.py -v

# Run specific test
pytest tests/test_hop_job_parsing.py::TestToolParsing::test_parse_router_tool -v
```

Test files follow `test_*.py` pattern. See [pytest.ini](../pytest.ini) for configuration.

### Code Quality

Format with Black and lint with Ruff before committing:
```bash
black src/ tests/
ruff check src/ tests/
```

## Project-Specific Conventions

### 1. Fluent API Pattern

Operations support method chaining via category-specific abstract classes:

```python
# OperationCommand provides .with_tool(), .with_workplane(), .with_feedrate()
operation = SawingOperation(sx=100, sy=200, sz=-50, ex=300, ey=400, ez=-50) \
    .with_tool(saw_tool) \
    .with_workplane(WorkPlane.TOP) \
    .with_feedrate(2000)

# MoveCommand provides .with_feedrate(), .with_stop()
g01 = G01(100, 100, -10).with_feedrate(4000).with_stop("Check alignment")
```

**Implementation**: Fluent methods in abstract base classes call `add_before()` internally and return `self`.

### 2. Enum Usage for HOPS Constants

Use IntEnum/StrEnum for HOPS-specific values:
- `ToolCallType`: ROUTER="WZF", SAW="WZS", DRILL="WZB"
- `WorkPlane`: TOP=0, BOTTOM=1, etc. (maps to EBENE0-5)
- `EasySnapXY`, `EasySnapZ`: Coordinate reference modes
- `CompensationMode`, `LeadInOutMode`, `ProcessMode`: Machining parameters

**Pattern**: Enums in [hop_core.py](../src/easyhops/hop_core.py) and [machining_commands.py](../src/easyhops/machining_commands.py) map directly to HOPS numeric values.

### 3. HOPS System Variables (_SD, _ANF)

Use `None` in Python to represent HOPS macro variables:
- `_ANF` (Anfang = "start") → `None` (use tool manager default)
- `_SD` (Standard) → `None` (use standard value)

**Example**: `MachiningTool(..., motor_speed=None)` serializes to `_SD` in HOPS output.

### 4. HOPSMachining Container

`HOPSMachining` groups operations that share the same tool and workplane:

```python
HOPSMachining(
    tool=MachiningTool(...),
    work_plane=FreePlane(...),
    operations=[MillingOperation(...), MillingOperation(...)],  # Multiple ops OK
    feedrate_overrides=[((op_idx, cmd_idx), FeedrateOverride(...))]
)
```

**Feedrate tracking**: `((operation_idx, command_idx), override)` where `command_idx=None` for sawing/drilling, or specific move index for milling.

### 5. Coordinate System & Z-Reference

- **Z-axis**: Negative = into material, Positive = above material
- **EasySnapZ**: Controls Z reference (TOP_EDGE=0, BOTTOM_EDGE=1, RELATIVE=2)
- **X/Y**: Always absolute in HOPS (no incremental XY)

## Key Files Reference

- [ARCHITECTURE.md](../ARCHITECTURE.md): Complete architectural documentation with class diagrams
- [PARSING_STRATEGY.md](../docs/PARSING_STRATEGY.md): Detailed parsing algorithm and chunking rules
- [base_commands.py](../src/easyhops/base_commands.py): Abstract base classes defining command hierarchy
- [hop_job.py](../src/easyhops/hop_job.py): Main parser and `HOPSJob` container
- [hop_core.py](../src/easyhops/hop_core.py): Core enums and file structure (`VarsDefinition`, `FinishedPart`, `ParkPosition`)
- [machining_commands.py](../src/easyhops/machining_commands.py): All operation types (milling, sawing, drilling)
- [data/test.hop](../data/test.hop): Reference HOP file for testing

**⚠️ DEPRECATED/LEGACY** (do not use as reference):
- [writehops.py](../src/writehops.py): Legacy HOP generation (use OOP approach instead)
- [parse_btlx.py](../src/easyhops/parse_btlx.py): Legacy BTLx parser (new implementation TBD)
- [btlx_processes.py](../src/easyhops/btlx_processes.py): Legacy BTLx processing (new implementation TBD)

## Tool Library (.too File Format)

The `ToolLibrary` class parses CNC machine tool configuration files (`.too` format):

**File Structure**:
- **Format**: INI-like with sections `[ToolData0]`, `[ToolData1]`, etc.
- **Encoding**: UTF-16 (fallback to UTF-8)
- **Tool Metadata**: `[ToolDataN]` sections contain `Name`, `ToolType` index
- **Tool Position**: Actual tool ID stored in `[ToolDataNCuttingEdge0]` section under `ID` key

**ToolType Mapping** (index → ToolCallType enum):
- `0` = Schaft (Cassette) → `ToolCallType.ROUTER` (WZF)
- `1` = Drill → `ToolCallType.DRILLER` (WZB)
- `2` = Säge (Saw blade) → `ToolCallType.SAW` (WZS)

**Usage**: `ToolLibrary.get("Birdsmouth")` or `ToolLibrary.get(tool_no=504)` automatically loads from `data/7235C_219.too`.

**Debugging**: If tool parsing fails, check UTF-16 encoding and that `CuttingEdge0` section exists with valid `ID` field.

## BTLx Integration

BTLx (timber processing XML standard) integration is planned but implementation is **still to be defined**. The current legacy modules (`parse_btlx.py`, `btlx_processes.py`) demonstrate the concept but should not be used as reference for new development. Future BTLx workflow will follow the same OOP wrapper pattern as the HOPS implementation.

## Common Patterns

### Creating a New Command

1. Inherit from appropriate abstract class (`OperationCommand`, `MoveCommand`, etc.)
2. Implement `_to_hop_line(self) -> str` for serialization
3. Implement `from_hop_line(cls, line: str) -> Self` classmethod for parsing
4. Use regex patterns for parsing HOPS syntax
5. Add tests in `tests/test_*.py`

### Adding a New Machining Operation

See [machining_commands.py](../src/easyhops/machining_commands.py) examples:
- `MillingOperation`: Composite (SP + moves + EP)
- `SawingOperation`: Single SAEGEN command
- `DrillingOperation`: Single BOHRUNG command

All inherit from `OperationCommand` to get `.with_tool()`, `.with_workplane()`, etc.

## Troubleshooting

- **Parsing errors**: Use `strict=True` with `HOPSJob.from_hop_file()` to raise on first error
- **Regex patterns**: All command parsing uses numbered capture groups, not named groups (for consistency)
- **Tool library**: Tools can be defined inline or loaded from .too files ([tool_library.py](../src/easyhops/tool_library.py))
- **Legacy code**: [writehops.py](../src/writehops.py) and [merge_stock_hops.py](../src/easyhops/merge_stock_hops.py) are legacy - prefer new OOP approach

## Testing Strategy

- **Unit tests**: Test individual commands and parsing (`test_hop_core.py`, `test_machining_commands.py`)
- **Integration tests**: Test complete file parsing (`test_hop_job_parsing.py`) using [data/test.hop](../data/test.hop)
- **Regression tests**: Parse → serialize → parse roundtrip should be identical
