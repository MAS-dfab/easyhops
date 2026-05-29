"""Unit tests for hop_core module."""

import math

import pytest
from easyhops.hop_core import (
    EasySnapXY,
    EasySnapZ,
    FinishedPart,
    HopsSystemVars,
    ParkMode,
    ParkPosition,
    VarsDefinition,
)


class TestEasySnapZ:
    """Tests for EasySnapZ enum."""

    def test_easy_snap_z_values(self):
        """Test EasySnapZ enum values."""
        assert EasySnapZ.TOP_EDGE == 0
        assert EasySnapZ.BOTTOM_EDGE == 1
        assert EasySnapZ.RELATIVE == 2


class TestEasySnapXY:
    """Tests for EasySnapXY enum."""

    def test_easy_snap_xy_values(self):
        """Test EasySnapXY enum values."""
        assert EasySnapXY.DISABLED == 0
        assert EasySnapXY.BOTTOM_LEFT == 1
        assert EasySnapXY.BOTTOM_CENTER == 2
        assert EasySnapXY.BOTTOM_RIGHT == 3
        assert EasySnapXY.CENTER_RIGHT == 4
        assert EasySnapXY.TOP_RIGHT == 5
        assert EasySnapXY.TOP_CENTER == 6
        assert EasySnapXY.TOP_LEFT == 7
        assert EasySnapXY.CENTER_LEFT == 8
        assert EasySnapXY.CENTER == 9


class TestVarsDefinition:
    """Tests for VarsDefinition class."""

    def test_vars_definition_init(self):
        """Test VarsDefinition initialization."""
        vars_def = VarsDefinition(dx=1000.0, dy=500.0, dz=50.0)
        assert vars_def.dx == 1000.0
        assert vars_def.dy == 500.0
        assert vars_def.dz == 50.0

    def test_vars_definition_str(self):
        """Test VarsDefinition.__str__() generates VARS section."""
        vars_def = VarsDefinition(dx=873.902, dy=140.0, dz=70.0)
        output = str(vars_def)
        assert "VARS" in output
        assert "DX := 873.902" in output
        assert "DY := 140" in output
        assert "DZ := 70" in output
        assert "START" in output

    def test_vars_definition_from_hop_line(self):
        """Test VarsDefinition.from_hop_line() parsing."""
        lines = [
            "VARS\n",
            "   DX := 873.902;\n",
            "   DY := 140;\n",
            "   DZ := 70;\n",
            "START\n",
        ]
        vars_def = VarsDefinition.from_hop_line(lines)
        assert vars_def.dx == pytest.approx(873.902)
        assert vars_def.dy == pytest.approx(140.0)
        assert vars_def.dz == pytest.approx(70.0)

    def test_vars_definition_from_hop_line_negative_values(self):
        """Test VarsDefinition.from_hop_line() with negative values."""
        lines = [
            "VARS\n",
            "   DX := -100.5;\n",
            "   DY := 200;\n",
            "   DZ := -50.25;\n",
        ]
        vars_def = VarsDefinition.from_hop_line(lines)
        assert vars_def.dx == pytest.approx(-100.5)
        assert vars_def.dy == pytest.approx(200.0)
        assert vars_def.dz == pytest.approx(-50.25)

    def test_vars_definition_from_hop_line_missing_values(self):
        """Test VarsDefinition.from_hop_line() with missing values defaults to 0."""
        lines = ["VARS\n", "START\n"]
        vars_def = VarsDefinition.from_hop_line(lines)
        assert vars_def.dx == 0.0
        assert vars_def.dy == 0.0
        assert vars_def.dz == 0.0


