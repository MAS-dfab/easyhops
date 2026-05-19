"""timber_model_to_hops.py
========================
Example: parse a BTLx file and write one .hop file per timber element.

Explicit workflow (recommended):
   Build each HOPSJob yourself — iterate processings, call strategies directly,
   handle flip logic and sorting explicitly for full control.

Usage
-----
    python examples/timber_model_to_hops.py
    python examples/timber_model_to_hops.py --btlx path/to/model.btlx --output-dir out/
    python examples/timber_model_to_hops.py --index 3    # single element only
"""

import argparse
import os

from compas_timber.btlx import BTLxReader

from easyhops.hop_job import HOPSJob
from easyhops.strategies import LapStrategies
from easyhops.strategies.jack_rafter_cut import JackRafterCutStrategies
from easyhops.tool_library import SaegeD350
from easyhops.utility_commands import MachineStop

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BTLx_PATH = os.path.join(os.path.dirname(__file__), "BTLx", "test_btlx.btlx")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "hops_output")


# ---------------------------------------------------------------------------
# 1.  Load model
# ---------------------------------------------------------------------------
def load_model(btlx_path: str):
    reader = BTLxReader()
    model = reader.read(btlx_path)
    reader.print_errors()
    return model


# ---------------------------------------------------------------------------
# 2.  Explicit workflow — developer drives everything
# ---------------------------------------------------------------------------
def element_to_job(element):
    """Build a HOPSJob for *element* with explicit control over dispatch."""
    job = HOPSJob.from_element(element)
    rsi = job.ref_side_index
    opp_rsi = (rsi + 2) % 4

    pre_flip = []
    post_flip = []

    for processing in element.features:
        name = processing.PROCESSING_NAME

        if name == "Lap":
            machinings = LapStrategies.milling(processing)
            if processing.ref_side_index == opp_rsi:
                pre_flip.extend(machinings)
            elif processing.ref_side_index == rsi:
                post_flip.extend(machinings)
            else:
                raise ValueError(f"Unexpected ref_side_index {processing.ref_side_index} for Lap")

        elif name == "JackRafterCut":
            assert processing.ref_side_index in (rsi, opp_rsi), f"Unexpected ref_side_index {processing.ref_side_index} for JackRafterCut"
            post_flip.extend(JackRafterCutStrategies.sawing(processing, machine_ref_side_index=rsi, tool=SaegeD350()))

    # Sort post-flip: milling before sawing
    post_flip.sort(key=lambda m: {"MILLING": 0, "SAWING": 1}.get(getattr(m, "OPERATION_TYPE", ""), 2))

    if pre_flip:
        job.add(pre_flip)
        job.add(MachineStop("flip beam 180deg"))
    job.add(post_flip)

    return job


# ---------------------------------------------------------------------------
# 3.  Convert all elements, skip failures
# ---------------------------------------------------------------------------
def model_to_hop_jobs(model):
    results = []
    errors = []
    for i, element in enumerate(model.elements()):
        try:
            job = element_to_job(element)
            results.append((f"part_{i}.hop", job))
        except Exception as exc:
            errors.append((i, exc))
    return results, errors


# ---------------------------------------------------------------------------
# 4.  Write .hop files
# ---------------------------------------------------------------------------
def write_jobs(jobs, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    for filename, job in jobs:
        path = os.path.join(output_dir, filename)
        job.to_hop_file(path)
        print(f"  wrote {path}")


# ---------------------------------------------------------------------------
# 5.  Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--btlx", default=BTLx_PATH, metavar="FILE", help="Input .btlx file")
    parser.add_argument("--output-dir", "-o", default=OUTPUT_DIR, metavar="DIR", help="Output directory")
    parser.add_argument("--index", "-i", type=int, default=None, metavar="N", help="Convert only element N (0-based)")
    args = parser.parse_args()

    model = load_model(args.btlx)

    errors = []
    if args.index is not None:
        element = list(model.elements())[args.index]
        try:
            jobs = [(f"part_{args.index}.hop", element_to_job(element))]
        except Exception as exc:
            jobs = []
            errors.append((args.index, exc))
    else:
        jobs, errors = model_to_hop_jobs(model)

    print(f"Writing {len(jobs)} HOP file(s) to {args.output_dir}")
    write_jobs(jobs, args.output_dir)

    if errors:
        print(f"\n{len(errors)} element(s) failed:")
        for idx, exc in errors:
            print(f"  part_{idx}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
