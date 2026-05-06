"""Abstract base classes for all HOPS commands.

This module contains the foundational abstract classes that define the command
hierarchy for HOPS operations. All concrete command implementations inherit from
these base classes.

Classes:
--------
HOPSCommand : ABC
    Root abstract base class for all HOPS commands
OperationCommand : ABC
    Base class for complete machining operations (milling, sawing, drilling)
MoveCommand : ABC
    Base class for individual movements (StartPoint, G01, G02M, G03M, EndPoint)
WorkPlaneCommand : ABC
    Base class for work plane definitions (EBENE, EBENEF)
ToolCommand : ABC
    Base class for tool definitions (WKZ)
UtilityCommand : ABC
    Base class for utility/modifier commands (feedrate override, stops, etc.)
HopsMacroCommand : ABC
    Base class for HOPS CALL macro statements (_ExecutePocket_V5, OpenPocket, etc.)
ContourCommand : ABC
    Base class for contour buffer commands (KB, KG01, KG01ZuKB)
"""

from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import List
from typing import Optional

if TYPE_CHECKING:
    # Only import for type hints to avoid circular dependencies
    pass


class HOPSCommand(ABC):
    """Abstract base class for all HOPS commands.

    All HOPS commands (tools, workplanes, operations, moves, utility commands)
    inherit from this class. This enables a unified interface for command manipulation
    and allows commands to have other commands attached before/after them.

    Attributes:
    -----------
    _before_commands : List[HOPSCommand]
        Commands to execute before this command
    _after_commands : List[HOPSCommand]
        Commands to execute after this command

    Example:
    --------
    >>> sp = StartPoint(0, 0, 0)
    >>> sp.add_before(FeedrateOverride(3000))
    >>> str(sp)
    'CALL _Tvorschub_v5(VAL VORSCHUB:=3000)\\nSP(0,0,0,...)'
    """

    def __init__(self):
        """Initialize command with empty before/after lists."""
        self._before_commands: List["HOPSCommand"] = []
        self._after_commands: List["HOPSCommand"] = []

    @abstractmethod
    def _to_hop_line(self) -> str:
        """Generate the core HOPS command line.

        This method must be implemented by all concrete command classes.
        It should return only the command itself, without any before/after commands.

        Returns:
        --------
        str
            The HOPS command line (e.g., "SP(0,0,0,...)" or "EBENE0()")
        """
        pass

    def add_before(self, command: "HOPSCommand") -> "HOPSCommand":
        """Add a command to execute before this command.

        Parameters:
        -----------
        command : HOPSCommand
            The command to add before this one

        Returns:
        --------
        HOPSCommand
            Self, for method chaining

        Example:
        --------
        >>> sp = StartPoint(0, 0, 0)
        >>> sp.add_before(FeedrateOverride(3000))
        >>> sp.add_before(MachineStop("Check setup"))
        """
        self._before_commands.append(command)
        return self

    def add_after(self, command: "HOPSCommand") -> "HOPSCommand":
        """Add a command to execute after this command.

        Parameters:
        -----------
        command : HOPSCommand
            The command to add after this one

        Returns:
        --------
        HOPSCommand
            Self, for method chaining

        Example:
        --------
        >>> op = MillingOperation(...)
        >>> op.add_after(CommentLine("Operation completed"))
        """
        self._after_commands.append(command)
        return self

    def __str__(self) -> str:
        """Generate complete HOPS output including before/after commands.

        Returns:
        --------
        str
            Complete HOPS output with before commands, this command, and after commands
        """
        lines = []

        # Add before commands
        for cmd in self._before_commands:
            lines.append(str(cmd))

        # Add this command
        lines.append(self._to_hop_line())

        # Add after commands
        for cmd in self._after_commands:
            lines.append(str(cmd))

        return "\n".join(lines)


