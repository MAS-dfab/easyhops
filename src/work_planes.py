from typing import Optional
from enum import StrEnum

from compas.geometry import Frame
from compas.geometry import Vector
from compas.geometry import angle_vectors_projected


class WorkPlane(StrEnum):
    """Standard HOPS work plane type definitions.

    Parameters:
    ----------
    TOP : literal("EBENE0()")
        Standard top view (absolute coordinates)
    FRONT : literal("EBENE1()")
        Front view
    START : literal("EBENE2()")
        Start view
    BACK : literal("EBENE3()")
        Side view
    END : literal("EBENE4()")
        End view
    UNKNOWN : literal("UNKNOWN")
        Unknown or unrecognized work plane
    """

    TOP = "EBENE0()"
    FRONT = "EBENE1()"
    START = "EBENE2()"
    BACK = "EBENE3()"
    END = "EBENE4()"
    UNKNOWN = "UNKNOWN"


class FreePlane:
    """EBENEF (Free View) parametric work plane definition.

    Defines a free view coordinate system where all subsequent machining operations
    and coordinate values are related to this new coordinate system.

    The transformation sequence is:
        1. Tilt the view (rotation around X-axis)
        2. Rotate the view (rotation around Z-axis)
        3. Shift the view to the specified origin point
        4. Apply Z-offset in the direction of the defined view

    Parameters:
    ----------
    x : float
        X-coordinate of the free view zero point (origin)
    y : float
        Y-coordinate of the free view zero point (origin)
    z : float
        Z-coordinate of the free view zero point (origin)
    rotation_angle : float
        Rotation angle β1 in degrees (rotation around Z-axis)
        Applied after tilting the view
    tilt_angle : float
        Tilt angle β2 in degrees (rotation around X-axis)
        Applied first in transformation sequence
    z_offset : Optional[float]
        Z-offset in the direction of the defined view
        Shifts working plane perpendicular to tilted/rotated surface
    additional_param : Optional[float]
        Optional 7th parameter for extended functionality

    Example:
    --------
        >>> plane = FreePlane(x=100, y=50, z=0, rotation_angle=45, tilt_angle=0)
        >>> str(plane)
        'EBENEF(100,50,0,45,0)'
        >>> plane.z_offset = 10
        >>> str(plane)
        'EBENEF(100,50,0,45,0,10)'
    """

    def __init__(
        self,
        x: float,
        y: float,
        z: float,
        rotation_angle: float,
        tilt_angle: float,
        z_offset: Optional[float] = 0.0,
        additional_param: Optional[float] = 0.0,
    ):
        self.x = x
        self.y = y
        self.z = z
        self.rotation_angle = rotation_angle
        self.tilt_angle = tilt_angle
        self.z_offset = z_offset
        self.additional_param = additional_param

    def __str__(self) -> str:
        """Return EBENEF command string.

        Returns:
            Formatted EBENEF command with minimal required parameters
        """
        params = [
            self.x,
            self.y,
            self.z,
            self.rotation_angle,
            self.tilt_angle,
            self.z_offset,
            self.additional_param,
        ]
        return f"EBENEF({','.join(map(str, params))})"

    def __repr__(self) -> str:
        """Return detailed string representation for debugging."""
        return (
            f"FreePlane(x={self.x}, y={self.y}, z={self.z}, "
            f"rotation={self.rotation_angle}°, tilt={self.tilt_angle}°, "
            f"z_offset={self.z_offset}, additional_param={self.additional_param})"
        )

    @classmethod
    def from_frame(cls, frame: Frame) -> "FreePlane":
        """Create FreePlane from a frame dictionary.

        Parameters:
        ----------
        frame : :class:`~compas.geometry.Frame`
            Frame defining origin and orientation.

        Returns:
        --------
        :class:`FreePlane`
            The constructed FreePlane object.
        """
        rotation_angle = angle_vectors_projected(
            Vector.Xaxis(), frame.xaxis, Vector.Zaxis(), deg=True
        )
        tilt_angle = angle_vectors_projected(
            frame.yaxis, Vector.Yaxis(), frame.xaxis, deg=True
        )
        return cls(
            x=frame.point.x,
            y=frame.point.y,
            z=frame.point.z,
            rotation_angle=rotation_angle,
            tilt_angle=tilt_angle,
        )
