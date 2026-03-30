import math
import re
from enum import StrEnum
from typing import Optional

from compas.geometry import Frame
from compas.geometry import Vector
from compas.geometry import angle_vectors
from compas.geometry import angle_vectors_signed
from compas.tolerance import TOL

from .base_commands import WorkPlaneCommand
from .hop_core import EasySnapXY
from .hop_core import EasySnapZ


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

    @classmethod
    def from_hop_line(cls, line: str) -> "WorkPlane":
        """Parse EBENE command from HOPS line.

        Parameters:
        ----------
        line : str
            HOPS EBENE(...) command line

        Returns:
        --------
        :class:`WorkPlane`
            Parsed WorkPlane enum member

        Example:
        --------
            >>> WorkPlane.from_hop_line("EBENE0()")
            <WorkPlane.TOP: 'EBENE0()'>
            >>> WorkPlane.from_hop_line("EBENE(1)")
            <WorkPlane.FRONT: 'EBENE1()'>
        """
        # Try to match EBENE0() format first
        if line.strip() in cls._value2member_map_:
            return cls(line.strip())

        # Try to match EBENE(n) format
        match = re.match(r"EBENE\((\d+)\)", line.strip())
        if match:
            plane_num = int(match.group(1))
            plane_map = {
                0: cls.TOP,
                1: cls.FRONT,
                2: cls.START,
                3: cls.BACK,
                4: cls.END,
            }
            if plane_num in plane_map:
                return plane_map[plane_num]

        raise ValueError(f"Invalid EBENE line: {line}")


