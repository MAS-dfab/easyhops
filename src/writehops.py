from compas.geometry import Frame, Transformation, Rotation, Translation, Point, Vector
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

    def generate_hops(self, process):
        # Generate for the start of the part (left)
        self.hop = self.header
        self.hop += self.toolcall
        self.hop += process.params


class FrenchRidgeProcess:

    def __init__(self, hopper, face_front):
        """
        Initialize the FrenchRidgeProcess class with the given parameters
        Args:
            hopper (HOPSWriter): The HOPSWriter object
            face_front (str): 00, 01, 10, 11, 12, 21, 22; 0 - None, 1 - Front, 2 - Back
        """
        self.face_front = face_front
        self.length = hopper.length
        self.width = hopper.width
        self.params = ""
        self.generate_process_params()

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
        beta = beta if face_front else beta + 180

        plane.rotate(math.radians(beta), plane.zaxis, plane.point)
        plane.rotate(math.radians(theta), plane.xaxis, plane.point)

        point1 = Point(self.width, 0, self.width / 3)
        point2 = Point(self.width, self.width, self.width / 2)

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
        beta = beta if face_front else beta + 180

        plane.rotate(math.radians(beta), plane.zaxis, plane.point)
        plane.rotate(math.radians(theta), plane.xaxis, plane.point)

        point1 = Point(self.length - self.width, 0, self.width / 3)
        point2 = Point(self.length - self.width, self.width, self.width / 2)

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
                    "SP({:.3f},{:.3f},{:.3f},{},1,_ANF,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)".format(
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
        face_front_start = True if self.face_front[0] == "1" else False
        if self.face_front[0] != "0":
            self.params += self.format_to_hops(
                *self.generate_params_start(face_front_start),
                is_vert="start",
                orientation=2
            )
            self.params += self.format_to_hops(
                *self.generate_params_start(face_front_start), orientation=1
            )

        face_front_end = True if self.face_front[1] == "1" else False
        if self.face_front[1] != "0":
            self.params += self.format_to_hops(
                *self.generate_params_end(face_front_end), is_vert="end", orientation=1
            )
            self.params += self.format_to_hops(
                *self.generate_params_end(face_front_end), orientation=2
            )
