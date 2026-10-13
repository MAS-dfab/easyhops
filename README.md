# easyhops

Python library for parsing, manipulating, and generating HOPS (`.hop`) CNC machining files used in timber fabrication.

The core focus is an object-oriented wrapper around the HOPS file format that enables programmatic creation and modification of machining programs for woodworking CNC machines.

---

## Installation

```bash
pip install -e .
```

**Requirements**: Python ≥ 3.9, `compas >= 2.0`

**Optional** (for `compas_timber` integration and fabrication strategies):
```bash
pip install compas_timber
```

**Dev tools**:
```bash
pip install -r requirements-dev.txt
```

---

## Two-layer design

| Layer | Location | Purpose |
|-------|----------|---------|
| **Core** | `easyhops/` root modules | Pure HOPS parsing and serialization — no `compas_timber` dependency |
| **Strategies** | `easyhops/strategies/` | Converts `compas_timber` processing objects into `HOPSMachining` instances |

The core layer is usable standalone (no `compas_timber` required).

---

## Core usage

### Parse an existing HOP file

```python
from easyhops.hop_job import HOPSJob

job = HOPSJob.from_hop_file("part.hop")

print(f"Dimensions: {job.vars.dx} x {job.vars.dy} x {job.vars.dz}")
print(f"Machinings: {len(job.machinings)}")

for m in job.machinings:
    print(f"  {m.tool.tool_type.value}@{m.tool.position}  plane={m.work_plane}")
```

### Build a HOP file from scratch

```python
from easyhops.hop_core import VarsDefinition, FinishedPart, ParkPosition, ParkMode
from easyhops.hop_job import HOPSJob, HOPSMachining
from easyhops.machining_commands import MillingOperation, StartPoint, G01, EndPoint
from easyhops.tool_library import MachiningTool, ToolCallType
from easyhops.work_planes import FreePlane

tool = MachiningTool(ToolCallType.ROUTER, position=504)
plane = FreePlane(x=0, y=0, z=0, rotation_angle=0, tilt_angle=0)
operation = MillingOperation(
    start_point=StartPoint(0, 0, -10),
    moves=[G01(100, 0, -10), G01(100, 100, -10)],
    end_point=EndPoint(),
)
machining = HOPSMachining(tool=tool, work_plane=plane, operations=[operation])

job = HOPSJob(
    vars=VarsDefinition(dx=1000, dy=200, dz=100),
    finished_part=FinishedPart(dx=1000, dy=200, dz=100),
    park_mode=ParkPosition(mode=ParkMode.RIGHT_MIDDLE),
    machinings=[machining],
)
job.to_hop_file("output.hop")
```

---

## Strategies (compas_timber integration)

Strategies convert `compas_timber` processing objects into `HOPSMachining` lists. All strategy classes are stateless namespaces of `@staticmethod` methods.

| Class | Processing type | Methods |
|-------|----------------|---------|
| `LapStrategies` | `Lap` | `milling()` |
| `DoubleCutStrategies` | `DoubleCut` | `milling()`, `pocketing()` |
| `BirdsMouthStrategies` | `BirdsMouth` | `milling()` |
| `JackRafterCutStrategies` | `JackRafterCut` | `sawing()`, `milling()`, `open_pocket()`, `contour_pocket()` |

### Full workflow: BTLx model → HOP files

```python
from easyhops.hop_job import HOPSJob
from easyhops.strategies import LapStrategies
from easyhops.strategies.jack_rafter_cut import JackRafterCutStrategies
from easyhops.tool_library import SaegeD350
from easyhops.utility_commands import MachineStop

def element_to_job(element):
    job = HOPSJob.from_element(element)   # shell: vars/finished_part/park_mode from element
    rsi = job.ref_side_index
    opp_rsi = (rsi + 2) % 4              # geometrically opposite face

    pre_flip, post_flip = [], []

    for processing in element.features:
        name = processing.PROCESSING_NAME

        if name == "Lap":
            ms = LapStrategies.milling(processing)
            if processing.ref_side_index == opp_rsi:
                pre_flip.extend(ms)   # needs beam flip first
            else:
                post_flip.extend(ms)

        elif name == "JackRafterCut":
            post_flip.extend(
                JackRafterCutStrategies.sawing(processing, machine_ref_side_index=rsi, tool=SaegeD350())
            )

    # Sort: milling before sawing (customisable key)
    post_flip = HOPSJob.sort_machinings(post_flip)

    if pre_flip:
        job.add(pre_flip)
        job.add(MachineStop("flip beam 180deg"))
    job.add(post_flip)

    return job
```

