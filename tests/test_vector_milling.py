"""Tests for vector (5-axis) milling: VSP / VG01 / VEP and FrameToolpathStrategies."""

import math
import random

import pytest
from compas.geometry import Frame, Point, Transformation, Vector

from easyhops.hop_core import FinishedPart, ParkPosition, VarsDefinition
from easyhops.hop_job import HOPSJob
from easyhops.machining_commands import VectorEndPoint, VectorMillingOperation, VectorMove, VectorStartPoint
from easyhops.strategies.frames import FrameToolpathStrategies
from easyhops.tool_library import MachiningTool


def tool_frame(point, tool_vector):
    """Frame with origin = tool tip and Z = tool_vector (tip -> holder); X/Y arbitrary."""
    z = Vector(*tool_vector)
    z.unitize()
    helper = Vector(1, 0, 0) if abs(z.x) < 0.9 else Vector(0, 1, 0)
    y = z.cross(helper)
    x = y.cross(z)
    return Frame(Point(*point), x, y)


# ---------------------------------------------------------------- angle convention


@pytest.mark.parametrize(
    "vector, expected",
    [
        ((1, 0, 0), (90.0, 90.0)),  # Fusion files: horizontal tool from the +X end
        ((0, -1, 0), (0.0, 90.0)),  # Fusion files: from the -Y face
        ((0, 1, 0), (180.0, 90.0)),  # Fusion files: from the +Y face
        ((-1, 0, 0), (270.0, 90.0)),
        ((0, 0, 1), (0.0, 0.0)),  # vertical: Calc_DW_KW_NV sets DW = 0
        ((0, -1, 1), (0.0, 45.0)),
    ],
)
def test_angles_from_vector_matches_hops_convention(vector, expected):
    dw, kw = VectorMove.angles_from_vector(vector)
    assert dw == pytest.approx(expected[0], abs=1e-9)
    assert kw == pytest.approx(expected[1], abs=1e-9)


def test_angles_round_trip():
    rng = random.Random(1)
    for _ in range(2000):
        v = [rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.5, 1)]
        length = math.sqrt(sum(c * c for c in v))
        v = [c / length for c in v]
        back = VectorMove.vector_from_angles(*VectorMove.angles_from_vector(v))
        assert back == pytest.approx(v, abs=1e-9)


# ---------------------------------------------------------------- commands


def test_vg01_parses_machine_folder_formats():
    fusion = VectorMove.from_hop_line("VG01 (490,-129.968,192.5,90,90.000,3000)")
    assert (fusion.x, fusion.y, fusion.z, fusion.rotation_angle, fusion.tilt_angle, fusion.feedrate) == (490, -129.968, 192.5, 90, 90, 3000)
    macro = VectorMove.from_hop_line("vg01 (1,2,3,45,30,_VAKT)")
    assert macro.feedrate == "_VAKT"
    assert str(fusion) == "VG01 (490,-129.968,192.5,90,90,3000)"


def test_vsp_parameters_follow_hops_definition():
    # VSP.SYS: X, Y, Z, DW, KW, Laser, Res3, Res4, Res5, Darstellen, SaugerCheck, DreiAchsMode, AB
    fusion = VectorStartPoint.from_hop_line("VSP (490,-129.968,192.5,90,90.000,0,0,0,0,3,0,0,0)")
    assert (fusion.laser, fusion.display, fusion.check_pads, fusion.three_axis, fusion.approach) == (False, 3, False, False, 0)
    sphere_3axis = VectorStartPoint.from_hop_line("vsp (1,2,3,45,30,0,0,0,0,3,1,1,0)")
    assert sphere_3axis.three_axis is True
    assert str(VectorStartPoint.from_hop_line(str(fusion))) == str(fusion)
    assert VectorEndPoint.from_hop_line("VEP (6)").mode == 6
    with pytest.raises(ValueError):
        VectorStartPoint.from_hop_line("VSP (1,2,3)")


