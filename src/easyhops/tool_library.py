import configparser
import re
from enum import Enum
from pathlib import Path
from typing import Dict
from typing import Optional
from typing import Union

from . import DATA
from .base_commands import ToolCommand
from .hop_core import HopsSystemVars


class ToolCallType(str, Enum):
    """Tool holder types for HOPS commands.

    Parameters:
    -----------
    ROUTER : str
        Router/milling tool ("WZF")
    SAW : str
        Saw blade tool ("WZS")
    DRILLER : str
        Drilling tool ("WZB")

    """

    ROUTER = "WZF"  # TOOLM
    SAW = "WZS"  # TOOLS
    DRILLER = "WZB"  # TOOLD

    def __str__(self):
        return self.value


class MachiningTool(ToolCommand):
    """HOPS tool instance with parameters for generating machining commands.

    Represents a machining tool with configurable parameters like feedrates
    and machining modes. Tool instances can be converted to HOPS command strings
    using str(). Parameters default to None, which outputs HOPS macro variables
    that use the CNC machine's configured default values.

    Parameters:
    -----------
    tool_type : :class:`ToolCallType`
        Type of tool (`ToolCallType.ROUTER`,  `ToolCallType.SAW`, `ToolCallType.DRILLER`)
    position : int
        Tool position number in the holder
    lead_in_feedrate : Optional[float]
        Lead in/out feedrate in mm/min. If None, uses HopsSystemVars.LEAD_IN_FEEDRATE (_VE)
    feedrate : Optional[float]
        General/rapid feedrate in mm/min. If None, uses HopsSystemVars.FEEDRATE (_V)
    lead_out_feedrate : Optional[float]
        Lead out feedrate in mm/min. If None, uses HopsSystemVars.LEAD_OUT_FEEDRATE (_VA)
    motor_speed : Optional[float]
        Motor speed (RPM). If None, uses HopsSystemVars.MOTOR_SPEED (_SD)
    lead_in_out_factor : Optional[float]
        Lead-in/out factor. This is a multiplying factor of the default value set in the tool manager.
        If None, uses HopsSystemVars.LEAD_IN_OUT_FACTOR (_ANF)
    head_id : str
        Tool head identifier (default: '1')
    name : str
        Tool name/description (e.g., 'Birdsmouth W41', 'Saw blade Ø350')

    Example:
        >>> # Use machine defaults
        >>> tool = MachiningTool(ToolHolderType.CASSETTE, 7, name="Example Tool")
        >>> str(tool)
        'WZF(7,_VE,_V,_VA,_SD,_ANF,'1')'

        >>> # Override specific parameters (lead_in_feedrate=5000, feedrate=8000, surface_feedrate=5000)
        >>> tool = MachiningTool(ToolHolderType.CASSETTE, 1, lead_in_feedrate=5000, feedrate=8000, surface_feedrate=5000, name="DIA20_R")
        >>> str(tool)
        'WZF(1,5000,8000,5000,_SD,_ANF,'1')'

        >>> # Modify after creation
        >>> tool.surface_feedrate = 6000
        >>> str(tool)
        'WZF(1,5000,8000,6000,_SD,_ANF,'1')'
    """

    def __init__(
        self,
        tool_type: ToolCallType,
        position: int,
        lead_in_feedrate: Optional[float] = None,
        feedrate: Optional[float] = None,
        lead_out_feedrate: Optional[float] = None,
        motor_speed: Optional[float] = None,
        lead_in_out_factor: Optional[float] = None,
        head_id: str = "1",
        name: str = "",
    ):
        super().__init__()
        self._tool_type = None
        self._position = None
        self._lead_in_feedrate = None
        self._feedrate = None
        self._lead_out_feedrate = None
        self._motor_speed = None
        self._lead_in_out_factor = None
        self._head_id = None
        self._name = None

        self.tool_type = tool_type
        self.position = position
        self.lead_in_feedrate = lead_in_feedrate
        self.feedrate = feedrate
        self.lead_out_feedrate = lead_out_feedrate
        self.motor_speed = motor_speed
        self.lead_in_out_factor = lead_in_out_factor
        self.head_id = head_id
        self.name = name

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "diameter" and isinstance(value, (int, float)):
            HopsSystemVars.TOOL_DIAMETER.set(value)
            HopsSystemVars.TOOL_RADIUS.set(value / 2.0)
        elif name == "saw_width" and isinstance(value, (int, float)):
            HopsSystemVars.SAW_WIDTH.set(value)

    @property
    def tool_type(self) -> ToolCallType:
        """Tool type (ROUTER, SAW, or DRILLER)."""
        return self._tool_type

    @tool_type.setter
    def tool_type(self, value: ToolCallType):
        if not isinstance(value, ToolCallType):
            raise TypeError(f"tool_type must be ToolCallType, got {type(value).__name__}")
        self._tool_type = value

    @property
    def position(self) -> int:
        """Tool position number in the holder."""
        return self._position

    @position.setter
    def position(self, value: int):
        if not isinstance(value, int):
            raise TypeError(f"position must be int, got {type(value).__name__}")
        if value < 0:
            raise ValueError(f"position must be non-negative, got {value}")
        self._position = value

    @property
    def lead_in_feedrate(self) -> Optional[float]:
        """Lead in/out feedrate in mm/min."""
        return self._lead_in_feedrate

    @lead_in_feedrate.setter
    def lead_in_feedrate(self, value: Optional[float]):
        if value is not None:
            if not isinstance(value, (int, float)):
                raise TypeError(f"lead_in_feedrate must be a number or None, got {type(value).__name__}")
            if value < 0:
                raise ValueError(f"lead_in_feedrate must be non-negative, got {value}")
            value = float(value)
        self._lead_in_feedrate = value

    @property
    def feedrate(self) -> Optional[float]:
        """General/rapid feedrate in mm/min."""
        return self._feedrate

    @feedrate.setter
    def feedrate(self, value: Optional[float]):
        if value is not None:
            if not isinstance(value, (int, float)):
                raise TypeError(f"feedrate must be a number or None, got {type(value).__name__}")
            if value < 0:
                raise ValueError(f"feedrate must be non-negative, got {value}")
            value = float(value)
        self._feedrate = value

    @property
    def lead_out_feedrate(self) -> Optional[float]:
        """Lead out feedrate in mm/min."""
        return self._lead_out_feedrate

    @lead_out_feedrate.setter
    def lead_out_feedrate(self, value: Optional[float]):
        if value is not None:
            if not isinstance(value, (int, float)):
                raise TypeError(f"lead_out_feedrate must be a number or None, got {type(value).__name__}")
            if value < 0:
                raise ValueError(f"lead_out_feedrate must be non-negative, got {value}")
            value = float(value)
        self._lead_out_feedrate = value

    @property
    def motor_speed(self) -> Optional[float]:
        """Motor speed in RPM."""
        return self._motor_speed

    @motor_speed.setter
    def motor_speed(self, value: Optional[float]):
        if value is not None:
            if not isinstance(value, (int, float)):
                raise TypeError(f"motor_speed must be a number or None, got {type(value).__name__}")
            if value < 0:
                raise ValueError(f"motor_speed must be non-negative, got {value}")
            value = float(value)
        self._motor_speed = value

    @property
    def lead_in_out_factor(self) -> Optional[float]:
        """Lead-in/out factor multiplier."""
        return self._lead_in_out_factor

    @lead_in_out_factor.setter
    def lead_in_out_factor(self, value: Optional[float]):
        if value is not None:
            if not isinstance(value, (int, float)):
                raise TypeError(f"lead_in_out_factor must be a number or None, got {type(value).__name__}")
            if value < 0:
                raise ValueError(f"lead_in_out_factor must be non-negative, got {value}")
            value = float(value)
        self._lead_in_out_factor = value

    @property
    def head_id(self) -> str:
        """Tool head identifier."""
        return self._head_id

    @head_id.setter
    def head_id(self, value: str):
        if not isinstance(value, str):
            raise TypeError(f"head_id must be str, got {type(value).__name__}")
        self._head_id = value

    @property
    def name(self) -> str:
        """Tool name/description."""
        return self._name

    @name.setter
    def name(self, value: str):
        if not isinstance(value, str):
            raise TypeError(f"name must be str, got {type(value).__name__}")
        self._name = value

    @property
    def radius(self) -> Optional[float]:
        """Tool radius in mm. Returns diameter / 2 if diameter is set, else None."""
        diameter = getattr(self, "diameter", None)
        return diameter / 2.0 if diameter is not None else None

    def _to_hop_line(self) -> str:
        """Return HOPS tool command string."""
        cmd_prefix = self.tool_type.value
        lead_in_feedrate_str = str(int(self.lead_in_feedrate)) if self.lead_in_feedrate is not None else HopsSystemVars.LEAD_IN_FEEDRATE
        feedrate_str = str(int(self.feedrate)) if self.feedrate is not None else HopsSystemVars.FEEDRATE
        lead_out_feedrate_str = str(int(self.lead_out_feedrate)) if self.lead_out_feedrate is not None else HopsSystemVars.LEAD_OUT_FEEDRATE
        motor_speed_str = str(int(self.motor_speed)) if self.motor_speed is not None else HopsSystemVars.MOTOR_SPEED
        lead_in_out_factor_str = f"{self.lead_in_out_factor:.2f}" if self.lead_in_out_factor is not None else HopsSystemVars.LEAD_IN_OUT_FACTOR

        return f"{cmd_prefix}({self.position},{lead_in_feedrate_str},{feedrate_str},{lead_out_feedrate_str},{motor_speed_str},{lead_in_out_factor_str},'{self.head_id}')"

    def __repr__(self) -> str:
        """Return detailed string representation for debugging."""
        return f"Tool({self.tool_type.name}, position={self.position}, name='{self.name}')"

    def get_code(self) -> str:
        """Return tool code string (e.g., 'WZF504', 'WZS201')."""
        return f"{self.tool_type.value}{self.position}"

    @classmethod
    def from_code(cls, tool_code: str, **kwargs) -> "MachiningTool":
        """Parse tool code string into Tool instance.

        Parameters:
        -----------
        tool_code : str
            Tool code string (e.g., 'WZF504', 'WZS201')

        Returns:
        -----------
        :class:`easyhops.MachiningTool`
            Parsed tool instance with parameters from code and overrides from kwargs.

        Example:
        -----------
            >>> MachiningTool.from_code("WZF504", feedrate=3500)
            MachiningTool(ROUTER, position=504, name='', priority=0)
            >>> MachiningTool.from_code("WZS201")
            MachiningTool(SAW, position=201, name='', priority=100)
        """
        match = re.match(r"(WZ[SFB])(\d+)", tool_code)
        if not match:
            raise ValueError(f"Unknown tool holder type in code: {tool_code}")

        tool_str, position_str = match.groups()
        position = int(position_str)

        if tool_str == "WZF":
            tool_type = ToolCallType.ROUTER
        elif tool_str == "WZS":
            tool_type = ToolCallType.SAW
        elif tool_str == "WZB":
            tool_type = ToolCallType.DRILLER
        else:
            raise ValueError(f"Unknown tool holder type in code: {tool_code}")

        return cls(tool_type, position, **kwargs)

    @classmethod
    def from_hop_line(cls, line: str) -> "MachiningTool":
        """Parse a HOPS tool command line into a MachiningTool instance.

        Parameters:
        -----------
        line : str
            HOPS tool command line (e.g., "WZF(504,3000,4000,5000,_SD,_ANF,'1')")

        Returns:
        -----------
        :class:`easyhops.MachiningTool`
            Parsed tool instance

        Example:
        -----------
            >>> MachiningTool.from_hop_line("WZF(504,3000,4000,5000,_SD,_ANF,'1')")
            MachiningTool(ROUTER, position=504, ...)
        """
        # Match WZF(pos,lead_in,feed,lead_out,motor,factor,'head') or similar
        # Allow optional whitespace around commas
        pattern = r"(WZ[FSB])\(\s*(\d+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*'([^']*)'\s*\)"
        match = re.match(pattern, line.strip())

        if not match:
            raise ValueError(f"Invalid tool line: {line}")

        tool_str = match.group(1)
        position = int(match.group(2))
        lead_in_str = match.group(3)
        feedrate_str = match.group(4)
        lead_out_str = match.group(5)
        motor_str = match.group(6)
        factor_str = match.group(7)
        head_id = match.group(8)

        # Determine tool type
        if tool_str == "WZF":
            tool_type = ToolCallType.ROUTER
        elif tool_str == "WZS":
            tool_type = ToolCallType.SAW
        elif tool_str == "WZB":
            tool_type = ToolCallType.DRILLER
        else:
            raise ValueError(f"Unknown tool type: {tool_str}")

        # Parse numeric parameters (handle _SD, _V, etc. as None)
        def parse_param(s: str) -> Optional[float]:
            if s.startswith("_"):
                return None
            try:
                return float(s)
            except ValueError:
                return None

        lead_in_feedrate = parse_param(lead_in_str)
        feedrate = parse_param(feedrate_str)
        lead_out_feedrate = parse_param(lead_out_str)
        motor_speed = parse_param(motor_str)
        lead_in_out_factor = parse_param(factor_str)

        return cls(
            tool_type=tool_type,
            position=position,
            lead_in_feedrate=lead_in_feedrate,
            feedrate=feedrate,
            lead_out_feedrate=lead_out_feedrate,
            motor_speed=motor_speed,
            lead_in_out_factor=lead_in_out_factor,
            head_id=head_id,
        )


