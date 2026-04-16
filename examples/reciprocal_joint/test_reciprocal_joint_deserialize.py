from __future__ import annotations

from pathlib import Path

from compas.data import json_load

from easyhops.hop_job import HOPSJob

FILEPATH = Path(__file__).with_name("reciprocal_joint.json")


def main() -> None:
    """TODO: implement your custom test flow here."""

    model = json_load(str(FILEPATH))
    model.process_joinery()

    for i, element in enumerate(model.elements()):
        job = HOPSJob.from_timber_element(element)
        job.to_hop_file(Path(__file__).with_name(f"reciprocal_joint_{i}.hop"))


if __name__ == "__main__":
    main()
