"""
Unit tests for work_planes module

Tests for WorkPlane and FreePlane classes.
"""

import math

import pytest

from compas.geometry import Frame
from compas.geometry import Point

from easyhops.hop_core import EasySnapXY
from easyhops.hop_core import EasySnapZ
from easyhops.work_planes import FreePlane
from easyhops.work_planes import WorkPlane


# ==========================================================================
# Fixtures
# ==========================================================================


@pytest.fixture
def basic_plane():
    return FreePlane(x=100, y=50, z=0, rotation_angle=45, tilt_angle=0)


@pytest.fixture
def plane_with_snaps():
    return FreePlane(
        x=100,
        y=50,
        z=0,
        rotation_angle=45,
        tilt_angle=30,
        easy_snap_xy=EasySnapXY.BOTTOM_CENTER,
        easy_snap_z=EasySnapZ.BOTTOM_EDGE,
        offset_z=1.0,
    )


# ==========================================================================
# WorkPlane Enum Tests
# ==========================================================================


class TestWorkPlane:
    """Test WorkPlane enum"""

    def test_standard_work_planes(self):
        """Test standard work plane values"""
        assert WorkPlane.TOP == "EBENE0()"
        assert WorkPlane.FRONT == "EBENE1()"
        assert WorkPlane.START == "EBENE2()"
        assert WorkPlane.BACK == "EBENE3()"
        assert WorkPlane.END == "EBENE4()"
        assert WorkPlane.UNKNOWN == "UNKNOWN"

    def test_work_plane_is_string(self):
        """Test that work planes are string enums"""
        assert isinstance(WorkPlane.TOP.value, str)
        assert isinstance(WorkPlane.FRONT.value, str)


# ==========================================================================
# FreePlane Tests
# ==========================================================================


def test_free_plane_creation_basic(basic_plane):
    """Test creating free plane with basic parameters."""
    assert basic_plane.x == 100
    assert basic_plane.y == 50
    assert basic_plane.z == 0
    assert basic_plane.rotation_angle == 45
    assert basic_plane.tilt_angle == 0


def test_free_plane_creation_with_snap_modes(plane_with_snaps):
    """Test creating free plane with snap modes."""
    assert plane_with_snaps.easy_snap_xy == EasySnapXY.BOTTOM_CENTER
    assert plane_with_snaps.easy_snap_z == EasySnapZ.BOTTOM_EDGE
    assert plane_with_snaps.offset_z == 1.0


def test_free_plane_default_snap_modes():
    """Test default snap mode values."""
    plane = FreePlane(x=0, y=0, z=0, rotation_angle=0, tilt_angle=0)

    assert plane.easy_snap_xy == EasySnapXY.DISABLED
    assert plane.easy_snap_z == EasySnapZ.RELATIVE
    assert plane.offset_z == 0.0


def test_free_plane_string_basic(basic_plane):
    """Test EBENEF command string generation."""
    result = str(basic_plane)
    assert result == "EBENEF(100,50,0,45,0,0,2,0)"


def test_free_plane_string_with_snap_modes():
    """Test EBENEF string with snap modes."""
    plane = FreePlane(x=100, y=50, z=0, rotation_angle=45, tilt_angle=30, easy_snap_xy=9, easy_snap_z=1, offset_z=1.5)

    result = str(plane)
    assert result == "EBENEF(100,50,0,45,30,9,1,1.500)"


def test_free_plane_string_negative_values():
    """Test EBENEF string with negative coordinates."""
    plane = FreePlane(x=-100, y=-50, z=-25, rotation_angle=-45, tilt_angle=-15)

    result = str(plane)
    assert "-100" in result
    assert "-50" in result
    assert "-25" in result
    assert "-45" in result
    assert "-15" in result


def test_free_plane_repr():
    """Test FreePlane repr output."""
    plane = FreePlane(x=100, y=50, z=0, rotation_angle=45, tilt_angle=30)

    result = repr(plane)
    assert "FreePlane" in result
    assert "100" in result
    assert "50" in result
    assert "45" in result
    assert "30" in result


