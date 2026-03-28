"""Shared electrical calculations used by multiple page builders.

Provides:
  - compute_branch_circuits() — split N panels into balanced branch circuits
"""

import math
from typing import List, Tuple


def compute_branch_circuits(total_panels: int, max_per_branch: int) -> List[int]:
    """Split *total_panels* into balanced branch circuits.

    Each branch has at most *max_per_branch* panels.  The panels are
    distributed as evenly as possible (larger branches first).

    Returns:
        List of ints — number of panels in each branch circuit.

    Examples:
        >>> compute_branch_circuits(30, 7)
        [6, 6, 6, 6, 6]
        >>> compute_branch_circuits(5, 7)
        [5]
    """
    n = max(total_panels, 1)
    if n <= max_per_branch:
        return [n]
    nb = math.ceil(n / max_per_branch)
    base_sz = n // nb
    rem = n % nb
    return [base_sz + (1 if i < rem else 0) for i in range(nb)]
