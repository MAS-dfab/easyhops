# Grasshopper: tool frames → HOPS vector milling

`frames_to_hop.py` is the script for a Rhino 8 **Script** component (Python 3). It turns
tool frames into a HOPS program with `VSP` / `VG01` / `VEP`, where every point carries its
own tool orientation (continuous 5-axis), and previews what the written file contains.

## Setup

1. Clone easyhops to `Documents\GitHub\easyhops` and check out the branch with vector
   milling (`feature/vector-milling` until it is merged into `main`). If your clone is
   elsewhere, change `EASYHOPS_SRC` at the top of the script.
2. In Grasshopper, place a **Script** component (Maths › Script), open it and paste
   `frames_to_hop.py`. The first lines select Python 3, a Rhino environment called
   `easyhops`, and compas 2.15.1. Rhino installs compas into that environment on the
   first run (internet needed once).
3. Add the parameters below with the ⊕ buttons (zoom in on the component), rename them
   exactly, and set access and type hint with a right-click.

The script imports easyhops straight from your clone and re-imports it on every run:
after a `git pull` or a fix, press F5 in Grasshopper; no Rhino restart, no reinstall.

## Inputs

| Name | Access, type hint | Content |
|---|---|---|
| `Frames` | Tree Access, Plane | One branch per pass, in machining order: approach point in the air, cutting frames, exit point in the air. Origin = tool tip, Z = tool axis from tip to holder. X/Y are ignored. |
| `Feeds` | Tree Access, float | Optional, mm/min. Per branch one value (whole pass) or one value per frame. A single value applies to all passes. Empty = tool-manager feed. |
| `PartPlane` | Item, Plane | Origin at the X=0/Y=0/Z=0 corner of the finished part (bottom face), X along DX, Y along DY, Z up on the machine table. Empty = World XY. |
| `DX`, `DY`, `DZ` | Item, float | Finished part size in mm. |
| `ToolNo` | Item, int | Tool position in the magazine, e.g. 404. |
| `RPM` | Item, float | Optional spindle speed. Empty = tool-manager value. |
| `ZToHolder` | Item, bool | Optional, default True. Set False if your plane Z points into the material. |
| `MaxTilt` | Item, float | Optional, default 90 (horizontal tool). A plane that tilts more is turned about its origin (tool tip), towards `PartPlane` Z, to exactly `MaxTilt`; its rotation angle stays the same. A warning names the branch and frame (first 10 on the component, all in `Report`). |
| `Name` | Item, str | Program and file name. Default `toolpath`. |
| `Folder` | Item, str | Output folder. |
| `Write` | Item, bool | Connect a Button: writes `<Folder>\<Name>.hop`. |

## Outputs

| Name | Content |
|---|---|
| `Hop` | The program text. |
| `Report` | Read-back of the written program against your frames: position and tool-axis error, tilt range, largest rotation step, warnings. |
| `Stock` | Box of the finished part at `PartPlane`. It must sit exactly where your part is. |
| `ToolAxes` | Tool-axis lines per pass, computed back from the written program (not from your input). |
| `TipPaths` | Tool-tip polylines per pass, computed back from the written program. |
| `FilePath` | Path of the written file. |

## Checks before going to the machine

- `Stock` overlaps your part model, with its origin at the part's zero corner.
- `ToolAxes` lie on top of your frames' Z axes and point away from the material.
- `Report` shows position errors below 0.001 mm and no unexpected warnings. A warning
  about DW crossing 0/360 means the head may turn the long way round: check that
  spot in the HOPS simulation.
- Simulate the written file in HOPS on the machine PC before cutting.
