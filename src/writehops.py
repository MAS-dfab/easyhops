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
        self.hop = self.header
        self.hop += self.toolcall
        if isinstance(processes, list):
            for process in processes:
                self.hop += process.params
        else:
            self.hop += processes.params

    def write_to_file(self, file_path):
        with open(file_path, "w") as f:
            f.write(self.hop)


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
        self.ref_face = ref_face
        self.params = ""
        self.frame1, self.frame2 = [], []
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
            plane_pt = Point(0, 0, self.width / 2)
        else:
            plane_pt = Point(0, self.width, self.width / 2)

        plane = Frame(plane_pt, [1, 0, 0], [0, 1, 0])
        beta, theta = 45.0, 13.263
        beta = beta if face_front else 180 - beta

        plane.rotate(math.radians(beta), plane.zaxis, plane.point)
        plane.rotate(math.radians(theta), plane.xaxis, plane.point)

        point1 = (
            Point(self.width, 0, self.width / 3)
            if face_front
            else Point(self.width, 0, self.width / 2)
        )
        point2 = (
            Point(self.width, self.width, self.width / 2)
            if face_front
            else Point(self.width, self.width, self.width / 3)
        )
        self.pts.append([point1.copy(), point2.copy()])

        return [point1, point2], plane, theta, beta

    def generate_params_end(self, face_front=True):
        """
        Generate the parameters for the end of the part
        """
        if face_front == True:
            plane_pt = Point(self.length, 0, self.width / 2)
        else:
            plane_pt = Point(self.length, self.width, self.width / 2)

        plane = Frame(plane_pt, [1, 0, 0], [0, 1, 0])
        beta, theta = -45.0, 13.263
        beta = beta if face_front else 180 - beta

        plane.rotate(math.radians(beta), plane.zaxis, plane.point)
        plane.rotate(math.radians(theta), plane.xaxis, plane.point)

        point1 = (
            Point(self.length - self.width, 0, self.width / 3)
            if face_front
            else Point(self.length - self.width, 0, self.width / 2)
        )
        point2 = (
            Point(self.length - self.width, self.width, self.width / 2)
            if face_front
            else Point(self.length - self.width, self.width, self.width / 3)
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
                        pt.x, pt.y, pt.z, orientation
                    )
                    + "\n"
                )
            else:
                reference = 0  # Z Reference : 0 for top, 1 for bottom, 2 for relative
                hop += (
                    "G01({:.3f},{:.3f},{:.3f},0,0,{})".format(
                        pt.x, pt.y, pt.z, reference
                    )
                    + "\n"
                )
        hop += "EP(1,_ANF,0)\n"

        return hop

    def generate_process_params(self):
        # self.face_front = "11"
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

    @staticmethod
    def frame_to_yaw_pitch(frame_to, frame_from):
        frame = Frame(frame_to.point, [1, 0, 0], [0, 1, 0])

        target_normal = frame_from.zaxis
        factor = 1
        flipped = False

        # Angle to rotate around the z-axis to align the normal vector with the x-y plane
        beta = math.atan2(target_normal.y, target_normal.x) + math.pi / 2
        frame.rotate(beta, frame.zaxis, frame.point)
        # Angle to rotate around the x-axis to align the normal vector with the z-axis
        theta = angle_vectors_signed([0, 0, 1], target_normal, frame.xaxis)
        theta = wrap_to_pi(theta) if factor == 1 else wrap_to_pi(-theta)
        frame.rotate(theta, frame.xaxis, frame.point)
        return frame, theta, beta

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
        # Opp face is basically 1 for 3, 3 for 1, 2 for 4, 4 for 2
        opp_face_index = (
            int(self.ref_face) + 2 if int(self.ref_face) < 3 else int(self.ref_face) - 2
        )
        ref = self.ref_faces[opp_face_index - 1]
        point = Point(
            *intersection_plane_plane_plane(
                Plane.from_frame(self.frame1),
                Plane.from_frame(self.frame2),
                Plane.from_frame(ref),
            )
        )
        return self.frame1.point, Point(point.x, point.y, point.z)

    def rotate_things(self, start_point, end_point, frame1, frame2, ref_plane):
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
            start_point.transformed(T),
            end_point.transformed(T),
            frame1.transformed(T),
            frame2.transformed(T),
            ref_plane.transformed(T),
        )

    def generate_process_params(self):
        pts = self.generate_endpoint()
        if pts == None:
            return
        start_point, end_point = pts
        orientation1 = 2 if self.orientation == "start" else 1
        orientation2 = 1 if self.orientation == "start" else 2
        start_point, end_point, self.frame1, self.frame2, self.ref_plane = (
            self.rotate_things(
                start_point, end_point, self.frame1, self.frame2, self.ref_plane
            )
          )
        self.cf1, theta, beta = self.frame_to_yaw_pitch(
            deepcopy(self.ref_plane), self.frame1
        )

        if start_point.z < end_point.z:
            print("flipped, ref face was at bottom")
            start_point, end_point = end_point, start_point
            orientation1 = 1
            orientation2 = 2

        self.params += self.format_to_hops(
            points=[start_point, end_point],
            frame=deepcopy(self.cf1),
            theta=math.degrees(theta),
            beta=math.degrees(beta),
            orientation=orientation1,
        )
        self.cf2, theta, beta = self.frame_to_yaw_pitch(
            deepcopy(self.ref_plane), self.frame2
        )
        self.params += self.format_to_hops(
            points=[start_point, end_point],
            frame=deepcopy(self.cf2),
            theta=math.degrees(theta),
            beta=math.degrees(beta),
            orientation=orientation2,
        )
        return [start_point, end_point]


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
            and dot_vectors(-f2.zaxis, Vector.Zaxis()) < 0
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


if __name__ == "__main__":
    import os
    from parse_btlx import BTLXParser

    file_path = os.path.join(os.path.dirname(__file__), "240514_Module81.btlx")
    parser = BTLXParser(file_path)
    remachining_dict = parser.get_remachining_dict()
    index = 27
    print(remachining_dict)
    for index, value in remachining_dict.items():
        hopper = HOPSWriter(remachining_dict[str(index)]["length"])
        processes = []
        for machining in remachining_dict[str(index)]["machinings"]:
            if machining["Name"] == "French ridge lap":
                process = FrenchRidgeProcess(
                    hopper, machining["facefront"], machining["ReferencePlaneID"]
                )
            elif machining["Name"] == "T-Butt Joint":
                process = DoubleCutProcess(hopper, machining)
                processes.append(process)
        hopper.generate_hops(processes)
        # create folder with btlx name
        filename = os.path.join(
            os.path.dirname(__file__), "hops", "%s_.hop" % str(index)
        )
        hopper.write_to_file(file_path=filename)
