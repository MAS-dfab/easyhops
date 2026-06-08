from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING
from typing import List
from typing import Optional

from easyhops.hop_core import EasySnapXY
from easyhops.hop_core import EasySnapZ

from ..machining_commands import DrillingOperation
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

    @staticmethod
    def drilling(
        drilling: "Drilling",
        machine_ref_side_index: int,
        pre_drill: Optional[bool] = True,
        tool: Optional[MachiningTool] = None,
    ) -> "List[HOPSMachining]":
        """Create HOPSMachining instances for a drilling operation derived from a Longitudinal processing with a contouring strategy.

        Parameters:
        -----------
        longitudinal_cut : LongitudinalCut
            The LongitudinalCut processing containing the geometric information
        machine_ref_side_index : int
            The index of the reference side on the machine (0-3), used to determine the orientation of the milling operation
        pre_drill : Optional[bool], optional
            Whether to perform a pre-drill operation, by default True
        tool : MachiningTool, optional
            The machining tool to use; defaults to CastorD61

        Returns:
        --------
        List[HOPSMachining]
            One or more HOPSMachining instances representing this milling operation
        """
        from ..hop_job import HOPSMachining

        tool = tool or MachiningTool(position=607)
        pre_drill_tool = MachiningTool(position=301)  # Folding Tool
        tool_max_depth = 60.0  # Limit max depth to 80mm for drilling operations

        # check the ref_side of the drilling
        diff = (drilling.ref_side_index - machine_ref_side_index) % 4
        if diff == 2:  # opposite side
            raise ValueError("Drilling on the opposite side of the machine is not supported.")
        elif diff == 0:  # same side
            x = drilling.start_x
            y = drilling.start_y
            z = 0.0
            rotation = 180 - drilling.angle
            tilt = -drilling.inclination
            easy_snap_xy = EasySnapXY.FRONT_LEFT
            easy_snap_z = EasySnapZ.TOP_SIDE
        elif diff == 1:  # front side
            x = drilling.start_x
            y = 0.0
            z = drilling.start_y
            rotation = drilling.inclination
            tilt = 180 - drilling.angle
            easy_snap_xy = EasySnapXY.FRONT_LEFT
            easy_snap_z = EasySnapZ.TOP_SIDE
        elif diff == 3:  # back side
            x = drilling.start_x
            y = 0.0
            z = drilling.start_y
            rotation = 180 - drilling.inclination
            tilt = drilling.angle
            easy_snap_xy = EasySnapXY.REAR_LEFT
            easy_snap_z = EasySnapZ.TOP_SIDE

        drilling_operation = DrillingOperation(
            x=x,
            y=y,
            z=z,
            depth=-min(drilling.depth, tool_max_depth),
            diameter=drilling.diameter,
            rotation=rotation,
            tilt=tilt,
            easy_snap_xy=easy_snap_xy,
            easy_snap_z=easy_snap_z,
        )

        if pre_drill:
            predrill_operation = deepcopy(drilling_operation)
            predrill_operation.diameter = 1.0
            predrill_operation.depth = -8.0
            comment_labels = ["Drilling_PreDrill", "Drilling_Drill"]
            comments = ["\n".join(["; ---------------------------------", f"; {comment_labels[i]}", "; ---------------------------------"]) for i in range(2)]
            return [
                HOPSMachining(tool=pre_drill_tool, work_plane=WorkPlane.TOP, operations=predrill_operation, comments=[comments[0]]),
                HOPSMachining(tool=tool, work_plane=WorkPlane.TOP, operations=drilling_operation, comments=[comments[1]]),
            ]
        else:
            comment_label = "Drilling_Drill"
            comment = "\n".join(["; ---------------------------------", f"; {comment_label}", "; ---------------------------------"])
            return [HOPSMachining(tool=tool, work_plane=WorkPlane.TOP, operations=drilling_operation, comments=[comment])]
