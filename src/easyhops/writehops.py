"""
HOPS Writer and Beam Merger Module

This module provides utilities for generating and manipulating HOPS (Holz-Her CNC)
machining files for timber fabrication.

Classes:
    HOPSWriter: Generates HOPS files with standard headers and tool definitions
    HOPSBeamMerger: Merges multiple variant files of the same beam (e.g., _bis.hop, .hop, _.hop)

For BTLx process conversion, see btlx_processes.py
For merging multiple beams into a stock, see merge_stock_hops.py
"""

import os
import shutil


class HOPSWriter:
    def __init__(self, length, leadout="_ANF", width=60.0):
        """
        Initialize the HOPWriter class with the given parameters
        Args:
            length (float): The length of the path
            leadout (float): The leadout distance
            width (float): The width of the path (Default is 60)
        """
        self.length = length
        self.leadout = leadout
        self.width = width
        self.ref_orientation = None
        self.hop = ""

    @property
    def header(self):
        headerstring = (
            "VARS\n"
            + " DX := {:.3f};*VAR* Piece Length\n".format(self.length)
            + " DY := {:.3f};*VAR* Piece Height\n".format(self.width)
            + " DZ := {:.3f};*VAR* Piece Thickness\n".format(self.width)
            + "START\n"
            + "FERTIGTEIL(DX,DY,DZ,0,0,0,0,0,'',0,0,0)\n"
            + "CALL Park_V7 ( VAL MODE:=11,POSX:=0,POSY:=0)\n"
        )
        return headerstring

    @property
    def toolcall(self):
        toolstring = "WZS(201,10000,7000,20000,_SD,_ANF,'1')\n"
        return toolstring

    def generate_hops(self, processes):
        # Generate for the start of the part (left)
        # self.hop = self.header
        self.hop += self.toolcall
        if isinstance(processes, list):
            for process in processes:
                self.hop += process.params
        else:
            self.hop += processes.params

    def write_to_file(self, file_path):
        with open(file_path, "w") as f:
            f.write(self.hop)


