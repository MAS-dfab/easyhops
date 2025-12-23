"""Utility commands for HOPS files.

This module contains utility/modifier commands that enhance or modify
the behavior of other commands without being core machining operations.
"""

import re
from typing import Optional

from .base_commands import UtilityCommand


class FeedrateOverride(UtilityCommand):
    """Represents a standalone feedrate override command.

    Should be called before a machining command to set a specific feedrate that would override
    the tool's default feedrate for the subsequent operation.

    Parameters:
    -----------
    feedrate : float
        Feedrate in mm/min

    Example:
        >>> override = FeedrateOverride(3500)
        >>> str(override)
        'CALL _Tvorschub_v5(VAL VORSCHUB:=3500)'
    """

    def __init__(self, feedrate: float):
        super().__init__()
        self.feedrate = feedrate

    def _to_hop_line(self) -> str:
        return f"CALL _Tvorschub_v5(VAL VORSCHUB:={self.feedrate})"

    @classmethod
    def from_hop_line(cls, line: str) -> "FeedrateOverride":
        match = re.match(r"CALL _Tvorschub_v5\(VAL VORSCHUB:=(\d+\.?\d*)\)", line.strip())
        if match:
            return cls(float(match.group(1)))
        raise ValueError(f"Invalid feedrate override line: {line}")


class MachineStop(UtilityCommand):
    """Represents a machine stop/pause command using HOPS CALL MachineStop_V7.

    Causes the machine to pause execution until operator confirmation.
    Useful for manual checks, tool changes, or safety verification.

    Parameters:
    -----------
    message : Optional[str]
        Optional message to display to the operator (STR parameter)
    mode : int
        Stop mode (default: 0)
    park_mode : int
        Park mode setting (default: 10)
    park_pos_x : float
        X position for parking (default: 0.0)
    park_pos_y : float
        Y position for parking (default: 0.0)
    typ : int
        Type parameter (default: 0)
    r6 : int
        Reserved parameter 6 (default: 0)
    r7 : int
        Reserved parameter 7 (default: 0)

    Example:
        >>> # Simple stop with message
        >>> stop = MachineStop("Check workpiece alignment")
        >>> str(stop)
        "CALL MachineStop_V7 ( VAL MODE:=0,PARKMODE:=10,PARKPOSX:=0.000,PARKPOSY:=0,TYP:=0,R6:=0, STR:='Check workpiece alignment',R7:=0)"

        >>> # Stop with custom park position
        >>> stop = MachineStop("flip beam 180deg", park_pos_x=1500.0)
        >>> str(stop)
        "CALL MachineStop_V7 ( VAL MODE:=0,PARKMODE:=10,PARKPOSX:=1500.000,PARKPOSY:=0,TYP:=0,R6:=0, STR:='flip beam 180deg',R7:=0)"

        >>> # Simple stop without message
        >>> stop = MachineStop()
        >>> str(stop)
        "CALL MachineStop_V7 ( VAL MODE:=0,PARKMODE:=10,PARKPOSX:=0.000,PARKPOSY:=0,TYP:=0,R6:=0, STR:='',R7:=0)"
    """

    def __init__(
        self,
        message: Optional[str] = None,
        mode: int = 0,
        park_mode: int = 10,
        park_pos_x: float = 0.0,
        park_pos_y: float = 0.0,
        typ: int = 0,
        r6: int = 0,
        r7: int = 0,
    ):
        super().__init__()
        self.message = message or ""
        self.mode = mode
        self.park_mode = park_mode
        self.park_pos_x = park_pos_x
        self.park_pos_y = park_pos_y
        self.typ = typ
        self.r6 = r6
        self.r7 = r7

    def _to_hop_line(self) -> str:
        return (
            f"CALL MachineStop_V7 ( VAL MODE:={self.mode},"
            f"PARKMODE:={self.park_mode},"
            f"PARKPOSX:={self.park_pos_x:.3f},"
            f"PARKPOSY:={self.park_pos_y},"
            f"TYP:={self.typ},"
            f"R6:={self.r6}, "
            f"STR:='{self.message}',"
            f"R7:={self.r7})"
        )

    @classmethod
    def from_hop_line(cls, line: str) -> "MachineStop":
        """Parse a CALL MachineStop_V7 line.

        Example:
            CALL MachineStop_V7 ( VAL MODE:=0,PARKMODE:=10,PARKPOSX:=1500.000,PARKPOSY:=0,TYP:=0,R6:=0, STR:='flip beam 180deg',R7:=0)
        """
        pattern = (
            r"CALL MachineStop_V7\s*\(\s*VAL\s+"
            r"MODE:=(\d+),?"
            r"PARKMODE:=(\d+),?"
            r"PARKPOSX:=([-+]?\d+\.?\d*),?"
            r"PARKPOSY:=([-+]?\d+\.?\d*),?"
            r"TYP:=(\d+),?"
            r"R6:=(\d+),?\s*"
            r"STR:='([^']*)',?"
            r"R7:=(\d+)"
        )

        match = re.match(pattern, line.strip())
        if match:
            mode = int(match.group(1))
            park_mode = int(match.group(2))
            park_pos_x = float(match.group(3))
            park_pos_y = float(match.group(4))
            typ = int(match.group(5))
            r6 = int(match.group(6))
            message = match.group(7)
            r7 = int(match.group(8))

            return cls(
                message=message if message else None,
                mode=mode,
                park_mode=park_mode,
                park_pos_x=park_pos_x,
                park_pos_y=park_pos_y,
                typ=typ,
                r6=r6,
                r7=r7,
            )
        raise ValueError(f"Invalid MachineStop_V7 line: {line}")
