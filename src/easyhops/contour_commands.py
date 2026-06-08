"""Contour buffer commands for HOPS.

These commands write geometry into a named HOPS contour buffer rather than
moving the spindle directly.  They always appear as a group::

    KB  ('K0', '', -_WZR, -_WZR, 0, '', 7, 0)   ← ContourStart
    KG01 ('',   0, 0, 0, '', 10, 2)               ← ContourLine
    KG01 ('L1', 0, 0, 0, '',  7, 2)               ← ContourLine
    ...
    KG01ZuKB()                                     ← CloseContour

Classes:
--------
ContourStart
    Opens a new contour buffer (KB command).
ContourLine
    Adds a straight-line segment to the active buffer (KG01 command).
CloseContour
    Closes the active buffer and appends it as a contour (KG01ZuKB command).
"""

from typing import Union

from .base_commands import ContourCommand
from .hop_core import EasySnapXY
from .hop_core import EasySnapZ


def _fmt(val) -> str:
    """Format a single HOPS parameter value."""
    if isinstance(val, str):
        return val
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float)):
        i = int(val)
        return str(i) if val == i else f"{val:.3f}"
    return str(val)


class ContourStart(ContourCommand):
    """Opens a new HOPS contour buffer.

    Serialises to::

        KB("{name}", "", {x}, {y}, {z}, "", {easy_snap_xy}, 0)

    Parameters
    ----------
    name : str
        Contour buffer identifier, e.g. ``'K0'``.
    x : Union[float, str]
        X offset of the contour origin (accepts HOPS expressions like ``'-_WZR'``).
    y : Union[float, str]
        Y offset of the contour origin.
    z : Union[float, str]
        Z offset of the contour origin.
    easy_snap_xy : int
        Corner snap mode for the XY origin (``EasySnapXY`` value).
    """

    def __init__(
        self,
        name: str = "K0",
        x: Union[float, str] = 0,
        y: Union[float, str] = 0,
        z: Union[float, str] = 0,
        easy_snap_xy: int = EasySnapXY.REAR_LEFT,
    ):
        super().__init__()
        self.name = name
        self.x = x
        self.y = y
        self.z = z
        self.easy_snap_xy = easy_snap_xy

    def __repr__(self) -> str:
        return f"ContourStart({self.name!r}, x={self.x}, y={self.y}, z={self.z})"

    def _to_hop_line(self) -> str:
        return f"KB ('{self.name}','',{_fmt(self.x)},{_fmt(self.y)},{_fmt(self.z)},'',{_fmt(self.easy_snap_xy)},0)"


class ContourLine(ContourCommand):
    """Adds a straight-line segment to the active contour buffer.

    Serialises to::

        KG01("{name}", {x}, {y}, {z}, "", {easy_snap_xy}, {easy_snap_z})

    Parameters
    ----------
    name : str
        Optional segment label, e.g. ``'L1'``.  Use ``''`` for unlabelled segments.
    x : Union[float, str]
        Target X coordinate (accepts HOPS expressions like ``'111.32-_WZR'``).
    y : Union[float, str]
        Target Y coordinate.
    z : Union[float, str]
        Target Z coordinate.
    easy_snap_xy : int
        Corner snap mode for XY (``EasySnapXY`` value).
    easy_snap_z : int
        Snap mode for Z (``EasySnapZ`` value).
    """

    def __init__(
        self,
        name: str = "",
        x: Union[float, str] = 0,
        y: Union[float, str] = 0,
        z: Union[float, str] = 0,
        easy_snap_xy: int = EasySnapXY.REAR_LEFT,
        easy_snap_z: int = EasySnapZ.RELATIVE,
    ):
        super().__init__()
        self.name = name
        self.x = x
        self.y = y
        self.z = z
        self.easy_snap_xy = easy_snap_xy
        self.easy_snap_z = easy_snap_z

    def __repr__(self) -> str:
        return f"ContourLine({self.name!r}, x={self.x}, y={self.y}, z={self.z}, esxy={self.easy_snap_xy}, esz={self.easy_snap_z})"

    def _to_hop_line(self) -> str:
        return f"KG01 ('{self.name}',{_fmt(self.x)},{_fmt(self.y)},{_fmt(self.z)},'',{_fmt(self.easy_snap_xy)},{_fmt(self.easy_snap_z)})"


class ContourLineAngle(ContourCommand):
    """Wraps the HOPS ``CALL _KWGerade_V5`` macro (angled straight milling move).

    Executes a direct spindle move of a given length at a given angle within the
    current work plane.

    Serialises to a single HOPS line::

        CALL _KWGerade_V5 ( VAL NAME:='',LAENGE:=-150.133,WINKEL:=61.661,Z:=0,INFO:='',ESD:=2)

    Parameters
    ----------
    name : str
        ``NAME`` — optional label for the move segment (default ``''``).
    length : Union[float, str]
        ``LAENGE`` — move length.  Accepts HOPS expressions such as
        ``'_RZ/COS(180-132.98)'``.
    angle : Union[float, str]
        ``WINKEL`` — direction angle in degrees.  Accepts HOPS expressions
        such as ``'180-132.98'``.
    z : Union[float, str]
        ``Z`` — milling depth (default 0 = use current plane depth).
    info : str
        ``INFO`` — optional comment string (default ``''``).
    easy_snap_z : EasySnapZ
        ``ESD`` — EasySnap z-mode (default EasySnapZ.RELATIVE).
    """

    _MACRO_NAME = "_KWGerade_V5"

    def __init__(
        self,
        name: str = "",
        length: Union[float, str] = 0,
        angle: Union[float, str] = 0,
        z: Union[float, str] = 0,
        info: str = "",
        easy_snap_z: EasySnapZ = EasySnapZ.RELATIVE,
    ):
        super().__init__()
        self.name = name
        self.length = length
        self.angle = angle
        self.z = z
        self.info = info
        self.easy_snap_z = easy_snap_z

    def __repr__(self) -> str:
        return f"AngledLine(length={self.length!r}, angle={self.angle!r})"

    @staticmethod
    def _fmt(val) -> str:
        if isinstance(val, str):
            return val
        if isinstance(val, bool):
            return "1" if val else "0"
        if isinstance(val, (int, float)):
            i = int(val)
            return str(i) if val == i else f"{val:.3f}"
        return str(val)

    def _to_hop_line(self) -> str:
        f = self._fmt
        parts = [
            f"NAME:='{self.name}'",
            f"LAENGE:={f(self.length)}",
            f"WINKEL:={f(self.angle)}",
            f"Z:={f(self.z)}",
            f"INFO:='{self.info}'",
            f"ESD:={f(self.easy_snap_z)}",
        ]
        return f"CALL {self._MACRO_NAME} ( VAL {','.join(parts)})"

    @classmethod
    def from_hop_line(cls, line: str) -> "ContourLineAngle":
        raise NotImplementedError("Parsing AngledLine from a HOPS line is not yet implemented.")


class CloseContour(ContourCommand):
    """Closes the active contour buffer.

    Serialises to::

        KG01ZuKB()
    """

    def __init__(self):
        super().__init__()

    def __repr__(self) -> str:
        return "CloseContour()"

    def _to_hop_line(self) -> str:
        return "KG01ZuKB()"
