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
import bpy
import enum
import logging
import threading
from typing import Any, Callable, Set
import weakref
from . import geometry


class BMeshGuard:
    """
    Manages a BMesh resource that is bound to the scope of a 'with' statement

    Example Usage:
        with BMeshGuard() as bm:
            ...

    Attributes:
        _bm (bmesh.types.BMesh): Guarded BMesh resource
    """

    def __enter__(self):
        """
        Creates a BMesh resource upon entering the scope of a 'with' statement
        """
        self._bm = bmesh.new()
        return self._bm

    def __exit__(self, type, value, traceback):
        """
        Frees a BMesh resource upon leaving the scope of a 'with' statement
        """
        if self._bm.is_valid:
            self._bm.free()


class Cache(dict):
    """
    Data structure for caching values, essentially functioning as a dictionary
    where values can be calculated for keys not present in the collection

    Attributes:
        _calc (typing.Callable): Caching function to calculate values
    """

    def __init__(self, calc, *args, **kwargs):
        """
        Initializes this cache

        Parameters:
            calc (callable): Caching function to calculate values
        """
        super().__init__(*args, **kwargs)
        if calc is None:
            raise TypeError('A caching function is required')
        else:
            self._calc = calc

    def __getitem__(self, key):
        """
        Gets cached value or calculates a value if not already cached

        Returns:
            Any: Cached value
        """
        if key not in self:
            self[key] = self._calc(key)
        return super().__getitem__(key)

    def get(self, key):
        """
        Gets cached value or calculates a value if not already cached

        Returns:
            Any: Cached value
        """
        return self[key]


class CancellableThread(threading.Thread):
    """
    Cancellable worker thread

    Attributes:
        _cancel_event (threading.Event): Threading event to cancel execution
        _status_fmt (str):               Status message format string
        _status_args (Tuple[Any]):       Status message arguments
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes this thread
        """
        super().__init__(*args, **kwargs)
        self.daemon = True
        self._cancel_event = threading.Event()
        self._status_fmt = ''
        self._status_args = ()

    def cancel(self):
        """
        Cancels this thread only if it is still alive
        """
        if self.is_alive():
            self._cancel_event.set()

    def is_cancelled(self):
        """
        Getter for the cancellation state of this thread

        Returns:
            bool: True if thread not cancelled; False otherwise
        """
        return self._cancel_event.is_set()

    def get_status(self) -> str:
        """
        Getter for a message indicating the status of this thread

        Returns:
            str: Status message
        """
        status = ''
        try:
            status = self._status_fmt.format(*self._status_args)
        except:
            logging.warn('Failed to format status message')
        return status

    def set_status(self, fmt: str, *args):
        """
        Setter for a message indicating the status of this thread

        Parameters:
            fmt (str):         Status message format string
            args (Tuple[Any]): Status message arguments
        """
        self._status_fmt = fmt
        self._status_args = args


class Observable():
    """
    Base class for objects that can inform observers of changes

    Attributes:
        _observers (Set[weakref]): Weak references to observers
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes this observable object
        """
        self._observers = set()

    def cleanup(self):
        """
        Removes any garbage collected observers
        """
        self._observers = set(
            ref for ref in self._observers if ref() is not None)

    def subscribe(self, observer):
        """
        Adds an observer to be informed of changes

        Parameters:
            observer (types.Observer): Observer to add
        """
        ref = weakref.ref(observer)
        if ref not in self._observers:
            self._observers.add(ref)

    def unsubscribe(self, observer):
        """
        Removes an observer from being informed of changes

        Parameters:
            observer (types.Observer): Observer to remove
        """
        ref = weakref.ref(observer)
        if ref in self._observers:
            self._observers.remove(ref)

    def notify(self, *args, **kwargs):
        """
        Notifies subscribed observers of a change
        """
        self.cleanup()
        for ref in self._observers:
            ref().update(self, *args, **kwargs)


class Observer():
    """
    Interface for an object to be informed of changes in observable objects
    """

    def update(self, observable, *args, **kwargs):
        """
        Abstract method to update an observation

        Parameters:
            observable (types.Observable): Object being observed

        Raises: NotImplementedError
        """
        raise NotImplementedError


class Property(Observable):
    """
    Generic property that can be observed for changes in value

    Attributes:
        _value (Any): Property value
    """

    def __init__(self):
        """
        Initializes this property
        """
        super().__init__()
        self._value = None

    def __format__(self, format_spec: str) -> str:
        """
        Formats this object as a string

        Parameters:
            format_spec (str): Format specification

        Returns:
            str: This object formatted as a string
        """
        return format(self._value, format_spec)

    def __repr__(self) -> str:
        """
        Represents this object as a string

        Returns:
            str: This object represented as a string
        """
        return repr(self._value)

    def __str__(self) -> str:
        """
        Converts this object to a string

        Returns:
            str: This object converted to a string
        """
        return str(self._value)

    def get(self) -> Any:
        """
        Getter for the value of this property

        Returns:
            Any: Property value
        """
        return self._value

    def set(self, value: Any):
        """
        Setter for the value of this property

        Parameters:
            value (Any): Value to set
        """
        if value != self._value:
            self._value = value
            self.notify()


