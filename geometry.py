# ##### BEGIN GPL LICENSE BLOCK #####
#
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

import bmesh
import collections
import math
import mathutils
import sys
import threading
from typing import Dict, List, Optional, Set, Tuple
from . import linalg
from . import types


def calc_circumcenter(a: mathutils.Vector,
                      b: mathutils.Vector,
                      c: mathutils.Vector) -> float:
    """
    Calculates the 3-dimensional circumcenter of three points

        https://gamedev.stackexchange.com/a/60631

    Parameters:
        a, b, c (mathutils.Vector): Points of a triangle

    Returns:
        mathutils.Vector: Circumcenter point
    """
    ab = b - a
    ac = c - a
    ab_cross_ac = ab.cross(ac)
    if ab_cross_ac.length_squared > 0:
        d = ac.length_squared * ab_cross_ac.cross(ab)
        d += ab.length_squared * ac.cross(ab_cross_ac)
        d /= 2 * ab_cross_ac.length_squared
        return a + d
    else:
        return a


def calc_uniform_vertex_weight(v: bmesh.types.BMVert) -> float:
    """
    Calculates uniform weight of the given vertex

    Parameters:
        v (bmesh.types.BMVert): Vertex for which to calculate the weight

    Returns:
        float: Uniform vertex weight
    """
    n = len(v.link_edges)
    return 1 / n if n != 0 else sys.maxsize


def calc_barycentric_vertex_weight(v: bmesh.types.BMVert) -> float:
    """
    Calculates inverse Barycentric area weight of the given vertex

    Parameters:
        v (bmesh.types.BMVert): Vertex

    Returns:
        float: Inverse Barycentric area vertex weight
    """
    area = 0
    a = v.co
    for l in v.link_loops:
        b = l.link_loop_next.vert.co
        c = l.link_loop_prev.vert.co
        area += mathutils.geometry.area_tri(a, b, c) / 3
    return 1 / area if area != 0 else 1e12


def calc_voronoi_vertex_weight(v: bmesh.types.BMVert) -> float:
    """
    Calculates inverse Voronoi area weight of the given vertex

    Parameters:
        v (bmesh.types.BMVert): Vertex

    Returns:
        float: Inverse Voronoi area vertex weight
    """
    area = 0
    a = v.co
    acute_threshold = math.pi / 2
    for l in v.link_loops:
        b = l.link_loop_next.vert.co
        c = l.link_loop_prev.vert.co
        if l.calc_angle() < acute_threshold:
            d = calc_circumcenter(a, b, c)
        else:
            d = (b + c) / 2
        area += mathutils.geometry.area_tri(a, (a + b) / 2, d)
        area += mathutils.geometry.area_tri(a, d, (a + c) / 2)
    return 1 / area if area != 0 else 1e12


def calc_cotangent_loop_weight(l: bmesh.types.BMLoop) -> float:
    """
    Calculates cotangent weight of the given loop

    Parameters:
        l (bmesh.types.BMLoop): Loop

    Returns:
        float: Cotangent loop weight
    """
    weight = 0
    co_a = l.vert.co
    co_b = l.link_loop_next.vert.co
    coords = [l.link_loop_prev.vert.co]
    if not l.edge.is_boundary:
        coords.append(
            l.link_loop_radial_next.link_loop_next.link_loop_next.vert.co)
    for co_c in coords:
        try:
            angle = (co_a - co_c).angle(co_b - co_c)
            weight += 1 / math.tan(angle)
        except (ValueError, ZeroDivisionError):
            weight += 1e-4
    weight /= 2
    return weight


def calc_mvc_loop_weight(l: bmesh.types.BMLoop) -> float:
    """
    Calculates mean value coordinate weight of the given loop

    Parameters:
        l (bmesh.types.BMLoop): Loop

    Returns:
        float: Mean value coordinate loop weight
    """
    weight = 0
    length = l.edge.calc_length()
    if length > 0:
        weight += math.tan(l.calc_angle() / 2)
        if not l.edge.is_boundary:
            weight += math.tan(
                l.link_loop_radial_next.link_loop_next.calc_angle() / 2)
        weight /= length
    return weight


