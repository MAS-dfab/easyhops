"""HOPS CALL macro command classes.

Each class in this module wraps a single built-in HOPS macro invoked via a
``CALL <name> ( VAL ...)`` statement.  Classes inherit from
:class:`~easyhops.base_commands.HopsMacroCommand` and serialise to/from the
corresponding HOPS line.

Classes:
--------
FreeFormPocket
    Wraps ``CALL _ExecutePocket_ETH ( VAL ...)``
"""

from typing import Union

from .base_commands import HopsMacroCommand


class FreeFormPocket(HopsMacroCommand):
    """Wraps the HOPS ``CALL _ExecutePocket_V5`` macro (Free-form pocket).

    Serialises to a single HOPS line::

        CALL _ExecutePocket_V5 ( VAL NAMEN:='K0',AA:=-_WZR,UEBERLAPPUNG:=10,\\
            MODE:=2,ANGLE:=0,TIEFE:=0,ESMD:=0,ANZAHL:=0,MAXZ:=_AT_MAXDEPTH,\\
            RD:=1,FLIEGENDEINTAUCHEN:=0,MAXEINTAUCHLAENGE:=20)

    Parameters
    ----------
    contour_name : str
        ``NAMEN`` — name of the contour buffer to pocket (e.g. ``'K0'``).
    distance_to_contour : Union[float, str]
        ``AA`` — offset between tool centre and contour edge.
        Accepts HOPS expressions such as ``'-_WZR'``.
    overlap : int
        ``UEBERLAPPUNG`` — path overlap as a percentage of tool diameter.
    mode : int
        ``MODE`` — fill strategy:
        0 = Spiral, 1 = Contour parallel, 2 = Parallel *(default)*, 3 = Parallel lines.
    angle : Union[float, str]
        ``ANGLE`` — direction angle for the parallel modes.
    depth : Union[float, str]
        ``TIEFE`` — pocket depth (L3); 0 means use the plane depth.
    easy_snap_md : int
        ``ESMD`` — easy-snap mode for the depth direction.
    count : int
        ``ANZAHL`` — number of depth passes; 0 = automatic.
    max_z : Union[float, str]
        ``MAXZ`` — maximum depth per pass.
        Accepts HOPS expressions such as ``'_AT_MAXDEPTH'``.
    outside_in : int
        ``RD`` — milling direction: 1 = outside-to-inside, 0 = inside-to-outside.
    flying_plunge : int
        ``FLIEGENDEINTAUCHEN`` — interpolate in Z (helical plunge): 1 = yes, 0 = no.
    max_plunge_length : Union[float, str]
        ``MAXEINTAUCHLAENGE`` — maximum plunge segment length in mm.
    """

    _MACRO_NAME = "_ExecutePocket_ETH"

    def __init__(
        self,
        contour_name: str = "K0",
        distance_to_contour: Union[float, str] = "-_WZR",
        overlap: int = 10,
        mode: int = 2,
        angle: Union[float, str] = 0,
        depth: Union[float, str] = 0,
        easy_snap_md: int = 0,
        count: int = 0,
        max_z: Union[float, str] = "_AT_MAXDEPTH",
        outside_in: int = 1,
        flying_plunge: int = 0,
        max_plunge_length: Union[float, str] = 20,
    ):
        super().__init__()
        self.contour_name = contour_name
        self.distance_to_contour = distance_to_contour
        self.overlap = overlap
        self.mode = mode
        self.angle = angle
        self.depth = depth
        self.easy_snap_md = easy_snap_md
        self.count = count
        self.max_z = max_z
        self.outside_in = outside_in
        self.flying_plunge = flying_plunge
        self.max_plunge_length = max_plunge_length

    def __repr__(self) -> str:
        return f"FreeFormPocket(contour_name={self.contour_name!r}, overlap={self.overlap}, mode={self.mode})"

    @staticmethod
    def _fmt(val) -> str:
        """Format a parameter value for the HOPS CALL line."""
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
            f"NAMEN:='{self.contour_name}'",
            f"AA:={f(self.distance_to_contour)}",
            f"UEBERLAPPUNG:={f(self.overlap)}",
            f"MODE:={f(self.mode)}",
            f"ANGLE:={f(self.angle)}",
            f"TIEFE:={f(self.depth)}",
            f"ESMD:={f(self.easy_snap_md)}",
            f"ANZAHL:={f(self.count)}",
            f"MAXZ:={f(self.max_z)}",
            f"RD:={f(self.outside_in)}",
            f"FLIEGENDEINTAUCHEN:={f(self.flying_plunge)}",
            f"MAXEINTAUCHLAENGE:={f(self.max_plunge_length)}",
        ]
        return f"CALL {self._MACRO_NAME} ( VAL {','.join(parts)})"

    @classmethod
    def from_hop_line(cls, line: str) -> "FreeFormPocket":
        raise NotImplementedError("Parsing FreeFormPocket from a HOPS line is not yet implemented.")
