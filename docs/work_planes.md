# Work Planes System

## Overview

The work planes system provides abstractions for HOPS work plane definitions (`EBENE0-4` and `EBENEF`). Work planes define coordinate systems for CNC machining operations, allowing operations to be specified relative to different faces and orientations of the workpiece.

## Architecture

- **`work_planes.py`**: Core implementation with `WorkPlane` enum and `FreePlane` class
- **Standard planes**: Five predefined views (TOP, FRONT, START, BACK, END)
- **Free plane**: Parametric work plane with custom origin, rotation, and tilt

## Usage Patterns

### 1. Standard Work Planes

```python
from src.work_planes import WorkPlane

# Use predefined work planes
top_plane = WorkPlane.TOP      # EBENE0()
front_plane = WorkPlane.FRONT  # EBENE1()
start_plane = WorkPlane.START  # EBENE2()
back_plane = WorkPlane.BACK    # EBENE3()
end_plane = WorkPlane.END      # EBENE4()

# Get HOPS command string
print(top_plane)   # "EBENE0()"
print(front_plane) # "EBENE1()"
```

### 2. Free Plane (Parametric)

```python
from src.work_planes import FreePlane

# Create a free plane with origin, rotation, and tilt
plane = FreePlane(
    x=100,
    y=50,
    z=0,
    rotation_angle=45,  # β1: rotation around Z-axis
    tilt_angle=0        # β2: tilt around X-axis
)
print(str(plane))  # EBENEF(100,50,0,45,0,0.0,0.0)

# Add Z-offset (perpendicular to tilted surface)
plane.z_offset = 10
print(str(plane))  # EBENEF(100,50,0,45,0,10,0.0)
```

### 3. Create from COMPAS Frame

```python
from compas.geometry import Frame, Point
from src.work_planes import FreePlane

# Define frame with origin and orientation
frame = Frame(
    point=Point(100, 50, 0),
    xaxis=[1, 0, 0],
    yaxis=[0, 1, 0]
)

# Create FreePlane from frame
plane = FreePlane.from_frame(frame)
print(str(plane))  # EBENEF(100,50,0,<rotation>,<tilt>,0.0,0.0)
```

## WorkPlane Enum

Standard HOPS work plane definitions as enum values:

| Enum Value | HOPS Command | Description |
|------------|--------------|-------------|
| `WorkPlane.TOP` | `EBENE0()` | Standard top view (absolute coordinates) |
| `WorkPlane.FRONT` | `EBENE1()` | Front view |
| `WorkPlane.START` | `EBENE2()` | Start view |
| `WorkPlane.BACK` | `EBENE3()` | Side view |
| `WorkPlane.END` | `EBENE4()` | End view |
| `WorkPlane.UNKNOWN` | `UNKNOWN` | Unknown or unrecognized work plane |

### Usage

```python
# Access by name
plane = WorkPlane.TOP

# String conversion
command = str(plane)  # "EBENE0()"

# Comparison
if plane == WorkPlane.TOP:
    print("Using top view")
```

## FreePlane Class

Parametric work plane definition with custom coordinate system.

### Parameters

- **x, y, z** (float): Origin point coordinates of the free view zero point
- **rotation_angle** (float): β1 rotation angle in degrees (rotation around Z-axis)
- **tilt_angle** (float): β2 tilt angle in degrees (rotation around X-axis)
- **z_offset** (float, optional): Z-offset perpendicular to tilted/rotated surface (default: 0.0)
- **additional_param** (float, optional): Extended functionality parameter (default: 0.0)

### Transformation Sequence

The HOPS machine applies transformations in this order:

1. **Tilt the view** - Rotate around X-axis by `tilt_angle` (β2)
2. **Rotate the view** - Rotate around Z-axis by `rotation_angle` (β1)
3. **Shift the view** - Move origin to (x, y, z)
4. **Apply Z-offset** - Offset perpendicular to the defined view

All subsequent machining coordinates are relative to this transformed coordinate system.

### Methods

#### `__str__()` → str
Returns HOPS command string in format: `EBENEF(x,y,z,rotation,tilt,z_offset,additional_param)`