def test_default_start_point_is_five_axis():
    """Regression: DreiAchsMode=1 makes HOPS ignore DW/KW and mill everything vertically."""
    vsp = VectorStartPoint(1, 2, 3, 90, 90)
    assert vsp.three_axis is False
    assert str(vsp) == "VSP (1,2,3,90,90,0,0,0,0,3,1,0,0)"  # same flags as the HOPS Clamex vector macros
    op = FrameToolpathStrategies.vector_milling([[tool_frame((0, 0, 0), (0, -1, 0)), tool_frame((10, 0, 0), (0, -1, 0))]], MachiningTool(404))[0].operations[0]
    assert op.start_point.three_axis is False


def test_from_points_holds_rotation_through_vertical():
    vectors = [(0, -1, 1), (0, 0, 1), (1, 0, 1)]
    op = VectorMillingOperation.from_points([(0, 0, 0), (1, 0, 0), (2, 0, 0)], vectors, 1000)
    assert op.start_point.rotation_angle == pytest.approx(0.0)
    assert [m.rotation_angle for m in op.moves] == pytest.approx([0.0, 0.0, 90.0])
    assert op.moves[1].tilt_angle == 0.0


def test_hop_job_round_trip_without_work_plane():
    op = VectorMillingOperation.from_points([(0, -15, 50), (0, -5, 50), (100, -5, 50)], [(0, -1, 0)] * 3, [5000, 1000, 3000])
    machinings = FrameToolpathStrategies.vector_milling([[tool_frame((0, -15, 50), (0, -1, 0)), tool_frame((1, -15, 50), (0, -1, 0))]], MachiningTool(404))
    machinings[0].operations.append(op)
    job = HOPSJob(VarsDefinition(dx=500, dy=200, dz=100), FinishedPart(), ParkPosition(), machinings)
    parsed = HOPSJob.from_hop_string(str(job))
    assert len(parsed.machinings) == 1
    assert parsed.machinings[0].work_plane is None
    assert [str(o) for o in parsed.machinings[0].operations] == [str(o) for o in machinings[0].operations]


# ---------------------------------------------------------------- strategy


def make_passes():
    """Two passes: a flank-style pass with the tool axis turning around Z, and a tilt sweep."""
    flank = [tool_frame((40 + 10 * i, 2, 30 + i), (math.sin(math.radians(a)), -math.cos(math.radians(a)), 0)) for i, a in enumerate(range(-20, 21, 5))]
    sweep = [tool_frame((300 + 10 * i, 100, 98), (0, -math.sin(math.radians(t)), math.cos(math.radians(t)))) for i, t in enumerate(range(0, 46, 5))]
    return [flank, sweep]


def test_vector_milling_with_part_frame_reads_back_exactly():
    part_frame = Frame(Point(-250, -100, -50), Vector(1, 0, 0), Vector(0, 1, 0))
    to_world = [[f.transformed(Transformation.from_frame(part_frame)) for f in p] for p in make_passes()]
    machinings = FrameToolpathStrategies.vector_milling(to_world, MachiningTool(404, motor_speed=18000), part_frame=part_frame, feedrates=[3000, 2000])
    job = HOPSJob(VarsDefinition(dx=500, dy=200, dz=100), FinishedPart(), ParkPosition(), machinings)

    first_move = machinings[0].operations[0].moves[0]
    assert (first_move.x, first_move.y, first_move.z) == pytest.approx((40, 2, 30), abs=1e-9)
    assert first_move.rotation_angle == pytest.approx(340.0)  # axis turned -20 deg from the -Y face
    assert machinings[0].operations[0].moves[-1].rotation_angle == pytest.approx(20.0)

    report = FrameToolpathStrategies.check(job, to_world, part_frame=part_frame)
    assert report["passes"] == 2
    assert report["points"] == 9 + 10
    assert report["max_position_error"] < 1e-3
    assert report["max_axis_error_deg"] < 0.01
    assert report["tilt_range_deg"] == pytest.approx((0.0, 90.0))
    assert any("crosses 0/360" in w for w in report["warnings"])  # 340 -> 345 ... 0 -> 5: flank pass crosses DW = 0