def test_free_plane_zero_origin():
    """Test free plane at origin."""
    plane = FreePlane(x=0, y=0, z=0, rotation_angle=0, tilt_angle=0)

    result = str(plane)
    assert result == "EBENEF(0,0,0,0,0,0,2,0)"


def test_free_plane_90_degree_rotation():
    """Test free plane with 90 degree rotation."""
    plane = FreePlane(x=100, y=100, z=0, rotation_angle=90, tilt_angle=0)

    assert plane.rotation_angle == 90
    result = str(plane)
    assert "90" in result


def test_free_plane_negative_rotation():
    """Test free plane with negative rotation."""
    plane = FreePlane(x=0, y=0, z=0, rotation_angle=-90, tilt_angle=-45)

    assert plane.rotation_angle == -90
    assert plane.tilt_angle == -45


def test_free_plane_180_degree_rotation():
    """Test free plane with 180 degree rotation."""
    plane = FreePlane(x=50, y=50, z=10, rotation_angle=180, tilt_angle=0)

    assert plane.rotation_angle == 180


def test_free_plane_large_coordinates():
    """Test free plane with large coordinate values."""
    plane = FreePlane(x=5000, y=3000, z=500, rotation_angle=45, tilt_angle=30)

    result = str(plane)
    assert "5000" in result
    assert "3000" in result
    assert "500" in result


def test_free_plane_decimal_values():
    """Test free plane with decimal values."""
    plane = FreePlane(x=100.5, y=50.25, z=25.125, rotation_angle=45.5, tilt_angle=30.25)

    assert plane.x == 100.5
    assert plane.y == 50.25
    assert plane.z == 25.125
    assert plane.rotation_angle == 45.5
    assert plane.tilt_angle == 30.25

    # Check formatting (3 decimal places for floats)
    result = str(plane)
    assert "100.500" in result
    assert "50.250" in result
    assert "25.125" in result
    assert "45.500" in result
    assert "30.250" in result


def test_number_formatting_integers_vs_floats():
    """Test that integers are formatted without decimals, floats with 3 decimals."""
    # Integer values - no decimals
    plane_int = FreePlane(x=100, y=50, z=0, rotation_angle=45, tilt_angle=0)
    result_int = str(plane_int)
    assert result_int == "EBENEF(100,50,0,45,0,0,2,0)"

    # Float values - 3 decimals
    plane_float = FreePlane(x=100.5, y=50.25, z=0.125, rotation_angle=45.5, tilt_angle=0.1)
    result_float = str(plane_float)
    assert "100.500" in result_float
    assert "50.250" in result_float
    assert "0.125" in result_float
    assert "45.500" in result_float
    assert "0.100" in result_float


def test_free_plane_from_frame():
    """Test creating FreePlane from COMPAS Frame."""
    frame = Frame(point=Point(100, 50, 0), xaxis=[1, 0, 0], yaxis=[0, 1, 0])

    plane = FreePlane.from_frame(frame)

    assert plane.x == 100
    assert plane.y == 50
    assert plane.z == 0
    # Rotation and tilt should be calculated from frame axes
    assert isinstance(plane.rotation_angle, (int, float))
    assert isinstance(plane.tilt_angle, (int, float))


def test_free_plane_from_frame_rotated():
    """Test creating FreePlane from rotated COMPAS Frame."""
    # Frame rotated 45 degrees around Z
    cos45 = math.cos(math.radians(45))
    sin45 = math.sin(math.radians(45))

    frame = Frame(point=Point(100, 100, 0), xaxis=[cos45, sin45, 0], yaxis=[-sin45, cos45, 0])

    plane = FreePlane.from_frame(frame)

    assert plane.x == 100
    assert plane.y == 100
    # Rotation angle should be approximately 45 degrees
    assert abs(plane.rotation_angle - 45) < 1.0


def test_free_plane_modification(basic_plane):
    """Test modifying free plane parameters."""
    basic_plane.x = 200
    basic_plane.rotation_angle = 90
    basic_plane.easy_snap_xy = 5

    assert basic_plane.x == 200
    assert basic_plane.rotation_angle == 90
    assert basic_plane.easy_snap_xy == 5