# ==================== Tool Library ====================
# Predefined tools with their standard configurations


class BirdsmouthW41(MachiningTool):
    """Birdsmouth W41 wheel tool (WZF504) for contour milling and pocketing.

    Parameters:
    -----------
    lead_in_feedrate : Optional[float]
        Lead in/out feedrate in mm/min. If None, uses HopsSystemVars.LEAD_IN_FEEDRATE (_VE)
    feedrate : Optional[float]
        General/rapid feedrate in mm/min. If None, uses HopsSystemVars.FEEDRATE (_V)
    lead_out_feedrate : Optional[float]
        Lead out feedrate in mm/min. If None, uses HopsSystemVars.LEAD_OUT_FEEDRATE (_VA)
    motor_speed : Optional[float]
        Motor speed (RPM). If None, uses HopsSystemVars.MOTOR_SPEED (_SD)
    lead_in_out_factor : Optional[float]
        Lead-in/out factor. This is a multiplying factor of the default value set in the tool manager.
        If None, uses HopsSystemVars.LEAD_IN_OUT_FACTOR (_ANF)
    head_id : str
        Tool head identifier (default: '1')

    Attributes:
    -----------
    max_depth : float
        Maximum cutting depth in mm (default: 31.0)
    diameter : float
        Tool diameter in mm (default: 200.0)

    Example:
        >>> tool = BirdsmouthW41(lead_out_feedrate=4500)
        >>> str(tool)
        "WZF(504,_VE,_V,4500,_SD,_ANF,'1')"

        >>> tool = BirdsmouthW41(feedrate=3000, lead_out_feedrate=4000)
        >>> str(tool)
        "WZF(504,_VE,3000,4000,_SD,_ANF,'1')"
    """

    def __init__(
        self,
        lead_in_feedrate: Optional[float] = None,
        feedrate: Optional[float] = None,
        lead_out_feedrate: Optional[float] = None,
        motor_speed: Optional[float] = None,
        lead_in_out_factor: Optional[float] = None,
        head_id: str = "1",
    ):
        super().__init__(
            tool_type=ToolCallType.ROUTER,
            position=504,
            lead_in_feedrate=lead_in_feedrate,
            feedrate=feedrate,
            lead_out_feedrate=lead_out_feedrate,
            motor_speed=motor_speed,
            lead_in_out_factor=lead_in_out_factor,
            head_id=head_id,
            name="Birdsmouth W41",
        )

        self.max_depth = 31.0
        self.diameter = 200.0


