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

import glob
import importlib
import logging
import os
import subprocess
import sys


def is_available(module):
    """
    Checks if given module is available for use

    Parameters:
        module (str): Module name

    Returns:
        True if available; False otherwise
    """
    return (module in locals() and
            type(locals()[module]) is importlib.types.ModuleType)


def is_installed(module):
    """
    Checks if given module is installed

    Parameters:
        module (str): Module name

    Returns:
        True if installed; False otherwise
    """
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


def install(module: str, options: str = None):
    """
    Installs given module with pip

    Parameters:
        module (str):  Module name
        options (str): Command line options for pip (e.g. '--no-deps -r')

    Returns:
        True if installation succeeded; False otherwise
    """
    # Determine the path to Blender's Python interpreter.
    executable = None
    try:
        for path in glob.glob('{}/bin/python*'.format(sys.exec_prefix)):
            if os.access(path, os.X_OK) and not path.lower().endswith('dll'):
                executable = path
                logging.debug(
                    'Blender\'s Python interpreter: {}'.format(executable))
                break
    except Exception as e:
        logging.error(e)
    if executable is None:
        logging.error('Unable to locate Blender\'s Python interpreter')

    # Install Python package manager.
    if is_installed('ensurepip'):
        subprocess.call([executable, '-m', 'ensurepip'])
    elif not is_installed('pip'):
        url = 'https://bootstrap.pypa.io/get-pip.py'
        filepath = '{}/get-pip.py'.format(os.getcwd())
        try:
            requests = importlib.import_module('requests')
            response = requests.get(url)
            with open(filepath, 'w') as f:
                f.write(response.text)
            subprocess.call([executable, filepath])
        except Exception as e:
            logging.error(e)
        finally:
            if os.path.isfile(filepath):
                os.remove(filepath)

    # Install given module.
    if not is_installed(module) and executable is not None:
        try:
            if options is None or options.strip() == '':
                subprocess.call([executable, '-m', 'pip', 'install', module])
            else:
                subprocess.call([executable, '-m', 'pip', 'install', options, module])
        except Exception as e:
            logging.error(e)

    return is_installed(module)
