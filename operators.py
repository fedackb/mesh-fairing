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
import logging
import time
from . import geometry
from . import moduleutil
from . import types
from . import ui


class MESH_OT_fair_vertices(bpy.types.Operator):
    bl_idname = 'mesh.fair_vertices'
    bl_label = 'Fair Vertices'
    bl_description = (
        'Displaces selected vertices to produce a smooth-as-possible mesh '
        'patch with respect to the specified continuity constraint')
    bl_options = {'REGISTER'}

    continuity: types.Continuity.create_property()
    triangulate: bpy.props.BoolProperty(
        name = 'Triangulate',
        description = (
            'Triangulates affected region to produce higher quality results'),
        default = False)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return MESH_OT_fair_vertices_internal.poll(context)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        bpy.ops.mesh.fair_vertices_internal('INVOKE_DEFAULT', True,
                                            triangulate = self.triangulate,
                                            continuity = self.continuity)
        return {'FINISHED'}

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.prop(self, 'continuity')
        layout.prop(self, 'triangulate')


class MESH_OT_fair_vertices_internal(bpy.types.Operator):
    bl_idname = 'mesh.fair_vertices_internal'
    bl_label = 'Fair Vertices (Internal)'
    bl_description = (
        'Displaces selected vertices to produce a smooth-as-possible mesh ' +
        'patch with respect to the specified continuity constraint')
    bl_options = {'INTERNAL', 'UNDO'}

    continuity: types.Continuity.create_property()
    triangulate: bpy.props.BoolProperty(
        name = 'Triangulate',
        description = (
            'Triangulates affected region to produce higher quality results'),
        default = False)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        edit_object = context.edit_object
        return (edit_object and
                edit_object.type == 'MESH' and
                edit_object.mode == 'EDIT' and
                edit_object.data.total_vert_sel > 0 and
                context.space_data.type == 'VIEW_3D')

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):

        # Enter modal state of operation.
        wm = context.window_manager
        wm.modal_handler_add(self)
        self._modal_handler = self.modal_start
        self._timer = wm.event_timer_add(0.1, window = context.window)
        return {'RUNNING_MODAL'}

    def modal(self, context: bpy.types.Context, event: bpy.types.Event):
        return self._modal_handler(context, event)

    def modal_start(self, context: bpy.types.Context, event: bpy.types.Event):
        mesh = context.edit_object.data

        # Perform mesh fairing in a separate, cancellable thread.
        self._worker = MESH_OT_fair_vertices_internal.WorkerThread(
            mesh, types.Continuity[self.continuity], self.triangulate)
        self._worker.start()

        self._modal_handler = self.modal_monitor
        return {'RUNNING_MODAL'}

    def modal_monitor(self, context: bpy.types.Context, event: bpy.types.Event):
        if self._worker.is_alive() and not self._worker.is_cancelled():

            # Display the status of mesh fairing.
            ellipsis = '.' * (int(self._timer.time_duration * 4) % 4)
            status = self._worker.get_status()
            context.area.header_text_set(
                    text = '{}{:<3} ESC: Cancel'.format(status, ellipsis))

            # Cancel the mesh fairing thread.
            if event.type == 'ESC' and event.value == 'PRESS':
                self._worker.cancel()
        else:
            self._modal_handler = self.modal_finish

        return {'RUNNING_MODAL'}

    def modal_finish(self, context: bpy.types.Context, event: bpy.types.Event):
        context.area.header_text_set(text = None)
        context.window_manager.event_timer_remove(self._timer)
        return {'CANCELLED'} if self._worker.is_cancelled() else {'FINISHED'}

    class WorkerThread(types.CancellableThread):
        """
        Inner worker class for performing mesh fairing in a separate thread

        Attributes:
            _mesh (bpy.types.Mesh):         Mesh on which to operate
            _continuity (types.Continuity): Continuity constraint for fairing
            _triangulate (bool):            Flag controlling mesh triangulation
        """

        def __init__(self,
                     mesh: bpy.types.Mesh,
                     continuity: types.Continuity,
                     triangulate: bool):
            """
            Initializes this worker thread

            Parameters:
                mesh (bpy.types.Mesh):         Mesh on which to operate
                continuity (types.Continuity): Continuity constraint for fairing
                triangulate (bool):            Flag controlling mesh triangulation
            """
            super().__init__()
            self._mesh = mesh
            self._continuity = continuity
            self._triangulate = triangulate

        def run(self):
            """
            Performs mesh fairing
            """
            fairing_status = types.Property()

            # Initialize BMesh.
            self.set_status('Initializing BMesh')
            bm = bmesh.from_edit_mesh(self._mesh)

            # Determine which vertices are affected.
            if not self.is_cancelled():
                self.set_status('Determining which vertices are affected')
                affected_verts = [v for v in bm.verts if v.select]

            # Triangulate region to produce higher quality results.
            if not self.is_cancelled() and self._triangulate:
                self.set_status('Triangulating involved faces')

                # Determine which faces are involved, accounting for continuity.
                involved_faces = {f for v in affected_verts for f in v.link_faces}
                involved_faces.update(
                    geometry.expand_faces(
                        geometry.get_boundary_faces(involved_faces),
                        self._continuity.value - 1))

                # Triangulate involved faces.
                bmesh.ops.triangulate(bm, faces = list(involved_faces))

                # Flush the selection.
                bm.select_mode = {'VERT'}
                bm.select_flush_mode()

            # Pre-fair affected vertices for consistent results.
            if not self.is_cancelled():
                self.set_status('[Pre-Fairing] {}', fairing_status)
                if not geometry.fair(
                    affected_verts, types.Continuity.POS.value,
                    types.VertexWeight.UNIFORM.create_cache(),
                    types.LoopWeight.UNIFORM.create_cache(),
                    self._cancel_event, fairing_status):

                    # Cancel this thread if pre-fairing failed.
                    logging.warn('Mesh pre-fairing failed')
                    self.cancel()

            # Fair affected vertices.
            if not self.is_cancelled():
                self.set_status('[Fairing] {}', fairing_status)
                if not geometry.fair(
                    affected_verts, self._continuity.value,
                    types.VertexWeight.VORONOI.create_cache(),
                    types.LoopWeight.COTAN.create_cache(),
                    self._cancel_event, fairing_status):

                    # Cancel this thread if fairing failed.
                    logging.warn('Mesh fairing failed')
                    self.cancel()

            # Update the mesh.
            self.set_status('Updating the mesh')
            bm.normal_update()
            bmesh.update_edit_mesh(self._mesh)