class SaegeD350(MachiningTool):
    """Saw blade Ø350 (WZS201) for cutting operations.

    Parameters:
    -----------
    lead_in_feedrate : Optional[float]
        Lead in/out feedrate in mm/min. If None, uses HopsSystemVars.LEAD_IN_FEEDRATE (_VE)
    feedrate : Optional[float]
        General/rapid feedrate in mm/min. If None, uses HopsSystemVars.FEEDRATE (_V)
    lead_out_feedrate : Optional[float]
        Lead out feedrate in mm/min. If None, uses HopsSystemVars.LEAD_OUT_FEEDRATE (_VA)
    motor_speed : Optional[float]
        Motor speed (RPM). If None, uses HopsSystemVars.MOTOR_SPEED (_SD)
    lead_in_out_factor : Optional[float]
        Lead-in/out factor. This is a multiplying factor of the default value set in the tool manager.
        If None, uses HopsSystemVars.LEAD_IN_OUT_FACTOR (_ANF)
    head_id : str
        Tool head identifier (default: '1')

    Example:
        >>> tool = SaegeD350()
        >>> str(tool)
        "WZS(201,_VE,_V,_VA,_SD,_ANF,'1')"

        >>> tool = SaegeD350(feedrate=10000, lead_out_feedrate=7000)
        >>> str(tool)
        "WZS(201,_VE,10000,7000,_SD,_ANF,'1')"
    """

    def __init__(
        self,
        lead_in_feedrate: Optional[float] = None,
        feedrate: Optional[float] = None,
        lead_out_feedrate: Optional[float] = None,
        motor_speed: Optional[float] = None,
        lead_in_out_factor: Optional[float] = None,
        head_id: str = "1",
    ):
        super().__init__(
            tool_type=ToolCallType.SAW,
            position=201,
            lead_in_feedrate=lead_in_feedrate,
            feedrate=feedrate,
            lead_out_feedrate=lead_out_feedrate,
            motor_speed=motor_speed,
            lead_in_out_factor=lead_in_out_factor,
            head_id=head_id,
            name="Saw blade Ø350",
        )


