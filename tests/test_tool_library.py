"""
Unit tests for tool_library module

Tests for HopsSystemVars, ToolCallType, MachiningTool, and ToolLibrary classes.
"""

import pytest

from easyhops.tool_library import HopsSystemVars
from easyhops.tool_library import MachiningTool
from easyhops.tool_library import ToolCallType
from easyhops.tool_library import ToolLibrary


# ==========================================================================
# Fixtures
# ==========================================================================


@pytest.fixture
def router_tool():
    return MachiningTool(tool_type=ToolCallType.ROUTER, position=504, name="Birdsmouth")


@pytest.fixture
def saw_tool():
    return MachiningTool(tool_type=ToolCallType.SAW, position=201, name="Saw blade")


@pytest.fixture
def tool_library():
    return ToolLibrary()


# ==========================================================================
# HopsSystemVars Tests
# ==========================================================================


class TestHopsSystemVars:
    """Test HopsSystemVars enum"""

    def test_system_vars_values(self):
        """Test that system variable values match HOPS format"""
        assert HopsSystemVars.LEAD_IN_FEEDRATE == "_VE"
        assert HopsSystemVars.FEEDRATE == "_V"
        assert HopsSystemVars.LEAD_OUT_FEEDRATE == "_VA"
        assert HopsSystemVars.MOTOR_SPEED == "_SD"
        assert HopsSystemVars.LEAD_IN_OUT_FACTOR == "_ANF"
        assert HopsSystemVars.TOOL_DIAMETER == "_WZD"
        assert HopsSystemVars.TOOL_RADIUS == "_WZR"
        assert HopsSystemVars.SAW_WIDTH == "_SBB"


# ==========================================================================
# ToolCallType Tests
# ==========================================================================


class TestToolCallType:
    """Test ToolCallType enum"""

    def test_tool_types(self):
        """Test tool type values"""
        assert ToolCallType.ROUTER == "WZF"
        assert ToolCallType.SAW == "WZS"
        assert ToolCallType.DRILLER == "WZB"


# ==========================================================================
# MachiningTool Tests
# ==========================================================================


def test_tool_creation_with_defaults():
    """Test creating tool with default parameters."""
    tool = MachiningTool(tool_type=ToolCallType.ROUTER, position=504, name="Test Tool")

    assert tool.tool_type == ToolCallType.ROUTER
    assert tool.position == 504
    assert tool.name == "Test Tool"
    assert tool.lead_in_feedrate is None
    assert tool.feedrate is None
    assert tool.head_id == "1"


def test_tool_string_with_defaults(router_tool):
    """Test tool string output with default system variables."""
    tool = MachiningTool(tool_type=ToolCallType.ROUTER, position=504)

    result = str(tool)
    assert result == "WZF(504,_VE,_V,_VA,_SD,_ANF,'1')"


def test_tool_string_with_overrides():
    """Test tool string output with parameter overrides."""
    tool = MachiningTool(
        tool_type=ToolCallType.ROUTER,
        position=504,
        lead_in_feedrate=3000,
        feedrate=4000,
        lead_out_feedrate=5000,
        motor_speed=6000,
        lead_in_out_factor=1.5,
        head_id="2",
    )

    result = str(tool)
    assert result == "WZF(504,3000,4000,5000,6000,1.50,'2')"


def test_tool_string_partial_overrides(saw_tool):
    """Test tool string with some parameters overridden."""
    tool = MachiningTool(tool_type=ToolCallType.SAW, position=201, feedrate=7000, motor_speed=4000)

    result = str(tool)
    assert result == "WZS(201,_VE,7000,_VA,4000,_ANF,'1')"


def test_tool_repr(router_tool):
    """Test tool repr output."""
    result = repr(router_tool)
    assert "ROUTER" in result
    assert "504" in result
    assert "Birdsmouth" in result


