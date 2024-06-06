from compas.geometry import Frame, Transformation, Rotation, Translation, Point, Vector
from compas.geometry import (
    intersection_plane_plane_plane,
    Plane,
    angle_vectors_signed,
    dot_vectors,
    angle_vectors,
)
from copy import deepcopy
import math
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


class HOPSMerger:
    def __init__(self):
        self.merged_content = ""
        self.types = []

    def merge_fabrication_files(self, folder_path, index):
        file_paths = self.get_fabrication_file_paths(folder_path, index)
        print(file_paths)
        for i, path in enumerate(file_paths):
            if self.types[i] == "_bis.hop":
                print("_bis.hop")
                with open(path, "r") as file:
                    # find DX in file
                    with open(path, "r") as filecopy:
                        for line in filecopy:
                            # Check if the line contains "DX"
                            if "DX" in line and ":=" in line:
                                # Extract the value after ":=" and before ";"
                                length = float(line.split(":=")[1].split(";")[0].strip())
                                # Break the loop after finding the first DX
                                break
                    self.merged_content += file.read() + "\n"
                add_pause = "CALL MachineStop_V7 ( VAL MODE:=0,PARKMODE:=10,PARKPOSX:={:.3f},PARKPOSY:=0,TYP:=0,R6:=0, STR:='flip beam 180deg',R7:=0)".format(
                    length + 750
                )
                self.merged_content += add_pause + "\n"
            elif self.types[i] == ".hop":
                print(".hop")
                with open(path, "r") as file:
                    self.merged_content += file.read() + "\n"
            elif self.types[i] == "_.hop":
                print("_.hop")
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

        with open(merged_file_path, 'r') as file:
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