class TestFinishedPart:
    """Tests for FinishedPart class."""

    def test_finished_part_init_with_values(self):
        """Test FinishedPart initialization with explicit values."""
        fp = FinishedPart(dx=1000.0, dy=500.0, dz=50.0)
        assert fp.dx == 1000.0
        assert fp.dy == 500.0
        assert fp.dz == 50.0
        assert fp.rotation_flag == 0
        assert fp.offset_x == 0
        assert fp.offset_y == 0
        assert fp.offset_z == 0

    def test_finished_part_init_with_none(self):
        """Test FinishedPart initialization with None (uses VARS)."""
        fp = FinishedPart(dx=None, dy=None, dz=None)
        assert fp.dx is None
        assert fp.dy is None
        assert fp.dz is None

    def test_finished_part_init_with_rotation(self):
        """Test FinishedPart initialization with rotation flag."""
        fp = FinishedPart(dx=1000.0, dy=500.0, dz=50.0, rotation_flag=2)
        assert fp.rotation_flag == 2

    def test_finished_part_init_with_offsets(self):
        """Test FinishedPart initialization with offsets."""
        fp = FinishedPart(
            dx=1000.0,
            dy=500.0,
            dz=50.0,
            offset_x=10.5,
            offset_y=20.5,
            offset_z=5.0,
        )
        assert fp.offset_x == 10.5
        assert fp.offset_y == 20.5
        assert fp.offset_z == 5.0

    def test_finished_part_init_with_comment(self):
        """Test FinishedPart initialization with comment."""
        fp = FinishedPart(dx=1000.0, dy=500.0, dz=50.0, comment="Test comment")
        assert fp.comment == "Test comment"

    def test_finished_part_init_with_flags(self):
        """Test FinishedPart initialization with field linking and laser flags."""
        fp = FinishedPart(
            dx=1000.0,
            dy=500.0,
            dz=50.0,
            field_linking=True,
            activates_laser=True,
        )
        assert fp.field_linking is True
        assert fp.activates_laser is True

    def test_finished_part_str_with_values(self):
        """Test FinishedPart.__str__() with explicit values."""
        fp = FinishedPart(dx=1000.0, dy=500.0, dz=50.0)
        output = str(fp)
        assert "FERTIGTEIL(1000" in output
        assert "500" in output
        assert "50" in output

    def test_finished_part_str_with_vars(self):
        """Test FinishedPart.__str__() with VARS references."""
        fp = FinishedPart(dx=None, dy=None, dz=None)
        output = str(fp)
        assert "DX" in output
        assert "DY" in output
        assert "DZ" in output

    def test_finished_part_str_with_comment(self):
        """Test FinishedPart.__str__() includes comment."""
        fp = FinishedPart(dx=1000.0, dy=500.0, dz=50.0, comment="Test")
        output = str(fp)
        assert "'Test'" in output

    def test_finished_part_from_hop_line_with_values(self):
        """Test FinishedPart.from_hop_line() with explicit values."""
        line = "FERTIGTEIL(1000.0,500.0,50.0,0,0,0,0,0,,0,0,0)"
        fp = FinishedPart.from_hop_line(line)
        assert fp.dx == pytest.approx(1000.0)
        assert fp.dy == pytest.approx(500.0)
        assert fp.dz == pytest.approx(50.0)
        assert fp.rotation_flag == 0
        assert fp.empty_parameter == 0
        assert fp.offset_x == pytest.approx(0)
        assert fp.offset_y == pytest.approx(0)
        assert fp.offset_z == pytest.approx(0)
        assert fp.field_linking is False
        assert fp.activates_laser is False
        assert fp.stop_flag == 0

    def test_finished_part_from_hop_line_with_vars(self):
        """Test FinishedPart.from_hop_line() with VARS references."""
        line = "FERTIGTEIL(VARS DX,VARS DY,VARS DZ,0,0,0,0,0,,0,0,0)"
        fp = FinishedPart.from_hop_line(line)
        assert fp.dx is None
        assert fp.dy is None
        assert fp.dz is None

    def test_finished_part_from_hop_line_with_rotation(self):
        """Test FinishedPart.from_hop_line() with rotation flag."""
        line = "FERTIGTEIL(1000.0,500.0,50.0,2,0,0,0,0,,0,0,0)"
        fp = FinishedPart.from_hop_line(line)
        assert fp.rotation_flag == 2

    def test_finished_part_from_hop_line_with_offsets(self):
        """Test FinishedPart.from_hop_line() with offsets."""
        line = "FERTIGTEIL(1000.0,500.0,50.0,0,0,10.5,20.5,5.0,,0,0,0)"
        fp = FinishedPart.from_hop_line(line)
        assert fp.offset_x == pytest.approx(10.5)
        assert fp.offset_y == pytest.approx(20.5)
        assert fp.offset_z == pytest.approx(5.0)

    def test_finished_part_from_hop_line_with_comment(self):
        """Test FinishedPart.from_hop_line() with comment."""
        line = "FERTIGTEIL(1000.0,500.0,50.0,0,0,0,0,0,'Test comment',0,0,0)"
        fp = FinishedPart.from_hop_line(line)
        assert fp.comment == "Test comment"

    def test_finished_part_from_hop_line_with_flags(self):
        """Test FinishedPart.from_hop_line() with field linking and laser flags."""
        line = "FERTIGTEIL(1000.0,500.0,50.0,0,0,0,0,0,,1,1,3)"
        fp = FinishedPart.from_hop_line(line)
        assert fp.field_linking is True
        assert fp.activates_laser is True
        assert fp.stop_flag == 3

    def test_finished_part_from_hop_line_with_spaces(self):
        """Test FinishedPart.from_hop_line() handles spaces."""
        line = "FERTIGTEIL( 1000.0 , 500.0 , 50.0 , 0 , 0 , 0 , 0 , 0 ,  , 0 , 0 , 0 )"
        fp = FinishedPart.from_hop_line(line)
        assert fp.dx == pytest.approx(1000.0)
        assert fp.dy == pytest.approx(500.0)
        assert fp.dz == pytest.approx(50.0)

    def test_finished_part_from_hop_line_invalid(self):
        """Test FinishedPart.from_hop_line() with invalid input."""
        with pytest.raises(ValueError, match="Invalid FERTIGTEIL line"):
            FinishedPart.from_hop_line("INVALID(1,2,3)")