@enum.unique
class Continuity(enum.Enum):
    """
    Defines the enumeration of continuity types
    """
    POS = 1
    TAN = 2
    CURV = 3

    @classmethod
    def create_property(cls):
        """
        Creates a bpy.props.EnumProperty representation of this enumeration

        Returns:
            bpy.props.EnumProperty: Continuity as a Blender property
        """
        return bpy.props.EnumProperty(
            name = 'Continuity',
            description = (
                'Determines how inner vertices blend with surrounding faces ' +
                'to produce a smooth-as-possible mesh patch'
            ),
            default = cls.TAN.name,
            items = [(
                    cls.POS.name,
                    'Position',
                    'Change in vertex position is minimized.',
                    '',
                    cls.POS.value
                ), (
                    cls.TAN.name,
                    'Tangency',
                    'Change in vertex tangency is minimized.',
                    '',
                    cls.TAN.value
                ), (
                    cls.CURV.name,
                    'Curvature',
                    'Change in vertex curvature is minimized.',
                    '',
                    cls.CURV.value
                )
            ]
        )


@enum.unique
class VertexWeight(enum.Enum):
    """
    Defines the enumeration of vertex weight types
    """
    UNIFORM = 1
    BARYCENTRIC = 2
    VORONOI = 3

    def create_cache(self):
        """
        Factory method for creating a vertex weight cache

        Returns:
            Cache: Vertex weight cache
        """
        if self is VertexWeight.UNIFORM:
            return Cache(geometry.calc_uniform_vertex_weight)
        elif self is VertexWeight.BARYCENTRIC:
            return Cache(geometry.calc_barycentric_vertex_weight)
        elif self is VertexWeight.VORONOI:
            return Cache(geometry.calc_voronoi_vertex_weight)

    @classmethod
    def create_property(cls):
        """
        Creates a bpy.props.EnumProperty representation of this enumeration
        """
        return bpy.props.EnumProperty(
            name = 'Vertex Weight',
            description = 'Determines the influence of each vertex',
            default = cls.VORONOI.name,
            items = [(
                    cls.UNIFORM.name,
                    'Uniform', (
                        'Influence is the same for each vertex, taking the ' +
                        'shortest time to calculate but generally ' +
                        'providing poorest results'
                    ),
                    '',
                    cls.UNIFORM.value
                ), (
                    cls.BARYCENTRIC.name,
                    'Barycentric', (
                        'Influence is inversely proportional to the ' +
                        'Barycentric area of a vertex, taking a longer time ' +
                        'to calculate but generally providing better results.'
                    ),
                    '',
                    cls.BARYCENTRIC.value
                ), (
                    cls.VORONOI.name,
                    'Voronoi', (
                        'Influence is inversely proportional to the ' +
                        'Voronoi area of a vertex, taking the longest time ' +
                        'to calculate but generally providing best results.'
                    ),
                    '',
                    cls.VORONOI.value
                )
            ]
        )


@enum.unique
class LoopWeight(enum.Enum):
    """
    Defines the enumeration of loop weight types
    """
    UNIFORM = 1
    COTAN = 2
    MVC = 3

    def create_cache(self):
        """
        Factory method for creating a loop weight cache

        Returns:
            Cache: Loop weight cache
        """
        if self is LoopWeight.UNIFORM:
            return Cache(lambda l: 1)
        elif self is LoopWeight.MVC:
            return Cache(geometry.calc_mvc_loop_weight)
        elif self is LoopWeight.COTAN:
            return Cache(geometry.calc_cotangent_loop_weight)

    @classmethod
    def create_property(cls):
        """
        Creates a bpy.props.EnumProperty representation of this enumeration
        """
        return bpy.props.EnumProperty(
            name = 'Loop Weight',
            description = 'Determines the influence of each loop link',
            default = cls.COTAN.name,
            items = [(
                    cls.UNIFORM.name,
                    'Uniform', (
                        'Influence is the same for each loop link, taking ' +
                        'the shortest time to calculate but generally ' +
                        'providing poorest results'
                    ),
                    '',
                    cls.UNIFORM.value
                ), (
                    cls.COTAN.name,
                    'Cotangent', (
                        'Influence is proportional to the angles of loop ' +
                        'links, typically providing best results'
                    ),
                    '',
                    cls.COTAN.value
                ), (
                    cls.MVC.name,
                    'Mean Value Coordinates', (
                        'Influence is proportional to both the angles and ' +
                        'lengths of loop links, providing an alternative to ' +
                        'cotangent weights'
                    ),
                    '',
                    cls.MVC.value
                )
            ]
        )