class OperationCommand(HOPSCommand, ABC):
    """Abstract base class for all operation commands.

    Operations represent complete machining operations like milling, sawing, or drilling.
    Operations can have tools, workplanes, and utility commands attached to them.

    Available fluent methods:
    - with_tool(): Add a tool before this operation
    - with_workplane(): Add a workplane before this operation
    - with_feedrate(): Add a feedrate override before this operation
    - with_stop(): Add a machine stop before this operation
    """

    def with_tool(self, tool: HOPSCommand) -> "OperationCommand":
        """Add a tool before this operation.

        Parameters:
        -----------
        tool : HOPSCommand
            The tool command to add

        Returns:
        --------
        OperationCommand
            Self, for method chaining

        Example:
        --------
        >>> from easyhops.tool_library import MachiningTool
        >>> tool = MachiningTool(position=505, depth=3000, ...)
        >>> op = MillingOperation(...).with_tool(tool)
        """
        return self.add_before(tool)

    def with_workplane(self, workplane: HOPSCommand) -> "OperationCommand":
        """Add a workplane before this operation.

        Parameters:
        -----------
        workplane : HOPSCommand
            The workplane command to add

        Returns:
        --------
        OperationCommand
            Self, for method chaining

        Example:
        --------
        >>> from easyhops.work_planes import FreePlane
        >>> plane = FreePlane(x=100, y=50, z=0, rotation_angle=45, tilt_angle=0)
        >>> op = MillingOperation(...).with_workplane(plane)
        """
        return self.add_before(workplane)

    def with_feedrate(self, feedrate: float) -> "OperationCommand":
        """Add a feedrate override before this operation.

        Parameters:
        -----------
        feedrate : float
            Feedrate in mm/min

        Returns:
        --------
        OperationCommand
            Self, for method chaining

        Example:
        --------
        >>> op = MillingOperation(...).with_feedrate(2000)
        """
        from .utility_commands import FeedrateOverride

        return self.add_before(FeedrateOverride(feedrate))

    def with_stop(self, message: Optional[str] = None, **kwargs) -> "OperationCommand":
        """Add a machine stop before this operation.

        Parameters:
        -----------
        message : Optional[str]
            Optional message to display at the stop
        **kwargs : dict
            Additional parameters for MachineStop (park_pos_x, park_pos_y, etc.)

        Returns:
        --------
        OperationCommand
            Self, for method chaining

        Example:
        --------
        >>> op = MillingOperation(...).with_stop("Verify alignment")
        >>> op = MillingOperation(...).with_stop("Flip part", park_pos_x=1500.0)
        """
        from .utility_commands import MachineStop

        return self.add_before(MachineStop(message, **kwargs))


class MoveCommand(HOPSCommand, ABC):
    """Abstract base class for all move commands.

    Move commands represent individual movements: StartPoint, G01, G02M, G03M, EndPoint.
    Moves can have feedrate, spindle speed, and stop overrides attached.

    Available fluent methods:
    - with_feedrate(): Add a feedrate override before this move
    - with_stop(): Add a machine stop before this move
    """

    def with_feedrate(self, feedrate: float) -> "MoveCommand":
        """Add a feedrate override before this move.

        Parameters:
        -----------
        feedrate : float
            Feedrate in mm/min

        Returns:
        --------
        MoveCommand
            Self, for method chaining

        Example:
        --------
        >>> sp = StartPoint(0, 0, 0).with_feedrate(1500)
        >>> g01 = G01(100, 100, 0).with_feedrate(4000)
        """
        from .utility_commands import FeedrateOverride

        return self.add_before(FeedrateOverride(feedrate))

    def with_stop(self, message: Optional[str] = None, **kwargs) -> "MoveCommand":
        """Add a machine stop before this move.

        Parameters:
        -----------
        message : Optional[str]
            Optional message to display at the stop
        **kwargs : dict
            Additional parameters for MachineStop (park_pos_x, park_pos_y, etc.)

        Returns:
        --------
        MoveCommand
            Self, for method chaining

        Example:
        --------
        >>> g01 = G01(100, 100, 0).with_stop("Check cut quality")
        >>> g01 = G01(100, 100, 0).with_stop("Flip beam", park_pos_x=1500.0)
        """
        from .utility_commands import MachineStop

        return self.add_before(MachineStop(message, **kwargs))


class WorkPlaneCommand(HOPSCommand, ABC):
    """Abstract base class for work plane commands.

    Work planes define the coordinate system for machining operations.
    Includes standard planes (EBENE0-4) and parametric free planes (EBENEF).
    """

    pass


class ToolCommand(HOPSCommand, ABC):
    """Abstract base class for tool commands.

    Tools define the cutting tool to use for machining operations.
    Includes tool definitions (WKZ) with all associated parameters.
    """

    pass


class UtilityCommand(HOPSCommand, ABC):
    """Abstract base class for utility/modifier commands.

    Utility commands modify the behavior of other commands without being
    standalone operations. Examples include feedrate overrides, spindle speed
    overrides, and machine stops.
    """

    pass


class HopsMacroCommand(HOPSCommand, ABC):
    """Abstract base class for HOPS CALL macro commands.

    Macro commands represent CALL statements that invoke built-in HOPS macros,
    such as _ExecutePocket_V5, OpenPocket, KonturFraesen, etc.
    """

    pass


class ContourCommand(HOPSCommand, ABC):
    """Abstract base class for contour buffer commands.

    Contour commands write geometry into a named HOPS contour buffer
    (KB, KG01, KG01ZuKB) rather than moving the spindle directly.
    """

    pass