class TestParkMode:
    """Tests for ParkMode class."""

    def test_park_mode_init_defaults(self):
        """Test ParkMode initialization with defaults."""
        park = ParkPosition()
        assert park.mode == ParkMode.AUTOMATIC
        assert park.pos_x == 0
        assert park.pos_y == 0

    def test_park_mode_init_with_values(self):
        """Test ParkMode initialization with explicit values."""
        park = ParkPosition(mode=ParkMode(2), pos_x=100.5, pos_y=200.5)
        assert park.mode == ParkMode(2)
        assert park.pos_x == 100.5
        assert park.pos_y == 200.5

    def test_park_mode_str(self):
        """Test ParkMode.__str__() generates Park_V7 command."""
        park = ParkPosition(mode=ParkMode(11), pos_x=0, pos_y=0)
        output = str(park)
        assert output == "CALL Park_V7 ( VAL MODE:=11,POSX:=0,POSY:=0)"

    def test_park_mode_str_with_values(self):
        """Test ParkMode.__str__() with non-default values."""
        park = ParkPosition(mode=ParkMode(2), pos_x=100.5, pos_y=200.5)
        output = str(park)
        assert "MODE:=2" in output
        assert "POSX:=100.5" in output
        assert "POSY:=200.5" in output

    def test_park_mode_from_hop_line(self):
        """Test ParkMode.from_hop_line() parsing."""
        line = "CALL Park_V7 ( VAL MODE:=11,POSX:=0,POSY:=0)"
        park = ParkPosition.from_hop_line(line)
        assert park.mode == ParkMode(11)
        assert park.pos_x == pytest.approx(0)
        assert park.pos_y == pytest.approx(0)

    def test_park_mode_from_hop_line_with_values(self):
        """Test ParkMode.from_hop_line() with non-default values."""
        line = "CALL Park_V7 ( VAL MODE:=2,POSX:=100.5,POSY:=200.5)"
        park = ParkPosition.from_hop_line(line)
        assert park.mode == ParkMode(2)
        assert park.pos_x == pytest.approx(100.5)
        assert park.pos_y == pytest.approx(200.5)

    def test_park_mode_from_hop_line_with_spaces(self):
        """Test ParkMode.from_hop_line() handles various spacing."""
        line = "CALL Park_V7 (  VAL  MODE:=11 , POSX:=0 , POSY:=0 )"
        park = ParkPosition.from_hop_line(line)
        assert park.mode == ParkMode(11)
        assert park.pos_x == pytest.approx(0)
        assert park.pos_y == pytest.approx(0)

    def test_park_mode_from_hop_line_negative_values(self):
        """Test ParkMode.from_hop_line() with negative positions."""
        line = "CALL Park_V7 ( VAL MODE:=11,POSX:=-50.5,POSY:=-100.5)"
        park = ParkPosition.from_hop_line(line)
        assert park.mode == ParkMode(11)
        assert park.pos_x == pytest.approx(-50.5)
        assert park.pos_y == pytest.approx(-100.5)

    def test_park_mode_from_hop_line_invalid(self):
        """Test ParkMode.from_hop_line() with invalid input."""
        with pytest.raises(ValueError, match="Invalid Park_V7 line"):
            ParkPosition.from_hop_line("INVALID(1,2,3)")

    def test_park_mode_round_trip(self):
        """Test ParkMode round-trip conversion (to string and back)."""
        park1 = ParkPosition(mode=ParkMode(2), pos_x=100.5, pos_y=200.5)
        line = str(park1)
        park2 = ParkPosition.from_hop_line(line)
        assert park2.mode == park1.mode
        assert park2.pos_x == pytest.approx(park1.pos_x)
        assert park2.pos_y == pytest.approx(park1.pos_y)


