"""Unit tests for HOPSJob and HOPSMachining object behavior.

This module tests the object-oriented behavior of HOPSJob and HOPSMachining classes,
including initialization, string representations, and serialization methods.

For parsing tests, see test_hop_job_parsing.py
"""

import tempfile
from pathlib import Path

from easyhops.hop_core import FinishedPart, ParkMode, ParkPosition, VarsDefinition
from easyhops.hop_job import HOPSJob, HOPSMachining
from easyhops.machining_commands import (
    DrillingOperation,
    EndPoint,
    G01,
    MillingOperation,
    SawingFreeOperation,
    StartPoint,
)
from easyhops.tool_library import MachiningTool, ToolCallType
from easyhops.work_planes import FreePlane, WorkPlane


class TestMachining:
    """Tests for HOPSMachining class object behavior."""

    def test_machining_init(self):
        """Test HOPSMachining initialization."""
        tool = MachiningTool(ToolCallType.ROUTER, 1, name="Test Router")
        plane = WorkPlane.FRONT
        sp = StartPoint(100.0, 200.0, -20.0)
        ep = EndPoint()
        op = MillingOperation(sp, [], ep)

        machining = HOPSMachining(tool, plane, [op])

        assert machining.tool == tool
        assert machining.work_plane == plane
        assert len(machining.operations) == 1
        assert machining.operations[0] == op

    def test_machining_repr(self):
        """Test HOPSMachining __repr__."""
        tool = MachiningTool(ToolCallType.ROUTER, 1, name="Router")
        plane = WorkPlane.FRONT
        sp = StartPoint(100.0, 200.0, -20.0)
        ep = EndPoint()
        op = MillingOperation(sp, [], ep)

        machining = HOPSMachining(tool, plane, op)

        repr_str = repr(machining)
        assert "WZF" in repr_str
        assert "MillingOperation" in repr_str

    def test_machining_str_milling_with_workplane(self):
        """Test HOPSMachining __str__ with milling operation and standard work plane."""
        tool = MachiningTool(ToolCallType.ROUTER, 1)
        plane = WorkPlane.FRONT
        sp = StartPoint(100.0, 200.0, -20.0)
        g01 = G01(150.0, 250.0, -20.0)
        ep = EndPoint()
        op = MillingOperation(sp, [g01], ep)

        machining = HOPSMachining(tool, plane, op)

        output = str(machining)
        assert "WZF(" in output
        assert "EBENE1()" in output
        assert "SP(" in output
        assert "G01(" in output
        assert "EP(" in output

    def test_machining_str_milling_with_freeplane(self):
        """Test HOPSMachining __str__ with milling operation and free plane."""
        tool = MachiningTool(ToolCallType.ROUTER, 1)
        plane = FreePlane(100.0, 50.0, 0.0, 45.0, 0.0)
        sp = StartPoint(100.0, 200.0, -20.0)
        g01 = G01(150.0, 250.0, -20.0)
        ep = EndPoint()
        op = MillingOperation(sp, [g01], ep)

        machining = HOPSMachining(tool, plane, op)

        output = str(machining)
        assert "WZF(" in output
        assert "EBENEF(" in output
        assert "SP(" in output
        assert "G01(" in output
        assert "EP(" in output

    def test_machining_str_sawing(self):
        """Test HOPSMachining __str__ with sawing operation."""
        tool = MachiningTool(ToolCallType.SAW, 2)
        plane = WorkPlane.BACK
        op = SawingFreeOperation(100.0, 200.0, -30.0, 150.0, 250.0, -30.0)

        machining = HOPSMachining(tool, plane, op)

        output = str(machining)
        assert "WZS(" in output
        assert "EBENE3()" in output
        assert "CALL _saege_frei_V7" in output

    def test_machining_str_drilling(self):
        """Test HOPSMachining __str__ with drilling operation."""
        tool = MachiningTool(ToolCallType.DRILLER, 3)
        plane = FreePlane(50.0, 100.0, 0.0, 0.0, 0.0)
        op = DrillingOperation(100.0, 200.0, -30.0, depth=50.0, diameter=8.0)

        machining = HOPSMachining(tool, plane, op)

        output = str(machining)
        assert "WZB(" in output
        assert "EBENEF(" in output
        assert "BOHRUNG(" in output


