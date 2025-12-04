"""Dynamic tool library parser for .too files.

Parses HOPS .too (tool) files from CNC machines and provides dynamic
access to tool configurations with their feedrates and parameters.
"""

import re
import configparser
from pathlib import Path
from typing import Dict, Optional, Union
from enum import StrEnum


class HopsMacro(StrEnum):
    """HOPS global macro variables for tool parameters.

    These macro variables reference the CNC machine's configured default values.
    When used in HOPS commands, the machine substitutes them with current values
    from the tool manager during program execution.

    Parameters:
    -----------
    FEEDRATE : str
        Current feed rate from tool manager (_V) - general/rapid feed rate
    SURFACE_FEEDRATE : str
        Current surface feed rate from tool manager (_VA) - surface/cutting speed
    LEAD_IN_FEEDRATE : str
        Current lead in feed rate from tool manager (_VE) - lead in/out speed
    MOTOR_SPEED : str
        Current motor speed from tool manager (_SD)
    LEAD_IN_OUT_FACTOR : str
        Current tool lead in and lead out factor from tool manager (_ANF)
    TOOL_DIAMETER : str
        Current tool diameter from tool manager (_WZD)
    TOOL_RADIUS : str
        Current tool radius from tool manager (_WZR)
    SAW_WIDTH : str
        Current saw blade width from tool manager (_SBB)
    """

    FEEDRATE = "_V"  # Current feed rate (tool manager)
    SURFACE_FEEDRATE = "_VA"  # Current surface feed rate (tool manager)
    LEAD_IN_FEEDRATE = "_VE"  # Current lead in feed rate (tool manager)
    MOTOR_SPEED = "_SD"  # Current motor speed (tool manager)
    LEAD_IN_OUT_FACTOR = "_ANF"  # Current tool lead in/out factor (tool manager)
    TOOL_DIAMETER = "_WZD"  # Current tool diameter (tool manager)
    TOOL_RADIUS = "_WZR"  # Current tool radius (tool manager)
    SAW_WIDTH = "_SBB"  # Current saw blade width (tool manager)


class ToolHolderType(StrEnum):
    """Tool holder types for HOPS commands.

    Parameters:
    -----------
    CASSETTE : str
        Cassette for multiple milling tools
    BLADE : str
        Blade holder (single saw blade)
    UNKNOWN : str
        Unknown or unspecified tool type
    """

    CASSETTE = "WZF"  # Cassette for multiple milling tools
    BLADE = "WZS"  # Blade holder (single saw blade)
    DRILLS = "WZB"  # Drill holder (single drill)


