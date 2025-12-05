"""Unit tests for machining_commands module."""

import pytest

from easyhops.machining_commands import (
    CompensationMode,
    DrillingOperation,
    EndPoint,
    G01,
    LeadInOutMode,
    MillingOperation,
    ProcessMode,
    SawingOperation,
    StartPoint,
)
from easyhops.hop_core import EasySnapXY, EasySnapZ


class TestCompensationMode:
    """Tests for CompensationMode enum."""

    def test_compensation_mode_values(self):
        """Test CompensationMode enum values."""
        assert CompensationMode.CENTER == 0
        assert CompensationMode.LEFT == 1
        assert CompensationMode.RIGHT == 2


class TestLeadInOutMode:
    """Tests for LeadInOutMode enum."""

    def test_lead_in_out_mode_values(self):
        """Test LeadInOutMode enum values."""
        assert LeadInOutMode.NONE == 0
        assert LeadInOutMode.LINEAR == 1
        assert LeadInOutMode.TANGENT == 2
        assert LeadInOutMode.LATERAL == 3


class TestProcessMode:
    """Tests for ProcessMode enum."""

    def test_process_mode_values(self):
        """Test ProcessMode enum values."""
        assert ProcessMode.NO_CHANGE == 0
        assert ProcessMode.WITH_ROTATION == 1
        assert ProcessMode.AGAINST_ROTATION == 2
        assert ProcessMode.WITH_ROTATION_MIRROR == 3
        assert ProcessMode.AGAINST_ROTATION_MIRROR == 4