def test_free_plane_command_format():
    """Test that EBENEF command has correct format."""
    plane = FreePlane(x=100, y=50, z=25, rotation_angle=45, tilt_angle=30)

    result = str(plane)

    # Should start with EBENEF(
    assert result.startswith("EBENEF(")
    # Should end with )
    assert result.endswith(")")
    # Should contain 8 parameters separated by commas
    params = result[7:-1].split(",")
    assert len(params) == 8


def test_free_plane_parameter_order():
    """Test parameter order in EBENEF command."""
    plane = FreePlane(x=111, y=222, z=333, rotation_angle=444, tilt_angle=555, easy_snap_xy=6, easy_snap_z=1, offset_z=2.5)

    result = str(plane)
    params = result[7:-1].split(",")

    assert params[0] == "111"  # x
    assert params[1] == "222"  # y
    assert params[2] == "333"  # z
    assert params[3] == "444"  # rotation_angle
    assert params[4] == "555"  # tilt_angle
    assert params[5] == "6"  # easy_snap_xy
    assert params[6] == "1"  # easy_snap_z
    assert params[7] == "2.500"  # offset_z


def test_multiple_free_planes():
    """Test creating multiple independent free planes."""
    plane1 = FreePlane(100, 50, 0, 45, 0)
    plane2 = FreePlane(200, 100, 10, 90, 30)
    plane3 = FreePlane(0, 0, 0, 0, 0)

    assert plane1.x != plane2.x
    assert plane2.rotation_angle != plane3.rotation_angle

    # Modifying one shouldn't affect others
    plane1.x = 999
    assert plane2.x == 200
    assert plane3.x == 0


# ==========================================================================
# Type Validation Tests
# ==========================================================================


def test_type_validation_x_invalid():
    """Test that x setter rejects invalid types."""
    with pytest.raises(TypeError, match="x must be a number"):
        FreePlane(x="100", y=50, z=0, rotation_angle=45, tilt_angle=0)


def test_type_validation_y_invalid():
    """Test that y setter rejects invalid types."""
    with pytest.raises(TypeError, match="y must be a number"):
        FreePlane(x=100, y="50", z=0, rotation_angle=45, tilt_angle=0)


def test_type_validation_z_invalid():
    """Test that z setter rejects invalid types."""
    with pytest.raises(TypeError, match="z must be a number"):
        FreePlane(x=100, y=50, z="0", rotation_angle=45, tilt_angle=0)


def test_type_validation_rotation_angle_invalid():
    """Test that rotation_angle setter rejects invalid types."""
    with pytest.raises(TypeError, match="rotation_angle must be a number"):
        FreePlane(x=100, y=50, z=0, rotation_angle="45", tilt_angle=0)


def test_type_validation_tilt_angle_invalid():
    """Test that tilt_angle setter rejects invalid types."""
    with pytest.raises(TypeError, match="tilt_angle must be a number"):
        FreePlane(x=100, y=50, z=0, rotation_angle=45, tilt_angle="0")


def test_type_validation_easy_snap_xy_invalid():
    """Test that easy_snap_xy setter rejects invalid types."""
    with pytest.raises(TypeError, match="easy_snap_xy must be EasySnapXY enum or int"):
        FreePlane(x=100, y=50, z=0, rotation_angle=45, tilt_angle=0, easy_snap_xy="10")


def test_type_validation_easy_snap_z_invalid():
    """Test that easy_snap_z setter rejects invalid types."""
    with pytest.raises(TypeError, match="easy_snap_z must be EasySnapZ enum or int"):
        FreePlane(x=100, y=50, z=0, rotation_angle=45, tilt_angle=0, easy_snap_z="2")


def test_type_validation_offset_z_invalid():
    """Test that offset_z setter rejects invalid types."""
    with pytest.raises(TypeError, match="offset_z must be a number"):
        FreePlane(x=100, y=50, z=0, rotation_angle=45, tilt_angle=0, offset_z="2")


def test_type_validation_accepts_int_for_coordinates():
    """Test that coordinate setters accept integers and convert to float."""
    plane = FreePlane(x=100, y=50, z=0, rotation_angle=45, tilt_angle=0)

    assert isinstance(plane.x, float)
    assert isinstance(plane.y, float)
    assert isinstance(plane.z, float)
    assert plane.x == 100.0
    assert plane.y == 50.0
    assert plane.z == 0.0


