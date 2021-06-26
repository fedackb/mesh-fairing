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

bl_info = {
    'name' : 'Mesh Fairing',
    'description' : 'Continuity based smoothing tool',
    'author' : 'Brett Fedack',
    'location': (
        'Sculpt mode: Sculpt menu, Edit mode: Vertex menu'
    ),
    'version' : (1, 0, 4),
    'blender' : (2, 90, 0),
    'category' : 'Mesh'
}

import logging

if 'bpy' not in locals():
    import bpy
    from . import operators
    from . import preferences
    from . import ui
else:
    import imp
    imp.reload(operators)
    imp.reload(preferences)
    imp.reload(ui)

classes = (operators.MESH_OT_fair_vertices,
           operators.MESH_OT_fair_vertices_internal,
           operators.SCULPT_OT_fair_vertices,
           operators.SCULPT_OT_fair_vertices_internal,
           operators.SCULPT_OT_push_undo,
           operators.SCRIPT_OT_install_module,
           preferences.MeshFairingPreferences)


def register():

    # Configure the logging service.
    logging_format = (
        '[%(levelname)s] ' +
        '(%(asctime)s) ' +
        '{0}.%(module)s.%(funcName)s():L%(lineno)s'.format(__package__) +
        ' - %(message)s'
    )
    logging.basicConfig(
        level = logging.DEBUG,
        format = logging_format,
        datefmt = '%Y/%m/%d %H:%M:%S'
    )

    # Initialize the linear algebra solver.
    linalg.init()

    # Register this Blender addon.
    for cls in classes:
        bpy.utils.register_class(cls)

    # Add mesh fairing operators to existing menus.
    bpy.types.VIEW3D_MT_edit_mesh_vertices.append(ui.draw_vertex_menu)
    bpy.types.VIEW3D_MT_sculpt.append(ui.draw_sculpt_menu)


def unregister():

    # Remove mesh fairing operators from existing menus.
    bpy.types.VIEW3D_MT_edit_mesh_vertices.remove(ui.draw_vertex_menu)
    bpy.types.VIEW3D_MT_sculpt.remove(ui.draw_sculpt_menu)

    # Unregister this Blender addon.
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
