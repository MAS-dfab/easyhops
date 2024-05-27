import os
import glob

class HOPSMerger:
    @staticmethod
    def merge_files(primary_file, secondary_file):
        # Append contents of secondary file to primary file
        with open(primary_file, 'a') as outfile:
            with open(secondary_file, 'r') as infile:
                outfile.write(infile.read())
        # Remove the secondary file after merging
        os.remove(secondary_file)

    @staticmethod
    def merge_hop_files(directory):
        # Change to the specified directory
        os.chdir(directory)
        
        # Find all primary files with the pattern '*.hop' excluding '*_.hop'
        primary_files = glob.glob("*.hop")
        primary_files = [f for f in primary_files if not f.endswith("_.hop")]
        
        for primary_file in primary_files:
            base_name = primary_file[:-4]  # Remove the '.hop' extension
            secondary_file = f"{base_name}_.hop"
            
            # Check if the corresponding secondary file exists
            if os.path.isfile(secondary_file):
                HOPSMerger.merge_files(primary_file, secondary_file)
                print(f"Merged {secondary_file} into {primary_file}")
