import xml.etree.ElementTree as ET
import os

class BTLXParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.namespaces = {"d2m": "https://www.design2machine.com"}
        self.french_ridge_lap_machinings = {}
        self.double_cut_machinings = {}
        self.remachining_dict = {}
        self.part_lengths = {}
        self._parse_file()
    
    @property
    def __data__(self):
        data_dict = {
            "file_path": str(self.file_path),
            "namespaces": self.namespaces,
            "french_ridge_lap_machinings": self.french_ridge_lap_machinings,
            "double_cut_machinings": self.double_cut_machinings,
            "remachining_dict": self.remachining_dict,
            "part_lengths": self.part_lengths
        }
        return data_dict
    
    @classmethod
    def __from_data__(cls, data):
        instance = cls(data["file_path"])
        instance.namespaces = data["namespaces"]
        instance.french_ridge_lap_machinings = data["french_ridge_lap_machinings"]
        instance.double_cut_machinings = data["double_cut_machinings"]
        instance.remachining_dict = data["remachining_dict"]
        instance.part_lengths = data["part_lengths"]
        return instance

    def _parse_file(self):
        try:
            # Load and parse the XML file
            tree = ET.parse(self.file_path)
            root = tree.getroot()
            # Iterate through each part in the XML
            for part in root.findall("d2m:Project/d2m:Parts/d2m:Part", self.namespaces):
                part_id = part.get("OrderNumber")
                self.part_lengths[part_id] = float(part.get("Length"))
                frlmachinings = self._parse_machinings(part, "d2m:Processings/d2m:FrenchRidgeLap", True)
                dcmachinings = self._parse_machinings(part, "d2m:Processings/d2m:DoubleCut", False)

                if frlmachinings:
                    self.french_ridge_lap_machinings[part_id] = frlmachinings
                if dcmachinings:
                    self.double_cut_machinings[part_id] = dcmachinings
        except Exception as e:
            print("Error parsing BTLX file: ", e)

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
                    "Orientation": machining.find("d2m:Orientation", self.namespaces).text,
                    "StartX": machining.find("d2m:StartX", self.namespaces).text,
                    "Angle": machining.find("d2m:Angle", self.namespaces).text,
                    "RefPosition": machining.find("d2m:RefPosition", self.namespaces).text,
                    "Drillhole": machining.find("d2m:Drillhole", self.namespaces).text,
                    "DrillholeDiam": machining.find("d2m:DrillholeDiam", self.namespaces).text,
                }
            else:
                machining_data = {
                    "Name": machining.get("Name"),
                    "Priority": machining.get("Priority"),
                    "Process": machining.get("Process"),
                    "ProcessID": machining.get("ProcessID"),
                    "ReferencePlaneID": machining.get("ReferencePlaneID"),
                    "Orientation": (
                        machining.find("d2m:Orientation", self.namespaces).text
                        if machining.find("d2m:Orientation", self.namespaces) is not None
                        else None
                    ),
                    "StartX": (
                        machining.find("d2m:StartX", self.namespaces).text
                        if machining.find("d2m:StartX", self.namespaces) is not None
                        else None
                    ),
                    "StartY": (
                        machining.find("d2m:StartY", self.namespaces).text
                        if machining.find("d2m:StartY", self.namespaces) is not None
                        else None
                    ),
                    "Angle1": (
                        machining.find("d2m:Angle1", self.namespaces).text
                        if machining.find("d2m:Angle1", self.namespaces) is not None
                        else None
                    ),
                    "Inclination1": (
                        machining.find("d2m:Inclination1", self.namespaces).text
                        if machining.find("d2m:Inclination1", self.namespaces) is not None
                        else None
                    ),
                    "Angle2": (
                        machining.find("d2m:Angle2", self.namespaces).text
                        if machining.find("d2m:Angle2", self.namespaces) is not None
                        else None
                    ),
                    "Inclination2": (
                        machining.find("d2m:Inclination2", self.namespaces).text
                        if machining.find("d2m:Inclination2", self.namespaces) is not None
                        else None
                    ),
                }
            machinings.append(machining_data)
        return machinings

    def _create_remachining_dict(self):
        for part_id, machinings in self.french_ridge_lap_machinings.items():
            self.remachining_dict[part_id] = {"length": self.part_lengths[part_id], "machinings": []}
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
            self.remachining_dict[part_id]["machinings"].append(FRL_face_front)            
                    
        for part_id, machinings in self.double_cut_machinings.items():
            if part_id not in self.remachining_dict:
                self.remachining_dict[part_id] = {"length": self.part_lengths[part_id], "machinings": []}
            for machining in machinings:
                self.remachining_dict[part_id]["machinings"].append(machining)

    def get_remachining_dict(self):
        return self.remachining_dict

if __name__ == "__main__":
    # Usage example
    file_path = os.path.join(os.path.dirname(__file__), "240514_Module81.btlx")
    parser = BTLXParser(file_path)
    remachining_dict = parser.get_remachining_dict()
    print(remachining_dict)