class TestSawingOperation:
    """Tests for SawingOperation class."""

    def test_sawing_operation_init(self):
        """Test SawingOperation initialization."""
        saw = SawingOperation(
            sx=100.0,
            sy=200.0,
            sz=-50.0,
            ex=300.0,
            ey=400.0,
            ez=-50.0,
        )
        assert saw.sx == 100.0
        assert saw.sy == 200.0
        assert saw.sz == -50.0
        assert saw.ex == 300.0
        assert saw.ey == 400.0
        assert saw.ez == -50.0

    def test_sawing_operation_with_optional_params(self):
        """Test SawingOperation with optional parameters."""
        saw = SawingOperation(
            sx=100.0,
            sy=200.0,
            sz=-50.0,
            ex=300.0,
            ey=400.0,
            ez=-50.0,
            radius_compensation=CompensationMode.LEFT,
            fit_in=False,
            lead_in_out=5.0,
            process_mode=ProcessMode.WITH_ROTATION,
            tilt_angle=-7.5,
            z_level=10.0,
        )
        assert saw.radius_compensation == CompensationMode.LEFT
        assert saw.fit_in is False
        assert saw.lead_in_out == 5.0
        assert saw.process_mode == ProcessMode.WITH_ROTATION
        assert saw.tilt_angle == -7.5
        assert saw.z_level == 10.0

    def test_sawing_coordinate_setters_type_validation(self):
        """Test coordinate setters validate type."""
        saw = SawingOperation(0, 0, 0, 0, 0, 0)

        with pytest.raises(TypeError, match="sx must be a number"):
            saw.sx = "invalid"
        with pytest.raises(TypeError, match="sy must be a number"):
            saw.sy = "invalid"
        with pytest.raises(TypeError, match="sz must be a number"):
            saw.sz = "invalid"
        with pytest.raises(TypeError, match="ex must be a number"):
            saw.ex = "invalid"
        with pytest.raises(TypeError, match="ey must be a number"):
            saw.ey = "invalid"
        with pytest.raises(TypeError, match="ez must be a number"):
            saw.ez = "invalid"

    def test_sawing_radius_compensation_setter_accepts_enum(self):
        """Test radius_compensation setter accepts CompensationMode enum."""
        saw = SawingOperation(0, 0, 0, 0, 0, 0)
        saw.radius_compensation = CompensationMode.RIGHT
        assert saw.radius_compensation == CompensationMode.RIGHT

    def test_sawing_radius_compensation_setter_accepts_int(self):
        """Test radius_compensation setter accepts int and validates range."""
        saw = SawingOperation(0, 0, 0, 0, 0, 0)
        saw.radius_compensation = 1
        assert saw.radius_compensation == CompensationMode.LEFT

    def test_sawing_radius_compensation_setter_validates_range(self):
        """Test radius_compensation setter validates range 0-2."""
        saw = SawingOperation(0, 0, 0, 0, 0, 0)

        with pytest.raises(ValueError, match="radius_compensation must be between 0 and 2"):
            saw.radius_compensation = 3
        with pytest.raises(ValueError, match="radius_compensation must be between 0 and 2"):
            saw.radius_compensation = -1

    def test_sawing_process_mode_setter_accepts_enum(self):
        """Test process_mode setter accepts ProcessMode enum."""
        saw = SawingOperation(0, 0, 0, 0, 0, 0)
        saw.process_mode = ProcessMode.AGAINST_ROTATION
        assert saw.process_mode == ProcessMode.AGAINST_ROTATION

    def test_sawing_process_mode_setter_accepts_int(self):
        """Test process_mode setter accepts int and validates range."""
        saw = SawingOperation(0, 0, 0, 0, 0, 0)
        saw.process_mode = 2
        assert saw.process_mode == ProcessMode.AGAINST_ROTATION

    def test_sawing_process_mode_setter_validates_range(self):
        """Test process_mode setter validates range 0-4."""
        saw = SawingOperation(0, 0, 0, 0, 0, 0)

        with pytest.raises(ValueError, match="process_mode must be between 0 and 4"):
            saw.process_mode = 5
        with pytest.raises(ValueError, match="process_mode must be between 0 and 4"):
            saw.process_mode = -1

    def test_sawing_fit_in_setter_validates_bool(self):
        """Test fit_in setter validates bool type."""
        saw = SawingOperation(0, 0, 0, 0, 0, 0)

        with pytest.raises(TypeError, match="fit_in must be bool"):
            saw.fit_in = 1
        with pytest.raises(TypeError, match="fit_in must be bool"):
            saw.fit_in = "true"

    def test_sawing_easy_snap_xy_setter_accepts_enum(self):
        """Test easy_snap_xy setters accept EasySnapXY enum."""
        saw = SawingOperation(0, 0, 0, 0, 0, 0)
        saw.easy_snap_xy_start = EasySnapXY.DISABLED
        saw.easy_snap_xy_end = EasySnapXY.DISABLED
        assert saw.easy_snap_xy_start == 0
        assert saw.easy_snap_xy_end == 0

    def test_sawing_easy_snap_xy_setter_validates_range(self):
        """Test easy_snap_xy setters validate range 0-9."""
        saw = SawingOperation(0, 0, 0, 0, 0, 0)

        with pytest.raises(ValueError, match="easy_snap_xy_start must be between 0 and 9"):
            saw.easy_snap_xy_start = 10
        with pytest.raises(ValueError, match="easy_snap_xy_end must be between 0 and 9"):
            saw.easy_snap_xy_end = -1

    def test_sawing_easy_snap_z_setter_validates_range(self):
        """Test easy_snap_z setter validates range 0-2."""
        saw = SawingOperation(0, 0, 0, 0, 0, 0)

        with pytest.raises(ValueError, match="easy_snap_z must be between 0 and 2"):
            saw.easy_snap_z = 3
        with pytest.raises(ValueError, match="easy_snap_z must be between 0 and 2"):
            saw.easy_snap_z = -1

    def test_sawing_to_line(self):
        """Test SawingOperation._to_line() formatting."""
        saw = SawingOperation(
            sx=100,
            sy=200,
            sz=-50.5,
            ex=300,
            ey=400,
            ez=-50.5,
            fit_in=True,
            tilt_angle=-7.57,
        )
        line = saw._to_line()
        assert line.startswith("SAEGEN(")
        assert "100," in line
        assert "200," in line
        assert "-50.5" in line
        assert "-7.57" in line

    def test_sawing_str(self):
        """Test SawingOperation.__str__() calls _to_line()."""
        saw = SawingOperation(100, 200, -50, 300, 400, -50)
        assert str(saw) == saw._to_line()

    def test_sawing_repr(self):
        """Test SawingOperation.__repr__()."""
        saw = SawingOperation(100, 200, -50, 300, 400, -50, tilt_angle=-7.5)
        repr_str = repr(saw)
        assert "SawingOperation" in repr_str
        assert "100.0" in repr_str
        assert "200.0" in repr_str
        assert "-7.5" in repr_str

    def test_sawing_from_hop_line(self):
        """Test SawingOperation.from_hop_line() parsing."""
        line = "SAEGEN(852.354,-0.428,-70.735, 849.565,139.941,-70.735, 0,0,0, 1,-7.57, 0,0,0, 2,0,0)"
        saw = SawingOperation.from_hop_line(line)

        assert saw.sx == pytest.approx(852.354)
        assert saw.sy == pytest.approx(-0.428)
        assert saw.sz == pytest.approx(-70.735)
        assert saw.ex == pytest.approx(849.565)
        assert saw.ey == pytest.approx(139.941)
        assert saw.ez == pytest.approx(-70.735)
        assert saw.fit_in is True
        assert saw.tilt_angle == pytest.approx(-7.57)

    def test_sawing_from_hop_line_invalid(self):
        """Test SawingOperation.from_hop_line() with invalid input."""
        with pytest.raises(ValueError, match="Invalid SAEGEN line"):
            SawingOperation.from_hop_line("INVALID(1,2,3)")