def test_type_validation_property_setter(basic_plane):
    """Test that property setters validate types after initialization."""
    with pytest.raises(TypeError, match="x must be a number"):
        basic_plane.x = "invalid"

    with pytest.raises(TypeError, match="rotation_angle must be a number"):
        basic_plane.rotation_angle = [45]


def test_type_validation_accepts_enum_values():
    """Test that snap parameters accept enum values."""
    plane = FreePlane(
        x=100,
        y=50,
        z=0,
        rotation_angle=45,
        tilt_angle=0,
        easy_snap_xy=EasySnapXY.TOP_LEFT,
        easy_snap_z=EasySnapZ.TOP_EDGE,
        offset_z=1.0,
    )

    assert plane.easy_snap_xy == EasySnapXY.TOP_LEFT.value
    assert plane.easy_snap_z == EasySnapZ.TOP_EDGE.value
    assert plane.offset_z == 1.0


def test_type_validation_accepts_int_for_snap_modes():
    """Test that snap parameters accept raw integer values."""
    plane = FreePlane(x=100, y=50, z=0, rotation_angle=45, tilt_angle=0, easy_snap_xy=5, easy_snap_z=1, offset_z=1)

    assert plane.easy_snap_xy == 5
    assert plane.easy_snap_z == 1
    assert plane.offset_z == 1.0


def test_easy_snap_xy_range_validation():
    """Test that easy_snap_xy enforces valid range (0-9)."""
    # Valid values should work
    for i in range(10):
        plane = FreePlane(x=0, y=0, z=0, rotation_angle=0, tilt_angle=0, easy_snap_xy=i, easy_snap_z=0, offset_z=0)
        assert plane.easy_snap_xy == i

    # Invalid values should raise
    with pytest.raises(ValueError, match="easy_snap_xy must be between 0 and 9"):
        FreePlane(x=0, y=0, z=0, rotation_angle=0, tilt_angle=0, easy_snap_xy=10, easy_snap_z=0, offset_z=0)

    with pytest.raises(ValueError, match="easy_snap_xy must be between 0 and 9"):
        FreePlane(x=0, y=0, z=0, rotation_angle=0, tilt_angle=0, easy_snap_xy=-1, easy_snap_z=0, offset_z=0)


def test_easy_snap_z_range_validation():
    """Test that easy_snap_z enforces valid range (0-2)."""
    # Valid values should work
    for i in range(3):
        plane = FreePlane(x=0, y=0, z=0, rotation_angle=0, tilt_angle=0, easy_snap_xy=0, easy_snap_z=i, offset_z=0)
        assert plane.easy_snap_z == i

    # Invalid values should raise
    with pytest.raises(ValueError, match="easy_snap_z must be between 0 and 2"):
        FreePlane(x=0, y=0, z=0, rotation_angle=0, tilt_angle=0, easy_snap_xy=0, easy_snap_z=3, offset_z=0)

    with pytest.raises(ValueError, match="easy_snap_z must be between 0 and 2"):
        FreePlane(x=0, y=0, z=0, rotation_angle=0, tilt_angle=0, easy_snap_xy=0, easy_snap_z=-1, offset_z=0)


def test_offset_z_accepts_any_float():
    """Test that offset_z accepts any float value."""
    # Valid values should work
    test_values = [0.0, 1.5, -10.0, 100.5, -50.25]
    for val in test_values:
        plane = FreePlane(x=0, y=0, z=0, rotation_angle=0, tilt_angle=0, easy_snap_xy=0, easy_snap_z=0, offset_z=val)
        assert plane.offset_z == val


def test_easy_snap_property_setters_validate_range(basic_plane):
    """Test that property setters validate range after initialization."""
    with pytest.raises(ValueError, match="easy_snap_xy must be between 0 and 9"):
        basic_plane.easy_snap_xy = 100

    with pytest.raises(ValueError, match="easy_snap_z must be between 0 and 2"):
        basic_plane.easy_snap_z = 10

    # offset_z can be any float, no range validation needed
    basic_plane.offset_z = 10.5
    assert basic_plane.offset_z == 10.5