class FrenchRidgeProcess:

    def __init__(self, hopper, face_front, ref_face=1):
        """
        Initialize the FrenchRidgeProcess class with the given parameters
        Args:
            hopper (HOPSWriter): The HOPSWriter object
            face_front (str): 00, 01, 10, 11, 12, 21, 22; 0 - None, 1 - Front, 2 - Back
        """
        self.face_front = face_front
        self.length = hopper.length
        self.width = hopper.width
        self.hopper = hopper
        self.ref_face = int(ref_face)
        self.params = ""
        self.frame1, self.frame2 = [], []
        self.frames = []
        self.pts = []
        self.ref_orientation = self.calculate_rotation()
        self.generate_process_params()

    def calculate_rotation(self):
        alpha = 0
        if self.ref_face == 1:
            alpha = -math.pi / 2
        if self.ref_face == 3:
            alpha = math.pi / 2
        if self.ref_face == 2:
            alpha = -math.pi
        if self.ref_face == 4:
            alpha = 0

        return alpha

    def generate_params_start(self, face_front=True):
        """
        Generate the parameters for the start of the part
        """
        if face_front == True:
            plane_pt = Point(0+self.width, 0, self.width / 2)
        else:
            plane_pt = Point(0+self.width, self.width, self.width / 2)

        plane = Frame(plane_pt, [1, 0, 0], [0, 1, 0])
        beta, theta = 45.0, 13.263
        beta = beta if face_front else 180 - beta

        plane.rotate(math.radians(beta), plane.zaxis, plane.point)
        plane.rotate(math.radians(theta), plane.xaxis, plane.point)

        point1 = (
            Point(self.width*2, 0, self.width / 3)
            if face_front
            else Point(self.width*2, 0, self.width / 2)
        )
        point2 = (
            Point(self.width*2, self.width, self.width / 2)
            if face_front
            else Point(self.width*2, self.width, self.width / 3)
        )
        self.pts.append([point1.copy(), point2.copy()])

        return [point1, point2], plane, theta, beta

    def generate_params_end(self, face_front=True):
        """
        Generate the parameters for the end of the part
        """
        if face_front == True:
            plane_pt = Point(self.length - self.width, 0, self.width / 2)
        else:
            plane_pt = Point(self.length - self.width, self.width, self.width / 2)

        plane = Frame(plane_pt, [1, 0, 0], [0, 1, 0])
        beta, theta = -45.0, 13.263
        beta = beta if face_front else 180 - beta

        plane.rotate(math.radians(beta), plane.zaxis, plane.point)
        plane.rotate(math.radians(theta), plane.xaxis, plane.point)

        point1 = (
            Point(self.length - self.width*2, 0, self.width / 3)
            if face_front
            else Point(self.length - self.width*2, 0, self.width / 2)
        )
        point2 = (
            Point(self.length - self.width*2, self.width, self.width / 2)
            if face_front
            else Point(self.length - self.width*2, self.width, self.width / 3)
        )
        self.pts.append([point1.copy(), point2.copy()])
        return [point1, point2], plane, theta, beta

    def format_to_hops(self, points, plane, theta, beta, is_vert=None, orientation=0):
        hop = ""
        if is_vert == "start":
            ref_plane = Frame(Point(0, 0, 0), [0, -1, 0], [0, 0, 1])
            ebenef = "EBENE2()"
        elif is_vert == "end":
            ref_plane = Frame(Point(self.length, 0, 0), [0, 1, 0], [0, 0, 1])
            ebenef = "EBENE4()"
        else:
            ref_plane = plane
            ebenef = "EBENEF({:.3f},{:.3f},{:.3f},{},{},0,0)".format(
                plane.point.x, plane.point.y, plane.point.z, theta, beta
            )
        hop += ebenef + "\n"

        T = Transformation.from_change_of_basis(Frame.worldXY(), ref_plane)
        [point.transform(T) for point in points]

        for pt in points:
            # if it is point 0 then it is the start point
            if points.index(pt) == 0:
                hop += (
                    "SP({:.3f},{:.3f},{:.3f},{},3,_ANF,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)".format(
                        pt.x, pt.y, pt.z + 1.6, orientation
                    )
                    + "\n"
                )
            else:
                reference = 0  # Z Reference : 0 for top, 1 for bottom, 2 for relative
                hop += (
                    "G01({:.3f},{:.3f},{:.3f},0,0,{})".format(
                        pt.x, pt.y, pt.z + 1.6, reference
                    )
                    + "\n"
                )
        hop += "EP(1,_ANF,0)\n"

        return hop

    def generate_process_params(self):
        # self.face_front = "11"
        self.params += "WZS(201,10000,7000,20000,_SD,_ANF,'1')\n"
        self.params += "EBENE0()\n"
        self.params += "SAEGEN({:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},1,0,0,1,0,-2,1,1,0,0,0)\n".format(
            self.width, 0.0, 0.0, self.width, self.width, 0.0
        )
        cf0 = Frame.worldYZ()
        cf0.point = Point(self.width, 0, 0)
        cf1 = Frame.worldYZ()
        cf1.point = Point(self.length - self.width, 0, 0)
        self.frames.append(cf1)
        self.frames.append(cf0)

        face_front_start = True if self.face_front[0] == "1" else False
        if self.face_front[0] != "0":
            [point1, point2], plane, theta, beta = self.generate_params_start(
                face_front_start
            )
            self.params += self.format_to_hops(
                [point1, point2], plane, theta, beta, is_vert="start", orientation=2
            )
            self.frame1.append(plane)
            [point1, point2], plane, theta, beta = self.generate_params_start(
                face_front_start
            )
            self.params += self.format_to_hops(
                [point1, point2], plane, theta, beta, orientation=1
            )
            self.frame1.append(plane)

        self.params += "EBENE0()\n"
        self.params += "SAEGEN({:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},2,0,0,1,0,-2,1,1,0,0,0)\n".format(
            self.length - self.width, 0.0, 0.0, self.length - self.width, self.width, 0.0
        )

        face_front_end = True if self.face_front[1] == "1" else False
        if self.face_front[1] != "0":
            [point1, point2], plane, theta, beta = self.generate_params_end(
                face_front_end
            )
            self.params += self.format_to_hops(
                [point1, point2], plane, theta, beta, is_vert="end", orientation=1
            )
            self.frame2.append(plane)
            [point1, point2], plane, theta, beta = self.generate_params_end(
                face_front_end
            )
            self.params += self.format_to_hops(
                [point1, point2], plane, theta, beta, orientation=2
            )
            self.frame2.append(plane)


