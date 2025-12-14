"""Unit tests for HOP file parsing components.

This module tests the parsing functionality of HOP files, including component-level
parsing (tools, work planes, operations) and integration tests using data/test.hop.

For object behavior tests, see test_hop_job_objects.py
"""

import os
import tempfile
from pathlib import Path

import pytest
from easyhops.hop_core import FinishedPart, ParkMode, VarsDefinition
from easyhops.hop_job import HOPSJob, HOPSMachining, HOPParsingError, UnparsedLineError
from easyhops.machining_commands import (
    DrillingOperation,
    EndPoint,
    G01,
    MillingOperation,
    SawingOperation,
    StartPoint,
)
from easyhops.tool_library import MachiningTool, ToolCallType
from easyhops.work_planes import FreePlane, WorkPlane

# Path to test data
TEST_HOP_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "test.hop")


class TestToolParsing:
    """Test MachiningTool.from_hop_line() with actual lines from test.hop"""

    def test_parse_router_tool(self):
        """Test parsing WZF (router) tool line."""
        line = "WZF(504,3000,4000,5000,_SD,_ANF,'1')"
        tool = MachiningTool.from_hop_line(line)

        assert tool.tool_type == ToolCallType.ROUTER
        assert tool.position == 504
        assert tool.lead_in_feedrate == pytest.approx(3000.0)
        assert tool.feedrate == pytest.approx(4000.0)
        assert tool.lead_out_feedrate == pytest.approx(5000.0)
        assert tool.motor_speed is None  # _SD means use default
        assert tool.lead_in_out_factor is None  # _ANF means use default
        assert tool.head_id == "1"

    def test_parse_saw_tool(self):
        """Test parsing WZS (saw) tool line."""
        line = "WZS(201,10000,7000,20000,_SD,_ANF,'1')"
        tool = MachiningTool.from_hop_line(line)

        assert tool.tool_type == ToolCallType.SAW
        assert tool.position == 201
        assert tool.lead_in_feedrate == pytest.approx(10000.0)
        assert tool.feedrate == pytest.approx(7000.0)
        assert tool.lead_out_feedrate == pytest.approx(20000.0)


class TestWorkPlaneParsing:
    """Test WorkPlane and FreePlane parsing with actual lines from test.hop"""

    def test_parse_standard_plane_ebene0(self):
        """Test parsing EBENE0() (TOP plane)."""
        line = "EBENE0()"
        plane = WorkPlane.from_hop_line(line)

        assert plane == WorkPlane.TOP
        assert str(plane) == "EBENE0()"

    def test_parse_standard_plane_ebene_format(self):
        """Test parsing EBENE(1) format."""
        line = "EBENE(1)"
        plane = WorkPlane.from_hop_line(line)

        assert plane == WorkPlane.FRONT

    def test_parse_free_plane(self):
        """Test parsing EBENEF (free plane) line."""
        line = "EBENEF(1351.763,268.987,182.642,13.003,0,0,0)"
        plane = FreePlane.from_hop_line(line)

        assert plane.x == pytest.approx(1351.763)
        assert plane.y == pytest.approx(268.987)
        assert plane.z == pytest.approx(182.642)
        assert plane.rotation_angle == pytest.approx(13.003)
        assert plane.tilt_angle == pytest.approx(0.0)


class TestVarsParsing:
    """Test VARS section parsing"""

    def test_parse_vars_with_comments(self):
        """Test parsing VARS from actual test.hop format."""
        if not os.path.exists(TEST_HOP_FILE):
            pytest.skip("Test file not found")

        job = HOPSJob.from_hop_file(TEST_HOP_FILE)
        assert job.vars.dx == pytest.approx(1352.233)
        assert job.vars.dy == pytest.approx(140.0)
        assert job.vars.dz == pytest.approx(100.0)


class TestFinishedPartParsing:
    """Test FERTIGTEIL parsing"""

    def test_parse_fertigteil_with_variable_refs(self):
        """Test parsing FERTIGTEIL with DX/DY/DZ variable references."""
        line = "FERTIGTEIL(DX,DY,DZ,0,0,0,0,0,'',0,0,0)"
        part = FinishedPart.from_hop_line(line)

        # Variable references should result in None
        assert part.dx is None
        assert part.dy is None
        assert part.dz is None
        assert part.rotation_flag == 0


