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

import functools
import logging

import hideitem
from miro.frontends.widgets import widgetsapi

class ItemFilterHidden(widgetsapi.ExtensionItemFilter):
    """A filter to show only hidden items"""

    key = u'hidden'
    user_label = 'Hidden'

    def filter(self, item_info):
        if hideitem.hide_item_view.hide_item_model.is_hidden_item(item_info):
            logging.debug("Extension: Hidden Item: Found hidden item: " + item_info.name)
            return True
        return False
                
class ItemFilterNonHidden(widgetsapi.ExtensionItemFilter):
    """A filter to show all-hidden items"""

    key = u'non-hidden'
    user_label = 'Filtered'

    def filter(self, item_info):
        if not hideitem.hide_item_view.hide_item_model.is_hidden_item(item_info):
            return True
        return False

class HideItemView(object):
    """Encapsulates the user interface operations, callbacks"""
    hide_label = 'Hide Item'
    unhide_label = 'Unhide Item'

    def __init__(self, hide_item_model):
        self.hide_item_model = hide_item_model

    def get_item_list_filters(self, type_, id_):
        """Returns list of filters implemented by this extension"""
        return [ItemFilterHidden(), ItemFilterNonHidden()]

    def context_menu_action(self, selection):
        """Trigger the action on set of selected items"""
        [self.hide_item_model.toggle_hidden(item) for item in selection]

    def update_item_context_menu(self, selection, menu):
        """Registers actions and inserts extension specific entries into menu"""
        action = functools.partial(self.context_menu_action, selection)
        label = self.hide_label
        if self.hide_item_model.is_hidden_item(selection[0]):
            label = self.unhide_label
        if len(selection) > 1:
            label = label + 's'
        menu.insert(0, (label, action))

    def unload(self):
        if self.hide_item_model is not None:
            self.hide_item_model.unload()
