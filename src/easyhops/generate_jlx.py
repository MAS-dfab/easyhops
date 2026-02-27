"""
JLX Layout File Generator for Holz-Her CNC Machines

This module generates .jlx (Job Layout XML) files that can be imported into
the BZ_manual/Workcenter software on Holz-Her CNC machines. These layout files
define workpiece positions and bar/traverse configurations on the machine table.

Classes:
    JLXGenerator: Main class for generating JLX layout files

Usage Example:
    ```python
    from easyhops.generate_jlx import JLXGenerator

    # Create generator for machine 7235C_219
    generator = JLXGenerator(machine_id="7235C_219")

    # Add workpiece with bar positions
    generator.add_workpiece(
        hop_filename="S0_R01.hop",
        hop_path="D:\\Campus\\Data\\jobs_archive\\T2\\M29\\",
        bar_positions=[660.26, 1350.84, 1820.30, 2555.64, 3941.0, 4138.5],
        dimensions=(2160, 60, 60),  # DX, DY, DZ
        placement=(55.64, 38.22, 125),  # X, Y, Z placement
    )

    # Write JLX file
    generator.write_jlx("output_layout.jlx")
    ```
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List
from typing import Tuple


class JLXGenerator:
    """
    Generator for JLX layout files for Holz-Her CNC machines.

    This class creates XML layout files that define workpiece positions,
    bar/traverse configurations, and machine settings for the BZ_manual/Workcenter
    software interface.

    Attributes:
        machine_id (str): Machine identifier (e.g., "7235C_219")
        field_id (int): Current field ID counter
        traverse_id (int): Current traverse ID counter
        workpiece_id (int): Current workpiece ID counter
        fields (list): List of field configurations
    """

    def __init__(self, machine_id: str = "7235C_219"):
        """
        Initialize JLX generator.

        Args:
            machine_id: Machine identifier string
        """
        self.machine_id = machine_id
        self.field_id = 0
        self.traverse_id = 0
        self.workpiece_id = 0
        self.fields = []

    def add_workpiece(
        self,
        hop_filename: str,
        hop_path: str,
        bar_positions: List[float],
        dimensions: Tuple[float, float, float],
        placement: Tuple[float, float, float] = (0, 0, 0),
        rotation: int = 0,
        mirror_x: bool = False,
        mirror_y: bool = False,
        stop_name: str = "AV",
    ):
        """
        Add a workpiece to the layout with specified bar positions.

        Args:
            hop_filename: Name of the HOP file (e.g., "S0_R01.hop")
            hop_path: Absolute path to HOP file directory
            bar_positions: List of 6 X-coordinates for bar/traverse positions (consoles K1-K6)
            dimensions: Tuple of (DX, DY, DZ) workpiece dimensions in mm
            placement: Tuple of (X, Y, Z) placement coordinates, default (0, 0, 0)
            rotation: Rotation code (0=0°, 1=90°, 2=180°, 3=270°), default 0
            mirror_x: Mirror along X-axis, default False
            mirror_y: Mirror along Y-axis, default False
            stop_name: Stop position name, default "AV"

        Raises:
            ValueError: If bar_positions doesn't contain exactly 6 values
        """
        OFFSET_X = 56.0  # Offset from the origin of the machine to the origin of the part

        if len(bar_positions) != 6:
            raise ValueError(f"bar_positions must contain exactly 6 values, got {len(bar_positions)}")

        # Standard Y, Z positions for bars (from example file)
        y_pos = 55.0
        z_pos = 0.0

        # Split bar positions into two fields (3 bars each)
        # Field 0: bars 0-2 (K1, K2, K3)
        # Field 1: bars 3-5 (K4, K5, K6)
        field_bar_groups = [bar_positions[0:3], bar_positions[3:6]]

        for field_idx, field_bars in enumerate(field_bar_groups):
            # Create field with traverses (bar positions)
            field_data = {"field_id": self.field_id, "traverses": [], "workpiece": None}

            # Create 3 traverses for this field
            for local_i, x_pos in enumerate(field_bars):
                # Calculate position with offset (consistent +56 offset for all)
                position_x = x_pos + OFFSET_X

                # Calculate bounds (based on example file pattern)
                left = position_x - 275.5
                right = position_x + 102.0
                top = 1580.0
                bottom = -45.0

                traverse_data = {
                    "traverse_id": self.traverse_id,
                    "field_id": self.field_id,
                    "position": (int(position_x), int(y_pos), int(z_pos)),
                    "display": (int(x_pos), 0, 0),
                    "bounds": {"top": int(top), "bottom": int(bottom), "left": int(left), "right": int(right)},
                    "height": 0,
                }

                field_data["traverses"].append(traverse_data)
                self.traverse_id += 1

            # Create workpiece data (one per field)
            dx, dy, dz = dimensions
            px, py, pz = placement

            # Prepare variables (DX, DY, DZ)
            vars_dict = {"DX": dx, "DY": dy, "DZ": dz}

            workpiece_data = {
                "id": self.workpiece_id,
                "field": self.field_id,
                "name": hop_filename,
                "path": hop_path,
                "rotation": rotation,
                "stop_name": stop_name,
                "mirror_x": mirror_x,
                "mirror_y": mirror_y,
                "variables": vars_dict,
                "placement": (px, py, pz),
                "dimensions": (dx, dy, dz),
            }

            field_data["workpiece"] = workpiece_data
            self.fields.append(field_data)

            self.field_id += 1
            self.workpiece_id += 1

    def _create_xml_tree(self) -> ET.ElementTree:
        """
        Create the XML tree structure for the JLX file.

        Returns:
            ElementTree object containing the complete JLX structure
        """
        root = ET.Element("Data")

        # Create HeadInfo section
        head_info = ET.SubElement(root, "HeadInfo")
        ET.SubElement(head_info, "ActiveMachine").text = self.machine_id
        ET.SubElement(head_info, "TableConfig")

        # TimeStamp (Excel serial date format)
        timestamp = 40000 + (datetime.now() - datetime(1900, 1, 1)).days
        ET.SubElement(head_info, "TimeStamp").text = str(timestamp)

        ET.SubElement(head_info, "Checksume").text = "2"
        ET.SubElement(head_info, "ActiveFields").text = "0"
        ET.SubElement(head_info, "Activated").text = "-3"
        ET.SubElement(head_info, "FieldLink").text = "3"
        ET.SubElement(head_info, "Info")
        ET.SubElement(head_info, "Version").text = "2"
        ET.SubElement(head_info, "Mode").text = "0"
        ET.SubElement(head_info, "AutoStart").text = "0"

        # Create Fields sections
        for field_data in self.fields:
            fields_elem = ET.SubElement(root, "Fields")
            ET.SubElement(fields_elem, "FieldID").text = str(field_data["field_id"])
            ET.SubElement(fields_elem, "type").text = "0"
            ET.SubElement(fields_elem, "Used").text = "True"

            # Create Scenes element with all 3 traverses
            scenes_elem = ET.SubElement(fields_elem, "Scenes")
            scene_data = ET.SubElement(scenes_elem, "SceneData")
            ET.SubElement(scene_data, "Mode").text = "0"
            ET.SubElement(scene_data, "Checksume").text = "0"
            ET.SubElement(scene_data, "Name")

            # Add all traverses for this field
            for trav_data in field_data["traverses"]:
                self._add_traverse_element(scenes_elem, trav_data)

            # Add workpiece if present
            if field_data["workpiece"]:
                self._add_workpiece_element(fields_elem, field_data["workpiece"])

        return ET.ElementTree(root)

    def _add_traverse_element(self, parent: ET.Element, trav_data: dict):
        """Add a Traverse element to the parent."""
        traverse_elem = ET.SubElement(parent, "Traverse")
        trav_data_elem = ET.SubElement(traverse_elem, "TraverseData")

        ET.SubElement(trav_data_elem, "TraverseID").text = str(trav_data["traverse_id"])
        ET.SubElement(trav_data_elem, "type").text = "0"
        ET.SubElement(trav_data_elem, "FieldID").text = str(trav_data["field_id"])

        # Position
        pos_elem = ET.SubElement(trav_data_elem, "Position")
        px, py, pz = trav_data["position"]
        ET.SubElement(pos_elem, "XPos").text = str(px)
        ET.SubElement(pos_elem, "YPos").text = str(py)
        ET.SubElement(pos_elem, "ZPos").text = str(pz)

        ET.SubElement(trav_data_elem, "Used").text = "False"

        # Display
        disp_elem = ET.SubElement(trav_data_elem, "Display")
        dx, dy, dz = trav_data["display"]
        ET.SubElement(disp_elem, "XPos").text = str(dx)
        ET.SubElement(disp_elem, "YPos").text = str(dy)
        ET.SubElement(disp_elem, "ZPos").text = str(dz)

        # Bounds
        bounds_elem = ET.SubElement(trav_data_elem, "Bounds")
        bounds = trav_data["bounds"]
        ET.SubElement(bounds_elem, "Top").text = str(bounds["top"])
        ET.SubElement(bounds_elem, "Bottom").text = str(bounds["bottom"])
        ET.SubElement(bounds_elem, "Left").text = str(bounds["left"])
        ET.SubElement(bounds_elem, "Right").text = str(bounds["right"])

        ET.SubElement(trav_data_elem, "Height").text = str(trav_data["height"])
        # Add pad element
        self._add_pad_element(traverse_elem, trav_data)

    def _add_pad_element(self, parent: ET.Element, trav_data: dict):
        """Add a Pad element to the parent Traverse."""
        pad_elem = ET.SubElement(parent, "pad")
        pad_data = ET.SubElement(pad_elem, "PadData")

        ET.SubElement(pad_data, "PadID").text = "1"
        ET.SubElement(pad_data, "PadType").text = "114x140x125"
        ET.SubElement(pad_data, "BaseRot").text = "0"

        # Position - use traverse X position
        pos_elem = ET.SubElement(pad_data, "Position")
        px, _, _ = trav_data["position"]
        ET.SubElement(pos_elem, "XPos").text = str(px)
        ET.SubElement(pos_elem, "YPos").text = "121.42"
        ET.SubElement(pos_elem, "ZPos").text = "0"

        ET.SubElement(pad_data, "Used").text = "False"
        ET.SubElement(pad_data, "WorkpieceID").text = "-1"

        # Display
        disp_elem = ET.SubElement(pad_data, "Display")
        ET.SubElement(disp_elem, "XPos").text = "0"
        ET.SubElement(disp_elem, "YPos").text = "1430"
        ET.SubElement(disp_elem, "ZPos").text = "0"

        # Bounds
        bounds = trav_data["bounds"]
        bounds_elem = ET.SubElement(pad_data, "Bounds")
        ET.SubElement(bounds_elem, "Top").text = "204.42"
        ET.SubElement(bounds_elem, "Bottom").text = "64.4200000000001"
        ET.SubElement(bounds_elem, "Left").text = str(bounds["left"])
        ET.SubElement(bounds_elem, "Right").text = str(bounds["right"])

        ET.SubElement(pad_data, "Height").text = "125"

        # Clamps
        clamps_elem = ET.SubElement(pad_elem, "Clamps")
        ET.SubElement(clamps_elem, "ID").text = "0"

        clamp_pos = ET.SubElement(clamps_elem, "Position")
        ET.SubElement(clamp_pos, "XPos").text = "0"
        ET.SubElement(clamp_pos, "YPos").text = "0"
        ET.SubElement(clamp_pos, "ZPos").text = "0"

        ET.SubElement(clamps_elem, "ClampType").text = "114x140x125"
        ET.SubElement(clamps_elem, "Rot").text = "0"

        clamp_bounds = ET.SubElement(clamps_elem, "Bounds")
        ET.SubElement(clamp_bounds, "Top").text = "178.419574"
        ET.SubElement(clamp_bounds, "Bottom").text = "38.4195740000001"
        ET.SubElement(clamp_bounds, "Left").text = str(float(bounds["left"]) + 7)
        ET.SubElement(clamp_bounds, "Right").text = str(float(bounds["right"]) - 7)

        ET.SubElement(clamps_elem, "Height").text = "0"

    def _add_workpiece_element(self, parent: ET.Element, wp_data: dict):
        """Add a Workpiece element to the parent."""
        wp_elem = ET.SubElement(parent, "Workpiece")

        ET.SubElement(wp_elem, "ID").text = str(wp_data["id"])
        ET.SubElement(wp_elem, "Field").text = str(wp_data["field"])
        ET.SubElement(wp_elem, "Name").text = wp_data["name"]
        ET.SubElement(wp_elem, "Path").text = wp_data["path"]
        ET.SubElement(wp_elem, "RelPath").text = wp_data["path"]
        ET.SubElement(wp_elem, "JobRelPath")
        ET.SubElement(wp_elem, "Info")
        ET.SubElement(wp_elem, "RotCode").text = str(wp_data["rotation"])
        ET.SubElement(wp_elem, "StopID").text = "3"
        ET.SubElement(wp_elem, "StopName").text = wp_data["stop_name"]

        # Offset
        offset_elem = ET.SubElement(wp_elem, "Offset")
        ET.SubElement(offset_elem, "XOff").text = "0"
        ET.SubElement(offset_elem, "YOff").text = "0"
        ET.SubElement(offset_elem, "ZOff").text = "0"

        # Mirror
        mirror_elem = ET.SubElement(wp_elem, "Mirror")
        ET.SubElement(mirror_elem, "XMirr").text = str(wp_data["mirror_x"])
        ET.SubElement(mirror_elem, "YMirr").text = str(wp_data["mirror_y"])

        ET.SubElement(wp_elem, "Count").text = "0"

        # Variables
        for var_name, var_value in wp_data["variables"].items():
            var_elem = ET.SubElement(wp_elem, "Variable")
            ET.SubElement(var_elem, "VarName").text = var_name
            ET.SubElement(var_elem, "VarValue").text = str(var_value)

        # Placement
        placement_elem = ET.SubElement(wp_elem, "Placement")
        px, py, pz = wp_data["placement"]
        ET.SubElement(placement_elem, "X").text = str(px)
        ET.SubElement(placement_elem, "Y").text = str(py)
        ET.SubElement(placement_elem, "Z").text = str(pz)

        # Dimensions
        dims_elem = ET.SubElement(wp_elem, "Dimensions")
        dx, dy, dz = wp_data["dimensions"]
        ET.SubElement(dims_elem, "X").text = str(dx)
        ET.SubElement(dims_elem, "Y").text = str(dy)
        ET.SubElement(dims_elem, "Z").text = str(dz)

    def write_jlx(self, output_path: str):
        """
        Write the JLX file to disk.

        Args:
            output_path: Path where the JLX file should be written
        """
        tree = self._create_xml_tree()

        # Pretty print with proper formatting
        self._indent(tree.getroot())

        # Write with XML declaration
        tree.write(output_path, encoding="utf-8", xml_declaration=True)

        print(f"✅ JLX file written to: {output_path}")

    def _indent(self, elem, level=0):
        """
        Add indentation to XML tree for pretty printing.

        Args:
            elem: XML element to indent
            level: Current indentation level
        """
        indent = "\n" + "  " * level
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent


# def generate_jlx_from_nesting(nesting_json_path: str, hop_directory: str, output_path: str, machine_id: str = "7235C_219", bar_positions: List[float] = None):
#     """
#     Generate JLX layout file from nesting JSON and merged HOP files.