class TestDrillingOperation:
    """Tests for DrillingOperation class."""

    def test_drilling_operation_init(self):
        """Test DrillingOperation initialization."""
        drill = DrillingOperation(x=100.0, y=200.0, z=50.0, depth=-30.0, diameter=10.0)
        assert drill.x == 100.0
        assert drill.y == 200.0
        assert drill.z == 50.0
        assert drill.depth == -30.0
        assert drill.diameter == 10.0

    def test_drilling_operation_with_none_diameter(self):
        """Test DrillingOperation with None diameter (tool default)."""
        drill = DrillingOperation(x=100.0, y=200.0, z=50.0)
        assert drill.diameter is None

    def test_drilling_operation_with_angles(self):
        """Test DrillingOperation with rotation and tilt angles."""
        drill = DrillingOperation(x=100.0, y=200.0, z=50.0, rotation=45.0, tilt=30.0)
        assert drill.rotation == 45.0
        assert drill.tilt == 30.0

    def test_drilling_coordinate_setters_type_validation(self):
        """Test coordinate setters validate type."""
        drill = DrillingOperation(0, 0, 0)

        with pytest.raises(TypeError, match="x must be a number"):
            drill.x = "invalid"
        with pytest.raises(TypeError, match="y must be a number"):
            drill.y = "invalid"
        with pytest.raises(TypeError, match="z must be a number"):
            drill.z = "invalid"

    def test_drilling_diameter_setter_validates_positive(self):
        """Test diameter setter validates positive values."""
        drill = DrillingOperation(0, 0, 0)

        drill.diameter = 10.0
        assert drill.diameter == 10.0

        drill.diameter = None
        assert drill.diameter is None

        with pytest.raises(ValueError, match="diameter must be positive"):
            drill.diameter = 0
        with pytest.raises(ValueError, match="diameter must be positive"):
            drill.diameter = -5

    def test_drilling_rotation_setter_validates_range(self):
        """Test rotation setter validates range 0-180."""
        drill = DrillingOperation(0, 0, 0)

        drill.rotation = 0
        assert drill.rotation == 0
        drill.rotation = 180
        assert drill.rotation == 180
        drill.rotation = 90
        assert drill.rotation == 90

        with pytest.raises(ValueError, match="rotation must be between 0 and 180 degrees"):
            drill.rotation = 181
        with pytest.raises(ValueError, match="rotation must be between 0 and 180 degrees"):
            drill.rotation = -1

    def test_drilling_tilt_setter_validates_range(self):
        """Test tilt setter validates range -90 to 90."""
        drill = DrillingOperation(0, 0, 0)

        drill.tilt = -90
        assert drill.tilt == -90
        drill.tilt = 90
        assert drill.tilt == 90
        drill.tilt = 0
        assert drill.tilt == 0

        with pytest.raises(ValueError, match="tilt must be between -90 and 90 degrees"):
            drill.tilt = 91
        with pytest.raises(ValueError, match="tilt must be between -90 and 90 degrees"):
            drill.tilt = -91

    def test_drilling_drilling_flags_setter_validates_int(self):
        """Test drilling_flags setter validates int type."""
        drill = DrillingOperation(0, 0, 0)

        with pytest.raises(TypeError, match="drilling_flags must be int"):
            drill.drilling_flags = 1.5
        with pytest.raises(TypeError, match="drilling_flags must be int"):
            drill.drilling_flags = "0"

    def test_drilling_easy_snap_xy_setter_accepts_enum(self):
        """Test easy_snap_xy setter accepts EasySnapXY enum."""
        drill = DrillingOperation(0, 0, 0)
        drill.easy_snap_xy = EasySnapXY.DISABLED
        assert drill.easy_snap_xy == 0

    def test_drilling_easy_snap_xy_setter_validates_range(self):
        """Test easy_snap_xy setter validates range 0-9."""
        drill = DrillingOperation(0, 0, 0)

        with pytest.raises(ValueError, match="easy_snap_xy must be between 0 and 9"):
            drill.easy_snap_xy = 10
        with pytest.raises(ValueError, match="easy_snap_xy must be between 0 and 9"):
            drill.easy_snap_xy = -1

    def test_drilling_easy_snap_z_setter_validates_range(self):
        """Test easy_snap_z setter validates range 0-2."""
        drill = DrillingOperation(0, 0, 0)

        with pytest.raises(ValueError, match="easy_snap_z must be between 0 and 2"):
            drill.easy_snap_z = 3
        with pytest.raises(ValueError, match="easy_snap_z must be between 0 and 2"):
            drill.easy_snap_z = -1

    def test_drilling_to_line_with_diameter(self):
        """Test DrillingOperation._to_line() with diameter."""
        drill = DrillingOperation(x=100.5, y=200, z=50, depth=-30, diameter=10.5, rotation=45, tilt=-30)
        line = drill._to_line()
        assert line.startswith("BOHR(")
        assert "100.5" in line
        assert "200," in line
        assert "10.5" in line
        assert "-30," in line
        assert "45," in line

    def test_drilling_to_line_without_diameter(self):
        """Test DrillingOperation._to_line() without diameter (uses _WZD)."""
        drill = DrillingOperation(x=100, y=200, z=50, depth=-30)
        line = drill._to_line()
        assert "_WZD" in line

    def test_drilling_str(self):
        """Test DrillingOperation.__str__() calls _to_line()."""
        drill = DrillingOperation(100, 200, 50)
        assert str(drill) == drill._to_line()

    def test_drilling_repr(self):
        """Test DrillingOperation.__repr__()."""
        drill = DrillingOperation(100, 200, 50, depth=-30, diameter=10)
        repr_str = repr(drill)
        assert "DrillingOperation" in repr_str
        assert "100.0" in repr_str
        assert "200.0" in repr_str
        assert "50.0" in repr_str

    def test_drilling_from_hop_line_with_diameter(self):
        """Test DrillingOperation.from_hop_line() with diameter."""
        line = "BOHR(100.5,200.25,50,10.5,-30,0,45.5,-30.5,0,2)"
        drill = DrillingOperation.from_hop_line(line)

        assert drill.x == pytest.approx(100.5)
        assert drill.y == pytest.approx(200.25)
        assert drill.z == pytest.approx(50)
        assert drill.diameter == pytest.approx(10.5)
        assert drill.depth == pytest.approx(-30)
        assert drill.drilling_flags == 0
        assert drill.rotation == pytest.approx(45.5)
        assert drill.tilt == pytest.approx(-30.5)
        assert drill.easy_snap_xy == 0
        assert drill.easy_snap_z == 2

    def test_drilling_from_hop_line_with_wzd(self):
        """Test DrillingOperation.from_hop_line() with _WZD (tool default diameter)."""
        line = "BOHR(100,200,50,_WZD,-30,0,0,0,0,2)"
        drill = DrillingOperation.from_hop_line(line)

        assert drill.x == pytest.approx(100)
        assert drill.y == pytest.approx(200)
        assert drill.z == pytest.approx(50)
        assert drill.diameter is None
        assert drill.depth == pytest.approx(-30)

    def test_drilling_from_hop_line_invalid(self):
        """Test DrillingOperation.from_hop_line() with invalid input."""
        with pytest.raises(ValueError, match="Invalid BOHR line"):
            DrillingOperation.from_hop_line("INVALID(1,2,3)")

    def test_drilling_number_formatting(self):
        """Test that drilling formats numbers correctly (integers without decimals)."""
        drill = DrillingOperation(x=100.0, y=200.0, z=50.0, depth=-30.0, diameter=10.0)
        line = drill._to_line()
        # Integers should not have decimals
        assert "100" in line
        assert "200" in line
        assert "50" in line
        assert "10" in line
        assert "-30" in line

    def test_drilling_number_formatting_with_floats(self):
        """Test that drilling formats floats with 3 decimals."""
        drill = DrillingOperation(x=100.123, y=200.456, z=50.789, depth=-30.5)
        line = drill._to_line()
        # Floats should have 3 decimals
        assert "100.123" in line
        assert "200.456" in line
        assert "50.789" in line
        assert "-30.5" in line