def test_z_into_material_option_and_tilt_limit():
    frames = [tool_frame((0, 0, 10), (0, 0, -1)), tool_frame((10, 0, 10), (0, 0, -1))]
    op = FrameToolpathStrategies.vector_milling([frames], MachiningTool(404), z_to_holder=False)[0].operations[0]
    assert op.moves[0].tilt_angle == pytest.approx(0.0)
    with pytest.raises(ValueError, match="exceeds max_tilt"):
        FrameToolpathStrategies.vector_milling([frames], MachiningTool(404))  # Z down read as tip->holder = 180 deg tilt


def test_per_frame_feeds_and_validation():
    frames = make_passes()[1]
    feeds = [5000] + [1000] * (len(frames) - 1)
    op = FrameToolpathStrategies.vector_milling([frames], MachiningTool(404), feedrates=[feeds])[0].operations[0]
    assert [m.feedrate for m in op.moves] == feeds
    with pytest.raises(ValueError):
        FrameToolpathStrategies.vector_milling([frames], MachiningTool(404), feedrates=[1000, 2000])


def test_read_back_returns_world_coordinates():
    part_frame = Frame(Point(-250, -100, -50), Vector(0, 1, 0), Vector(-1, 0, 0))  # part rotated 90 deg in plan
    world_passes = [[f.transformed(Transformation.from_frame(part_frame)) for f in p] for p in make_passes()]
    machinings = FrameToolpathStrategies.vector_milling(world_passes, MachiningTool(404), part_frame=part_frame)
    job = HOPSJob(VarsDefinition(dx=500, dy=200, dz=100), FinishedPart(), ParkPosition(), machinings)
    back = FrameToolpathStrategies.read_back(job, part_frame=part_frame)
    assert [len(p) for p in back] == [len(p) for p in world_passes]
    for written, frames in zip(back, world_passes):
        for (point, vector), frame in zip(written, frames):
            assert point == pytest.approx(tuple(frame.point), abs=1e-3)
            assert vector == pytest.approx(tuple(frame.zaxis), abs=1e-6)


def test_limit_tilt_turns_frame_to_max_tilt_and_keeps_tip_and_rotation():
    too_steep = tool_frame((10, 20, 30), (0.3, -0.9, -0.4))  # below horizontal
    ok = tool_frame((0, 0, 0), (0, -1, 1))
    down = tool_frame((5, 5, 5), (0, 0, -1))  # straight down: 180 deg
    passes, changes = FrameToolpathStrategies.limit_tilt([[ok, too_steep], [down]], max_tilt=90.0)

    assert passes[0][0] is ok
    assert [(p, f) for p, f, _ in changes] == [(0, 1), (1, 0)]
    assert changes[1][2] == pytest.approx(180.0)
    for frame in (passes[0][1], passes[1][0]):
        assert VectorMove.angles_from_vector(frame.zaxis)[1] == pytest.approx(90.0)
    assert tuple(passes[0][1].point) == pytest.approx((10, 20, 30))
    dw_before = VectorMove.angles_from_vector(too_steep.zaxis)[0]
    assert VectorMove.angles_from_vector(passes[0][1].zaxis)[0] == pytest.approx(dw_before)
    op = FrameToolpathStrategies.vector_milling(passes[:1], MachiningTool(404))[0].operations[0]
    assert op.moves[1].tilt_angle == pytest.approx(90.0)


def test_limit_tilt_uses_part_z_and_z_into_material():
    part_frame = Frame(Point(0, 0, 0), Vector(1, 0, 0), Vector(0, 0, 1))  # part Z = world -Y
    frame = tool_frame((0, 0, 0), (0, 0, 1))  # 90 deg from part Z
    passes, changes = FrameToolpathStrategies.limit_tilt([[frame]], max_tilt=30.0, part_frame=part_frame)
    assert changes and math.degrees(passes[0][0].zaxis.angle(part_frame.zaxis)) == pytest.approx(30.0)
    into_material = tool_frame((0, 0, 0), (0, 0, -1))  # Z into material = tool vertical when z_to_holder=False
    passes, changes = FrameToolpathStrategies.limit_tilt([[into_material]], max_tilt=10.0, z_to_holder=False)
    assert changes == [] and passes[0][0] is into_material
