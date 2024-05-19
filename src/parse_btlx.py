import xml.etree.ElementTree as ET
import os

class BTLXParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.namespaces = {"": "https://www.design2machine.com"}
        self.french_ridge_lap_machinings = {}
        self.double_cut_machinings = {}
        self.remachining_dict = {}
        self._parse_file()

    def _parse_file(self):
        # Load and parse the XML file
        tree = ET.parse(self.file_path)
        root = tree.getroot()

        # Iterate through each part in the XML
        for part in root.findall("Project/Parts/Part", self.namespaces):
            part_id = part.get("OrderNumber")
            frlmachinings = self._parse_machinings(part, "Processings/FrenchRidgeLap", True)
            dcmachinings = self._parse_machinings(part, "Processings/DoubleCut", False)

            if frlmachinings:
                self.french_ridge_lap_machinings[part_id] = frlmachinings
            if dcmachinings:
                self.double_cut_machinings[part_id] = dcmachinings

        self._create_remachining_dict()

    def _parse_machinings(self, part, tag, is_french_ridge_lap):
        machinings = []
        for machining in part.findall(tag, self.namespaces):
            if is_french_ridge_lap:
                machining_data = {
                    "Name": machining.get("Name"),
                    "Priority": machining.get("Priority"),
                    "Process": machining.get("Process"),
                    "ProcessID": machining.get("ProcessID"),
                    "ReferencePlaneID": machining.get("ReferencePlaneID"),
                    "Orientation": machining.find("Orientation", self.namespaces).text,
                    "StartX": machining.find("StartX", self.namespaces).text,
                    "Angle": machining.find("Angle", self.namespaces).text,
                    "RefPosition": machining.find("RefPosition", self.namespaces).text,
                    "Drillhole": machining.find("Drillhole", self.namespaces).text,
                    "DrillholeDiam": machining.find("DrillholeDiam", self.namespaces).text,
                }
            else:
                machining_data = {
                    "Name": machining.get("Name"),
                    "Priority": machining.get("Priority"),
                    "Process": machining.get("Process"),
                    "ProcessID": machining.get("ProcessID"),
                    "ReferencePlaneID": machining.get("ReferencePlaneID"),
                    "Orientation": (
                        machining.find("Orientation", self.namespaces).text
                        if machining.find("Orientation", self.namespaces) is not None
                        else None
                    ),
                    "StartX": (
                        machining.find("StartX", self.namespaces).text
                        if machining.find("StartX", self.namespaces) is not None
                        else None
                    ),
                    "StartY": (
                        machining.find("StartY", self.namespaces).text
                        if machining.find("StartY", self.namespaces) is not None
                        else None
                    ),
                    "Angle1": (
                        machining.find("Angle1", self.namespaces).text
                        if machining.find("Angle1", self.namespaces) is not None
                        else None
                    ),
                    "Inclination1": (
                        machining.find("Inclination1", self.namespaces).text
                        if machining.find("Inclination1", self.namespaces) is not None
                        else None
                    ),
                    "Angle2": (
                        machining.find("Angle2", self.namespaces).text
                        if machining.find("Angle2", self.namespaces) is not None
                        else None
                    ),
                    "Inclination2": (
                        machining.find("Inclination2", self.namespaces).text
                        if machining.find("Inclination2", self.namespaces) is not None
                        else None
                    ),
                }
            machinings.append(machining_data)
        return machinings

    def _create_remachining_dict(self):
        for part_id, machinings in self.french_ridge_lap_machinings.items():
            self.remachining_dict[part_id] = []
            FRL_face_front = {}
            face_front = ""
            for machining in machinings:
                FRL_face_front["Name"] = machining['Name']
                if machining['RefPosition'] == 'oppedge':
                    face_front += str(1)
                elif machining['RefPosition'] == 'refedge':
                    face_front += str(2)
                else:
                    face_front += str(0)
            FRL_face_front["face_front"] = face_front
            self.remachining_dict[part_id].append(FRL_face_front)            
                    
        for part_id, machinings in self.double_cut_machinings.items():
            if part_id not in self.remachining_dict:
                self.remachining_dict[part_id] = []
            for machining in machinings:
                self.remachining_dict[part_id].append(machining)

    def get_remachining_dict(self):
        return self.remachining_dict

# Usage example
file_path = os.path.join(os.path.dirname(__file__), "240519_FRL.btlx")
parser = BTLXParser(file_path)
remachining_dict = parser.get_remachining_dict()
print(remachining_dict)