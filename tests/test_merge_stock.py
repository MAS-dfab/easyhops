"""
Tests for merge_stock_hops module

Simple tests for the stock-level HOPS merger functionality.
"""

import pytest
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from merge_stock_hops import HopOperation, HopFile, StockHopsMerger


class TestHopOperation:
    """Test HopOperation class for offsetting coordinates"""

    def test_extract_tool_type(self):
        """Test tool type extraction from command"""
        tool_cmd = "WZS(201,10000,7000,20000,_SD,_ANF,'1')\n"
        lines = [tool_cmd]
        op = HopOperation(tool_cmd, lines)
        assert op.tool_type == "WZS201"

    def test_offset_ebenef(self):
        """Test X-offset on EBENEF command"""
        tool_cmd = "WZF(504,3000,4000,5000,_SD,_ANF,'1')\n"
        lines = [tool_cmd, "EBENEF(100.000,50.000,30.000,15.5,0,0,0)\n"]
        op = HopOperation(tool_cmd, lines)
        offset_lines = op.apply_offset(500.0)

        # Find EBENEF line
        ebenef_line = [l for l in offset_lines if "EBENEF" in l][0]
        assert "600.0000" in ebenef_line  # 100 + 500
        assert "50.000" in ebenef_line  # Y unchanged

    def test_offset_saegen(self):
        """Test X-offset on SAEGEN command (both X coordinates)"""
        tool_cmd = "WZS(201,10000,7000,20000,_SD,_ANF,'1')\n"
        lines = [
            tool_cmd,
            "EBENE0()\n",
            "SAEGEN(120.051,137.872,-126.097,71.684,-21.725,-126.097,0,0,0,1,-25.763,0,0,0,2,0,0)\n",
        ]
        op = HopOperation(tool_cmd, lines)
        offset_lines = op.apply_offset(1000.0)

        # Find SAEGEN line
        saegen_line = [l for l in offset_lines if "SAEGEN" in l][0]
        assert "1120.051" in saegen_line  # First X: 120.051 + 1000
        assert "1071.684" in saegen_line  # Second X: 71.684 + 1000


class TestHopFile:
    """Test HopFile parsing"""

    def test_parse_hop_file(self):
        """Test parsing a real .hop file"""
        test_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "src",
            "test_files",
            "2811_whole_model",
            "2811_whole_model",
            "R_00_1.hop",
        )

        if os.path.exists(test_file):
            hop = HopFile(test_file)
            assert hop.dx is not None
            assert len(hop.operations) > 0
            assert hop.dx > 0
        else:
            pytest.skip("Test file not found")


class TestStockHopsMerger:
    """Test StockHopsMerger integration"""

    def test_load_nesting_json(self):
        """Test loading nesting JSON"""
        test_json = os.path.join(
            os.path.dirname(__file__),
            "..",
            "src",
            "test_files",
            "2811_whole_model",
            "2811_whole_model_nesting.json",
        )

        if os.path.exists(test_json):
            hop_dir = os.path.join(
                os.path.dirname(__file__),
                "..",
                "src",
                "test_files",
                "2811_whole_model",
                "2811_whole_model",
            )

            merger = StockHopsMerger(test_json, hop_dir)
            assert merger.stock_info is not None
            assert "length" in merger.stock_info
            assert len(merger.hop_files) > 0
        else:
            pytest.skip("Test data not found")
