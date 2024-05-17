from compas.geometry import Frame, Transformation, Rotation, Translation, Point, Vector
from compas.geometry import intersection_plane_plane_plane, Plane
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

    def generate_hops(self, processes):
        # Generate for the start of the part (left)
        self.hop = self.header
        self.hop += self.toolcall
        if isinstance(processes, list):
            for process in processes:
                self.hop += process.params
        else:
            self.hop += processes.params


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


class DoubleCutProcess:

    def __init__(self, hopper, btlx_params):
        self.angle1 = btlx_params["angle1"]
        self.angle2 = btlx_params["angle2"]
        self.inclination1 = btlx_params["inclination1"]
        self.inclination2 = btlx_params["inclination2"]
        self.ref_face = btlx_params["ref_face"]
        self.ref_faces = []
        self.startx = btlx_params["startx"]
        self.starty = btlx_params["starty"]
        self.length = hopper.length
        self.width = hopper.width
        self.frame1, self.frame2 = Frame.worldXY(), Frame.worldXY()
        self.beta1, self.beta2 = 0.0, 0.0
        self.theta1, self.theta2 = 0.0, 0.0
        self.params = ""
        self.ref_plane = None
        self.generate_process_params()

    def generate_planes(self):
        frame = Frame.worldXY()
        ref_angles = [-math.pi / 2, math.pi, math.pi / 2, 0]
        ref_translations = [
            [0, 0, 0],
            [0, self.width,0],
            [0, self.width, self.width],
            [0, 0, self.width],
        ]
        ref_angle = ref_angles[int(self.ref_face) - 1]
        ref_translation = ref_translations[int(self.ref_face) - 1]
        ref_frame = frame.rotated(ref_angle, frame.xaxis, frame.point)
        ref_frame = ref_frame.transformed(
            Translation.from_vector(Vector(*ref_translation))
        )
        T = Transformation.from_change_of_basis(ref_frame, Frame.worldXY())
        ref_frame.point = Point(self.startx, self.starty, 0.0).transformed(T)

        frame1 = deepcopy(ref_frame)
        frame1.rotate(math.radians(self.angle1), frame1.zaxis, frame1.point)
        frame1.rotate(math.radians(self.inclination1), frame1.xaxis, frame1.point)

        frame2 = deepcopy(ref_frame)
        frame2.rotate(math.radians(self.angle2), frame2.zaxis, frame2.point)
        frame2.rotate(math.radians(self.inclination2), frame2.xaxis, frame2.point)

        print(frame1, frame2)
        self.frame1 = frame1
        self.frame2 = frame2

        self.ref_point = ref_frame.point
        self.ref_faces = [frame.rotated(angle, frame.xaxis, frame.point) for angle in ref_angles]
        for T,face in zip(ref_translations, self.ref_faces):
            face.transform(Translation.from_vector(Vector(*T)))
        
        self.beta1 = math.degrees(self.frame1.euler_angles()[2])
        self.theta1 = math.degrees(self.frame1.euler_angles()[0] + ref_angle)

        self.beta2 = math.degrees(self.frame2.euler_angles()[2])
        self.theta2 = math.degrees(self.frame2.euler_angles()[0] + ref_angle)

    
    def format_to_hops(self, points, frame, theta, beta, orientation=0):
        hop = ""
        ref = deepcopy(frame)
        ebenef = "EBENEF({:.4f},{:.4f},{:.4f},{:.4f},{:.4f},0,0)".format(
            ref.point.x, ref.point.y, ref.point.z, theta, beta
        )
        hop += ebenef + "\n"

        Tr = Transformation.from_change_of_basis(Frame([0,0,0], [1,0,0], [0,1,0]), ref)
        pts = [point.transformed(Tr) for point in points]
        for pt in pts:
            # if it is point 0 then it is the start point
            if pts.index(pt) == 0:
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

    def generate_endpoint(self): 
        self.generate_planes()  
        for ref in self.ref_faces:
            point = intersection_plane_plane_plane(Plane.from_frame(self.frame1), Plane.from_frame(self.frame2), Plane.from_frame(ref))
            if point != None and point != self.frame1.point:
                return self.frame1.point, Point(*point)

    def generate_process_params(self):
        pts = self.generate_endpoint()
        if pts == None:
            return
        start_point, end_point = pts
        self.params += self.format_to_hops(
            points=[start_point, end_point],
            frame = self.frame1,
            theta = self.theta1,
            beta = self.beta1,
            orientation=2
        )
        self.params += self.format_to_hops(
            [start_point, end_point],
            self.frame2,
            self.theta2,
            self.beta2,
            orientation=1
        )



if __name__ == "__main__":
    hopper = HOPSWriter(1000)
    processes = [
        # FrenchRidgeProcess(hopper, "11"),  # frontfront
        DoubleCutProcess(
            hopper,
            {
                "angle1": 66.03,
                "angle2": 158.81,
                "inclination1": 78.44,
                "inclination2": 76.67,
                "ref_face": 2,
                "startx": 590.10,
                "starty": 46.53,
            },
        )
    ]
    hopper.generate_hops(processes)
    print(hopper.hop)