class TestVarsDefinitionRoundTrip:
    """Test round-trip conversions for VarsDefinition."""

    def test_vars_round_trip(self):
        """Test VarsDefinition round-trip is not directly possible due to format."""
        # Note: VarsDefinition.__str__() produces multi-line format,
        # while from_hop_line() expects list of lines.
        vars1 = VarsDefinition(dx=873.902, dy=140.0, dz=70.0)
        lines = str(vars1).split("\n")
        # Need to filter out empty lines and add newlines back
        lines = [line + "\n" for line in lines if line.strip()]
        vars2 = VarsDefinition.from_hop_line(lines)
        assert vars2.dx == pytest.approx(vars1.dx)
        assert vars2.dy == pytest.approx(vars1.dy)
        assert vars2.dz == pytest.approx(vars1.dz)


class TestFinishedPartRoundTrip:
    """Test round-trip conversions for FinishedPart."""

    def test_finished_part_round_trip_with_values(self):
        """Test FinishedPart round-trip with explicit values."""
        fp1 = FinishedPart(
            dx=1000.0,
            dy=500.0,
            dz=50.0,
            rotation_flag=2,
            offset_x=10.5,
            offset_y=20.5,
            offset_z=5.0,
            field_linking=True,
            activates_laser=True,
            stop_flag=3,
        )
        line = str(fp1)
        fp2 = FinishedPart.from_hop_line(line)
        assert fp2.dx == pytest.approx(fp1.dx)
        assert fp2.dy == pytest.approx(fp1.dy)
        assert fp2.dz == pytest.approx(fp1.dz)
        assert fp2.rotation_flag == fp1.rotation_flag
        assert fp2.offset_x == pytest.approx(fp1.offset_x)
        assert fp2.offset_y == pytest.approx(fp1.offset_y)
        assert fp2.offset_z == pytest.approx(fp1.offset_z)
        assert fp2.field_linking == fp1.field_linking
        assert fp2.activates_laser == fp1.activates_laser
        assert fp2.stop_flag == fp1.stop_flag


