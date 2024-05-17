import xml.etree.ElementTree as ET
import os

# Define the namespaces to parse the XML
namespaces = {
    '': 'https://www.design2machine.com'
}

file = os.path.join(os.path.dirname(__file__), 'french_lap - Copy.btlx')
# Load and parse the XML file
tree = ET.parse(file)
root = tree.getroot()

# Dictionary to store French Ridge Lap machinings for each part
french_ridge_lap_machinings = {}

# Iterate through each part in the XML
for part in root.findall('Project/Parts/Part', namespaces):
    part_id = part.get('OrderNumber')
    machinings = []
    
    # Iterate through each FrenchRidgeLap machining in the part
    for machining in part.findall('Processings/FrenchRidgeLap', namespaces):
        machining_data = {
            'Name': machining.get('Name'),
            'Priority': machining.get('Priority'),
            'Process': machining.get('Process'),
            'ProcessID': machining.get('ProcessID'),
            'ReferencePlaneID': machining.get('ReferencePlaneID'),
            'Orientation': machining.find('Orientation', namespaces).text,
            'StartX': machining.find('StartX', namespaces).text,
            'Angle': machining.find('Angle', namespaces).text,
            'RefPosition': machining.find('RefPosition', namespaces).text,
            'Drillhole': machining.find('Drillhole', namespaces).text,
            'DrillholeDiam': machining.find('DrillholeDiam', namespaces).text,
        }
        machinings.append(machining_data)
    
    french_ridge_lap_machinings[part_id] = machinings

# Print out the French Ridge Lap machinings for each part
for part_id, machinings in french_ridge_lap_machinings.items():
    print(f"Part ID: {part_id}")
    for machining in machinings:
        print(f"  Machining: {machining}")