class TestHOPSJob:
    """Tests for HOPSJob class object behavior."""

    def test_HOPSJob_init(self):
        \"\"\"Test HOPSJob initialization.\"\"\"
        vars_def = VarsDefinition(1000.0, 500.0, 50.0)
        finished_part = FinishedPart(1000.0, 500.0, 50.0)
        park_mode = ParkPosition(ParkMode.AUTOMATIC, 0, 0)
        machinings = []

        job = HOPSJob(vars_def, finished_part, park_mode, machinings)

        assert job.vars == vars_def
        assert job.finished_part == finished_part
        assert job.park_mode == park_mode
        assert job.machinings == machinings
        assert job.header is None

    def test_HOPSJob_init_with_header(self):
        \"\"\"Test HOPSJob initialization with header.\"\"\"
        vars_def = VarsDefinition(1000.0, 500.0, 50.0)
        finished_part = FinishedPart(1000.0, 500.0, 50.0)
        park_mode = ParkPosition(ParkMode.AUTOMATIC, 0, 0)
        machinings = []
        header = [\"; Test header\", \"; Another comment\"]

        job = HOPSJob(vars_def, finished_part, park_mode, machinings, header=header)

        assert job.header == header

    def test_HOPSJob_repr(self):
        """Test HOPSJob __repr__."""
        vars_def = VarsDefinition(1000.0, 500.0, 50.0)
        finished_part = FinishedPart(1000.0, 500.0, 50.0)
        park_mode = ParkPosition(ParkMode.AUTOMATIC, 0, 0)
        machinings = []

        job = HOPSJob(vars_def, finished_part, park_mode, machinings)

        repr_str = repr(job)
        assert "HOPSJob" in repr_str
        assert "machinings=0" in repr_str

    def test_HOPSJob_str_simple(self):
        """Test HOPSJob __str__ with simple job."""
        vars_def = VarsDefinition(1000.0, 500.0, 50.0)
        finished_part = FinishedPart(1000.0, 500.0, 50.0)
        park_mode = ParkPosition(ParkMode.AUTOMATIC, 0, 0)
        machinings = []

        job = HOPSJob(vars_def, finished_part, park_mode, machinings)

        output = str(job)
        assert "VARS" in output
        assert "DX := 1000.0" in output
        assert "FERTIGTEIL(" in output
        assert "Park_V7" in output

    def test_HOPSJob_str_with_header(self):
        """Test HOPSJob __str__ includes header."""
        vars_def = VarsDefinition(1000.0, 500.0, 50.0)
        finished_part = FinishedPart(1000.0, 500.0, 50.0)
        park_mode = ParkPosition(ParkMode.AUTOMATIC, 0, 0)
        header = ["; Test header", "; Comment line 2"]

        job = HOPSJob(vars_def, finished_part, park_mode, [], header=header)

        output = str(job)
        lines = output.split("\n")
        assert lines[0] == "; Test header"
        assert lines[1] == "; Comment line 2"

    def test_HOPSJob_str_with_machinings(self):
        """Test HOPSJob __str__ with machining operations."""
        vars_def = VarsDefinition(1000.0, 500.0, 50.0)
        finished_part = FinishedPart(1000.0, 500.0, 50.0)
        park_mode = ParkPosition(ParkMode.AUTOMATIC, 0, 0)

        # Create a milling operation
        tool = MachiningTool(tool_type=ToolCallType.ROUTER, position=1)
        plane = WorkPlane.TOP
        sp = StartPoint(100.0, 200.0, -20.0)
        g01 = G01(150.0, 250.0, -20.0)
        ep = EndPoint()
        milling_op = MillingOperation(sp, [g01], ep)
        machining1 = HOPSMachining(tool, plane, milling_op)

        # Create a sawing operation
        saw_op = SawingFreeOperation(100.0, 200.0, -30.0, 150.0, 250.0, -30.0)
        machining2 = HOPSMachining(tool, plane, saw_op)

        job = HOPSJob(vars_def, finished_part, park_mode, [machining1, machining2])

        output = str(job)
        assert "WZF(" in output
        assert "EBENE0()" in output
        assert "SP(" in output
        assert "G01(" in output
        assert "EP(" in output
        assert "CALL _saege_frei_V7" in output

    def test_HOPSJob_to_hop_file(self):
        """Test HOPSJob.to_hop_file() writes to file."""
        vars_def = VarsDefinition(1000.0, 500.0, 50.0)
        finished_part = FinishedPart(1000.0, 500.0, 50.0)
        park_mode = ParkPosition(ParkMode.AUTOMATIC, 0, 0)
        header = ["; Test file"]

        job = HOPSJob(vars_def, finished_part, park_mode, [], header=header)

        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".hop", delete=False) as f:
            temp_path = f.name

        try:
            job.to_hop_file(temp_path)

            # Read back and verify
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()

            assert "; Test file" in content
            assert "VARS" in content
            assert "FERTIGTEIL(" in content
            assert "Park_V7" in content
        finally:
            Path(temp_path).unlink()
