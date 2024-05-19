import xml.etree.ElementTree as ET
import os

# Define the namespaces to parse the XML
namespaces = {"": "https://www.design2machine.com"}

file = os.path.join(os.path.dirname(__file__), "240514_Module81.btlx")
# Load and parse the XML file
tree = ET.parse(file)
root = tree.getroot()

# Dictionary to store French Ridge Lap machinings for each part
french_ridge_lap_machinings = {}
double_cut_machinings = {}

# Iterate through each part in the XML
for part in root.findall("Project/Parts/Part", namespaces):
    part_id = part.get("OrderNumber")
    frlmachinings = []
    # Iterate through each FrenchRidgeLap machining in the part
    for machining in part.findall("Processings/FrenchRidgeLap", namespaces):
        machining_data = {
            "Name": machining.get("Name"),
            "Priority": machining.get("Priority"),
            "Process": machining.get("Process"),
            "ProcessID": machining.get("ProcessID"),
            "ReferencePlaneID": machining.get("ReferencePlaneID"),
            "Orientation": machining.find("Orientation", namespaces).text,
            "StartX": machining.find("StartX", namespaces).text,
            "Angle": machining.find("Angle", namespaces).text,
            "RefPosition": machining.find("RefPosition", namespaces).text,
            "Drillhole": machining.find("Drillhole", namespaces).text,
            "DrillholeDiam": machining.find("DrillholeDiam", namespaces).text,
        }
        frlmachinings.append(machining_data)

    dcmachinings = []
    # Iterate through each DoubleCut machining in the part
    for machining in part.findall("Processings/DoubleCut", namespaces):
        machining_data = {
            "Name": machining.get("Name"),
            "Priority": machining.get("Priority"),
            "Process": machining.get("Process"),
            "ProcessID": machining.get("ProcessID"),
            "ReferencePlaneID": machining.get("ReferencePlaneID"),
            "Orientation": (
                machining.find("Orientation", namespaces).text
                if machining.find("Orientation", namespaces) is not None
                else None
            ),
            "StartX": (
                machining.find("StartX", namespaces).text
                if machining.find("StartX", namespaces) is not None
                else None
            ),
            "StartY": (
                machining.find("StartY", namespaces).text
                if machining.find("StartY", namespaces) is not None
                else None
            ),
            "Angle1": (
                machining.find("Angle1", namespaces).text
                if machining.find("Angle1", namespaces) is not None
                else None
            ),
            "Inclination1": (
                machining.find("Inclination1", namespaces).text
                if machining.find("Inclination1", namespaces) is not None
                else None
            ),
            "Angle2": (
                machining.find("Angle2", namespaces).text
                if machining.find("Angle2", namespaces) is not None
                else None
            ),
            "Inclination2": (
                machining.find("Inclination2", namespaces).text
                if machining.find("Inclination2", namespaces) is not None
                else None
            ),
        }
        dcmachinings.append(machining_data)

    if len(frlmachinings) > 0:
        french_ridge_lap_machinings[part_id] = frlmachinings
    if len(dcmachinings) > 0:
        double_cut_machinings[part_id] = dcmachinings


for part_id, machinings in double_cut_machinings.items():
    print(f"Part ID: {part_id}")
    for machining in machinings:
        print(f"  Machining: {machining}")