class CastorD61(MachiningTool):
    """Castor Ø61 milling tool (WZF503) for general milling tasks.

    Parameters:
    -----------
    lead_in_feedrate : Optional[float]
        Lead in/out feedrate in mm/min. If None, uses HopsSystemVars.LEAD_IN_FEEDRATE (_VE)
    feedrate : Optional[float]
        General/rapid feedrate in mm/min. If None, uses HopsSystemVars.FEEDRATE (_V)
    lead_out_feedrate : Optional[float]
        Lead out feedrate in mm/min. If None, uses HopsSystemVars.LEAD_OUT_FEEDRATE (_VA)
    motor_speed : Optional[float]
        Motor speed (RPM). If None, uses HopsSystemVars.MOTOR_SPEED (_SD)
    lead_in_out_factor : Optional[float]
        Lead-in/out factor. This is a multiplying factor of the default value set in the tool manager.
        If None, uses HopsSystemVars.LEAD_IN_OUT_FACTOR (_ANF)
    head_id : str
        Tool head identifier (default: '1')

    Attributes:
    -----------
    max_depth : float
        Maximum cutting depth in mm (default: 130.0)
    diameter : float
        Tool diameter in mm (default: 61.092)

    Example:
        >>> tool = CastorD61()
        >>> str(tool)
        "WZF(503,_VE,_V,_VA,_SD,_ANF,'1')"

        >>> tool = CastorD61(feedrate=3500)
        >>> str(tool)
        "WZF(503,_VE,3500,_VA,_SD,_ANF,'1')"
    """

    def __init__(
        self,
        lead_in_feedrate: Optional[float] = None,
        feedrate: Optional[float] = None,
        lead_out_feedrate: Optional[float] = None,
        motor_speed: Optional[float] = None,
        lead_in_out_factor: Optional[float] = None,
        head_id: str = "1",
    ):
        super().__init__(
            tool_type=ToolCallType.ROUTER,
            position=503,
            lead_in_feedrate=lead_in_feedrate,
            feedrate=feedrate,
            lead_out_feedrate=lead_out_feedrate,
            motor_speed=motor_speed,
            lead_in_out_factor=lead_in_out_factor,
            head_id=head_id,
            name="Castor Ø61",
        )

        self.max_depth = 130.0
        self.diameter = 61.092


