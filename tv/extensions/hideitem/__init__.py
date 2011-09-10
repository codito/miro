# Hide Item Extension for Miro
# Copyright (C) 2011 Arun Mahapatra
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

import logging
import core, view

hide_item_view = view.HideItemView(None)

def load(context):
    """Initialize the hidden item extension. Setup view and database."""
    global hide_item_view

    model = core.HideItemModel(context.storage_manager)
    hide_item_view.hide_item_model = model
    logging.info("Extension: Hide Item: Loaded");

def unload():
    """Unload the view, this will save and cleanup any storage objects."""
    if hide_item_view is not None:
        hide_item_view.unload()
    logging.info("Extension: Hide Item: Unloaded.")