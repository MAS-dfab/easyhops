"""Test feedrate override tracking at multiple levels within milling operations."""

import pytest
from easyhops.hop_job import HOPSJob
from easyhops.machining_commands import MillingOperation


def test_feedrate_override_within_milling_operation():
    """Test that feedrate overrides can appear before any command within a milling operation."""

    hop_content = """VARS
   DX := 1382.928;*VAR* Piece Length
   DY := 140;*VAR* Piece Height
   DZ := 140;*VAR* Piece Thickness
START
FERTIGTEIL(DX,DY,DZ,0,0,0,0,0,'',0,0,0)
CALL Park_V7 ( VAL MODE:=2,POSX:=0,POSY:=0)
WZF(504,3000,4000,5000,_SD,_ANF,'1')
EBENEF(-202,81.392,415.485,80.77,0,0,0)
CALL _Tvorschub_v5(VAL VORSCHUB:=3000)
SP(0,-100,0,1,3,1.100,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)
G02M(101,-201,0,0,-201,0,0,2,0)
G03M(202,-302,0,202,-201,0,0,2,0)
CALL _Tvorschub_v5(VAL VORSCHUB:=4000)
G01(1584.928,-302,0,0,0,2)
CALL _Tvorschub_v5(VAL VORSCHUB:=5000)
G03M(1685.928,-201,0,1584.928,-201,0,0,2,0)
EP(3,1.100,0)
"""

    with open("test_feedrate_multi.hop", "w") as f:
        f.write(hop_content)

    try:
        # Parse the file
        job = HOPSJob.from_hop_file("test_feedrate_multi.hop")

        # Verify we have 1 machining block
        assert len(job.machinings) == 1

        machining = job.machinings[0]

        # Verify we have 1 milling operation
        assert len(machining.operations) == 1
        assert isinstance(machining.operations[0], MillingOperation)

        # Verify we have 3 feedrate overrides
        assert len(machining.feedrate_overrides) == 3

        # Verify the feedrate overrides are at the correct positions
        overrides = sorted(machining.feedrate_overrides, key=lambda x: (x[0][0], x[0][1] or 0))

        # First override: before SP (op 0, cmd 0)
        assert overrides[0][0] == (0, 0)
        assert overrides[0][1].feedrate == 3000.0

        # Second override: before 4th move (op 0, cmd 3)
        assert overrides[1][0] == (0, 3)
        assert overrides[1][1].feedrate == 4000.0

        # Third override: before 5th move (op 0, cmd 4)
        assert overrides[2][0] == (0, 4)
        assert overrides[2][1].feedrate == 5000.0

        # Test round-trip: write and re-parse
        output = job._to_hop_lines()

        # Verify output contains all feedrate overrides
        assert "CALL _Tvorschub_v5(VAL VORSCHUB:=3000.0)" in output
        assert "CALL _Tvorschub_v5(VAL VORSCHUB:=4000.0)" in output
        assert "CALL _Tvorschub_v5(VAL VORSCHUB:=5000.0)" in output

        # Write and re-parse
        with open("test_feedrate_multi_output.hop", "w") as f:
            f.write(output)

        job2 = HOPSJob.from_hop_file("test_feedrate_multi_output.hop")

        # Verify round-trip preservation
        assert len(job2.machinings) == 1
        assert len(job2.machinings[0].feedrate_overrides) == 3

        overrides2 = sorted(job2.machinings[0].feedrate_overrides, key=lambda x: (x[0][0], x[0][1] or 0))

        assert overrides2[0][0] == (0, 0)
        assert overrides2[0][1].feedrate == 3000.0
        assert overrides2[1][0] == (0, 3)
        assert overrides2[1][1].feedrate == 4000.0
        assert overrides2[2][0] == (0, 4)
        assert overrides2[2][1].feedrate == 5000.0

    finally:
        import os

        if os.path.exists("test_feedrate_multi.hop"):
            os.remove("test_feedrate_multi.hop")
        if os.path.exists("test_feedrate_multi_output.hop"):
            os.remove("test_feedrate_multi_output.hop")


def test_feedrate_override_before_sawing():
    """Test that feedrate overrides before sawing operations work correctly."""

    hop_content = """VARS
   DX := 100;*VAR* Piece Length
   DY := 100;*VAR* Piece Height
   DZ := 100;*VAR* Piece Thickness
START
FERTIGTEIL(DX,DY,DZ,0,0,0,0,0,'',0,0,0)
CALL Park_V7 ( VAL MODE:=2,POSX:=0,POSY:=0)
WZS(201,10000,7000,20000,_SD,_ANF,'1')
EBENE0()
CALL _Tvorschub_v5(VAL VORSCHUB:=8000)
SAEGEN(0,0,0,100,0,0,0,0,0,1,0,0,0,0,2,0,0)
"""

    with open("test_feedrate_sawing.hop", "w") as f:
        f.write(hop_content)

    try:
        job = HOPSJob.from_hop_file("test_feedrate_sawing.hop")

        assert len(job.machinings) == 1
        machining = job.machinings[0]

        # Verify feedrate override before sawing operation
        assert len(machining.feedrate_overrides) == 1
        assert machining.feedrate_overrides[0][0] == (0, None)  # op 0, no cmd_idx (sawing)
        assert machining.feedrate_overrides[0][1].feedrate == 8000.0

        # Test round-trip
        output = job._to_hop_lines()
        assert "CALL _Tvorschub_v5(VAL VORSCHUB:=8000.0)" in output

    finally:
        import os

        if os.path.exists("test_feedrate_sawing.hop"):
            os.remove("test_feedrate_sawing.hop")