class HOPSBeamMerger:
    """
    Merges multiple variant files of the SAME beam into a single .hop file.

    Handles special suffixes for beam variants:
    - _bis.hop: Operations for flipped/reversed orientation (adds flip instruction)
    - .hop: Standard operations
    - _.hop: Additional operations

    This is NOT for merging multiple beams into a stock - see merge_stock_hops.py for that.
    """

    def __init__(self):
        self.merged_content = ""
        self.types = []
        self.has_bis = None

    def merge_fabrication_files(self, folder_path, index):
        file_paths = self.get_fabrication_file_paths(folder_path, index)
        for i, path in enumerate(file_paths):
            print(self.types[i])
            if self.types[i] == "_bis.hop":
                self.has_bis = True
                with open(path, "r") as file:
                    # find DX in file
                    with open(path, "r") as filecopy:
                        for line in filecopy:
                            # Check if the line contains "DX"
                            if "DX" in line and ":=" in line:
                                # Extract the value after ":=" and before ";"
                                length = float(
                                    line.split(":=")[1].split(";")[0].strip()
                                )
                                # Break the loop after finding the first DX
                                break
                    self.merged_content += file.read() + "\n"
                add_pause = "CALL MachineStop_V7 ( VAL MODE:=0,PARKMODE:=10,PARKPOSX:={:.3f},PARKPOSY:=0,TYP:=0,R6:=0, STR:='flip beam 180deg',R7:=0)".format(
                    length + 1500
                )
                self.merged_content += add_pause + "\n"
            elif self.types[i] == ".hop":
                if self.has_bis:
                    print("removing intro")
                    self.remove_intro(path)
                else:
                    with open(path, "r") as file:
                        self.merged_content += file.read() + "\n"
            elif self.types[i] == "_.hop":
                with open(path, "r") as file:
                    self.merged_content += file.read() + "\n"
        self.save_merged_file(folder_path, index)

    def get_fabrication_file_paths(self, folder_path, index):
        file_paths = []
        file_suffixes = ["_bis.hop", ".hop", "_.hop"]
        for suffix in file_suffixes:
            file_name = "{}{}".format(str(index).zfill(2), suffix)
            file_path = os.path.join(folder_path, file_name)
            print(file_path, suffix)
            if os.path.exists(file_path):
                file_paths.append(file_path)
                self.types.append(suffix)
        return file_paths

    def remove_intro(self, file_path):
        with open(file_path, "r") as file:
            lines = file.readlines()

        end_index = None
        for i, line in enumerate(lines):
            if "CALL Park" in line:
                end_index = i
                break
        if end_index is not None:
            lines = lines[end_index + 1 :]
        self.merged_content += "".join(lines) + "\n"

    def save_merged_file(self, folder_path, index):
        merged_file_path = os.path.join(
            folder_path, "{}.hop".format(str(index).zfill(2))
        )
        with open(merged_file_path, "w") as file:
            file.write(self.merged_content)
        # self.add_centering_holes(merged_file_path)
        # self.delete_merged_files(folder_path, index)
        self.archive_merged_files(folder_path, index)

    def delete_merged_files(self, folder_path, index):
        file_suffixes = ["_bis.hop", "_.hop"]
        for suffix in file_suffixes:
            file_name = "{}{}".format(str(index).zfill(2), suffix)
            file_path = os.path.join(folder_path, file_name)
            if os.path.exists(file_path):
                os.remove(file_path)

    def archive_merged_files(self, folder_path, index):
        archive_folder = os.path.join(folder_path, "_")
        if not os.path.exists(archive_folder):
            os.makedirs(archive_folder)

        file_suffixes = ["_bis.hop", "_.hop"]
        for suffix in file_suffixes:
            file_name = "{}{}".format(str(index).zfill(2), suffix)
            file_path = os.path.join(folder_path, file_name)
            if os.path.exists(file_path):
                archive_path = os.path.join(archive_folder, file_name)
                shutil.move(file_path, archive_path)

    def add_centering_holes(self, merged_file_path):
        def modify_horzb_line(horzb_line):
            # Modify the HORZB values as needed
            # Example: Modify the X coordinate (second value)
            parts = horzb_line.split(",")
            # Parts 0, 1, and 2 are X, Y, and Z coordinates
            # 3 is diameter, 4 is depth, 5 is flag, 6 is tilt angle, 7 is rotation angle
            if len(parts) > 1:
                parts[3] = "1"  # change diameter to 1mm
                parts[4] = "-5"  # change depth to 5mm
            return ",".join(parts)

        with open(merged_file_path, "r") as file:
            lines = file.readlines()

        # List to store EBENE and HORZB lines
        ebene_horzb_pairs = []

        for i, line in enumerate(lines):
            if "HORZB" in line:
                # Store the EBENE line before HORZB line
                print("Found drilling, line: ", line)
                if i > 0 and "EBENE" in lines[i - 2]:
                    print("Found EBENE, line: ", lines[i - 2])
                    ebene_line = lines[i - 2]
                    horzb_line = modify_horzb_line(line)
                    ebene_horzb_pairs.append((ebene_line, horzb_line))

        # Find the position of the first WZB line
        insert_position = next(
            (i for i, line in enumerate(lines) if "WZB" in line), len(lines)
        )

        if len(ebene_horzb_pairs) > 0:
            with open(merged_file_path, "w") as file:
                # Write the lines up to the first WZB line to the output file
                file.writelines(lines[:insert_position])

                # Insert the new EBENE, WZB, and modified HORZB lines
                for ebene_line, horzb_line in ebene_horzb_pairs:
                    file.write("\n; Added EBENE and HORZB parts\n")
                    file.write(ebene_line)
                    file.write("WZB(301,_VE,_V,_VA,_SD,_ANF,'1')\n")
                    file.write(horzb_line)

                # Write the rest of the original lines to the output file
                file.writelines(lines[insert_position:])
            return True
        return False

    def get_hop_files_count(self, folder_path):
        hop_files = [file for file in os.listdir(folder_path) if file.endswith(".hop")]
        if len(hop_files) == 0:
            pass
        return len(hop_files)


# if __name__ == "__main__":
#     hops = HOPSBeamMerger()
#     folder_path = "..\mas-t2-2324\\production\\fabrication\\Module_67\\btlx\\Module_67"
#     # lissst = [28]
#     for i in range(0,29):
#     # for i in lissst:
#         file_str = str(i).zfill(2) + ".hop"
#         file_path = os.path.join(folder_path, file_str)
#         if hops.add_centering_holes(file_path):
#             print("Added centering holes to ", file_str)
#         else:
#             print("No centering holes added to ", file_str)