class TestHopsSystemVars:
    """Tests for HopsSystemVars dual-mode (macro string + numeric arithmetic)."""

    def setup_method(self):
        """Reset all numeric values before each test."""
        HopsSystemVars.reset_all()

    def test_str_returns_macro(self):
        """str() always returns the HOPS macro string, unaffected by set()."""
        assert str(HopsSystemVars.TOOL_DIAMETER) == "_WZD"
        HopsSystemVars.TOOL_DIAMETER.set(61.092)
        assert str(HopsSystemVars.TOOL_DIAMETER) == "_WZD"

    def test_equality_unchanged_after_set(self):
        """String equality checks continue to work after set()."""
        assert HopsSystemVars.TOOL_DIAMETER == "_WZD"
        HopsSystemVars.TOOL_DIAMETER.set(200.0)
        assert HopsSystemVars.TOOL_DIAMETER == "_WZD"
        assert HopsSystemVars.Y_DIM == "_RY"

    def test_numeric_raises_before_set(self):
        """Accessing .numeric raises ValueError when no value has been set."""
        with pytest.raises(ValueError, match="HopsSystemVars.TOOL_DIAMETER"):
            _ = HopsSystemVars.TOOL_DIAMETER.numeric

    def test_set_and_numeric(self):
        """set() stores the value and numeric returns it."""
        HopsSystemVars.TOOL_DIAMETER.set(61.092)
        assert HopsSystemVars.TOOL_DIAMETER.numeric == pytest.approx(61.092)

    def test_negation(self):
        """Unary negation returns a float."""
        HopsSystemVars.TOOL_DIAMETER.set(61.092)
        result = -HopsSystemVars.TOOL_DIAMETER
        assert result == pytest.approx(-61.092)
        assert isinstance(result, float)

    def test_subtraction(self):
        """Subtraction with a float returns a float."""
        HopsSystemVars.Y_DIM.set(100.0)
        assert HopsSystemVars.Y_DIM - 30.0 == pytest.approx(70.0)
        assert 130.0 - HopsSystemVars.Y_DIM == pytest.approx(30.0)

    def test_division(self):
        """Division returns a float."""
        HopsSystemVars.Y_DIM.set(100.0)
        result = HopsSystemVars.Y_DIM / math.sin(math.pi / 2)
        assert result == pytest.approx(100.0)
        assert isinstance(result, float)

    def test_addition_with_float(self):
        """Addition with a float returns a float (not string concatenation)."""
        HopsSystemVars.Y_DIM.set(100.0)
        assert HopsSystemVars.Y_DIM + 50.0 == pytest.approx(150.0)
        assert 50.0 + HopsSystemVars.Y_DIM == pytest.approx(150.0)

    def test_float_conversion(self):
        """float() returns the numeric value."""
        HopsSystemVars.TOOL_RADIUS.set(30.546)
        assert float(HopsSystemVars.TOOL_RADIUS) == pytest.approx(30.546)

    def test_reset(self):
        """reset() removes a single variable's numeric value."""
        HopsSystemVars.TOOL_DIAMETER.set(61.0)
        HopsSystemVars.TOOL_DIAMETER.reset()
        with pytest.raises(ValueError):
            _ = HopsSystemVars.TOOL_DIAMETER.numeric

    def test_reset_all(self):
        """reset_all() clears every variable."""
        HopsSystemVars.TOOL_DIAMETER.set(61.0)
        HopsSystemVars.Y_DIM.set(100.0)
        HopsSystemVars.reset_all()
        with pytest.raises(ValueError):
            _ = HopsSystemVars.TOOL_DIAMETER.numeric
        with pytest.raises(ValueError):
            _ = HopsSystemVars.Y_DIM.numeric

    def test_isinstance_str_still_true(self):
        """HopsSystemVars members must still pass isinstance(v, str) checks in _fmt()."""
        HopsSystemVars.TOOL_DIAMETER.set(61.0)
        assert isinstance(HopsSystemVars.TOOL_DIAMETER, str)
        assert isinstance(HopsSystemVars.Y_DIM, str)