class SCULPT_OT_fair_vertices(bpy.types.Operator):
    bl_idname = 'sculpt.fair_vertices'
    bl_label = 'Fair Vertices'
    bl_description = (
        'Displaces masked/unmasked vertices to produce a smooth-as-possible ' +
        'mesh patch with respect to the specified continuity constraint')
    bl_options = {'REGISTER'}

    continuity: types.Continuity.create_property()
    invert_mask: bpy.props.BoolProperty(
        name = 'Invert Mask',
        description = (
            'If this option is enabled, mesh fairing is applied to masked ' +
            'vertices; otherwise, only unmasked vertices are affected.'),
        default = True)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return SCULPT_OT_fair_vertices_internal.poll(context)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        bpy.ops.sculpt.fair_vertices_internal('INVOKE_DEFAULT', True,
                                              continuity = self.continuity,
                                              invert_mask = self.invert_mask)
        return {'FINISHED'}

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.prop(self, 'continuity')
        layout.prop(self, 'invert_mask')


class SCULPT_OT_fair_vertices_internal(bpy.types.Operator):
    bl_idname = 'sculpt.fair_vertices_internal'
    bl_label = 'Fair Vertices (Internal)'
    bl_description = (
        'Displaces masked/unmasked vertices to produce a smooth-as-possible ' +
        'mesh patch with respect to the specified continuity constraint')
    bl_options = {'INTERNAL', 'UNDO'}

    continuity: types.Continuity.create_property()
    invert_mask: bpy.props.BoolProperty(
        name = 'Invert Mask',
        description = (
            'If this option is enabled, mesh fairing is applied to masked ' +
            'vertices; otherwise, only unmasked vertices are affected.'),
        default = True)

    @classmethod
    def poll(cls, context):
        sculpt_object = context.sculpt_object
        return (sculpt_object and
                sculpt_object.type == 'MESH' and
                sculpt_object.mode == 'SCULPT' and
                len(sculpt_object.data.vertices) > 0 and
                context.space_data.type == 'VIEW_3D')

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):

        # Disallow mesh fairing if dynamic topology is enabled.
        if context.sculpt_object.use_dynamic_topology_sculpting:
            ui.display_popup(
                message = 'Mesh fairing is not supported in dyntopo.',
                title = 'Report: Error',
                icon = 'ERROR')
            return {'CANCELLED'}

        bpy.ops.sculpt.push_undo()

        # Enter modal state of operation.
        wm = context.window_manager
        wm.modal_handler_add(self)
        self._modal_handler = self.modal_start
        self._timer = wm.event_timer_add(0.1, window = context.window)
        return {'RUNNING_MODAL'}

    def modal(self, context: bpy.types.Context, event: bpy.types.Event):
        return self._modal_handler(context, event)

    def modal_start(self, context: bpy.types.Context, event: bpy.types.Event):
        sculpt_object = context.sculpt_object

        # Perform mesh fairing in a separate, cancellable thread.
        self._worker = SCULPT_OT_fair_vertices_internal.WorkerThread(
            sculpt_object,
            types.Continuity[self.continuity],
            self.invert_mask)
        self._worker.start()

        self._modal_handler = self.modal_monitor
        return {'RUNNING_MODAL'}

    def modal_monitor(self, context: bpy.types.Context, event: bpy.types.Event):
        if self._worker.is_alive() and not self._worker.is_cancelled():

            # Display the status of mesh fairing.
            ellipsis = '.' * (int(self._timer.time_duration * 4) % 4)
            status = self._worker.get_status()
            context.area.header_text_set(
                text = '{}{:<3} ESC: Cancel'.format(status, ellipsis))

            # Cancel the mesh fairing thread.
            if event.type == 'ESC' and event.value == 'PRESS':
                self._worker.cancel()
        else:
            self._modal_handler = self.modal_finish

        return {'RUNNING_MODAL'}

    def modal_finish(self, context: bpy.types.Context, event: bpy.types.Event):
        context.area.header_text_set(text = None)
        context.window_manager.event_timer_remove(self._timer)
        return {'CANCELLED'} if self._worker.is_cancelled() else {'FINISHED'}

    class WorkerThread(types.CancellableThread):
        """
        Inner worker class for performing mesh fairing in a separate thread

        Attributes:
            _sculpt_object (bpy.types.Object): Object on which to operate
            _continuity (types.Continuity):    Continuity constraint for fairing
            _invert_mask (bool):               Flag controlling mask inversion
        """

        def __init__(self,
                     sculpt_object: bpy.types.Object,
                     continuity: types.Continuity,
                     invert_mask: bool):
            """
            Initializes this worker thread

            Parameters:
                sculpt_object (bpy.types.Object): Object on which to operate
                continuity (types.Continuity):    Continuity constraint for fairing
                invert_mask (bool):               Flag controlling mask inversion
            """
            super().__init__()
            self._sculpt_object = sculpt_object
            self._continuity = continuity
            self._invert_mask = invert_mask

        def run(self):
            """
            Performs mesh fairing
            """
            fairing_status = types.Property()

            # Initialize BMesh.
            self.set_status('Initializing BMesh')
            with types.BMeshGuard() as bm:
                bm.from_mesh(self._sculpt_object.data, use_shape_key = True,
                             shape_key_index = self._sculpt_object.active_shape_key_index)
                mask_layer = bm.verts.layers.paint_mask.active

                # Determine which vertices are affected.
                affected_verts = list()
                if not self.is_cancelled():
                    self.set_status('Determining which vertices are affected')
                    if mask_layer is not None:
                        affected_verts = [
                            v for v in bm.verts
                            if ((self._invert_mask and v[mask_layer] >= 0.5) or
                                (not self._invert_mask and v[mask_layer] <= 0.5))
                        ]

                # Cancel this thread if there is no work to be done, which
                # effectively avoids an undo event for a null operation.
                if not self.is_cancelled() and len(affected_verts) == 0:
                    self.cancel()

                # Triangulate region to produce higher quality results.
                if not self.is_cancelled():
                    self.set_status('Temporarily triangulating involved faces')

                    # Determine which faces are involved, accounting for continuity.
                    involved_faces = {f for v in affected_verts for f in v.link_faces}
                    involved_faces.update(
                        geometry.expand_faces(
                            geometry.get_boundary_faces(involved_faces),
                            self._continuity.value - 1))

                    # Triangulate involved faces.
                    bmesh.ops.triangulate(bm, faces = list(involved_faces))

                # Pre-fair affected vertices for consistent results.
                if not self.is_cancelled():
                    self.set_status('[Pre-Fairing] {}', fairing_status)
                    if not geometry.fair(
                        affected_verts, types.Continuity.POS.value,
                        types.VertexWeight.UNIFORM.create_cache(),
                        types.LoopWeight.UNIFORM.create_cache(),
                        self._cancel_event, fairing_status):

                        # Cancel this thread if pre-fairing failed.
                        logging.warn('Mesh pre-fairing failed')
                        self.cancel()

                # Fair affected vertices.
                if not self.is_cancelled():
                    self.set_status('[Fairing] {}', fairing_status)
                    if not geometry.fair(
                        affected_verts, self._continuity.value,
                        types.VertexWeight.VORONOI.create_cache(),
                        types.LoopWeight.COTAN.create_cache(),
                        self._cancel_event, fairing_status):

                        # Cancel this thread if fairing failed.
                        logging.warn('Mesh fairing failed')
                        self.cancel()

                # Update the mesh.
                if not self.is_cancelled():
                    self.set_status('Updating the mesh')
                    vertices = self._sculpt_object.data.vertices
                    for v in affected_verts:
                        vertices[v.index].co = v.co


