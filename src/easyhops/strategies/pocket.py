from __future__ import annotations

from typing import TYPE_CHECKING
from typing import List
from typing import Optional

from easyhops.contour_commands import CloseContour
from easyhops.contour_commands import ContourLine
from easyhops.contour_commands import ContourStart

from ..hop_core import EasySnapXY
from ..hop_core import EasySnapZ
from ..machining_commands import FreeFormPocket
from ..tool_library import CastorD61
from ..tool_library import MachiningTool
from ..work_planes import FreePlane

if TYPE_CHECKING:
    from compas_timber.fabrication import Pocket

    from ..hop_job import HOPSMachining


class PocketStrategies:
    @staticmethod
    def pocketing(
        pocket: "Pocket",
        machine_ref_side_index: int,
        tool: Optional[MachiningTool] = None,
    ) -> "List[HOPSMachining]":
        """Create a HOPSMachining for a pocket milling operation derived from a Pocket processing.

        Generates an EBENEF work plane and a single _ExecutePocket_ETH macro call that mills
        the Pocket surface as a pocket with the given depth, angle, inclination, and slope.

        The work plane origin is at (start_x, start_y, 0), tilted by ``90 - inclination``
        and rotated by ``180 - angle``.

        Supports ref_side_index 0 (top face) and 2 (bottom face).

        Parameters
        ----------
        pocket : Pocket
            The Pocket processing containing the geometric information.
        machine_ref_side_index : int
            The index of the reference side on the machine (used for orientation).
        tool : MachiningTool, optional
            Defaults to CastorD61 (WZF503).

        Returns
        -------
        List[HOPSMachining]
            A single HOPSMachining instance.
        """
        from ..hop_job import HOPSMachining

        tool = tool or CastorD61()

        assert pocket.slope == 0.0, (
            f"Pocket milling is only supported for vertical Pockets (90° inclination and 0° slope). got inclination={pocket.inclination} and slope={pocket.slope}"
        )

        # check the ref_side of the Pocket
        diff = (pocket.ref_side_index - machine_ref_side_index) % 4
        if diff == 0:  # same side
            work_plane = FreePlane(
                x=pocket.start_x,
                y=pocket.start_y,
                z=0.0,
                rotation_angle=pocket.angle,
                tilt_angle=pocket.inclination,
                easy_snap_xy=EasySnapXY.FRONT_LEFT,
                easy_snap_z=EasySnapZ.TOP_SIDE,
            )
        else:
            raise NotImplementedError(
                f"Unsupported ref_side_index {Pocket.ref_side_index} for Pocket milling. "
                f"Expected {(machine_ref_side_index + 1) % 4} (front) or {(machine_ref_side_index - 1) % 4} (back)."
            )

        # define the contours (current implementation supports only rectangular pockets, so the contour is a simple rectangle)
        contour_name = "RE_" + str(pocket.guid)[:4]  # use first 4 chars of the guid as a short identifier for the contour name
        dx = pocket.length
        dy = pocket.width
        contours = [
            ContourStart(contour_name, x=dx, y=dy, easy_snap_xy=EasySnapXY.DISABLED),
            ContourLine(x=0, y=-dy, easy_snap_xy=EasySnapXY.RELATIVE),
            ContourLine(x=-dx, y=0, easy_snap_xy=EasySnapXY.RELATIVE),
            ContourLine(x=0, y=dy, easy_snap_xy=EasySnapXY.RELATIVE),
            CloseContour(),
        ]
        if pocket.start_x < 0:
            contours = [
                ContourStart(contour_name, x=0, y=0, easy_snap_xy=EasySnapXY.DISABLED),
                ContourLine(x=dx, y=0, easy_snap_xy=EasySnapXY.RELATIVE),
                ContourLine(x=0, y=dy, easy_snap_xy=EasySnapXY.RELATIVE),
                ContourLine(x=-dx, y=0, easy_snap_xy=EasySnapXY.RELATIVE),
                CloseContour(),
            ]

        milling_operations = [FreeFormPocket(contour_name=contour_name, distance_to_contour=0.0, overlap=33, mode=0, depth=-pocket.start_depth)]

        return [
            HOPSMachining(
                tool=tool,
                work_plane=work_plane,
                operations=contours + milling_operations,
                comments=[
                    "; ---------------------------------",
                    ";Pocket_Pocketing",
                    "; ---------------------------------",
                ],
            )
        ]