class FreePlane(WorkPlaneCommand):
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
    easy_snap_xy : Optional[EasySnapXY]
        Corner snap mode for XY movement. See EasySnapXY enum for options. If None, defaults to EasySnapXY.DISABLED
    easy_snap_z : Optional[EasySnapZ]
        Corner snap mode for Z movement. See EasySnapZ enum for options. If None, defaults to EasySnapZ.RELATIVE
    offset_z : Optional[float]
        Z-axis offset for depth calculations. If None, defaults to 0.0

    Example:
    --------
        >>> plane = FreePlane(x=100, y=50, z=0, rotation_angle=45, tilt_angle=0)
        >>> str(plane)
        'EBENEF(100,50,0,45,0)'
        >>> plane.easy_snap_xy = 10
        >>> str(plane)
        'EBENEF(100,50,0,45,0,10)'
        'EBENEF(x=2058.631,y=-19.864,z=384.569,tilt=64.735,angle=180, snapXY=0,snapZ=0,offset_z=666)'
    """

    def __init__(
        self,
        x: float,
        y: float,
        z: float,
        rotation_angle: float,
        tilt_angle: float,
        easy_snap_xy: Optional[EasySnapXY] = EasySnapXY.DISABLED,
        easy_snap_z: Optional[EasySnapZ] = EasySnapZ.RELATIVE,
        offset_z: Optional[float] = 0.0,
    ):
        super().__init__()
        self._x = None
        self._y = None
        self._z = None
        self._rotation_angle = None
        self._tilt_angle = None
        self._easy_snap_xy = None
        self._easy_snap_z = None
        self._offset_z = None

        self.x = x
        self.y = y
        self.z = z
        self.rotation_angle = rotation_angle
        self.tilt_angle = tilt_angle
        self.easy_snap_xy = easy_snap_xy
        self.easy_snap_z = easy_snap_z
        self.offset_z = offset_z

    @property
    def x(self) -> float:
        """X-coordinate of the free view zero point."""
        return self._x

    @x.setter
    def x(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"x must be a number, got {type(value).__name__}")
        self._x = float(value)

    @property
    def y(self) -> float:
        """Y-coordinate of the free view zero point."""
        return self._y

    @y.setter
    def y(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"y must be a number, got {type(value).__name__}")
        self._y = float(value)

    @property
    def z(self) -> float:
        """Z-coordinate of the free view zero point."""
        return self._z

    @z.setter
    def z(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"z must be a number, got {type(value).__name__}")
        self._z = float(value)

    @property
    def rotation_angle(self) -> float:
        """Rotation angle β1 in degrees (rotation around Z-axis)."""
        return self._rotation_angle

    @rotation_angle.setter
    def rotation_angle(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"rotation_angle must be a number, got {type(value).__name__}")
        if not (-180 <= value <= 180):
            raise ValueError(f"rotation_angle must be between -180 and 180 degrees, got {value}")
        self._rotation_angle = float(value)

    @property
    def tilt_angle(self) -> float:
        """Tilt angle β2 in degrees (rotation around X-axis)."""
        return self._tilt_angle

    @tilt_angle.setter
    def tilt_angle(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"tilt_angle must be a number, got {type(value).__name__}")
        if not (0 <= value <= 180):
            raise ValueError(f"tilt_angle must be between 0 and 180 degrees, got {value}")
        self._tilt_angle = float(value)

    @property
    def easy_snap_xy(self) -> int:
        """Corner snap mode for XY movement (0-9)."""
        return self._easy_snap_xy

    @easy_snap_xy.setter
    def easy_snap_xy(self, value):
        if isinstance(value, EasySnapXY):
            value = value.value
        elif not isinstance(value, int):
            raise TypeError(f"easy_snap_xy must be EasySnapXY enum or int, got {type(value).__name__}")

        if not 0 <= value <= 9:
            raise ValueError(f"easy_snap_xy must be between 0 and 9, got {value}")
        self._easy_snap_xy = value

    @property
    def easy_snap_z(self) -> int:
        """Corner snap mode for Z movement (0-2)."""
        return self._easy_snap_z

    @easy_snap_z.setter
    def easy_snap_z(self, value):
        if isinstance(value, EasySnapZ):
            value = value.value
        elif not isinstance(value, int):
            raise TypeError(f"easy_snap_z must be EasySnapZ enum or int, got {type(value).__name__}")
        if not 0 <= value <= 2:
            raise ValueError(f"easy_snap_z must be between 0 and 2, got {value}")
        self._easy_snap_z = value

    @property
    def offset_z(self) -> float:
        """Z-axis offset for depth calculations."""
        return self._offset_z

    @offset_z.setter
    def offset_z(self, value):
        if not isinstance(value, (int, float)):
            raise TypeError(f"offset_z must be a number, got {type(value).__name__}")
        self._offset_z = float(value)

    @staticmethod
    def _format_number(value: float) -> str:
        """Format number intelligently - integers without decimals, floats with 3 decimals.

        Parameters
        ----------
        value : float
            The number to format.

        Returns
        -------
        str
            Formatted number string.
        """
        if isinstance(value, int) or value == int(value):
            return str(int(value))
        return f"{value:.3f}"

    def _to_hop_line(self) -> str:
        """Return EBENEF command string.

        Returns:
            Formatted EBENEF command with minimal required parameters
        """
        params = [
            self._format_number(self.x),
            self._format_number(self.y),
            self._format_number(self.z),
            self._format_number(self.rotation_angle),
            self._format_number(self.tilt_angle),
            str(self.easy_snap_xy),
            str(self.easy_snap_z),
            self._format_number(self.offset_z),
        ]
        return f"EBENEF({','.join(params)})"

    def __repr__(self) -> str:
        """Return detailed string representation for debugging."""
        return f"FreePlane(x={self.x}, y={self.y}, z={self.z}, tilt={self.tilt_angle}°, rotation={self.rotation_angle}°, easy_snap_xy={self.easy_snap_xy}, easy_snap_z={self.easy_snap_z}, offset_z={self.offset_z})"  # noqa: E501

    @staticmethod
    def _wrap_to_pi(angle: float) -> float:
        """Normalize angle (in radians) to [0, π] range.

        This helper ensures tilt angles fall within HOPS-required [0, 180°] range.
        Algorithm ported from btlx_processes.py wrap_to_pi() function.

        Parameters
        ----------
        angle : float
            Angle in radians.

        Returns
        -------
        float
            Normalized angle in [0, π] radians.
        """
        # First normalize to [-π, π]
        angle = (angle + math.pi) % (2 * math.pi) - math.pi
        # Then map to [0, 2π]
        if angle < 0:
            angle += 2 * math.pi
        # Finally ensure [0, π]
        if angle > math.pi:
            angle = 2 * math.pi - angle
        return angle

    @classmethod
    def from_frame(cls, frame: Frame, easy_snap_xy=EasySnapXY.DISABLED, easy_snap_z=EasySnapZ.RELATIVE, offset_z=0.0) -> "FreePlane":
        """Create FreePlane from a COMPAS Frame.

        Derives EBENEF rotation and tilt angles from the frame's orientation.

        The algorithm:
        1. Selects hemisphere via angle_vectors(-zaxis, Z) > 99° test
        2. Computes beta: rotation around Z-axis to align normal into XZ plane
        3. Computes theta: signed angle from Z to normal around rotated X-axis
        4. Wraps theta to [0, π] to guarantee tilt ∈ [0, 180°]
        5. Maps beta → rotation_angle, theta → tilt_angle

        Parameters:
        ----------
        frame : :class:`~compas.geometry.Frame`
            Frame defining origin and orientation of the work plane.
        easy_snap_xy : :class:`EasySnapXY`, optional
            XY snap mode. Defaults to ``EasySnapXY.DISABLED``.
        easy_snap_z : :class:`EasySnapZ`, optional
            Z snap mode. Defaults to ``EasySnapZ.RELATIVE``.
        offset_z : float, optional
            Z-axis offset. Defaults to 0.0.

        Returns:
        --------
        :class:`FreePlane`
            The constructed FreePlane object with correct HOPS angles.
        """
        if not isinstance(frame, Frame):
            raise TypeError(f"Input must be a compas.geometry.Frame instance, got {type(frame).__name__}")

        print(frame)
        # Step 1: Hemisphere selection
        # If angle between -zaxis and world Z > 90°, use +zaxis
        # Otherwise use -zaxis
        angle_rad = angle_vectors(-frame.zaxis, Vector(0, 0, 1))
        condition = TOL.is_positive(angle_rad - (math.pi / 2))
        if condition:
            target_normal = frame.zaxis
        else:
            target_normal = -frame.zaxis

        # Step 2: Beta - rotation around Z-axis (azimuth)
        # Align target_normal into XZ plane via atan2
        beta = math.atan2(target_normal.y, target_normal.x) + math.pi / 2
        # Normalize beta to [-π, π] range
        beta = (beta + math.pi) % (2 * math.pi) - math.pi

        # Step 3: Create temporary frame and rotate by beta
        work_frame = Frame(frame.point, [1, 0, 0], [0, 1, 0])
        work_frame.rotate(beta, work_frame.zaxis, work_frame.point)

        # Step 4: Theta - tilt from Z-axis (inclination)
        # Signed angle from world Z to target_normal around rotated X-axis
        theta = angle_vectors_signed([0, 0, 1], target_normal, work_frame.xaxis)

        # Step 5: Wrap theta to [0, π] based on hemisphere
        if condition:
            theta = cls._wrap_to_pi(theta)
        else:
            theta = cls._wrap_to_pi(-theta)

        work_frame.rotate(theta, work_frame.xaxis, work_frame.point)
        print(work_frame)

        # Convert radians to degrees and assign to HOPS parameters
        # Geometric mapping: beta (Z-rotation) → rotation_angle, theta (X-rotation) → tilt_angle
        rotation_angle = math.degrees(beta)
        tilt_angle = math.degrees(theta)

        return cls(
            x=frame.point.x,
            y=frame.point.y,
            z=frame.point.z,
            rotation_angle=rotation_angle,
            tilt_angle=tilt_angle,
            easy_snap_xy=easy_snap_xy,
            easy_snap_z=easy_snap_z,
            offset_z=offset_z,
        )

    @classmethod
    def from_hop_line(cls, line: str) -> "FreePlane":
        """Parse EBENEF command from HOPS line.

        Parameters:
        ----------
        line : str
            HOPS EBENEF(...) command line

        Returns:
        --------
        :class:`FreePlane`
            Parsed FreePlane instance

        Example:
        --------
            >>> FreePlane.from_hop_line("EBENEF(1351.763,268.987,182.642,13.003,0,0,0,0)")
            FreePlane(x=1351.763, y=268.987, z=182.642, rotation=13.003, tilt=0.0, ...)
        """
        # Match EBENEF with 5, 7, or 8 parameters
        # 5 params: x, y, z, rotation, tilt
        # 7 params: x, y, z, rotation, tilt, snap_xy, snap_z
        # 8 params: x, y, z, rotation, tilt, snap_xy, snap_z, offset_z
        pattern = r"EBENEF\(\s*([-+]?\d+\.?\d*)\s*,\s*([-+]?\d+\.?\d*)\s*,\s*([-+]?\d+\.?\d*)\s*,\s*([-+]?\d+\.?\d*)\s*,\s*([-+]?\d+\.?\d*)(?:\s*,\s*([-+]?\d+)(?:\s*,\s*([-+]?\d+)(?:\s*,\s*([-+]?\d+\.?\d*))?)?)?\s*\)"
        match = re.match(pattern, line.strip())

        if match:
            x = float(match.group(1))
            y = float(match.group(2))
            z = float(match.group(3))
            rotation = float(match.group(4))
            tilt = float(match.group(5))
            snap_xy = EasySnapXY(int(match.group(6))) if match.group(6) else EasySnapXY.DISABLED
            snap_z = EasySnapZ(int(match.group(7))) if match.group(7) else EasySnapZ.RELATIVE
            offset = float(match.group(8)) if match.group(8) else 0.0

            return cls(x, y, z, rotation, tilt, snap_xy, snap_z, offset)

        raise ValueError(f"Invalid EBENEF line: {line}")