#     This is a convenience function that creates a JLX layout for stocks
#     based on nesting data and merged stock HOP files.

#     Args:
#         nesting_json_path: Path to nesting JSON file
#         hop_directory: Directory containing merged stock HOP files
#         output_path: Path for output JLX file
#         machine_id: Machine identifier, default "7235C_219"
#         bar_positions: List of 6 bar positions. If None, uses default positions

#     Example:
#         >>> generate_jlx_from_nesting(nesting_json_path="nesting.json", hop_directory="./merged/", output_path="layout.jlx", bar_positions=[660, 1350, 1820, 2555, 3941, 4138])
#     """
#     import json
#     import glob
#     import os

#     # Default bar positions if not provided
#     if bar_positions is None:
#         bar_positions = [660.26, 1350.84, 1820.30, 2555.64, 3941.0, 4138.5]

#     # Load nesting data
#     with open(nesting_json_path, "r") as f:
#         nesting_data = json.load(f)

#     generator = JLXGenerator(machine_id=machine_id)

#     # Find all merged stock HOP files
#     stock_files = glob.glob(os.path.join(hop_directory, "S*.hop"))

#     for stock_file in stock_files:
#         stock_filename = os.path.basename(stock_file)

#         # Try to parse stock dimensions from nesting data
#         # This is simplified - you may need to adjust based on your nesting format
#         try:
#             # Extract stock index from filename (e.g., S0_R01.hop -> 0)
#             import re

