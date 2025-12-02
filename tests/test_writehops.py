"""
Tests for writehops module

Simple tests for HOPS writer and beam merger functionality.
"""

import pytest
import os
import sys
import tempfile

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from writehops import HOPSWriter, HOPSBeamMerger


class TestHOPSWriter:
    """Test HOPSWriter functionality"""

    def test_header_generation(self):
        """Test HOPS file header generation"""
        writer = HOPSWriter(length=2000, width=60)
        header = writer.header

        assert "DX := 2000" in header
        assert "DY := 60" in header
        assert "FERTIGTEIL" in header

    def test_write_to_file(self):
        """Test writing HOPS file"""
        writer = HOPSWriter(length=1500, width=80)
        writer.hop = writer.header + writer.toolcall

        with tempfile.NamedTemporaryFile(mode="w", suffix=".hop", delete=False) as f:
            temp_path = f.name

        try:
            writer.write_to_file(temp_path)
            assert os.path.exists(temp_path)

            with open(temp_path, "r") as f:
                content = f.read()
                assert "DX := 1500" in content
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestHOPSBeamMerger:
    """Test HOPSBeamMerger functionality"""

    def test_merger_initialization(self):
        """Test merger can be initialized"""
        merger = HOPSBeamMerger()
        assert merger.merged_content == ""
        assert merger.types == []
