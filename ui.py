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

import bpy
from . import moduleutil
from . import operators


def display_popup(message: str, title: str = '', icon: str = ''):
    def draw(self, context):
        self.layout.label(text = message)
    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)


def draw_vertex_menu(menu: bpy.types.Menu, context: bpy.types.Context):
    layout = menu.layout
    layout.operator_context = 'INVOKE_DEFAULT'
    layout.separator()
    layout.operator(operators.MESH_OT_fair_vertices.bl_idname,
                    text = 'Fair Vertices')


def draw_sculpt_menu(menu: bpy.types.Menu, context: bpy.types.Context):
    layout = menu.layout
    layout.separator()
    layout.operator(operators.SCULPT_OT_fair_vertices.bl_idname,
                    text = 'Fair Vertices')


def draw_numpy_ui(context: bpy.types.Context, layout: bpy.types.UILayout):
    numpy_is_installed = moduleutil.is_installed('numpy')

    col = layout.column(align = True)

    if numpy_is_installed:
        col.label(text = 'NumPy is already installed', icon = 'INFO')
    else:
        col.label(text = 'NumPy is not installed', icon = 'ERROR')

    row = col.row()
    row.enabled = not numpy_is_installed

    op = row.operator(operators.SCRIPT_OT_install_module.bl_idname,
                      text = 'Install NumPy')
    op.name = 'numpy'
    op.reload_scripts = True


def draw_scipy_ui(context: bpy.types.Context, layout: bpy.types.UILayout):
    numpy_is_installed = moduleutil.is_installed('numpy')
    scipy_is_installed = moduleutil.is_installed('scipy')

    col = layout.column(align = True)

    if scipy_is_installed:
        col.label(text = 'SciPy is already installed', icon = 'INFO')
    else:
        col.label(text = 'SciPy is not installed', icon = 'ERROR')

    row = col.row()
    row.enabled = numpy_is_installed and not scipy_is_installed

    op = row.operator(operators.SCRIPT_OT_install_module.bl_idname,
                      text = 'Install SciPy')
    op.name = 'scipy'
    op.options = '--no-deps'
    op.reload_scripts = True