#### `__repr__()` → str
Returns detailed representation for debugging:
```python
FreePlane(x=100, y=50, z=0, rotation=45°, tilt=0°, z_offset=0.0, additional_param=0.0)
```

#### `from_frame(frame: Frame)` → FreePlane (classmethod)
Creates FreePlane from a COMPAS Frame object. Automatically calculates rotation and tilt angles from frame orientation.

**Parameters:**
- `frame` (compas.geometry.Frame): Frame defining origin and orientation

**Returns:**
- FreePlane instance with calculated angles

### Examples

#### Basic Free Plane
```python
# Simple horizontal plane at specific origin
plane = FreePlane(
    x=100, y=50, z=10,
    rotation_angle=0,
    tilt_angle=0
)
print(str(plane))  # EBENEF(100,50,10,0,0,0.0,0.0)
```

#### Rotated Plane
```python
# Plane rotated 45° around Z-axis
plane = FreePlane(
    x=0, y=0, z=0,
    rotation_angle=45,
    tilt_angle=0
)
print(str(plane))  # EBENEF(0,0,0,45,0,0.0,0.0)
```

#### Tilted Plane with Offset
```python
# Plane tilted 30° around X-axis with 10mm Z-offset
plane = FreePlane(
    x=50, y=100, z=0,
    rotation_angle=0,
    tilt_angle=30,
    z_offset=10
)
print(str(plane))  # EBENEF(50,100,0,0,30,10,0.0)
```

#### From COMPAS Frame
```python
from compas.geometry import Frame, Point, Vector

# Define frame on angled surface
frame = Frame(
    point=Point(100, 50, 20),
    xaxis=Vector(1, 0, 0),
    yaxis=Vector(0, 0.866, 0.5)  # 30° tilt
)

plane = FreePlane.from_frame(frame)
print(plane)  # FreePlane(x=100, y=50, z=20, rotation=0°, tilt=30°, ...)
print(str(plane))  # EBENEF(100,50,20,0,30,0.0,0.0)
```

## Use Cases

### 1. Machining Multiple Faces
```python
# Top face operations
print(WorkPlane.TOP)  # EBENE0()
# ... machining commands ...

# Switch to front face
print(WorkPlane.FRONT)  # EBENE1()
# ... machining commands ...
```

### 2. Angled Surface Machining
```python
# Define work plane on 45° angled surface
plane = FreePlane(
    x=0, y=0, z=0,
    rotation_angle=0,
    tilt_angle=45,
    z_offset=5  # Work 5mm above surface
)
print(str(plane))
# All subsequent coordinates are relative to this tilted plane
```

### 3. Complex Joinery
```python
# Create work plane aligned with joint surface
joint_frame = Frame(point, xaxis, yaxis)
plane = FreePlane.from_frame(joint_frame)

# Machine joint features in local coordinates
print(str(plane))
# ... joint machining operations ...
```

## Implementation Notes

### Coordinate System
- **Origin**: All coordinates are relative to the work plane's origin point
- **Z-axis**: Points perpendicular to the work plane surface
- **Rotation**: Right-hand rule applies for angle directions
- **Units**: All coordinates in millimeters, angles in degrees

### Angle Calculations
When using `from_frame()`:
- **rotation_angle**: Calculated from projection of frame's X-axis onto XY-plane
- **tilt_angle**: Calculated from frame's Y-axis relative to world Y-axis
- Uses COMPAS geometry functions for vector angle calculations

### HOPS Integration
- Work plane commands must precede machining operations
- Active work plane affects all subsequent coordinate interpretations
- Switch between work planes to machine different faces
- Standard planes (EBENE0-4) are faster than free planes (EBENEF)

### Best Practices
1. **Use standard planes when possible** - Simpler and faster execution
2. **Set work plane before tool selection** - Ensures correct coordinate system
3. **Document angle conventions** - Clarify rotation/tilt direction in comments
4. **Validate frame orientation** - Verify Z-axis points outward from surface
5. **Minimize plane switches** - Group operations by work plane for efficiency