class TestStartPoint:
    """Tests for StartPoint class."""

    def test_start_point_init(self):
        """Test StartPoint initialization."""
        sp = StartPoint(x=100.0, y=200.0, z=-30.0)
        assert sp.x == 100.0
        assert sp.y == 200.0
        assert sp.z == -30.0

    def test_start_point_str(self):
        """Test StartPoint.__str__() generates SP command."""
        sp = StartPoint(x=100.0, y=200.0, z=-30.0)
        line = str(sp)
        assert line.startswith("SP(")
        assert "100" in line
        assert "200" in line

    def test_start_point_from_hop_line(self):
        """Test StartPoint.from_hop_line() parsing."""
        line = "SP(68.807,-35.546,20,0,0,_ANF,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)"
        sp = StartPoint.from_hop_line(line)
        assert sp.x == pytest.approx(68.807)
        assert sp.y == pytest.approx(-35.546)
        assert sp.z == pytest.approx(20)
        assert sp.radius_compensation == CompensationMode.CENTER
        assert sp.lead_in_mode == LeadInOutMode.NONE
        assert sp.lead_in_factor is None

    def test_start_point_from_hop_line_with_spaces(self):
        """Test StartPoint.from_hop_line() parsing with spaces."""
        line = "SP(100, 200, -30, 1, 3, 3.000, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)"
        sp = StartPoint.from_hop_line(line)
        assert sp.x == pytest.approx(100)
        assert sp.y == pytest.approx(200)
        assert sp.z == pytest.approx(-30)
        assert sp.radius_compensation == CompensationMode.LEFT
        assert sp.lead_in_mode == LeadInOutMode.LATERAL
        assert sp.lead_in_factor == pytest.approx(3.0)

    def test_start_point_from_hop_line_invalid(self):
        """Test StartPoint.from_hop_line() with invalid input."""
        with pytest.raises(ValueError, match="Invalid SP line"):
            StartPoint.from_hop_line("INVALID(1,2,3)")