class DoubleCutStepJointProcess:
    def __init__(self, hopper, btlx_params):
        self.orientation = str(btlx_params["Orientation"])
        self.angle1 = float(btlx_params["Angle1"])
        self.angle2 = float(btlx_params["Angle2"])
        self.inclination1 = float(btlx_params["Inclination1"])
        self.inclination2 = float(btlx_params["Inclination2"])
        self.ref_face = int(btlx_params["ReferencePlaneID"])
        self.ref_faces = []
        self.startx = float(btlx_params["StartX"])
        self.starty = float(btlx_params["StartY"])
        self.length = hopper.length
        self.width = hopper.width
        self.hopper = hopper
        self.frame1, self.frame2 = Frame.worldXY(), Frame.worldXY()
        self.params = ""
        self.cf1, self.cf2 = None, None
        self.ref_plane = None
        self.ref_orientation = None
        self.pts = self.generate_process_params()

    def generate_planes(self):
        frame = Frame.worldXY()
        ref_angles = [math.pi / 2, math.pi, -math.pi / 2, 0]
        ref_translations = [
            [0, 0, 0],
            [0, self.width, 0],
            [0, self.width, self.width],
            [0, 0, self.width],
        ]
        ref_angle = ref_angles[int(self.ref_face) - 1]
        ref_translation = ref_translations[int(self.ref_face) - 1]
        ref_frame = frame.rotated(ref_angle, frame.xaxis, frame.point)
        ref_frame.transform(Translation.from_vector(Vector(*ref_translation)))
        self.ref_plane = ref_frame
        T = Transformation.from_change_of_basis(ref_frame, Frame.worldXY())
        ref_frame.point = Point(self.startx, self.starty, 0.0).transformed(T)

        if self.orientation == "start":
            print ("okay")
            angle1, angle2 = -self.angle1, -self.angle2
        else:
            angle1, angle2 = self.angle1, self.angle2
        frame1 = deepcopy(ref_frame)
        frame1.point = ref_frame.point
        print (self.angle1, self.inclination1)
        frame1.rotate(math.radians(-angle1), frame1.zaxis, frame1.point)
        frame1.rotate(math.radians(self.inclination1), frame1.xaxis, frame1.point)

        frame2 = deepcopy(ref_frame)
        frame2.point = ref_frame.point
        print (self.angle2, self.inclination2)
        frame2.rotate(math.radians(-angle2), frame2.zaxis, frame2.point)
        frame2.rotate(math.radians(self.inclination2), frame2.xaxis, frame2.point)

        if (
            dot_vectors(frame1.zaxis, Vector.Xaxis()) > 0
            and self.orientation == "start"
        ):
            frame1.rotate(math.pi, frame1.yaxis, frame1.point)
            frame2.rotate(math.pi, frame2.yaxis, frame2.point)
        elif (
            dot_vectors(frame1.zaxis, Vector.Xaxis()) < 0 and self.orientation == "end"
        ):
            frame1.rotate(math.pi, frame1.yaxis, frame1.point)
            frame2.rotate(math.pi, frame2.yaxis, frame2.point)
        self.frame1 = frame1
        self.frame2 = frame2

        self.ref_point = ref_frame.point
        self.ref_faces = [
            frame.rotated(angle, frame.xaxis, frame.point) for angle in ref_angles
        ]
        for i in range(len(self.ref_faces)):
            self.ref_faces[i].transform(
                Translation.from_vector(Vector(*ref_translations[i]))
            )

    def format_to_hops(self, points, orientation=0):
        hop = ""
        start_point, end_point = points 
        hop += "SAEGEN({:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{},0,0,1,0,-2,1,1,0,0,0)\n".format(
            start_point.x, start_point.y, 0.0, end_point.x, end_point.y, 0.0, orientation
        )

        return hop

    def generate_endpoint(self):
        self.generate_planes()
        # Opp face is basically 1 for 3, 3 for 1, 2 for 4, 4 for 2
        opp_face_index = (
            int(self.ref_face) + 2 if int(self.ref_face) < 3 else int(self.ref_face) - 2
        )
        other_faces = [
            i-1 for i in range(1, 5) if i not in [self.ref_face, opp_face_index]
        ]

        print(self.ref_face)
        sp_0 = Point(
            *intersection_plane_plane_plane(
                Plane.from_frame(self.frame1),
                Plane.from_frame(self.ref_plane),
                Plane.from_frame(self.ref_faces[other_faces[0]]),
            )
        )

        ep_0 = Point(
            *intersection_plane_plane_plane(
                Plane.from_frame(self.frame1),
                Plane.from_frame(self.ref_plane),
                Plane.from_frame(self.ref_faces[other_faces[1]]),
            )
        )

        sp_1 = Point(
            *intersection_plane_plane_plane(
                Plane.from_frame(self.frame2),
                Plane.from_frame(self.ref_plane),
                Plane.from_frame(self.ref_faces[other_faces[0]]),
            )
        )

        ep_1 = Point(
            *intersection_plane_plane_plane(
                Plane.from_frame(self.frame2),
                Plane.from_frame(self.ref_plane),
                Plane.from_frame(self.ref_faces[other_faces[1]]),
            )
        )    
        
        return sp_0, ep_0, sp_1, ep_1

    def rotate_things(self, sp0, ep0, sp1, ep1):
        if self.ref_face == 1:
            alpha = -math.pi / 2
            self.ref_orientation = alpha
        elif self.ref_face == 3:
            alpha = -math.pi / 2
            self.ref_orientation = alpha
        elif self.ref_face == 2:
            alpha = 0
            self.ref_orientation = 0
        else:
            alpha = 0
            self.ref_orientation = 0
        T = Rotation.from_axis_and_angle([1, 0, 0], alpha, point=[0, 30, 30])
        return (
            sp0.transformed(T),
            ep0.transformed(T),
            sp1.transformed(T),
            ep1.transformed(T),
        )

    def generate_process_params(self):
        pts = self.generate_endpoint()
        if pts == None:
            return
        sp0, ep0, sp1, ep1 = self.rotate_things(*pts)

        if sp0.y > ep0.y:
            print("end point flipped")
            sp0, ep0 = ep0, sp0
        if sp1.y > ep1.y:
            print("end point flipped")
            sp1, ep1 = ep1, sp1
            
        self.params += "WZS(201,10000,7000,20000,_SD,_ANF,'1')\n"
        self.params += "EBENE0()\n"
        self.params += self.format_to_hops(
            points=[sp0, ep0],
            orientation = 1 if self.orientation == "start" else 2 
        )
        self.params += self.format_to_hops(
            points=[sp1, ep1],
            orientation = 1 if self.orientation == "start" else 2
        )
        return [sp0, ep0, sp1, ep1]