class SCULPT_OT_push_undo(bpy.types.Operator):
    bl_idname = 'sculpt.push_undo'
    bl_label = 'Push Undo'
    bl_description = 'Pushes an undo step in Sculpt mode'
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context):
        sculpt_object = context.sculpt_object
        return (sculpt_object and
                sculpt_object.type == 'MESH' and
                sculpt_object.mode == 'SCULPT' and
                len(sculpt_object.data.vertices) > 0 and
                context.space_data.type == 'VIEW_3D')

    def execute(self, context: bpy.types.Context):
        tool_settings = context.tool_settings

        # Temporarily change the sculpt tool to one that displaces geometry.
        tool_name = context.workspace.tools.from_space_view3d_mode(context.mode).idname
        bpy.ops.wm.tool_set_by_id(name="builtin_brush.Draw")

        # Temporarily change the sculpt tool settings to effect all vertices.
        use_unified_size = tool_settings.unified_paint_settings.use_unified_size
        tool_settings.unified_paint_settings.use_unified_size = False
        brush_size = tool_settings.sculpt.brush.size
        tool_settings.sculpt.brush.size = 0x7fffffff

        # Apply a stroke that has no effect other than pushing an undo step.
        stroke = [{
            "name": "Null Stroke",
            "location": (0, 0, 0),
            "mouse" : (0, 0),
            "pressure": 0,
            "size": 0,
            "pen_flip" : False,
            "time": 0,
            "is_start": True
        }]
        bpy.ops.sculpt.brush_stroke(stroke = stroke)

        # Restore the initial sculpt tool and settings.
        bpy.ops.wm.tool_set_by_id(name=tool_name)
        tool_settings.unified_paint_settings.use_unified_size = use_unified_size
        tool_settings.sculpt.brush.size = brush_size

        return {'FINISHED'}


class SCRIPT_OT_install_module(bpy.types.Operator):
    bl_idname = 'script.install_module'
    bl_label = 'Install Python Module'
    bl_description = 'Installs given Python module with pip'
    bl_options = {'INTERNAL'}

    name: bpy.props.StringProperty(
        name = 'Module Name',
        description = 'Installs the given module')

    options: bpy.props.StringProperty(
        name = 'Command line options',
        description = 'Command line options for pip (e.g. "--no-deps -r")',
        default = '')

    reload_scripts: bpy.props.BoolProperty(
        name = 'Reload Scripts',
        description = 'Reloads Blender scripts upon successful installation',
        default = True)

    def execute(self, context):
        if len(self.name) > 0 and moduleutil.install(self.name, self.options):
            self.report({'INFO'},
                        'Installed Python module: {}'.format(self.name))
            if self.reload_scripts:
                bpy.ops.script.reload()
        else:
            self.report({'ERROR'},
                        'Unable to install Python module: {}'.format(self.name))
        return {'FINISHED'}