See [`examples/timber_model_to_hops.py`](examples/timber_model_to_hops.py) for a complete script with CLI and error collection.

---

## Vector (5-axis) milling from tool frames

`FrameToolpathStrategies` turns tool frames (e.g. Grasshopper planes) into the native HOPS
vector commands `VSP` / `VG01` / `VEP`, where every move carries its own tool orientation,
so all five axes interpolate continuously (the format used by the HOPS system macro
`Sphere.hop` and the Fusion 360 HOPS post).

- frame origin = tool tip, frame Z = tool axis from tip to holder (X/Y are ignored)
- coordinates are absolute in the finished part: origin at the X=0/Y=0/Z=0 corner
  (bottom face), X along DX, Y along DY, Z up
- one pass per `VSP … VEP` block; start and end each pass with the tool clear of the
  material, HOPS links the passes

```python
from easyhops.hop_core import FinishedPart, ParkPosition, VarsDefinition
from easyhops.hop_job import HOPSJob
from easyhops.strategies import FrameToolpathStrategies
from easyhops.tool_library import MachiningTool

machinings = FrameToolpathStrategies.vector_milling(
    passes,                      # list of passes, each a list of compas Frames
    MachiningTool(404, motor_speed=18000),
    part_frame=part_frame,       # compas Frame at the part's zero corner
    feedrates=feeds,             # one value, or per pass (value or list per frame)
)
job = HOPSJob(VarsDefinition(dx=500, dy=200, dz=100), FinishedPart(), ParkPosition(), machinings)
print(FrameToolpathStrategies.check(job, passes, part_frame=part_frame))  # read-back report
job.to_hop_file("toolpath.hop")
```

The tool angles follow the machine's own macros (`Calc_DW_KW_NV`, `Rot3D_V7`):
`KW = arccos(Nz)`, `DW = angle(Nx, Ny) + 90` in [0, 360). Run
`examples/vector_milling_calibration.py` to write a calibration program
(`data/calibration/`) that checks origin, axis directions and tool-tip reference in the
HOPS simulation.

For Grasshopper, use the Script component in [`examples/grasshopper/`](examples/grasshopper/README.md).

---

## Preset tools

Common machine tools are available as zero-argument classes:

```python
from easyhops.tool_library import CastorD61, SaegeD350, BirdsmouthW41

tool = CastorD61()       # 61 mm diameter router (WZF)
saw  = SaegeD350()       # 350 mm saw blade (WZS)
bird = BirdsmouthW41()   # 41 mm birdsmouth router (WZF)
```

Custom tools can also be loaded by name or number from a `.too` tool library file:

```python
from easyhops.tool_library import ToolLibrary

tool = ToolLibrary.get("Birdsmouth")
tool = ToolLibrary.get(tool_no=504)
```

---

## Sorting machinings

`HOPSJob.sort_machinings()` returns a sorted copy. The default order is milling → sawing → drilling. Pass a custom `key` to override:

```python
# Default
post_flip = HOPSJob.sort_machinings(post_flip)

# Custom: sawing first
order = {"SAWING": 0, "MILLING": 1, "DRILLING": 2}
post_flip = HOPSJob.sort_machinings(
    post_flip, key=lambda m: order.get(getattr(m, "OPERATION_TYPE", ""), 3)
)
```

---

## Running tests

```bash
pytest tests/ --cov=src/easyhops
```

---

## Project structure

```
src/easyhops/
├── base_commands.py        # Abstract base classes for all HOPS commands
├── hop_core.py             # Core enums and file structure components
├── hop_job.py              # HOPSJob parser and container
├── machining_commands.py   # Milling, sawing, drilling operations and moves
├── tool_library.py         # Tool definitions and preset tool instances
├── work_planes.py          # WorkPlane and FreePlane definitions
├── utility_commands.py     # FeedrateOverride, MachineStop
├── contour_commands.py     # Contour buffer commands (KB, KG01)
├── hop_macros.py           # HOPS CALL macro wrappers
└── strategies/             # compas_timber → HOPSMachining converters
    ├── birdsmouth.py
    ├── double_cut.py
    ├── jack_rafter_cut.py
    └── lap.py
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for full design documentation.