class MachiningTool:
    """HOPS tool instance with parameters for generating machining commands.

    Represents a machining tool with configurable parameters like feedrates
    and machining modes. Tool instances can be converted to HOPS command strings
    using str(). Parameters default to None, which outputs HOPS macro variables
    that use the CNC machine's configured default values.

    Parameters:
    -----------
    holder_type : :class:`ToolHolderType`
        Type of tool holder (`ToolHolderType.CASSETTE` or `ToolHolderType.BLADE`)
    position : int
        Tool position number in the holder
    lead_in_feedrate : Optional[float]
        Lead in/out feedrate in mm/min. If None, uses HopsMacro.LEAD_IN_FEEDRATE (_VE)
    feedrate : Optional[float]
        General/rapid feedrate in mm/min. If None, uses HopsMacro.FEEDRATE (_V)
    surface_feedrate : Optional[float]
        Surface/cutting feedrate in mm/min. If None, uses HopsMacro.SURFACE_FEEDRATE (_VA)
    motor_speed : Optional[float]
        Motor speed (RPM). If None, uses HopsMacro.MOTOR_SPEED (_SD)
    lead_in_factor : Optional[float]
        Lead-in/out factor. This is a multiplying factor of the default value set in the tool manager.
        If None, uses HopsMacro.LEAD_IN_OUT_FACTOR (_ANF)
    slot : str
        Tool slot identifier (default: '1')
    name : str
        Tool name/description (e.g., 'Birdsmouth W41', 'Saw blade Ø350')

    Example:
        >>> # Use machine defaults
        >>> tool = MachiningTool(ToolHolderType.CASSETTE, 7, name='Example Tool')
        >>> str(tool)
        'WZF(7,_VE,_V,_VA,_SD,_ANF,'1')'

        >>> # Override specific parameters (lead_in_feedrate=5000, feedrate=8000, surface_feedrate=5000)
        >>> tool = MachiningTool(ToolHolderType.CASSETTE, 1, lead_in_feedrate=5000, feedrate=8000, surface_feedrate=5000, name='DIA20_R')
        >>> str(tool)
        'WZF(1,5000,8000,5000,_SD,_ANF,'1')'

        >>> # Modify after creation
        >>> tool.surface_feedrate = 6000
        >>> str(tool)
        'WZF(1,5000,8000,6000,_SD,_ANF,'1')'
    """

    def __init__(
        self,
        holder_type: ToolHolderType,
        position: int,
        lead_in_feedrate: Optional[float] = None,
        feedrate: Optional[float] = None,
        surface_feedrate: Optional[float] = None,
        motor_speed: Optional[float] = None,
        lead_in_factor: Optional[float] = None,
        slot: str = "1",
        name: str = "",
    ):
        self.holder_type = holder_type
        self.position = position
        self.lead_in_feedrate = lead_in_feedrate
        self.feedrate = feedrate
        self.surface_feedrate = surface_feedrate
        self.motor_speed = motor_speed
        self.lead_in_factor = lead_in_factor
        self.slot = slot
        self.name = name

    def __str__(self) -> str:
        """Return HOPS command string for this tool.

        Uses HOPS macro variables for parameters that are None:
        - lead_in_feedrate=None -> HopsMacro.LEAD_IN_FEEDRATE (_VE - lead in/out speed)
        - feedrate=None -> HopsMacro.FEEDRATE (_V - general/rapid feed)
        - surface_feedrate=None -> HopsMacro.SURFACE_FEEDRATE (_VA - surface/cutting speed)
        - motor_speed=None -> HopsMacro.MOTOR_SPEED (_SD)
        - lead_in_factor=None -> HopsMacro.LEAD_IN_OUT_FACTOR (_ANF)

        Returns formatted command like: WZF(7,_VE,_V,_VA,_SD,_ANF,'1')
        or with overrides: WZF(1,5000,8000,5000,_SD,_ANF,'1')
        """
        cmd_prefix = self.holder_type.value
        lead_in_feedrate_str = (
            str(self.lead_in_feedrate)
            if self.lead_in_feedrate is not None
            else HopsMacro.LEAD_IN_FEEDRATE
        )
        feedrate_str = (
            str(self.feedrate) if self.feedrate is not None else HopsMacro.FEEDRATE
        )
        surface_feedrate_str = (
            str(self.surface_feedrate)
            if self.surface_feedrate is not None
            else HopsMacro.SURFACE_FEEDRATE
        )
        motor_speed_str = (
            str(self.motor_speed)
            if self.motor_speed is not None
            else HopsMacro.MOTOR_SPEED
        )
        lead_in_factor_str = (
            str(self.lead_in_factor)
            if self.lead_in_factor is not None
            else HopsMacro.LEAD_IN_OUT_FACTOR
        )

        return f"{cmd_prefix}({self.position},{lead_in_feedrate_str},{feedrate_str},{surface_feedrate_str},{motor_speed_str},{lead_in_factor_str},'{self.slot}')"

    def __repr__(self) -> str:
        """Return detailed string representation for debugging."""
        return f"Tool({self.holder_type.name}, position={self.position}, name='{self.name}')"

    def get_code(self) -> str:
        """Return tool code string (e.g., 'WZF504', 'WZS201')."""
        return f"{self.holder_type.value}{self.position}"

    @classmethod
    def from_code(cls, tool_code: str, **kwargs) -> "MachiningTool":
        """Parse tool code string into Tool instance.

        Parameters:
            tool_code: Tool code string (e.g., 'WZF504', 'WZS201')
            **kwargs: Additional parameters for MachiningTool (feedrate, plunge_rate, etc.)

        Example:
            >>> MachiningTool.from_code('WZF504', feedrate=3500)
            MachiningTool(CASSETTE, position=504, name='', priority=0)
            >>> MachiningTool.from_code('WZS201')
            MachiningTool(BLADE, position=201, name='', priority=100)
        """
        match = re.match(r"(WZ[SFB])(\d+)", tool_code)
        if not match:
            raise ValueError(f"Unknown tool holder type in code: {tool_code}")

        holder_str, position_str = match.groups()
        position = int(position_str)

        if holder_str == "WZF":
            holder_type = ToolHolderType.CASSETTE
        elif holder_str == "WZS":
            holder_type = ToolHolderType.BLADE
        elif holder_str == "WZB":
            holder_type = ToolHolderType.DRILLS
        else:
            raise ValueError(f"Unknown tool holder type in code: {tool_code}")

        return cls(holder_type, position, **kwargs)