def calc_mean_curvature(v: bmesh.types.BMVert,
                        vert_weights: Dict[bmesh.types.BMVert, float],
                        loop_weights: Dict[bmesh.types.BMLoop, float]) -> float:
    """
    Calculates signed mean curvature of the given vertex

    Parameters:
        v (bmesh.types.BMVert):                         Vertex
        vert_weights (Dict[bmesh.types.BMVert, float]): Vertex weights
        loop_weights (Dict[bmesh.types.BMLoop, float]): Loop weights

    Returns:
        float: Signed mean curvature (valleys < 0; flats == 0; ridges > 0)
    """
    curvature = 0
    normal = mathutils.Vector((0, 0, 0))
    for l in v.link_loops:
        normal += loop_weights[l] * (v.co - l.edge.other_vert(v).co)
    normal *= vert_weights[v]
    curvature = normal.length / 2
    if v.normal.dot(normal) < 1:
        curvature *= -1
    return curvature


def calc_gaussian_curvature(v: bmesh.types.BMVert,
                            vert_weights: Dict[bmesh.types.BMVert, float]) -> float:
    """
    Calculates Gaussian curvature of the given vertex

    Parameters:
        v (bmesh.types.BMVert):                         Vertex
        vert_weights (Dict[bmesh.types.BMVert, float]): Vertex weights

    Returns:
        float: Gaussian curvature
    """
    a = v.co
    angle_sum = 0
    acute_threshold = math.pi / 2
    for l in v.link_loops:
        angle = l.calc_angle()
        if angle < acute_threshold:
            angle_sum += angle
        else:
            b = l.link_loop_next.vert.co
            c = l.link_loop_prev.vert.co
            d = (b + c) / 2
            try:
                angle_sum += math.pi - (b - d).angle(c - d)
            except ValueError:
                angle_sum += 1e-4
    return vert_weights[v] * (2 * math.pi - angle_sum)


def fair(verts: List[bmesh.types.BMVert],
         order: int,
         vert_weights: Dict[bmesh.types.BMVert, float],
         loop_weights: Dict[bmesh.types.BMLoop, float],
         cancel_event: Optional[threading.Event] = None,
         status: Optional[types.Property] = None) -> bool:
    """
    Displaces given vertices to form a smooth-as-possible mesh patch

    Parameters:
        verts (List[bmesh.types.BMVert]):               Vertices to act upon
        order (int):                                    Laplace-Beltrami
                                                        operator order
        vert_weights (Dict[bmesh.types.BMVert, float]): Vertex weights
        loop_weights (Dict[bmesh.types.BMLoop, float]): Loop weights
        cancel_event (Optional[threading.Event]):       Event that can be set
                                                        to return prematurely
        status (Optional[types.Property]):              Status message

    Returns:
        bool: True if fairing succeeded; False otherwise
    """
    # Setup the linear system.
    interior_verts = (v for v in verts if not v.is_boundary and not v.is_wire)
    vert_col_map = {v: col for col, v in enumerate(interior_verts)}
    A = dict()
    b = [[0 for i in range(3)] for j in range(len(vert_col_map))]
    for v, col in vert_col_map.items():
        if cancel_event is None or not cancel_event.is_set():
            if status is not None:
                status.set('Setting up linear system ({:>3}%)'.format(
                    int((col + 1) / len(vert_col_map) * 100)))
            setup_fairing(v, col, A, b, 1, order, vert_col_map, vert_weights, loop_weights)

    # Solve the linear system.
    if cancel_event is None or not cancel_event.is_set():
        if status is not None:
            status.set('Solving linear system')
        x = linalg.solver.solve(A, b)

    # Apply results.
    if cancel_event is None or not cancel_event.is_set():
        if x is not None:
            if status is not None:
                status.set('Applying results')
            for v, col in vert_col_map.items():
                v.co = x[col]
            return True

    return False