def test_get_code():
    """Test tool code generation."""
    router = MachiningTool(tool_type=ToolCallType.ROUTER, position=504)
    saw = MachiningTool(tool_type=ToolCallType.SAW, position=201)
    driller = MachiningTool(tool_type=ToolCallType.DRILLER, position=603)

    assert router.get_code() == "WZF504"
    assert saw.get_code() == "WZS201"
    assert driller.get_code() == "WZB603"


def test_from_code_router():
    """Test parsing tool code for router."""
    tool = MachiningTool.from_code("WZF504")

    assert tool.tool_type == ToolCallType.ROUTER
    assert tool.position == 504


def test_from_code_saw():
    """Test parsing tool code for saw."""
    tool = MachiningTool.from_code("WZS201")

    assert tool.tool_type == ToolCallType.SAW
    assert tool.position == 201


def test_from_code_driller():
    """Test parsing tool code for driller."""
    tool = MachiningTool.from_code("WZB603")

    assert tool.tool_type == ToolCallType.DRILLER
    assert tool.position == 603


def test_from_code_with_kwargs():
    """Test parsing tool code with additional parameters."""
    tool = MachiningTool.from_code("WZF504", feedrate=3500, name="Custom Tool")

    assert tool.position == 504
    assert tool.feedrate == 3500
    assert tool.name == "Custom Tool"


def test_from_code_invalid():
    """Test parsing invalid tool code."""
    with pytest.raises(ValueError):
        MachiningTool.from_code("INVALID123")


def test_different_tool_types():
    """Test creating different tool types."""
    router = MachiningTool(tool_type=ToolCallType.ROUTER, position=504)
    saw = MachiningTool(tool_type=ToolCallType.SAW, position=201)
    driller = MachiningTool(tool_type=ToolCallType.DRILLER, position=603)

    assert "WZF" in str(router)
    assert "WZS" in str(saw)
    assert "WZB" in str(driller)


# ==========================================================================
# ToolLibrary Tests
# ==========================================================================


def test_library_initialization(tool_library):
    """Test creating tool library with default file."""
    assert tool_library is not None
    assert len(tool_library) > 0


def test_get_tool_by_name():
    """Test retrieving tool by name."""
    tool = ToolLibrary.get(name="Birdsmouth")

    assert tool is not None
    assert tool.name == "Birdsmouth"
    assert tool.position == 504


def test_get_tool_by_name_case_insensitive():
    """Test name lookup is case-insensitive."""
    tool1 = ToolLibrary.get(name="Birdsmouth")
    tool2 = ToolLibrary.get(name="birdsmouth")
    tool3 = ToolLibrary.get(name="BIRDSMOUTH")

    assert tool1 is not None
    assert tool2 is not None
    assert tool3 is not None
    assert tool1.position == tool2.position == tool3.position


def test_get_tool_by_number():
    """Test retrieving tool by ID number."""
    tool = ToolLibrary.get(tool_no=504)

    assert tool is not None
    assert tool.position == 504
    assert "Birdsmouth" in tool.name


def test_get_tool_by_partial_name():
    """Test retrieving tool by partial name match."""
    tool = ToolLibrary.get(name="Birds")

    assert tool is not None
    assert "Birdsmouth" in tool.name


def test_get_tool_by_name_and_number_matching():
    """Test retrieving tool with both name and number (matching)."""
    tool = ToolLibrary.get(name="Birdsmouth", tool_no=504)

    assert tool is not None
    assert tool.position == 504


def test_get_tool_by_name_and_number_mismatched():
    """Test error when name and number don't match."""
    with pytest.raises(ValueError):
        ToolLibrary.get(name="Birdsmouth", tool_no=201)


def test_get_tool_nonexistent_name():
    """Test retrieving non-existent tool by name."""
    tool = ToolLibrary.get(name="NonExistentTool12345")

    assert tool is None


def test_get_tool_nonexistent_number():
    """Test retrieving non-existent tool by number."""
    tool = ToolLibrary.get(tool_no=99999)

    assert tool is None


