# Tool Library System

## Overview

The tool library system provides **dynamic tool loading from .too files** for CNC machining operations. Tools use HOPS macro variables by default, allowing the CNC machine to use its configured default values. Parameters can be overridden as needed.

## Architecture

- **`tool_library.py`**: Core implementation with `MachiningTool`, predefined tool subclasses (`BirdsmouthW41`, `SaegeD350`, `CastorD61`), `ToolLibrary`, and `HopsSystemVars`
- **Predefined tools**: Subclasses with fixed positions and tool types
- **Dynamic loading**: Parse all tools from .too files

## Usage Patterns

### 1. Direct Tool Access (Recommended)

```python
from src.tool_library import ToolLibrary

# Get tool directly from default library - no instantiation needed!
tool = ToolLibrary.get('Birdsmouth')
print(str(tool))  # WZF(504,_VE,_V,_VA,_SD,_ANF,'1')

# Override specific parameters as needed
tool.feedrate = 3500
print(str(tool))  # WZF(504,_VE,3500,_VA,_SD,_ANF,'1')

# Get by tool number
tool = ToolLibrary.get(tool_no=27)
```

### 2. Predefined Tool Subclasses

```python
from src.tool_library import BirdsmouthW41, SaegeD350, CastorD61

# Use machine defaults (HOPS macro variables)
tool = BirdsmouthW41()
print(str(tool))  # WZF(504,_VE,_V,_VA,_SD,_ANF,'1')

# Override specific feedrates
tool = SaegeD350(feedrate=10000, surface_feedrate=7000)
print(str(tool))  # WZS(201,_VE,10000,7000,_SD,_ANF,'1')

# Mix custom and defaults
tool = CastorD61(feedrate=3500)
print(str(tool))  # WZF(503,_VE,3500,_VA,_SD,_ANF,'1')
```

### 3. Custom Tool Library

```python
from src.tool_library import ToolLibrary

# For custom .too files, create an instance
library = ToolLibrary('custom_tools.too')
tool = library.get_tool('CustomTool')
print(str(tool))  # Uses HOPS macro variables by default

# Default library uses data/7235C_219.too automatically
library = ToolLibrary()  # Loads default .too file
tool = library.get_tool('Birdsmouth')
```

### 4. Manual Tool Creation

```python
from src.tool_library import MachiningTool, ToolCallType

# Create tool with machine defaults (None parameters = HOPS macros)
tool = MachiningTool(
    tool_type=ToolCallType.ROUTER,
    position=504,
    name='Birdsmouth W41'
)
print(str(tool))  # WZF(504,_VE,_V,_VA,_SD,_ANF,'1')

# Override specific parameters
tool = MachiningTool(
    tool_type=ToolCallType.ROUTER,
    position=1,
    lead_in_feedrate=5000,
    feedrate=8000,
    lead_out_feedrate=5000,
    name='DIA20_R'
)
print(str(tool))  # WZF(1,5000,8000,5000,_SD,_ANF,'1')
```

### 5. Benefits of This System

**Direct access with `ToolLibrary.get()`**:
- ✅ No instantiation needed - just call the class method
- ✅ Singleton pattern - library parsed once
- ✅ Uses HOPS macro variables by default
- ✅ Override only what you need
- ✅ Case-insensitive, partial name matching
- ✅ Automatic tool type detection (cassette vs blade)

**Predefined tool subclasses**:
- ✅ Fixed position and holder type
- ✅ Semantic class names (`BirdsmouthW41`, not position 504)
- ✅ Optional parameter overrides
- ✅ Clean, simple API

## MachiningTool API

`MachiningTool` instances work like other HOPS command objects - instantiate with parameters, then use `str()` to get the HOPS command:

```python
# Use HOPS macro variables (None = machine defaults)
tool = MachiningTool(
    tool_type=ToolCallType.ROUTER,
    position=504,
    name='Birdsmouth'
)
command = str(tool)  # WZF(504,_VE,_V,_VA,_SD,_ANF,'1')

# Override specific parameters
tool = MachiningTool(
    tool_type=ToolCallType.ROUTER,
    position=504,
    feedrate=3500,
    lead_out_feedrate=4000,
    name='Birdsmouth'
)
command = str(tool)  # WZF(504,_VE,3500,4000,_SD,_ANF,'1')

# Modify parameters after creation
tool.feedrate = 4000
command = str(tool)  # WZF(504,_VE,4000,4000,_SD,_ANF,'1')
```

### Tool Properties

- `tool_type`: `ToolCallType.ROUTER`, `ToolCallType.SAW`, or `ToolCallType.DRILLER`
- `position`: Tool position number (e.g., 504 for birdsmouth, 201 for saw blade)
- `lead_in_feedrate`: Lead in/out feedrate in mm/min (None = `_VE` macro)
- `feedrate`: General/rapid feedrate in mm/min (None = `_V` macro)
- `lead_out_feedrate`: Lead out feedrate in mm/min (None = `_VA` macro)
- `motor_speed`: Motor speed in RPM (None = `_SD` macro)
- `lead_in_out_factor`: Lead-in/out factor multiplier (None = `_ANF` macro)
- `head_id`: Tool head identifier (default: `'1'`)
- `name`: Tool name/description

