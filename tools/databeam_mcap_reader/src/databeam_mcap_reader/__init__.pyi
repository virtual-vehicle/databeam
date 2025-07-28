from .reader import *
from .collector import *

__all__: list[str]

def parse_mcap(py_array: np.ndarray, mcap_path: str, topic: str, start_time_ns: int = 0) -> str:
    """
    Parse an MCAP file into a numpy structured array
    """