class TestParkModeParsing:
    """Test Park_V7 parsing"""

    def test_parse_park_mode(self):
        """Test parsing Park_V7 line."""
        line = "CALL Park_V7 ( VAL MODE:=11,POSX:=0,POSY:=0)"
        park = ParkMode.from_hop_line(line)

        assert park.mode == 11
        assert park.pos_x == pytest.approx(0.0)
        assert park.pos_y == pytest.approx(0.0)


class TestSawingOperationParsing:
    """Test SAEGEN parsing"""

    def test_parse_sawing_operation(self):
        """Test parsing SAEGEN line from test.hop."""
        line = "SAEGEN(105.607,140,-157.631,105.607,0,-157.631,0,0,0,1,-18.997,0,0,0,2,0,0)"
        op = SawingOperation.from_hop_line(line)

        assert op.sx == pytest.approx(105.607)
        assert op.sy == pytest.approx(140.0)
        assert op.sz == pytest.approx(-157.631)
        assert op.ex == pytest.approx(105.607)
        assert op.ey == pytest.approx(0.0)
        assert op.ez == pytest.approx(-157.631)


class TestMillingOperationParsing:
    """Test milling operation (SP/G01/EP) parsing"""

    def test_parse_start_point(self):
        """Test parsing SP line."""
        line = "SP(0,0,0,0,0,_ANF,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)"
        sp = StartPoint.from_hop_line(line)

        assert sp.x == pytest.approx(0.0)
        assert sp.y == pytest.approx(0.0)
        assert sp.z == pytest.approx(0.0)

    def test_parse_g01(self):
        """Test parsing G01 line."""
        line = "G01(0,0,-58.974,0,0,2)"
        g01 = G01.from_hop_line(line)

        assert g01.x == pytest.approx(0.0)
        assert g01.y == pytest.approx(0.0)
        assert g01.z == pytest.approx(-58.974)

    def test_parse_end_point(self):
        """Test parsing EP line."""
        line = "EP(0,_ANF,0)"
        ep = EndPoint.from_hop_line(line)

        assert ep.lead_out_mode.value == 0
        assert ep.lead_out_factor is None  # _ANF
        assert ep.reverse_direction is False


