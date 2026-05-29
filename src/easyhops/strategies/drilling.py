from __future__ import annotations

from typing import TYPE_CHECKING
from typing import List
from typing import Optional

from ..machining_commands import DrillingPocketOperation
from ..tool_library import SRSLD12
from ..tool_library import MachiningTool
from ..work_planes import WorkPlane

if TYPE_CHECKING:
    from compas_timber.fabrication import Drilling

    from ..hop_job import HOPSMachining


class DrillingStrategies:
    @staticmethod
    def pocketing(
        drilling: "Drilling",
        machine_ref_side_index: int,
        tool: Optional[MachiningTool] = None,
    ) -> "List[HOPSMachining]":
        """Create HOPSMachining instances for a milling operation derived from a Longitudinal processing with a contouring strategy.

        Parameters:
        -----------
        longitudinal_cut : LongitudinalCut
            The LongitudinalCut processing containing the geometric information
        machine_ref_side_index : int
            The index of the reference side on the machine (0-3), used to determine the orientation of the milling operation
        tool : MachiningTool, optional
            The machining tool to use; defaults to CastorD61

        Returns:
        --------
        List[HOPSMachining]
            One or more HOPSMachining instances representing this milling operation
        """
        from ..hop_job import HOPSMachining

        tool = tool or SRSLD12()

        # check if the drilling is reference on the oposite side. if so, raise an error, as drilling pockets from the opposite side is not supported
        diff = (drilling.ref_side_index - machine_ref_side_index) % 4
        if diff == 2:
            raise ValueError("Drilling pockets on the opposite side of the machine is not supported.")
        elif diff == 0:
            work_plane = WorkPlane.TOP
        elif diff == 1:
            work_plane = WorkPlane.FRONT
        elif diff == 3:
            work_plane = WorkPlane.BACK
        elif diff == 4:
            work_plane = WorkPlane.START
        elif diff == 5:
            work_plane = WorkPlane.END

        drilling_operation = DrillingPocketOperation(
            mx=drilling.start_x,
            my=drilling.start_y,
            radius=drilling.diameter / 2,
            depth=-drilling.depth,
            step_depth=tool.max_depth,
        )

        comment_label = "DrillingPocket"
        comment = "\n".join(["; ---------------------------------", f"; {comment_label}", "; ---------------------------------"])

        return [HOPSMachining(tool=tool, work_plane=work_plane, operations=drilling_operation, comments=[comment])]