def setup_fairing(v: bmesh.types.BMVert,
                  i: int,
                  A: Dict[Tuple[int], float],
                  b: List[List[float]],
                  multiplier: float,
                  depth: int,
                  vert_col_map: Dict[bmesh.types.BMVert, int],
                  vert_weights: Dict[bmesh.types.BMVert, float],
                  loop_weights: Dict[bmesh.types.BMLoop, float]):
    """
    Recursive helper function to build a linear system that represents the
    discretized fairing problem

    Implementation details are based on CGAL source code available on GitHub:

        cgal/Polygon_mesh_processing/include/CGAL/Polygon_mesh_processing/internal/fair_impl.h

    Parameters:
        v (bmesh.types.BMVert):                         Vertex
        i (int):                                        Row index of A
        A (Dict[Tuple[int], float]):                    Coefficient matrix A
        b (List[List[float]]):                          Right hand side of the
                                                        linear system
        multiplier (float):                             Recursive multiplier
        depth (int):                                    Recursion depth
        vert_col_map (Dict[bmesh.types.BMVert, int]):   Maps each vertex to a
                                                        column index j of A
        vert_weights (Dict[bmesh.types.BMVert, float]): Vertex weights
        loop_weights (Dict[bmesh.types.BMLoop, float]): Loop weights
    """
    if depth == 0:

        # Set the coefficient of an internal vertex.
        if v in vert_col_map:
            j = vert_col_map[v]
            if (i, j) not in A:
                A[i, j] = 0
            A[i, j] -= multiplier

        # Set the value of a boundary vertex.
        else:
            b[i][0] += multiplier * v.co.x
            b[i][1] += multiplier * v.co.y
            b[i][2] += multiplier * v.co.z
    else:
        w_ij_sum = 0
        w_i = vert_weights[v]

        # Recursively compute adjacent vertices.
        for l in v.link_loops:
            other = l.link_loop_next.vert
            w_ij = loop_weights[l]
            w_ij_sum += w_ij
            setup_fairing(other, i, A, b, w_i * w_ij * multiplier, depth - 1, vert_col_map, vert_weights, loop_weights)

        # Recursively compute this vertex.
        setup_fairing(v, i, A, b, -1 * w_i * w_ij_sum * multiplier, depth - 1, vert_col_map, vert_weights, loop_weights)


def find_edge(v1: bmesh.types.BMVert,
              v2: bmesh.types.BMVert) -> bmesh.types.BMEdge:
    """
    Finds the edge, if any, connecting given vertices

    Parameters:
        v1, v2 (bmesh.types.BMVert): Vertices

    Returns:
        bmesh.types.BMEdge: Edge connecting vertices; None if not found
    """
    for e in v1.link_edges:
        if e.other_vert(v1) is v2:
            return e
    return None


def get_closed_neighborhood(v: bmesh.types.BMVert, dist: int) -> Set[bmesh.types.BMVert]:
    """
    Gets all linked vertices within given distance of a vertex

    Parameters:
        v (bmesh.types.BMVert): Vertex from which to search
        dist (int):             Maximum distance to search

    Returns:
        Set[bmesh.types.BMVert]: Closed neighborhood
    """
    if dist <= 0:
        visisted = {v}
    else:
        visited = set()
        traversal_queue = collections.deque()
        traversal_queue.appendleft((v, 0))
        while len(traversal_queue) > 0:
            v_curr, dist_curr = traversal_queue.pop()
            visited.add(v_curr)
            if dist_curr < dist:
                dist_next = dist_curr + 1
                for e in v_curr.link_edges:
                    v_next = e.other_vert(v_curr)
                    if v_next not in visited:
                        traversal_queue.appendleft((v_next, dist_next))
    return visited


def expand_faces(faces: Set[bmesh.types.BMFace], dist: int) -> Set[bmesh.types.BMFace]:
    """
    Expands given face set by a specified topological distance

    Parameters:
        faces (List[bmesh.types.BMFace]): Faces to evaluate
        dist (int):                       Topological distance

    Returns:
        Set[bmesh.types.BMFace]: Expanded face selection
    """
    if dist <= 0:
        visited = set(faces)
    else:
        visited = set()
        traversal_queue = collections.deque((f, 0) for f in faces)
        while len(traversal_queue) > 0:
            f_curr, dist_curr = traversal_queue.pop()
            visited.add(f_curr)
            if dist_curr < dist:
                dist_next = dist_curr + 1
                for l in f_curr.loops:
                    f_next = l.link_loop_radial_next.face
                    if f_next not in visited:
                        traversal_queue.appendleft((f_next, dist_next))
    return visited


def get_boundary_faces(faces: Set[bmesh.types.BMFace]) -> Set[bmesh.types.BMFace]:
    """
    Determines which among the given faces are boundary faces

    Parameters:
        faces (List[bmesh.types.BMFace]): Faces to evaluate

    Returns:
        Set[bmesh.types.BMFace]: Boundary faces
    """
    boundary = set()
    for f_curr in faces:
        for l in f_curr.loops:
            f_other = l.link_loop_radial_next.face
            if f_other is f_curr or f_other not in faces:
                boundary.add(f_curr)
    return boundary
