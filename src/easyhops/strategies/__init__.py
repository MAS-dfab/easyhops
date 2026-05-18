from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Callable
from typing import List


from .birdsmouth import BirdsMouthStrategies
from .double_cut import DoubleCutStrategies
from .jack_rafter_cut import JackRafterCutStrategies
from .lap import LapStrategies

if TYPE_CHECKING:
    from ..hop_job import HOPSMachining

# Signature: (processing, ref_side_index: int) -> List[HOPSMachining]
StrategyCallable = Callable[..., "List[HOPSMachining]"]


# ---------------------------------------------------------------------------
# Built-in default strategy callables
# ---------------------------------------------------------------------------


def _default_double_cut(processing, ref_side_index: int) -> "List[HOPSMachining]":
    from ..tool_library import CastorD61

    tool = CastorD61()
    strategy = processing.user_attributes.get("strategy", None)
    if strategy == "pocketing":
        return DoubleCutStrategies.pocketing(processing, machine_ref_side_index=ref_side_index, tool=tool)
    return DoubleCutStrategies.milling(processing, tool=tool)


def _default_birdsmouth(processing, ref_side_index: int) -> "List[HOPSMachining]":
    from ..tool_library import CastorD61

    return BirdsMouthStrategies.milling(processing, tool=CastorD61())


def _default_jack_rafter_cut(processing, ref_side_index: int) -> "List[HOPSMachining]":
    from ..tool_library import SaegeD350

    return JackRafterCutStrategies.sawing(processing, machine_ref_side_index=ref_side_index, tool=SaegeD350())


def _default_lap(processing, ref_side_index: int) -> "List[HOPSMachining]":
    return LapStrategies.milling(processing)


@dataclass
class StrategyConfig:
    """Per-processing-type strategy configuration for :meth:`HOPSJob.from_timber_element`.

    Each field is a callable with the uniform signature::

        (processing, ref_side_index: int) -> List[HOPSMachining]

    The defaults implement the standard machining strategies.  Override any
    field to customise behaviour for a specific processing type while keeping
    all others at their defaults.

    Parameters
    ----------
    double_cut : callable
        Strategy for ``DoubleCut`` processings.
    birdsmouth : callable
        Strategy for ``BirdsMouth`` processings.
    jack_rafter_cut : callable
        Strategy for ``JackRafterCut`` processings.
    lap : callable
        Strategy for ``Lap`` processings.

    Examples
    --------
    Use all defaults::

        job = HOPSJob.from_timber_element(element)

    Override a single processing type, keep everything else default::

        config = StrategyConfig(
            double_cut=lambda p, rsi: DoubleCutStrategies.pocketing(p, machine_ref_side_index=rsi, overlap=80),
        )
        job = HOPSJob.from_timber_element(element, config=config)

    Custom tool for lap joints::

        config = StrategyConfig(
            lap=lambda p, rsi: LapStrategies.milling(p, tool=SaegeD350()),
        )
    """

    double_cut: StrategyCallable = field(default=_default_double_cut)
    birdsmouth: StrategyCallable = field(default=_default_birdsmouth)
    jack_rafter_cut: StrategyCallable = field(default=_default_jack_rafter_cut)
    lap: StrategyCallable = field(default=_default_lap)


__all__ = [
    "BirdsMouthStrategies",
    "DoubleCutStrategies",
    "JackRafterCutStrategies",
    "LapStrategies",
    "StrategyConfig",
]