class TestCompleteHOPFileParsing:
    """Integration tests for parsing complete HOP files"""

    def test_parse_complete_file(self):
        """Test parsing the entire test.hop file."""
        if not os.path.exists(TEST_HOP_FILE):
            pytest.skip("Test HOP file not found")

        job = HOPSJob.from_hop_file(TEST_HOP_FILE)

        # Check header
        assert job.header is not None
        assert len(job.header) > 0
        assert any("BILD" in line for line in job.header)
        assert any("INFO" in line for line in job.header)

        # Check variables
        assert job.vars.dx == pytest.approx(1352.233)
        assert job.vars.dy == pytest.approx(140.0)
        assert job.vars.dz == pytest.approx(100.0)

        # Check park mode
        assert job.park_mode.mode == 11

        # Check machinings - should have 5 operations (3 milling + 2 sawing)
        # Note: The two Birdsmouth operations share the same tool and workplane,
        # so they are combined into one chunk and only the first is parsed
        assert len(job.machinings) == 5

    def test_parse_tool_types(self):
        """Test that all tools are parsed correctly."""
        if not os.path.exists(TEST_HOP_FILE):
            pytest.skip("Test HOP file not found")

        job = HOPSJob.from_hop_file(TEST_HOP_FILE)

        router_count = sum(1 for m in job.machinings if m.tool.tool_type == ToolCallType.ROUTER)
        saw_count = sum(1 for m in job.machinings if m.tool.tool_type == ToolCallType.SAW)

        assert router_count == 3  # 1 Birdsmouth + 2 Castor (second Birdsmouth in same chunk)
        assert saw_count == 2

        # Check tool positions
        router_positions = {m.tool.position for m in job.machinings if m.tool.tool_type == ToolCallType.ROUTER}
        assert 503 in router_positions
        assert 504 in router_positions

        saw_positions = {m.tool.position for m in job.machinings if m.tool.tool_type == ToolCallType.SAW}
        assert 201 in saw_positions

    def test_parse_work_plane_types(self):
        """Test that all work planes are parsed correctly."""
        if not os.path.exists(TEST_HOP_FILE):
            pytest.skip("Test HOP file not found")

        job = HOPSJob.from_hop_file(TEST_HOP_FILE)

        freeplane_count = sum(1 for m in job.machinings if isinstance(m.work_plane, FreePlane))
        workplane_count = sum(1 for m in job.machinings if isinstance(m.work_plane, WorkPlane))

        assert freeplane_count == 1  # Birdsmouth operations (1 parsed from chunk with 2)
        assert workplane_count == 4  # Castor + Sawing operations

        # Check specific FreePlane details
        freeplane_ops = [m for m in job.machinings if isinstance(m.work_plane, FreePlane)]
        assert freeplane_ops[0].work_plane.x == pytest.approx(1351.763)
        assert freeplane_ops[0].work_plane.y == pytest.approx(268.987)

        # Check WorkPlane types
        workplane_ops = [m for m in job.machinings if isinstance(m.work_plane, WorkPlane)]

    def test_parse_operation_types(self):
        """Test that all operations are parsed correctly."""
        if not os.path.exists(TEST_HOP_FILE):
            pytest.skip("Test HOP file not found")

        job = HOPSJob.from_hop_file(TEST_HOP_FILE)

        # Count operations - note operations is now a list per machining
        milling_count = sum(len([op for op in m.operations if isinstance(op, MillingOperation)]) for m in job.machinings)
        sawing_count = sum(len([op for op in m.operations if isinstance(op, SawingOperation)]) for m in job.machinings)
        drilling_count = sum(len([op for op in m.operations if isinstance(op, DrillingOperation)]) for m in job.machinings)

        assert milling_count >= 3  # At least 3 milling operations
        assert sawing_count == 2  # 2 sawing operations
        assert drilling_count == 0  # No drilling in this file
        assert sawing_count == 2  # 2 SaegeD350 operations
        assert drilling_count == 0  # No drilling in this file

    def test_parse_milling_with_freeplane_details(self):
        """Test detailed parsing of milling operations with FreePlane."""
        if not os.path.exists(TEST_HOP_FILE):
            pytest.skip("Test HOP file not found")

        job = HOPSJob.from_hop_file(TEST_HOP_FILE)

        # Get Birdsmouth operations (use FreePlane) - now need to check operations list
        birdsmouth_ops = [m for m in job.machinings if isinstance(m.work_plane, FreePlane)]

        assert len(birdsmouth_ops) >= 1  # At least 1 machining block

        # Check first Birdsmouth operation
        m = birdsmouth_ops[0]
        assert m.tool.position == 504
        assert m.work_plane.rotation_angle == pytest.approx(13.003)
        # Check first operation in the list
        assert len(m.operations) > 0
        first_op = m.operations[0]
        assert isinstance(first_op, MillingOperation)
        assert first_op.start_point.x == pytest.approx(0.0)
        assert first_op.start_point.y == pytest.approx(0.0)
        assert len(first_op.moves) >= 7  # Multiple G01 moves

    def test_parse_sawing_operations_details(self):
        """Test detailed parsing of sawing operations."""
        if not os.path.exists(TEST_HOP_FILE):
            pytest.skip("Test HOP file not found")

        job = HOPSJob.from_hop_file(TEST_HOP_FILE)

        sawing_ops = [m for m in job.machinings if any(isinstance(op, SawingOperation) for op in m.operations)]
        assert len(sawing_ops) == 2

        # First sawing operation
        s1 = sawing_ops[0]
        assert s1.tool.tool_type == ToolCallType.SAW
        assert s1.tool.position == 201
        assert s1.work_plane == WorkPlane.TOP
        # Get first sawing operation from the list
        saw_op = s1.operations[0]
        assert isinstance(saw_op, SawingOperation)
        assert saw_op.sx == pytest.approx(105.607)
        assert saw_op.sy == pytest.approx(140.0)
        assert saw_op.sz == pytest.approx(-157.631)
        assert saw_op.ex == pytest.approx(105.607)
        assert saw_op.ey == pytest.approx(0.0)
        assert saw_op.ez == pytest.approx(-157.631)

        # Second sawing operation
        s2 = sawing_ops[1]
        saw_op2 = s2.operations[0]
        assert isinstance(saw_op2, SawingOperation)
        assert saw_op2.sx == pytest.approx(1240.165)
        assert saw_op2.sy == pytest.approx(0.0)

    @pytest.mark.xfail(reason="Round-trip loses milling operations - needs comment preservation")
    def test_round_trip(self):
        """Test that parsing and regenerating produces valid output.

        Currently fails because milling operations require intermediate comments
        or CALL _Tvorschub_v5 lines that aren't preserved during serialization.
        """
        if not os.path.exists(TEST_HOP_FILE):
            pytest.skip("Test HOP file not found")

        # Parse original
        job = HOPSJob.from_hop_file(TEST_HOP_FILE)
        original_count = len(job.machinings)

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".hop", delete=False) as f:
            temp_path = f.name

        try:
            job.to_hop_file(temp_path)

            # Parse again
            job2 = HOPSJob.from_hop_file(temp_path)

            # Verify
            assert job2.vars.dx == pytest.approx(job.vars.dx)
            assert len(job2.machinings) == original_count  # This currently fails

        finally:
            Path(temp_path).unlink()