#             match = re.match(r"S(\d+)", stock_filename)
#             if match:
#                 stock_idx = int(match.group(1))

#                 # Get dimensions from nesting data
#                 if stock_idx < len(nesting_data.get("data", {}).get("stocks", [])):
#                     stock_data = nesting_data["data"]["stocks"][stock_idx]["data"]
#                     stock_length = stock_data["length"]
#                     width, height = stock_data["cross_section"]

#                     generator.add_workpiece(
#                         hop_filename=stock_filename,
#                         hop_path=os.path.abspath(hop_directory) + "\\",
#                         bar_positions=bar_positions,
#                         dimensions=(stock_length, width, height),
#                         placement=(0, 0, 0),
#                     )
#         except Exception as e:
#             print(f"⚠️  Warning: Could not process {stock_filename}: {e}")
#             continue

#     generator.write_jlx(output_path)


# if __name__ == "__main__":
#     # Example usage
#     generator = JLXGenerator(machine_id="7235C_219")

#     # Add a stock workpiece with 6 bar positions
#     generator.add_workpiece(
#         hop_filename="S0_R01.hop",
#         hop_path="D:\\Campus\\Data\\jobs_archive\\T2\\M29\\",
#         bar_positions=[660.26, 1350.84, 1820.30, 2555.64, 3941.0, 4138.5],
#         dimensions=(2160, 60, 60),
#         placement=(55.64, 38.22, 125),
#         custom_variables={"K1": 500},
#     )

#     generator.write_jlx("test_output.jlx")
#     print("✅ Example JLX file generated!")