class TestG01:
    """Tests for G01 class."""

    def test_g01_init(self):
        """Test G01 initialization."""
        g01 = G01(x=100.0, y=200.0, z=-30.0)
        assert g01.x == 100.0
        assert g01.y == 200.0
        assert g01.z == -30.0

    def test_g01_str(self):
        """Test G01.__str__() generates G01 command."""
        g01 = G01(x=100.0, y=200.0, z=-30.0, corner_radius=5.0)
        line = str(g01)
        assert "G01(" in line
        assert "100" in line
        assert "200" in line

    def test_g01_from_hop_line(self):
        """Test G01.from_hop_line() parsing."""
        line = "G01(1028.902,-157.471,-59.321,0,0,2)"
        g01 = G01.from_hop_line(line)
        assert g01.x == pytest.approx(1028.902)
        assert g01.y == pytest.approx(-157.471)
        assert g01.z == pytest.approx(-59.321)
        assert g01.corner_radius == pytest.approx(0)
        assert g01.easy_snap_xy == 0
        assert g01.easy_snap_z == EasySnapZ.RELATIVE

    def test_g01_from_hop_line_with_spaces(self):
        """Test G01.from_hop_line() parsing with spaces."""
        line = "G01(155, 137.805, 5, 5, 0, 2)"
        g01 = G01.from_hop_line(line)
        assert g01.x == pytest.approx(155)
        assert g01.y == pytest.approx(137.805)
        assert g01.z == pytest.approx(5)
        assert g01.corner_radius == pytest.approx(5)
        assert g01.easy_snap_xy == 0
        assert g01.easy_snap_z == EasySnapZ.RELATIVE

    def test_g01_from_hop_line_invalid(self):
        """Test G01.from_hop_line() with invalid input."""
        with pytest.raises(ValueError, match="Invalid G01 line"):
            G01.from_hop_line("INVALID(1,2,3)")