class TestStrictModeParsing:
    """Test strict mode error handling."""

    def test_lenient_mode_succeeds_with_warnings(self):
        """Test that lenient mode (default) parses valid files without errors."""
        if not os.path.exists(TEST_HOP_FILE):
            pytest.skip("Test HOP file not found")

        # Should succeed and collect warnings if any
        job = HOPSJob.from_hop_file(TEST_HOP_FILE, strict=False)
        assert job is not None
        assert len(job.machinings) == 5

    def test_strict_mode_on_valid_file(self):
        """Test that strict mode succeeds on valid files."""
        if not os.path.exists(TEST_HOP_FILE):
            pytest.skip("Test HOP file not found")

        # Should succeed without raising
        job = HOPSJob.from_hop_file(TEST_HOP_FILE, strict=True)
        assert job is not None
        assert len(job.machinings) == 5

    def test_strict_mode_on_invalid_file(self):
        """Test that strict mode raises detailed error on invalid lines."""
        # Create a temp file with invalid content
        invalid_content = """VARS
   DX := 1000
   DY := 500
   DZ := 100
START

FERTIGTEIL(DX,DY,DZ,0,0,0,0,0,'',0,0,0)
CALL Park_V7 ( VAL MODE:=11,POSX:=0,POSY:=0)

WZF(504,3000,4000,5000,_SD,_ANF,'1')
INVALID_WORKPLANE_COMMAND(1,2,3)
SP(0,0,0,0,0,_ANF,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".hop", delete=False) as f:
            f.write(invalid_content)
            temp_path = f.name

        try:
            # Should raise HOPParsingError with detailed context
            with pytest.raises(HOPParsingError) as exc_info:
                HOPSJob.from_hop_file(temp_path, strict=True)

            error_msg = str(exc_info.value)

            # Check error message contains debug info
            assert "HOP PARSING ERROR" in error_msg
            assert temp_path in error_msg or "line" in error_msg.lower()
            assert "INVALID_WORKPLANE_COMMAND" in error_msg

            # Check that it shows line context
            assert "Line context:" in error_msg or "WZF" in error_msg

        finally:
            Path(temp_path).unlink()

    def test_unparsed_line_error_attributes(self):
        """Test that UnparsedLineError contains all expected attributes."""
        error = UnparsedLineError(line_number=42, line_content="INVALID_COMMAND(1,2,3)\n", context="Expected work plane")

        assert error.line_number == 42
        assert "INVALID_COMMAND" in error.line_content
        assert error.context == "Expected work plane"
        assert "Line 42" in str(error)
        assert "Expected work plane" in str(error)
