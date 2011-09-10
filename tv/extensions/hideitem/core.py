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

class HideItemModel(object):
    """Encapsulates the concept of data storage etc. for Hide Item. Contains the Storage Manager
    instance for this extension. We follow these conventions:
        - Key for the StorageManager is the Item itself
        - A row for an Item exists only if the Item is hidden
    """

    def __init__(self, storage_manager):
        self.storage_manager = storage_manager

    def hide_item(self, item_info):
        """Adds an Item into the hidden items data store"""
        try:
            self.storage_manager.set_value(item_info.id, True)
            return True
        except Exception, e:
            logging.error("Extension: Hide Item: Failed to hide item." +
                          "Item: {0}, Error: {1}".format(item_info.id, e))
        return False

    def is_hidden_item(self, item_info):
        """Returns True if the Item is hidden"""
        try:
            if self.storage_manager.get_value(item_info.id):
                return True
        except KeyError:
            pass
        return False

    def toggle_hidden(self, item_info):
        """Toggles hidden property for an Item"""
        if self.is_hidden_item(item_info):
            return self.unhide_item(item_info)
        else:
            return self.hide_item(item_info)

    def unhide_item(self, item_info):
        """Removes an item from data store"""
        try:
            self.storage_manager.clear_value(item_info.id)
            return True
        except Exception, e:
            logging.error("Extension: Hide Item: Failed to unhide item." +
                          "Item: {0}, Error: {1}".format(item_info.id, e))
        return False

    def unload(self):
        pass
