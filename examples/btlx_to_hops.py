import argparse
import os
import sys

from compas_timber.btlx import BTLxReader

from easyhops.hop_job import HOPSJob
from easyhops.tool_library import CastorD61

BTLxPATH = os.path.join(os.path.dirname(__file__), "BTLx", "user_ref_planes_test.btlx")
HOPS_DIR = os.path.join(os.path.dirname(__file__), "hops_output")


def parse_btlx():
    reader = BTLxReader()
    model = reader.read(BTLxPATH)
    reader.print_errors()
    return model


def get_hop_jobs_from_timber_model(model, index=None):
    tool = CastorD61()
    if index is not None:
        element = model.elements()[index]
        return [HOPSJob.from_timber_element(element, tool=tool)]
    else:
        return [HOPSJob.from_timber_element(element, tool=tool) for element in model.elements()]


def write_hop_jobs(hop_jobs, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    for i, job in enumerate(hop_jobs):
        output_path = os.path.join(output_dir, f"part_{i}.hop")
        job.to_hop_file(output_path)
        print(f"Wrote HOP file: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Convert a BTLx model to HOPS (.hop) files.")
    parser.add_argument(
        "--btlx",
        default=BTLxPATH,
        metavar="FILE",
        help=f"Path to the input .btlx file (default: {BTLxPATH})",
    )
    parser.add_argument(
        "--index",
        "-i",
        type=int,
        default=None,
        metavar="N",
        help="Index of a single element to convert (0-based). Omit to convert all elements.",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=HOPS_DIR,
        metavar="DIR",
        help=f"Directory to write .hop files (default: {HOPS_DIR})",
    )
    args = parser.parse_args()

    model = parse_btlx()
    hop_jobs = get_hop_jobs_from_timber_model(model, index=args.index)
    write_hop_jobs(hop_jobs, args.output_dir)


if __name__ == "__main__":
    main()