class DoubleCutProcess:
    def __init__(self, hopper, btlx_params):
        self.orientation = str(btlx_params["Orientation"])
        self.angle1 = float(btlx_params["Angle1"])
        self.angle2 = float(btlx_params["Angle2"])
        self.inclination1 = float(btlx_params["Inclination1"])
        self.inclination2 = float(btlx_params["Inclination2"])
        self.ref_face = int(btlx_params["ReferencePlaneID"])
        self.ref_faces = []
        self.startx = float(btlx_params["StartX"])
        self.starty = float(btlx_params["StartY"])
        self.length = hopper.length
        self.width = hopper.width
        self.hopper = hopper
        self.frame1, self.frame2 = Frame.worldXY(), Frame.worldXY()
        self.params = ""
        self.cf1, self.cf2 = None, None
        self.ref_plane = None
        self.ref_orientation = None
        self.pts = self.generate_process_params()

    @staticmethod
    def frame_to_yaw_pitch(frame_to, frame_from):
        frame = Frame(frame_to.point, [1, 0, 0], [0, 1, 0])
        condition = angle_vectors(-frame_from.zaxis, Vector.Zaxis(), deg=True) > 99.0
        print(angle_vectors(-frame_from.zaxis, Vector.Zaxis(), deg=True))
        if not condition:
            target_normal = -frame_from.zaxis
            factor = 1
            flipped = False
        else:
            target_normal = frame_from.zaxis
            factor = -1
            flipped = True

        # Angle to rotate around the z-axis to align the normal vector with the x-y plane
        beta = math.atan2(target_normal.y, target_normal.x) + math.pi / 2
        frame.rotate(beta, frame.zaxis, frame.point)
        # Angle to rotate around the x-axis to align the normal vector with the z-axis
        theta = angle_vectors_signed([0, 0, 1], target_normal, frame.xaxis)
        theta = wrap_to_pi(theta) if factor == 1 else wrap_to_pi(-theta)
        frame.rotate(theta, frame.xaxis, frame.point)
        return frame, theta, beta, flipped

    def generate_planes(self):
        frame = Frame.worldXY()
        ref_angles = [math.pi / 2, math.pi, -math.pi / 2, 0]
        ref_translations = [
            [0, 0, 0],
            [0, self.width, 0],
            [0, self.width, self.width],
            [0, 0, self.width],
        ]
        ref_angle = ref_angles[int(self.ref_face) - 1]
        ref_translation = ref_translations[int(self.ref_face) - 1]
        ref_frame = frame.rotated(ref_angle, frame.xaxis, frame.point)
        ref_frame.transform(Translation.from_vector(Vector(*ref_translation)))
        self.ref_plane = ref_frame
        T = Transformation.from_change_of_basis(ref_frame, Frame.worldXY())
        ref_frame.point = Point(self.startx, self.starty, 0.0).transformed(T)

        frame1 = deepcopy(ref_frame)
        frame1.point = ref_frame.point
        frame1.rotate(math.radians(-self.angle1), frame1.zaxis, frame1.point)
        frame1.rotate(math.radians(self.inclination1), frame1.xaxis, frame1.point)

        frame2 = deepcopy(ref_frame)
        frame2.point = ref_frame.point
        frame2.rotate(math.radians(-self.angle2), frame2.zaxis, frame2.point)
        frame2.rotate(math.radians(self.inclination2), frame2.xaxis, frame2.point)

        self.frame1 = frame1
        self.frame2 = frame2

        self.ref_point = ref_frame.point
        self.ref_faces = [
            frame.rotated(angle, frame.xaxis, frame.point) for angle in ref_angles
        ]
        for i in range(len(self.ref_faces)):
            self.ref_faces[i].transform(
                Translation.from_vector(Vector(*ref_translations[i]))
            )

    def format_to_hops(self, points, frame, theta, beta, orientation=0, ref_height=0.0):
        hop = ""
        ref = deepcopy(frame)
        ebenef = "EBENEF({:.4f},{:.4f},{:.4f},{:.4f},{:.4f},0,0)".format(
            ref.point.x, ref.point.y, ref.point.z, theta, beta
        )
        hop += ebenef + "\n"

        Tr = Transformation.from_change_of_basis(
            Frame([0, 0, 0], [1, 0, 0], [0, 1, 0]), ref
        )
        pts = [point.transformed(Tr) for point in points]
        for pt in pts:
            # if it is point 0 then it is the start point
            if pts.index(pt) == 0:
                hop += (
                    "SP({:.3f},{:.3f},{:.3f},{},1,_ANF,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)".format(
                        pt.x, pt.y, pt.z + ref_height, orientation
                    )
                    + "\n"
                )
            else:
                reference = 0  # Z Reference : 0 for top, 1 for bottom, 2 for relative
                hop += (
                    "G01({:.3f},{:.3f},{:.3f},0,0,{})".format(
                        pt.x, pt.y, pt.z + ref_height, reference
                    )
                    + "\n"
                )
        hop += "EP(3,2.0,0)\n"

        return hop

    def generate_endpoint(self):
        self.generate_planes()
        for ref in self.ref_faces:
            point = Point(
                *intersection_plane_plane_plane(
                    Plane.from_frame(self.frame1),
                    Plane.from_frame(self.frame2),
                    Plane.from_frame(ref),
                )
            )
            if point is not None:
                if Vector.from_start_end(point, self.frame1.point).length > 0.01:
                    if -0.1 <= point.y <= 60.1 and -0.1 <= point.z <= 60.1:
                        return self.frame1.point, Point(point.x, point.y, point.z)

    def rotate_things(self, start_point, end_point, frame1, frame2, ref_plane):
        if self.ref_face == 1:
            alpha = -math.pi / 2
            self.ref_orientation = alpha
        elif self.ref_face == 3:
            alpha = math.pi / 2
            self.ref_orientation = alpha
        elif self.ref_face == 2:
            alpha = 0
            self.ref_orientation = 0
        else:
            alpha = 0
            self.ref_orientation = 0
        T = Rotation.from_axis_and_angle([1, 0, 0], alpha, point=[0, 30, 30])
        sp1, ep1, f1, f2, rp = (
            start_point.transformed(T),
            end_point.transformed(T),
            frame1.transformed(T),
            frame2.transformed(T),
            ref_plane.transformed(T),
        )
        if (
            dot_vectors(-f1.zaxis, Vector.Zaxis()) < 0
            or dot_vectors(-f2.zaxis, Vector.Zaxis()) < 0
        ):
            secondary_rotation = Rotation.from_axis_and_angle(
                [1, 0, 0], math.pi, point=[0, 30, 30]
            )
            sp1.transform(secondary_rotation)
            ep1.transform(secondary_rotation)
            f1.transform(secondary_rotation)
            f2.transform(secondary_rotation)
            rp.transform(secondary_rotation)
            self.ref_orientation += math.pi

        return sp1, ep1, f1, f2, rp

    def generate_safe_points (self, start_point, end_point, plane, is_front):
        for ref in self.ref_faces:
            point = intersection_plane_plane_plane(
                    Plane.from_frame(self.ref_plane),
                    Plane.from_frame(plane),
                    Plane.from_frame(ref),
                )

            if point is not None:
                print("point is ", point)
                if is_front:
                    if 60.1 > point[1] > 59.9:
                        point = Point(*point)
                        if 0.1 < point[2] < 0.1:
                            ref = start_point
                        else:
                            ref = end_point
                        vec = Vector.from_start_end(ref, point)
                        vec.unitize()
                        vec *= 200.0
                        point = ref + vec
                        return point
                else:
                    if -0.1 < point[1] < 0.1:
                        point = Point(*point)
                        if 0.1 < point[2] < 0.1:
                            ref = start_point
                        else:
                            ref = end_point
                        vec = Vector.from_start_end(ref, point)
                        vec.unitize()
                        vec *= 200.0
                        point = ref + vec
                        return point
                
                    
    def generate_process_params(self):
        pts = self.generate_endpoint()
        if pts == None:
            return
        start_point, end_point = pts
        orientation1 = 1 if self.orientation == "start" else 2
        orientation2 = 2 if self.orientation == "start" else 1
        start_point, end_point, self.frame1, self.frame2, self.ref_plane = (
            self.rotate_things(
                start_point, end_point, self.frame1, self.frame2, self.ref_plane
            )
        )
        self.cf1, theta, beta, flipped1 = self.frame_to_yaw_pitch(
            deepcopy(self.ref_plane), self.frame1
        )
        ref_height = 0.0
        if start_point.z < end_point.z:
            print("point order flipped")
            start_point, end_point = end_point, start_point
            orientation1 = 1
            orientation2 = 2
        
        # Frame 1 points
        if flipped1:
            print("frame1 flipped")
            ref_height = -3.2
            orientation1 = 2 if orientation1 == 1 else 1

        self.params += self.format_to_hops(
            points=[start_point, end_point],
            frame=deepcopy(self.cf1),
            theta=math.degrees(theta),
            beta=math.degrees(beta),
            orientation=orientation1,
        )




        self.cf2, theta, beta, flipped2 = self.frame_to_yaw_pitch(
            deepcopy(self.ref_plane), self.frame2
        )
            
                # Frame 2 points
        if flipped2:
            print("frame2 flipped")
            ref_height = -3.2
            orientation2 = 1 if orientation2 == 2 else 2

        self.params += self.format_to_hops(
            points=[start_point, end_point],
            frame=deepcopy(self.cf2),
            theta=math.degrees(theta),
            beta=math.degrees(beta),
            orientation=orientation2,
            ref_height=ref_height,
        )
        return [start_point, end_point]