# ==================== Tool Library ====================
# Predefined tools with their standard configurations


class BirdsmouthW41(MachiningTool):
    """Birdsmouth W41 wheel tool (WZF504) for contour milling and pocketing.

    Example:
        >>> tool = BirdsmouthW41(surface_feedrate=4500)
        >>> str(tool)
        "WZF(504,_VE,_V,4500,_SD,_ANF,'1')"

        >>> tool = BirdsmouthW41(feedrate=3000, surface_feedrate=4000)
        >>> str(tool)
        "WZF(504,_VE,3000,4000,_SD,_ANF,'1')"
    """

    def __init__(
        self,
        lead_in_feedrate: Optional[float] = None,
        feedrate: Optional[float] = None,
        surface_feedrate: Optional[float] = None,
        motor_speed: Optional[float] = None,
        lead_in_factor: Optional[float] = None,
        slot: str = "1",
    ):
        super().__init__(
            holder_type=ToolHolderType.CASSETTE,
            position=504,
            lead_in_feedrate=lead_in_feedrate,
            feedrate=feedrate,
            surface_feedrate=surface_feedrate,
            motor_speed=motor_speed,
            lead_in_factor=lead_in_factor,
            slot=slot,
            name="Birdsmouth W41",
        )


class SaegeD350(MachiningTool):
    """Saw blade Ø350 (WZS201) for cutting operations.

    Example:
        >>> tool = SaegeD350()
        >>> str(tool)
        "WZS(201,_VE,_V,_VA,_SD,_ANF,'1')"

        >>> tool = SaegeD350(feedrate=10000, surface_feedrate=7000)
        >>> str(tool)
        "WZS(201,_VE,10000,7000,_SD,_ANF,'1')"
    """

    def __init__(
        self,
        lead_in_feedrate: Optional[float] = None,
        feedrate: Optional[float] = None,
        surface_feedrate: Optional[float] = None,
        motor_speed: Optional[float] = None,
        lead_in_factor: Optional[float] = None,
        slot: str = "1",
    ):
        super().__init__(
            holder_type=ToolHolderType.BLADE,
            position=201,
            lead_in_feedrate=lead_in_feedrate,
            feedrate=feedrate,
            surface_feedrate=surface_feedrate,
            motor_speed=motor_speed,
            lead_in_factor=lead_in_factor,
            slot=slot,
            name="Saw blade Ø350",
        )