### HOPS System Variables (HopsSystemVars enum)

When tool parameters are `None`, these HOPS macro variables are used:

- `HopsSystemVars.LEAD_IN_FEEDRATE` = `_VE` - Lead in/out speed
- `HopsSystemVars.FEEDRATE` = `_V` - General/rapid feed rate
- `HopsSystemVars.LEAD_OUT_FEEDRATE` = `_VA` - Lead out speed
- `HopsSystemVars.MOTOR_SPEED` = `_SD` - Motor speed
- `HopsSystemVars.LEAD_IN_OUT_FACTOR` = `_ANF` - Lead in/out factor
- `HopsSystemVars.TOOL_DIAMETER` = `_WZD` - Tool diameter
- `HopsSystemVars.TOOL_RADIUS` = `_WZR` - Tool radius
- `HopsSystemVars.SAW_WIDTH` = `_SBB` - Saw blade width

The CNC machine substitutes these with configured values during program execution.

## Predefined Tool Subclasses

### BirdsmouthW41
- **Position**: 504 (WZF)
- **Type**: Router (ToolCallType.ROUTER)
- **Use**: Contour milling and pocketing

### SaegeD350
- **Position**: 201 (WZS)
- **Type**: Saw (ToolCallType.SAW)
- **Use**: Saw cutting operations

### CastorD61
- **Position**: 503 (WZF)
- **Type**: Router (ToolCallType.ROUTER)
- **Use**: General milling tasks

## .too File Parsing

- **Encoding**: UTF-16 (automatically detected with fallback to UTF-8)
- **Format**: Windows INI-like structure
- **Sections**: `[ToolDataN]` for tool metadata
- **Extracted**: Name, ToolNo, ToolType
- **Default behavior**: All tools use HOPS macro variables (machine defaults)
- **Parsed but not used**: Feedrate values from .too file (use macro variables instead)

## ToolLibrary API

### Direct Access (Class Method)

```python
# No instantiation needed - uses singleton pattern
tool = ToolLibrary.get('Birdsmouth')  # From default data/7235C_219.too
print(str(tool))  # WZF(504,_VE,_V,_VA,_SD,_ANF,'1')

# By name (case-insensitive, partial match)
tool = ToolLibrary.get('birdsmouth')  # Same result
tool = ToolLibrary.get('birds')       # Partial match works too

# By tool number
tool = ToolLibrary.get(tool_no=27)

# Returns None if not found
unknown = ToolLibrary.get('NonExistent')  # None
```

### Instance Methods (Custom Libraries)

```python
# Create instance with custom .too file
library = ToolLibrary('custom_tools.too')

# Or use default
library = ToolLibrary()  # Uses data/7235C_219.too

print(library)  # ToolLibrary(tools=17, file_count=27)

# Get tool from instance
tool = library.get_tool('Birdsmouth')
tool = library.get_tool(tool_no=27)

# List available tools
tools = library.list_tools()  # ['birdsmouth', 'saw blade', 'turbex ø12', ...]
```

## Example Output

```python
# Direct access
tool = ToolLibrary.get('Birdsmouth')
print(tool)  # Tool(CASSETTE, position=504, name='Birdsmouth')
print(str(tool))  # WZF(504,_VE,_V,_VA,_SD,_ANF,'1')

# Override parameters
tool.feedrate = 3500
print(str(tool))  # WZF(504,_VE,3500,_VA,_SD,_ANF,'1')

# Predefined subclass
saw = SaegeD350(feedrate=10000, lead_out_feedrate=7000)
print(str(saw))  # WZS(201,_VE,10000,7000,_SD,_ANF,'1')
```

## Implementation Notes

### Tool Detection & Assignment
- **Tool positions**: Uses `ToolNo` from .too file as position for router tools
- **Saw blades**: Automatically detected (`ToolType=2`) and assigned position 201
- **Tool type**: Router (`WZF`), Saw (`WZS`), or Driller (`WZB`) determined from `ToolType` field
- **ToolType values**: 0=Schaft (router), 1=Drill (drill head), 2=Säge (saw blade), 3=Laser/Special

### Default Parameter Behavior
- **All tools from .too files use HOPS macro variables** - parameters default to `None`
- **Override when needed** - set specific feedrates only where required
- **Machine decides** - CNC uses its configured defaults for `_VE`, `_V`, `_VA`, `_SD`, `_ANF`

### Lookup Features
- **Singleton pattern**: `ToolLibrary.get()` uses cached instance (parsed once)
- **Case-insensitive**: `ToolLibrary.get('Birdsmouth')` and `ToolLibrary.get('birdsmouth')` both work
- **Partial matching**: `ToolLibrary.get('birds')` finds 'birdsmouth'
- **Flexible search**: Search by name or tool number
- **Name normalization**: Tool names are lowercased for consistent lookup

### Encoding Handling
- **Primary**: UTF-16 (standard for .too files)
- **Fallback**: UTF-8 with error handling
- Automatically detects and handles both encodings

### File Structure
- **Default path**: `data/7235C_219.too` (relative to module)
- **Custom paths**: Pass path to `ToolLibrary(path)` constructor
- **Parsed sections**: Only `ToolDataN` sections (not CuttingEdge sections)