def test_get_tool_no_parameters():
    """Test error when neither name nor number provided."""
    with pytest.raises(ValueError):
        ToolLibrary.get()


def test_library_repr(tool_library):
    """Test library string representation."""
    result = repr(tool_library)

    assert "ToolLibrary" in result
    assert "tools=" in result


def test_library_length(tool_library):
    """Test library length."""
    assert len(tool_library) > 0
    assert isinstance(len(tool_library), int)


def test_list_tools(tool_library):
    """Test listing all tool names."""
    tools = tool_library.list_tools()

    assert isinstance(tools, list)
    assert len(tools) > 0
    assert "birdsmouth" in tools


def test_saw_blade_tool():
    """Test retrieving saw blade tool."""
    tool = ToolLibrary.get(name="saw blade")

    assert tool is not None
    assert tool.tool_type == ToolCallType.SAW


def test_castor_tool():
    """Test retrieving Castor tool."""
    tool = ToolLibrary.get(name="Castor")

    assert tool is not None
    assert tool.tool_type == ToolCallType.ROUTER


def test_tool_library_singleton_pattern():
    """Test that default instance is reused."""
    tool1 = ToolLibrary.get(name="Birdsmouth")
    tool2 = ToolLibrary.get(name="Birdsmouth")

    # Should return the same tool instance from cached library
    assert tool1.position == tool2.position
    assert tool1.name == tool2.name


def test_custom_library_instance(tool_library):
    """Test creating custom library instance."""
    tool = tool_library.get_tool(name="Birdsmouth")

    assert tool is not None
    assert tool.position == 504


def test_tool_output_format():
    """Test that retrieved tools generate correct HOPS commands."""
    tool = ToolLibrary.get(tool_no=504)

    assert tool is not None
    output = str(tool)
    assert output.startswith("WZF(504,")
    assert "_VE" in output
    assert "_V" in output
    assert "_VA" in output
    assert "_SD" in output
    assert "_ANF" in output


# ==========================================================================
# Type Validation Tests
# ==========================================================================


def test_tool_type_validation():
    """Test that tool_type setter validates ToolCallType."""
    with pytest.raises(TypeError, match="tool_type must be ToolCallType"):
        MachiningTool(tool_type="WZF", position=504)


def test_position_type_validation():
    """Test that position setter validates int type."""
    with pytest.raises(TypeError, match="position must be int"):
        MachiningTool(tool_type=ToolCallType.ROUTER, position="504")


def test_position_value_validation():
    """Test that position setter validates non-negative values."""
    with pytest.raises(ValueError, match="position must be non-negative"):
        MachiningTool(tool_type=ToolCallType.ROUTER, position=-1)


def test_feedrate_type_validation():
    """Test that feedrate setter validates number type."""
    with pytest.raises(TypeError, match="feedrate must be a number or None"):
        MachiningTool(tool_type=ToolCallType.ROUTER, position=504, feedrate="3000")


def test_feedrate_value_validation():
    """Test that feedrate setter validates non-negative values."""
    with pytest.raises(ValueError, match="feedrate must be non-negative"):
        MachiningTool(tool_type=ToolCallType.ROUTER, position=504, feedrate=-100)


def test_lead_in_feedrate_validation():
    """Test that lead_in_feedrate setter validates correctly."""
    with pytest.raises(TypeError, match="lead_in_feedrate must be a number or None"):
        MachiningTool(tool_type=ToolCallType.ROUTER, position=504, lead_in_feedrate="3000")

    with pytest.raises(ValueError, match="lead_in_feedrate must be non-negative"):
        MachiningTool(tool_type=ToolCallType.ROUTER, position=504, lead_in_feedrate=-100)