class CastorD61(MachiningTool):
    """Castor Ø61 milling tool (WZF503) for general milling tasks.

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
        surface_feedrate: Optional[float] = None,
        motor_speed: Optional[float] = None,
        lead_in_factor: Optional[float] = None,
        slot: str = "1",
    ):
        super().__init__(
            holder_type=ToolHolderType.CASSETTE,
            position=503,
            lead_in_feedrate=lead_in_feedrate,
            feedrate=feedrate,
            surface_feedrate=surface_feedrate,
            motor_speed=motor_speed,
            lead_in_factor=lead_in_factor,
            slot=slot,
            name="Castor Ø61",
        )


class ToolLibrary:
    """Dynamic tool library parsed from CNC .too files.

    Parses .too files to extract tool configurations including names, positions,
    feedrates, and other parameters. Provides dynamic access to all tools
    defined in the CNC machine's tool library.

    Example:
        >>> # Use default tool library from data/7235C_219.too
        >>> tool = ToolLibrary.get('Birdsmouth')
        >>> str(tool)
        "WZF(504,_VE,_V,_VA,_SD,_ANF,'1')"
        >>> tool.feedrate = 3500  # Override as needed
        >>>
        >>> # Or create custom library instance
        >>> library = ToolLibrary('custom_tools.too')
        >>> tool = library.get('Birdsmouth')
        >>>
        >>> # Get by tool number
        >>> tool = ToolLibrary.get(tool_no=27)
        >>> tool.name
        'Birdsmouth'
    """

    _default_instance: Optional["ToolLibrary"] = None

    def __init__(self, too_path: Union[str, Path] = None):
        """Parse .too file and create tool library.

        Args:
            too_path: Path to .too file. If None, uses 'data/7235C_219.too'

        Example:
            >>> library = ToolLibrary()  # Uses default
            >>> library = ToolLibrary('data/7235C_219.too')
            >>> len(library)
            27
        """
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

        This is a class method that uses the default tool library (data/7235C_219.too).
        For custom tool libraries, create an instance and call get() on it.

        Args:
            name: Tool name (case-insensitive, partial match supported)
            tool_no: Tool number from .too file

        Returns:
            MachiningTool instance if found, None otherwise

        Example:
            >>> # Direct access without instantiation
            >>> tool = ToolLibrary.get('Birdsmouth')
            >>> str(tool)
            "WZF(504,_VE,_V,_VA,_SD,_ANF,'1')"
            >>>
            >>> # Get by tool number
            >>> tool = ToolLibrary.get(tool_no=27)
            >>> tool.name
            'Birdsmouth'
            >>>
            >>> # For custom tool library, create instance
            >>> library = ToolLibrary('custom_tools.too')
            >>> tool = library.get_tool('CustomTool')
        """
        instance = cls._get_default_instance()
        return instance.get_tool(name=name, tool_no=tool_no)

    def get_tool(
        self, name: str = None, tool_no: int = None
    ) -> Optional[MachiningTool]:
        """Get tool by name or tool number from this library instance.

        Args:
            name: Tool name (case-insensitive, partial match supported)
            tool_no: Tool number from .too file

        Returns:
            MachiningTool instance if found, None otherwise

        Example:
            >>> library = ToolLibrary()
            >>> tool = library.get_tool('Birdsmouth')
            >>> str(tool)
            "WZF(504,_VE,_V,_VA,_SD,_ANF,'1')"
        """
        if name is not None:
            # Try exact match first (case-insensitive)
            tool = self._tools_by_name.get(name.lower())
            if tool:
                return tool

            # Try partial match
            name_lower = name.lower()
            for tool_name, tool in self._tools_by_name.items():
                if name_lower in tool_name:
                    return tool
            return None
        elif tool_no is not None:
            return self._tools_by_number.get(tool_no)
        else:
            raise ValueError("Must provide either name or tool_no")

    def list_tools(self) -> list[str]:
        """List all tool names in library.

        Returns:
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
                tool_no = config.getint(section, "ToolNo", fallback=-1)
                tool_type = config.getint(section, "ToolType", fallback=0)

                # Skip tools with invalid numbers
                if tool_no == -1:
                    continue

                # Determine holder type based on tool type
                # ToolType: 0=Schaft (cassette), 1=Drill (drill head), 2=Säge (saw blade), 3=Laser/Special
                if tool_type == 2:  # Saw blade
                    holder_type = ToolHolderType.BLADE
                    position = 201  # Standard saw blade position
                else:  # Cassette tools
                    holder_type = ToolHolderType.CASSETTE
                    # Use tool_no as position for cassette tools
                    position = tool_no

                # Create MachiningTool instance
                # Don't pass feedrates - let them default to None so HOPS macro variables are used
                tool = MachiningTool(
                    holder_type=holder_type,
                    position=position,
                    name=name,
                )

                # Register tool by name and number
                if name:
                    self._tools_by_name[name.lower()] = tool
                self._tools_by_number[tool_no] = tool
