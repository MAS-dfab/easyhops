"""Tests for G02M and G03M arc commands."""

import pytest
from easyhops.machining_commands import G02M, G03M, EasySnapXY, EasySnapZ


def test_g02m_parsing():
    """Test parsing G02M command from HOP line."""
    line = "G02M(89.001,22.91,0,96.638,22.91,0,0,2,0)"
    result = G02M.from_hop_line(line)
    assert result.x == 89.001
    assert result.y == 22.91
    assert result.mx == 96.638
    assert result.my == 22.91
    assert result.corner_radius == 0
    assert result.easy_snap_xy == EasySnapXY.DISABLED
    assert result.easy_snap_z == EasySnapZ.RELATIVE
    assert result.easy_snap_center == 0


def test_g03m_parsing():
    """Test parsing G03M command from HOP line."""
    line = "G03M(104.274,7.637,0,96.638,7.637,0,0,2,0)"
    result = G03M.from_hop_line(line)
    assert result.x == 104.274
    assert result.y == 7.637
    assert result.mx == 96.638
    assert result.my == 7.637
    assert result.corner_radius == 0
    assert result.easy_snap_xy == EasySnapXY.DISABLED
    assert result.easy_snap_z == EasySnapZ.RELATIVE
    assert result.easy_snap_center == 0


def test_g02m_string_output():
    """Test G02M string conversion."""
    cmd = G02M(89.001, 22.91, 0, 96.638, 22.91, 0, 0, 2, 0)
    output = str(cmd)
    assert "G02M(89.001,22.91,0,96.638,22.91,0,0,2,0)" in output


def test_g03m_string_output():
    """Test G03M string conversion."""
    cmd = G03M(104.274, 7.637, 0, 96.638, 7.637, 0, 0, 2, 0)
    output = str(cmd)
    assert "G03M(104.274,7.637,0,96.638,7.637,0,0,2,0)" in output


def test_milling_operation_with_arc_commands_parsing():
    """Test parsing a complete milling operation with G01, G02M, and G03M commands."""
    from easyhops.hop_job import HOPSJob

    hop_content = """VARS
   DX := 100;
   DY := 100;
   DZ := 100;
START
FERTIGTEIL(100,100,100,0,0,0,0,0,'',0,0,0)
CALL Park_V7 ( VAL MODE:=11,POSX:=0,POSY:=0)
WZF(503,2000,2000,10000,_SD,_ANF,'1')
EBENE0()
SP(0,0,0,0,0,_ANF,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)
G01(10,0,0,0,0,2)
G03M(15,5,0,10,5,0,0,2,0)
G02M(20,0,0,15,0,0,0,2,0)
G01(30,0,0,0,0,2)
EP(0,_ANF,0)
"""

    job = HOPSJob.from_hop_string(hop_content)
    assert len(job.machinings) == 1
    assert len(job.machinings[0].operations) == 1

    operation = job.machinings[0].operations[0]
    assert len(operation.moves) == 4

    from easyhops.machining_commands import G01

    assert isinstance(operation.moves[0], G01)
    assert isinstance(operation.moves[1], G03M)
    assert isinstance(operation.moves[2], G02M)
    assert isinstance(operation.moves[3], G01)


def test_milling_operation_with_arc_commands_string_output():
    """Test string output of milling operation with mixed move types."""
    from easyhops.machining_commands import MillingOperation, StartPoint, EndPoint, G01

    sp = StartPoint(0, 0, 0, 0, 0, None, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    moves = [
        G01(10, 0, 0, 0, 0, 2),
        G03M(15, 5, 0, 10, 5, 0, 0, 2, 0),
        G02M(20, 0, 0, 15, 0, 0, 0, 2, 0),
        G01(30, 0, 0, 0, 0, 2),
    ]
    ep = EndPoint(0, None, False)

    operation = MillingOperation(sp, moves, ep)
    output = str(operation)

    assert "G01(10" in output
    assert "G03M(15,5,0,10,5" in output
    assert "G02M(20,0,0,15,0" in output
    assert "G01(30" in output
