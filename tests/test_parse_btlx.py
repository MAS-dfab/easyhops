"""
Tests for parse_btlx module

Simple tests for BTLx XML parsing functionality.
"""

import pytest
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from parse_btlx import BTLXParser


class TestBTLXParser:
    """Test BTLXParser functionality"""

    def test_parse_btlx_file(self):
        """Test parsing a BTLx XML file"""
        test_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "src",
            "test_files",
            "2811_whole_model",
            "2811_whole_model.btlx",
        )

        if os.path.exists(test_file):
            parser = BTLXParser(test_file)
            assert parser.part_lengths is not None
            assert len(parser.part_lengths) > 0
        else:
            pytest.skip("Test BTLx file not found")

    def test_remachining_dict(self):
        """Test remachining dictionary generation"""
        test_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "src",
            "test_files",
            "2811_whole_model",
            "2811_whole_model.btlx",
        )

        if os.path.exists(test_file):
            parser = BTLXParser(test_file)
            remach_dict = parser.get_remachining_dict()
            assert isinstance(remach_dict, dict)
        else:
            pytest.skip("Test BTLx file not found")