def test_lead_out_feedrate_validation():
    """Test that lead_out_feedrate setter validates correctly."""
    with pytest.raises(TypeError, match="lead_out_feedrate must be a number or None"):
        MachiningTool(tool_type=ToolCallType.ROUTER, position=504, lead_out_feedrate="3000")

    with pytest.raises(ValueError, match="lead_out_feedrate must be non-negative"):
        MachiningTool(tool_type=ToolCallType.ROUTER, position=504, lead_out_feedrate=-100)


def test_motor_speed_validation():
    """Test that motor_speed setter validates correctly."""
    with pytest.raises(TypeError, match="motor_speed must be a number or None"):
        MachiningTool(tool_type=ToolCallType.ROUTER, position=504, motor_speed="12000")

    with pytest.raises(ValueError, match="motor_speed must be non-negative"):
        MachiningTool(tool_type=ToolCallType.ROUTER, position=504, motor_speed=-1000)


def test_lead_in_out_factor_validation():
    """Test that lead_in_out_factor setter validates correctly."""
    with pytest.raises(TypeError, match="lead_in_out_factor must be a number or None"):
        MachiningTool(tool_type=ToolCallType.ROUTER, position=504, lead_in_out_factor="1.5")

    with pytest.raises(ValueError, match="lead_in_out_factor must be non-negative"):
        MachiningTool(tool_type=ToolCallType.ROUTER, position=504, lead_in_out_factor=-0.5)


def test_head_id_validation():
    """Test that head_id setter validates str type."""
    with pytest.raises(TypeError, match="head_id must be str"):
        MachiningTool(tool_type=ToolCallType.ROUTER, position=504, head_id=1)


def test_name_validation():
    """Test that name setter validates str type."""
    with pytest.raises(TypeError, match="name must be str"):
        MachiningTool(tool_type=ToolCallType.ROUTER, position=504, name=123)


def test_accepts_int_converts_to_float():
    """Test that numeric parameters accept integers and convert to float."""
    tool = MachiningTool(
        tool_type=ToolCallType.ROUTER,
        position=504,
        feedrate=3000,
        lead_in_feedrate=2500,
        lead_out_feedrate=2500,
        motor_speed=12000,
        lead_in_out_factor=1,
    )

    assert isinstance(tool.feedrate, float)
    assert isinstance(tool.lead_in_feedrate, float)
    assert isinstance(tool.lead_out_feedrate, float)
    assert isinstance(tool.motor_speed, float)
    assert isinstance(tool.lead_in_out_factor, float)
    assert tool.feedrate == 3000.0
    assert tool.lead_in_out_factor == 1.0


def test_property_setters_validate(router_tool):
    """Test that property setters validate after initialization."""
    with pytest.raises(TypeError, match="feedrate must be a number or None"):
        router_tool.feedrate = "invalid"

    with pytest.raises(ValueError, match="position must be non-negative"):
        router_tool.position = -50


def test_none_values_accepted():
    """Test that None is accepted for optional numeric parameters."""
    tool = MachiningTool(
        tool_type=ToolCallType.ROUTER,
        position=504,
        feedrate=None,
        lead_in_feedrate=None,
        lead_out_feedrate=None,
        motor_speed=None,
        lead_in_out_factor=None,
    )

    assert tool.feedrate is None
    assert tool.lead_in_feedrate is None
    assert tool.lead_out_feedrate is None
    assert tool.motor_speed is None
    assert tool.lead_in_out_factor is None


def test_formatting_integers_and_factor():
    """Test that feedrates format as integers and factor with 2 decimals."""
    tool = MachiningTool(
        tool_type=ToolCallType.ROUTER,
        position=504,
        feedrate=3000.7,
        lead_in_feedrate=2500.3,
        lead_out_feedrate=2800.9,
        motor_speed=12000.5,
        lead_in_out_factor=1.567,
    )

    result = str(tool)
    assert "3000" in result  # Should format as integer
    assert "2500" in result
    assert "2800" in result
    assert "12000" in result
    assert "1.57" in result  # Should format with 2 decimals