class TestEndPoint:
    """Tests for EndPoint class."""

    def test_end_point_init(self):
        """Test EndPoint initialization."""
        ep = EndPoint(lead_out_mode=LeadInOutMode.LINEAR)
        assert ep.lead_out_mode == LeadInOutMode.LINEAR

    def test_end_point_str(self):
        """Test EndPoint.__str__() generates EP command."""
        ep = EndPoint(lead_out_mode=LeadInOutMode.LINEAR, lead_out_factor=3.0)
        line = str(ep)
        assert line.startswith("EP(")

    def test_end_point_from_hop_line(self):
        """Test EndPoint.from_hop_line() parsing."""
        line = "EP(3,3.000,0)"
        ep = EndPoint.from_hop_line(line)
        assert ep.lead_out_mode == LeadInOutMode.LATERAL
        assert ep.lead_out_factor == pytest.approx(3.0)
        assert ep.reverse_direction is False

    def test_end_point_from_hop_line_with_anf(self):
        """Test EndPoint.from_hop_line() parsing with _ANF."""
        line = "EP(0,_ANF,1)"
        ep = EndPoint.from_hop_line(line)
        assert ep.lead_out_mode == LeadInOutMode.NONE
        assert ep.lead_out_factor is None
        assert ep.reverse_direction is True

    def test_end_point_from_hop_line_with_spaces(self):
        """Test EndPoint.from_hop_line() parsing with spaces."""
        line = "EP(1, 5.5, 0)"
        ep = EndPoint.from_hop_line(line)
        assert ep.lead_out_mode == LeadInOutMode.LINEAR
        assert ep.lead_out_factor == pytest.approx(5.5)
        assert ep.reverse_direction is False

    def test_end_point_from_hop_line_invalid(self):
        """Test EndPoint.from_hop_line() with invalid input."""
        with pytest.raises(ValueError, match="Invalid EP line"):
            EndPoint.from_hop_line("INVALID(1,2,3)")


class TestMillingOperation:
    """Tests for MillingOperation class."""

    def test_milling_operation_init(self):
        """Test MillingOperation initialization."""
        sp = StartPoint(x=100.0, y=200.0, z=-30.0)
        moves = [G01(x=200.0, y=300.0, z=-30.0)]
        ep = EndPoint()

        milling = MillingOperation(start_point=sp, moves=moves, end_point=ep)
        assert milling.start_point == sp
        assert milling.moves == moves
        assert milling.end_point == ep

    def test_milling_operation_str(self):
        """Test MillingOperation.__str__() generates complete sequence."""
        sp = StartPoint(x=100.0, y=200.0, z=-30.0)
        moves = [G01(x=200.0, y=300.0, z=-30.0)]
        ep = EndPoint()

        milling = MillingOperation(start_point=sp, moves=moves, end_point=ep)
        output = str(milling)

        assert "SP(" in output
        assert "G01(" in output
        assert "EP(" in output

    def test_milling_operation_repr(self):
        """Test MillingOperation.__repr__()."""
        sp = StartPoint(x=100.0, y=200.0, z=-30.0)
        moves = [G01(x=200.0, y=300.0, z=-30.0)]
        ep = EndPoint()

        milling = MillingOperation(start_point=sp, moves=moves, end_point=ep)
        repr_str = repr(milling)

        assert "MillingOperation" in repr_str
        assert "100.0" in repr_str
        assert "200.0" in repr_str