class ToolLibrary:
    """Dynamic tool library parsed from CNC .too files.

    Parses .too files to extract tool configurations including names, positions,
    feedrates, and other parameters. Provides dynamic access to all tools
    defined in the CNC machine's tool library.

    Parameters:
    -----------
    too_path : Union[str, Path]
        Path to .too file. If None, uses default 'data/7235C_219.too' included with easyhops.

    Example:
    -----------
        >>> # Use default tool library from data/7235C_219.too
        >>> tool = ToolLibrary.get("Birdsmouth")
        >>> str(tool)
        "WZF(504,_VE,_V,_VA,_SD,_ANF,'1')"
        >>> tool.feedrate = 3500  # Override as needed
        >>>
        >>> # Or create custom library instance
        >>> library = ToolLibrary("custom_tools.too")
        >>> tool = library.get("Birdsmouth")
        >>>
        >>> # Get by tool number
        >>> tool = ToolLibrary.get(tool_no=27)
        >>> tool.name
        'Birdsmouth'
    """

    _default_instance: Optional["ToolLibrary"] = None

    def __init__(self, too_path: Union[str, Path] = None):
        self._tools_by_name: Dict[str, MachiningTool] = {}
        self._tools_by_number: Dict[int, MachiningTool] = {}
        self._tool_count: int = 0

        if too_path is None:
            # Use default tool library from package DATA directory
            too_path = Path(DATA) / "7235C_219.too"

        self._parse_too_file(Path(too_path))

    def __len__(self) -> int:
        """Return number of tools in library."""
        return len(self._tools_by_number)

    def __repr__(self) -> str:
        """Return string representation."""
        return f"ToolLibrary(tools={len(self)}, file_count={self._tool_count})"

    @classmethod
    def _get_default_instance(cls) -> "ToolLibrary":
        """Get or create the default tool library instance (singleton pattern)."""
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    @classmethod
    def get(cls, name: str = None, tool_no: int = None) -> Optional[MachiningTool]:
        """Get tool by name or tool number from default library.

        If both name and tool_no are provided, validates they refer to the same tool.

        This is a class method that uses the default tool library (data/7235C_219.too).
        For custom tool libraries, create an instance and call get() on it.

        Parameters:
        -----------
        name : str
            Tool name (case-insensitive, partial match supported)
        tool_no : int
            Tool number from .too file

        Returns:
        -----------
        :class:`easyhops.MachiningTool`
            MachiningTool instance if found, None otherwise

        Raises:
        -----------
        ValueError
            If both name and tool_no are provided but don't match the same tool

        Example:
        -----------
            >>> # Direct access without instantiation
            >>> tool = ToolLibrary.get("Birdsmouth")
            >>> str(tool)
            "WZF(504,_VE,_V,_VA,_SD,_ANF,'1')"
            >>>
            >>> # Get by tool number
            >>> tool = ToolLibrary.get(tool_no=27)
            >>> tool.name
            'Birdsmouth'
            >>>
            >>> # For custom tool library, create instance
            >>> library = ToolLibrary("custom_tools.too")
            >>> tool = library.get_tool("CustomTool")
        """
        instance = cls._get_default_instance()
        return instance.get_tool(name=name, tool_no=tool_no)

    def get_tool(self, name: str = None, tool_no: int = None) -> Optional[MachiningTool]:
        """Get tool by name or tool number from this library instance.

        If both name and tool_no are provided, validates they refer to the same tool.

        Parameters:
        -----------
        name : str
            Tool name (case-insensitive, partial match supported)
        tool_no : int
            Tool number from .too file

        Returns:
        -----------
        :class:`easyhops.MachiningTool`
            MachiningTool instance if found, None otherwise

        Raises:
        -----------
        ValueError
            If both name and tool_no are provided but don't match the same tool

        Example:
            >>> library = ToolLibrary()
            >>> tool = library.get_tool("Birdsmouth")
            >>> str(tool)
            "WZF(504,_VE,_V,_VA,_SD,_ANF,'1')"
            >>>
            >>> # Validate name and number match
            >>> tool = library.get_tool("Birdsmouth", tool_no=504)
        """
        if name is None and tool_no is None:
            raise ValueError("Must provide either `name` or `tool_no` to get tool.")

        tool_by_name = None
        tool_by_number = None

        if name is not None:
            # Try exact match first (case-insensitive)
            tool_by_name = self._tools_by_name.get(name.lower())

            # Try partial match if exact match failed
            if tool_by_name is None:
                name_lower = name.lower()
                for tool_name, tool in self._tools_by_name.items():
                    if name_lower in tool_name:
                        tool_by_name = tool
                        break

        if tool_no is not None:
            tool_by_number = self._tools_by_number.get(tool_no)

        # If both provided, validate they match
        if name is not None and tool_no is not None:
            if tool_by_name is None and tool_by_number is None:
                return None  # Neither found
            elif tool_by_name is None:
                raise ValueError(f"Tool name '{name}' not found, but tool_no {tool_no} exists")
            elif tool_by_number is None:
                raise ValueError(f"Tool number {tool_no} not found, but name '{name}' exists")
            elif tool_by_name is not tool_by_number:
                raise ValueError(f"Tool name '{name}' (position {tool_by_name.position}) does not match tool_no {tool_no} (name '{tool_by_number.name}')")
            return tool_by_name  # Both match, return either one

        # Return whichever was found
        return tool_by_name if tool_by_name is not None else tool_by_number

    def list_tools(self) -> list[str]:
        """List all tool names in library.

        Returns:
        -----------
        List[str]
            List of tool names
        """
        return sorted(self._tools_by_name.keys())

    def _parse_too_file(self, too_path: Path):
        # Parse .too file and populate tool library.

        if not too_path.exists():
            raise FileNotFoundError(f"Tool file not found: {too_path}")

        # Parse .too file (INI-like format)
        # .too files are typically UTF-16 encoded
        config = configparser.ConfigParser()
        try:
            config.read(too_path, encoding="utf-16")
        except UnicodeDecodeError:
            # Fallback to utf-8 if utf-16 fails
            config.read(too_path, encoding="utf-8")

        # Get tool count
        if "ToolsCount" in config:
            self._tool_count = config.getint("ToolsCount", "Tools", fallback=0)

        for section in config.sections():
            # Match ToolDataN sections (not CuttingEdge sections)
            if match := re.match(r"^ToolData(\d+)$", section):
                # Extract tool metadata
                name = config.get(section, "Name", fallback="")
                tool_type_idx = config.getint(section, "ToolType", fallback=0)

                # Look for corresponding CuttingEdge section to get the actual tool ID
                cutting_edge_section = f"{section}CuttingEdge0"
                if cutting_edge_section not in config:
                    continue

                # Get the actual tool ID from CuttingEdge section
                tool_id = config.getint(cutting_edge_section, "ID", fallback=-1)

                # Skip tools with invalid IDs
                if tool_id == -1:
                    continue

                # Determine tool type based on tool type index
                # ToolType: 0=Schaft (cassette), 1=Drill (drill head), 2=Säge (saw blade), 3=Laser/Special
                if tool_type_idx == 2:  # Saw blade
                    tool_type = ToolCallType.SAW
                elif tool_type_idx == 1:  # Drill
                    tool_type = ToolCallType.DRILLER
                elif tool_type_idx == 0:  # Cassette tools
                    tool_type = ToolCallType.ROUTER

                # Create MachiningTool instance
                # Don't pass feedrates - let them default to None so HOPS macro variables are used
                tool = MachiningTool(
                    tool_type=tool_type,
                    position=tool_id,
                    name=name,
                )

                # Register tool by name and ID
                if name:
                    self._tools_by_name[name.lower()] = tool
                self._tools_by_number[tool_id] = tool
