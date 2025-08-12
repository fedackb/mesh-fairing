# ##### BEGIN GPL LICENSE BLOCK #####

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

import importlib
import logging
from typing import Dict, List, Tuple 
from . import moduleutil


class Solver():
    """
    Linear system solver interface
    """

    def solve(self, A: Dict[Tuple[int], float], b: List[List[float]]):
        """
        Solves the Ax=b linear system of equations

        Parameters:
            A (Dict[Tuple[int], float]): Coefficient matrix A
            b (List<List<float>>): Right hand side of the linear system

        Returns:
            numpy.ndarray: Variables matrix (x); None if unsuccessful

        Raises: NotImplementedError
        """
        raise NotImplementedError


class NullSolver(Solver):
    """
    Linear system solver implemented as a null object
    """

    def solve(self, A: Dict[Tuple[int], float], b: List[List[float]]):
        """
        Solves the Ax=b linear system of equations

        Parameters:
            A (Dict[Tuple[int], float]): Coefficient matrix A
            b (List[List[float]]): Right hand side of the linear system

        Returns:
            None: Indication of no-op
        """
        return None


class NumPySolver(Solver):
    """
    Linear system solver implemented with NumPy library

    Attributes:
        numpy (importlib.type.ModuleType): NumPy library
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes this linear system solver
        """
        super().__init__(*args, **kwargs)
        self.numpy = importlib.import_module('numpy')

    def solve(self, A: Dict[Tuple[int], float], b: List[List[float]]):
        """
        Solves the Ax=b linear system of equations using NumPy library

        Parameters:
            A (Dict[Tuple[int], float]): Coefficient matrix A
            b (List[List[float]]): Right hand side of the linear system

        Returns:
            numpy.ndarray: Variables matrix (x); None if unsuccessful
        """
        x = None
        n = len(b)

        # Attempt to solve the linear system with NumPy library.
        try:
            A_numpy = self.numpy.zeros((n, n), dtype = 'd')
            b = self.numpy.asarray(b, dtype = 'd')
            for key, val in A.items():
                A_numpy[key] = val
            x = self.numpy.linalg.solve(A_numpy, b)
        except Exception as e:
            logging.warn(e)

        return x


class SciPySolver(Solver):
    """
    Linear system solver implemented with SciPy library

    Attributes:
        scipy (importlib.type.ModuleType): SciPy library
        numpy (importlib.type.ModuleType): NumPy library
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes this linear system solver
        """
        super().__init__(*args, **kwargs)
        self.scipy = importlib.import_module('scipy')
        self.numpy = importlib.import_module('numpy')
        importlib.import_module('scipy.sparse.linalg')

    def solve(self, A: Dict[Tuple[int], float], b: List[List[float]]):
        """
        Solves the Ax=b linear system of equations using SciPy library

        Parameters:
            A (Dict[Tuple[int], float]): Coefficient matrix A
            b (List[List[float]]): Right hand side of the linear system

        Returns:
            numpy.ndarray: Variables matrix (x); None if unsuccessful
        """
        x = None
        n = len(b)

        # Attempt to solve the linear system with SciPy library.
        try:
            A_scipy = self.scipy.sparse.dok_matrix((n, n), dtype='d')
            for key, val in A.items():
                A_scipy[key] = val
            A_scipy = A_scipy.tocsc()
            b = self.numpy.array(b, dtype='d')
            factor = self.scipy.sparse.linalg.splu(A_scipy, diag_pivot_thresh=0.00001)
            x = factor.solve(b)
        except Exception as e:
            logging.warn(e)

        return x

def init():
    """
    Initializes this module's linear algebra solver
    """
    global solver
    if not moduleutil.is_installed('numpy'):
        solver = NullSolver()
        logging.debug('Using NullSolver')
    elif moduleutil.is_installed('scipy'):
        solver = SciPySolver()
        logging.debug('Using SciPySolver')
    else:
        solver = NumPySolver()
        logging.debug('Using NumPySolver')

solver = NullSolver()
