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
ContourRectangle
    Adds a complete rectangle as a contour (CALL Kontur_Rechteck macro).
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


class ContourRectangle(ContourCommand):
    """Wraps the HOPS ``CALL Kontur_Rechteck`` macro (rectangle contour).

    Adds a complete rectangle as a self-contained contour, without needing a
    matching :class:`ContourStart`/:class:`CloseContour` pair.

    Serialises to a single HOPS line::

        CALL Kontur_Rechteck ( VAL KONTURNAME:='RE1',MX:=146/2,MY:=65/2,Z:=0,\\
            LAENGE:=146,BREITE:=65,RADIUS:=0,DW:=0,ABST:=0,CW_CCW:=0,\\
            LAYER:='',INFO:='',ESXY:=0,ESZ:=0)

    Parameters
    ----------
    name : str
        ``KONTURNAME`` — contour buffer identifier, e.g. ``'RE1'``.
    mx : Union[float, str]
        ``MX`` — X coordinate of the rectangle centre.  Accepts HOPS
        expressions such as ``'146/2'``.
    my : Union[float, str]
        ``MY`` — Y coordinate of the rectangle centre.
    z : Union[float, str]
        ``Z`` — Z offset of the contour.
    length : Union[float, str]
        ``LAENGE`` — rectangle length (L1).
    width : Union[float, str]
        ``BREITE`` — rectangle width (L2).
    radius : Union[float, str]
        ``RADIUS`` — corner radius (r).
    angle : Union[float, str]
        ``DW`` — rotation angle (ß1) in degrees.
    distance_to_contour : Union[float, str]
        ``ABST`` — distance to contour (A).
    clockwise : bool
        ``CW_CCW`` — direction of the contour: ``True`` = clockwise (``0``,
        default), ``False`` = counterclockwise (``1``).
    layer : str
        ``LAYER`` — optional layer name.
    info : str
        ``INFO`` — optional comment string.
    easy_snap_xy : int
        ``ESXY`` — EasySnap mode for the XY centre (``EasySnapXY`` value).
    easy_snap_z : int
        ``ESZ`` — EasySnap mode for the Z offset (``EasySnapZ`` value).
    """

    _MACRO_NAME = "Kontur_Rechteck"

    def __init__(
        self,
        name: str = "RE1",
        mx: Union[float, str] = 0,
        my: Union[float, str] = 0,
        z: Union[float, str] = 0,
        length: Union[float, str] = 0,
        width: Union[float, str] = 0,
        radius: Union[float, str] = 0,
        angle: Union[float, str] = 0,
        distance_to_contour: Union[float, str] = 0,
        clockwise: bool = True,
        layer: str = "",
        info: str = "",
        easy_snap_xy: int = EasySnapXY.DISABLED,
        easy_snap_z: int = EasySnapZ.TOP_EDGE,
    ):
        super().__init__()
        self.name = name
        self.mx = mx
        self.my = my
        self.z = z
        self.length = length
        self.width = width
        self.radius = radius
        self.angle = angle
        self.distance_to_contour = distance_to_contour
        self.clockwise = clockwise
        self.layer = layer
        self.info = info
        self.easy_snap_xy = easy_snap_xy
        self.easy_snap_z = easy_snap_z

    def __repr__(self) -> str:
        return f"ContourRectangle({self.name!r}, length={self.length}, width={self.width})"

    def _to_hop_line(self) -> str:
        parts = [
            f"KONTURNAME:='{self.name}'",
            f"MX:={_fmt(self.mx)}",
            f"MY:={_fmt(self.my)}",
            f"Z:={_fmt(self.z)}",
            f"LAENGE:={_fmt(self.length)}",
            f"BREITE:={_fmt(self.width)}",
            f"RADIUS:={_fmt(self.radius)}",
            f"DW:={_fmt(self.angle)}",
            f"ABST:={_fmt(self.distance_to_contour)}",
            f"CW_CCW:={0 if self.clockwise else 1}",
            f"LAYER:='{self.layer}'",
            f"INFO:='{self.info}'",
            f"ESXY:={_fmt(self.easy_snap_xy)}",
            f"ESZ:={_fmt(self.easy_snap_z)}",
        ]
        return f"CALL {self._MACRO_NAME} ( VAL {','.join(parts)})"

    @classmethod
    def from_hop_line(cls, line: str) -> "ContourRectangle":
        raise NotImplementedError("Parsing ContourRectangle from a HOPS line is not yet implemented.")


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