class TextProcess:
    def __init__(self, hopper, btlx_params, ref_orientation=0.0):
        self.hopper = hopper
        self.ref_face = int(btlx_params["ReferencePlaneID"])
        self.text = btlx_params["Text"]
        self.startx = float(btlx_params["StartX"])
        self.starty = float(btlx_params["StartY"])
        self.ref_frame = None
        self.frame = self.create_text_frame()
        self.rotate_stuff(ref_orientation)

    def create_text_frame(self):
        frame = Frame.worldXY()
        ref_angles = [math.pi / 2, math.pi, -math.pi / 2, 0]
        ref_translations = [
            [0, 0, 0],
            [0, 60, 0],
            [0, 60, 60],
            [0, 0, 60],
        ]
        ref_angle = ref_angles[int(self.ref_face) - 1]
        ref_translation = ref_translations[int(self.ref_face) - 1]
        ref_frame = frame.rotated(ref_angle, frame.xaxis, frame.point)
        ref_frame.transform(Translation.from_vector(Vector(*ref_translation)))
        T = Transformation.from_change_of_basis(ref_frame, Frame.worldXY())
        ref_frame.point = Point(self.startx, self.starty, 0.0).transformed(T)
        self.ref_frame = ref_frame.copy()
        return ref_frame

    def rotate_stuff(self, ref_orientation=0.0):
        angle = ref_orientation
        rotation_axis = [1, 0, 0]
        rotation_pt = [0, 30, 30]
        self.frame.rotate(angle, rotation_axis, rotation_pt)


def wrap_to_pi(angle):
    # Normalize the angle to be within [-pi, pi]
    angle = (angle + math.pi) % (2 * math.pi) - math.pi
    # If the angle is negative, convert it to the positive equivalent
    if angle < 0:
        angle += 2 * math.pi

    # If the angle is greater than pi, wrap it to the range [0, pi]
    if angle > math.pi:
        angle = 2 * math.pi - angle

    return angle

def get_hop_files_count(folder_path):
    hop_files = [file for file in os.listdir(folder_path) if file.endswith(".hop")]
    return len(hop_files)

if __name__ == "__main__":
    hops = HOPSMerger()
    folder_path = "..\mas-t2-2324\\production\\fabrication\\Module_67\\btlx\\Module_67"
    # lissst = [28]
    for i in range(0,29):
    # for i in lissst:
        file_str = str(i).zfill(2) + ".hop"
        file_path = os.path.join(folder_path, file_str)
        if hops.add_centering_holes(file_path):
            print("Added centering holes to ", file_str)
        else:
            print("No centering holes added to ", file_str)