import configparser
import re
from enum import StrEnum
from pathlib import Path
from typing import Dict
from typing import Optional
from typing import Union


class HopsSystemVars(StrEnum):
    """HOPS global system variables for tool parameters.

    These macro variables reference the CNC machine's configured default values.
    When used in HOPS commands, the machine substitutes them with current values
    from the tool manager during program execution.

    Parameters:
    -----------
    FEEDRATE : str
        Current feed rate from tool manager ("_V")
    LEAD_OUT_FEEDRATE : str
        Current lead out feed rate from tool manager ("_VA")
    LEAD_IN_FEEDRATE : str
        Current lead in feed rate from tool manager ("_VE")
    MOTOR_SPEED : str
        Current motor speed from tool manager ("_SD")
    LEAD_IN_OUT_FACTOR : str
        Current tool lead in and lead out factor from tool manager ("_ANF")
    TOOL_DIAMETER : str
        Current tool diameter from tool manager ("_WZD")
    TOOL_RADIUS : str
        Current tool radius from tool manager ("_WZR")
    SAW_WIDTH : str
        Current saw blade width from tool manager ("_SBB")
    """

    LEAD_IN_FEEDRATE = "_VE"  # Current lead in feed rate (tool manager)
    FEEDRATE = "_V"  # Current feed rate (tool manager)
    LEAD_OUT_FEEDRATE = "_VA"  # Current lead out feed rate (tool manager)
    MOTOR_SPEED = "_SD"  # Current motor speed (tool manager)
    LEAD_IN_OUT_FACTOR = "_ANF"  # Current tool lead in/out factor (tool manager)
    TOOL_DIAMETER = "_WZD"  # Current tool diameter (tool manager)
    TOOL_RADIUS = "_WZR"  # Current tool radius (tool manager)
    SAW_WIDTH = "_SBB"  # Current saw blade width (tool manager)


class ToolCallType(StrEnum):
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


class MachiningTool:
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
        self.tool_type = tool_type
        self.position = position
        self.lead_in_feedrate = lead_in_feedrate
        self.feedrate = feedrate
        self.lead_out_feedrate = lead_out_feedrate
        self.motor_speed = motor_speed
        self.lead_in_out_factor = lead_in_out_factor
        self.head_id = head_id
        self.name = name

    def __str__(self) -> str:
        """Return HOPS tool command string."""
        cmd_prefix = self.tool_type.value
        lead_in_feedrate_str = str(self.lead_in_feedrate) if self.lead_in_feedrate is not None else HopsSystemVars.LEAD_IN_FEEDRATE
        feedrate_str = str(self.feedrate) if self.feedrate is not None else HopsSystemVars.FEEDRATE
        lead_out_feedrate_str = str(self.lead_out_feedrate) if self.lead_out_feedrate is not None else HopsSystemVars.LEAD_OUT_FEEDRATE
        motor_speed_str = str(self.motor_speed) if self.motor_speed is not None else HopsSystemVars.MOTOR_SPEED
        lead_in_out_factor_str = str(self.lead_in_out_factor) if self.lead_in_out_factor is not None else HopsSystemVars.LEAD_IN_OUT_FACTOR

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
            # Use default path relative to this module
            module_dir = Path(__file__).parent.parent
            too_path = module_dir / "data" / "7235C_219.too"

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
