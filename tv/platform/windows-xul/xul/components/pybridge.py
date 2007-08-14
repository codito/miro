from gettext import gettext as _
from xpcom import components
import ctypes
import os
import shutil
import sys
import traceback
import _winreg

try:
    import platformutils
    platformutils.initializeLocale()
    platformutils.setupLogging()
    import gtcache
    gtcache.init()
    import app
    import autoupdate
    import eventloop
    import config
    import dialogs
    import folder
    import playlist
    import prefs
    import platformcfg
    import singleclick
    import frontend
    import util
    import menubar
    import feed
    import database
    from frontend_implementation import HTMLDisplay
    from frontend_implementation.UIBackendDelegate import UIBackendDelegate
    from eventloop import asUrgent, asIdle
    from platformutils import getLongPathName
    import searchengines
    import views
    import moviedata
    import migrateappname
    import keyboard
    moviedata.RUNNING_MAX = 1
except:
    errorOnImport = True
    # get a fallback error message in case we can't import util either
    import traceback
    importErrorMessage = (_("Error importing modules:\n%s") %
        traceback.format_exc())
    try:
        import util
        importErrorMessage = util.failed(_("Starting up"),
                withExn=True)
    except:
        raise
    # we need to make a fake asUrgent since we probably couldn't import
    # eventloop.
    def asUrgent(func):
        return func
    def asIdle(func):
        return func
else:
    errorOnImport = False

# See http://www.xulplanet.com/tutorials/xultu/keyshort.html
XUL_MOD_STRINGS = {menubar.CTRL : 'control',
                   menubar.ALT:   'alt',
                   menubar.SHIFT: 'shift'}
XUL_KEY_STRINGS ={ menubar.RIGHT_ARROW: 'VK_RIGHT',
                   menubar.LEFT_ARROW:  'VK_LEFT',
                   menubar.UP_ARROW:    'VK_UP',
                   menubar.DOWN_ARROW:  'VK_DOWN',
                   menubar.SPACE : 'VK_SPACE',
                   menubar.ENTER: 'VK_ENTER',
                   menubar.DELETE: 'VK_DELETE',
                   menubar.BKSPACE: 'VK_BACK',
                   menubar.F1: 'VK_F1',
                   menubar.F2: 'VK_F2',
                   menubar.F3: 'VK_F3',
                   menubar.F4: 'VK_F4',
                   menubar.F5: 'VK_F5',
                   menubar.F6: 'VK_F6',
                   menubar.F7: 'VK_F7',
                   menubar.F8: 'VK_F8',
                   menubar.F9: 'VK_F9',
                   menubar.F10: 'VK_F10',
                   menubar.F11: 'VK_F11',
                   menubar.F12: 'VK_F12'}

# Extent the ShortCut class to include a XULString() function
def XULKey(shortcut):
    if isinstance(shortcut.key, int):
        return XUL_KEY_STRINGS[shortcut.key]
    else:
        return shortcut.key.upper()

def XULModifier(shortcut):
    if shortcut.key is None:
        return None
    output = []
    for modifier in shortcut.modifiers:
        output.append(XUL_MOD_STRINGS[modifier])
    return ' '.join(output)

def XULDisplayedShortcut(item):
    """Return the index of the default shortcut.  Normally items only have 1
    shortcut, which is an easy case.  If items have multiple shortcuts,
    normally we display the last one in the menus, however there are some
    special cases.

    Shortcut indicies are 1-based
    """

    if item.action.startswith("Remove"):
        return 1
    return len(item.shortcuts)

nsIEventQueueService = components.interfaces.nsIEventQueueService
nsIProperties = components.interfaces.nsIProperties
nsIFile = components.interfaces.nsIFile
nsIProxyObjectManager = components.interfaces.nsIProxyObjectManager
pcfIDTVPyBridge = components.interfaces.pcfIDTVPyBridge
pcfIDTVJSBridge = components.interfaces.pcfIDTVJSBridge
pcfIDTVVLCRenderer = components.interfaces.pcfIDTVVLCRenderer

def makeComp(clsid, iid):
    """Helper function to get an XPCOM component"""
    return components.classes[clsid].createInstance(iid)

def makeService(clsid, iid):
    """Helper function to get an XPCOM service"""
    return components.classes[clsid].getService(iid)

def createProxyObjects():
    """Creates the jsbridge and vlcrenderer xpcom components, then wraps them in
    a proxy object, then stores them in the frontend module.  By making them
    proxy objects, we ensure that the calls to them get made in the xul event
    loop.
    """

    proxyManager = makeComp("@mozilla.org/xpcomproxy;1",
            nsIProxyObjectManager)
    eventQueueService = makeService("@mozilla.org/event-queue-service;1",
            nsIEventQueueService)
    xulEventQueue = eventQueueService.getSpecialEventQueue(
            nsIEventQueueService.UI_THREAD_EVENT_QUEUE)

    jsBridge = makeService("@participatoryculture.org/dtv/jsbridge;1",
            pcfIDTVJSBridge)
    frontend.jsBridge = proxyManager.getProxyForObject(xulEventQueue,
            pcfIDTVJSBridge, jsBridge, nsIProxyObjectManager.INVOKE_ASYNC |
            nsIProxyObjectManager.FORCE_PROXY_CREATION)

    vlcRenderer = makeService("@participatoryculture.org/dtv/vlc-renderer;1",
            pcfIDTVVLCRenderer)
    frontend.vlcRenderer = proxyManager.getProxyForObject(xulEventQueue,
            pcfIDTVVLCRenderer, vlcRenderer, 
            nsIProxyObjectManager.INVOKE_SYNC |
            nsIProxyObjectManager.FORCE_PROXY_CREATION)

def initializeProxyObjects(window):
    frontend.vlcRenderer.init(window)
    frontend.jsBridge.init(window)

def initializeHTTPProxy():
    klass = components.classes["@mozilla.org/preferences-service;1"]
    xulprefs = klass.getService(components.interfaces.nsIPrefService)
    branch = xulprefs.getBranch("network.proxy.")
    if config.get(prefs.HTTP_PROXY_ACTIVE):                     
        branch.setIntPref("type",1)
        branch.setCharPref("http", config.get(prefs.HTTP_PROXY_HOST))
        branch.setCharPref("ssl", config.get(prefs.HTTP_PROXY_HOST))
        branch.setIntPref("http_port", config.get(prefs.HTTP_PROXY_PORT))
        branch.setIntPref("ssl_port", config.get(prefs.HTTP_PROXY_PORT))
        branch.setBoolPref("share_proxy_settings", True)
    else:
        branch.setIntPref("type",0)

def registerHttpObserver():
    observer = makeComp("@participatoryculture.org/dtv/httprequestobserver;1",
        components.interfaces.nsIObserver)
    observer_service = makeService("@mozilla.org/observer-service;1",
            components.interfaces.nsIObserverService)
    observer_service.addObserver(observer, "http-on-modify-request", False);
        
def getArgumentList(commandLine):
    """Convert a nsICommandLine component to a list of arguments to pass
    to the singleclick module."""

    args = [commandLine.getArgument(i) for i in range(commandLine.length)]
    # filter out the application.ini that gets included
    if len(args) > 0 and args[0].lower().endswith('application.ini'):
        args = args[1:]
    return [getLongPathName(path) for path in args]

# Copied from resources.py; if you change this function here, change it
# there too.
def appRoot():
    klass = components.classes["@mozilla.org/file/directory_service;1"]
    service = klass.getService(nsIProperties)
    file = service.get("XCurProcD", nsIFile)
    return file.path

# Functions to convert menu information into XUL form
def XULifyLabel(label):
    return label.replace(u'_',u'')
def XULAccelFromLabel(label):
    parts = label.split(u'_')
    if len(parts) > 1:
        return parts[1][0]


def prefsChangeCallback(mapped, id):
    if isinstance (mapped.actualFeed, feed.DirectoryWatchFeedImpl):
        frontend.jsBridge.directoryWatchAdded (str(id), mapped.dir, mapped.visible);

def prefsRemoveCallback(mapped, id):
    if isinstance (mapped.actualFeed, feed.DirectoryWatchFeedImpl):
        frontend.jsBridge.directoryWatchRemoved (str(id));


@asIdle
def startPrefs():
    for f in views.feeds:
        if isinstance (f.actualFeed, feed.DirectoryWatchFeedImpl):
            frontend.jsBridge.directoryWatchAdded (str(f.getID()), f.dir, f.visible)
    views.feeds.addChangeCallback(prefsChangeCallback)
    views.feeds.addAddCallback(prefsChangeCallback)
    views.feeds.addRemoveCallback(prefsRemoveCallback)

@asIdle
def endPrefs():
    views.feeds.removeChangeCallback(prefsChangeCallback)
    views.feeds.removeAddCallback(prefsChangeCallback)
    views.feeds.removeRemoveCallback(prefsRemoveCallback)


class PyBridge:
    _com_interfaces_ = [pcfIDTVPyBridge]
    _reg_clsid_ = "{F87D30FF-C117-401e-9194-DF3877C926D4}"
    _reg_contractid_ = "@participatoryculture.org/dtv/pybridge;1"
    _reg_desc_ = "Bridge into DTV Python core"

    def __init__(self):
        migrateappname.migrateSupport('Democracy Player', 'Miro')
        self.started = False
        self.cursorDisplayCount = 0
        if not errorOnImport:
            self.delegate = UIBackendDelegate()

    def getStartupError(self):
        if not errorOnImport:
            return ""
        else:
            return importErrorMessage

    def onStartup(self, window):
        if self.started:
            util.failed(_("Loading window"), 
                details=_("onStartup called twice"))
            return
        else:
            self.started = True

        initializeProxyObjects(window)
        registerHttpObserver()
        app.main()
        initializeHTTPProxy()
        views.waitForInit()
        self.initializeSearchEngines()
        
        migrateappname.migrateVideos('Democracy', 'Miro')

    @asUrgent
    def initializeViews(self):
        views.initialize()

    def onShutdown(self):
        frontend.vlcRenderer.stop()
        app.controller.onShutdown()

    def deleteVLCCache(self):
        appDataPath = platformcfg.getSpecialFolder("AppData")
        if appDataPath:
            vlcCacheDir = os.path.join(appDataPath, "PCF-VLC")
            shutil.rmtree(vlcCacheDir, ignore_errors=True)

    def shortenDirectoryName(self, path):
        """Shorten a directory name by recognizing well-known nicknames, like
        "Desktop", and "My Documents"
        """

        tries = [ "My Music", "My Pictures", "My Videos", "My Documents",
            "Desktop", 
        ]

        for name in tries:
            virtualPath = platformcfg.getSpecialFolder(name)
            if virtualPath is None:
                continue
            if path == virtualPath:
                return name
            elif path.startswith(virtualPath):
                relativePath = path[len(virtualPath):]
                if relativePath.startswith("\\"):
                    return name + relativePath
                else:
                    return "%s\\%s" % (name, relativePath)
        return path


    # Preference setters/getters.
    #
    # NOTE: these are not in the mail event loop, so we have to be careful in
    # accessing data.  config.get and config.set are threadsafe though.
    #
    def getRunAtStartup(self):
        return config.get(prefs.RUN_AT_STARTUP)
    def setRunAtStartup(self, value):
        self.delegate.setRunAtStartup(value)
        config.set(prefs.RUN_AT_STARTUP, value)
    def getCheckEvery(self):
        return config.get(prefs.CHECK_CHANNELS_EVERY_X_MN)
    def setCheckEvery(self, value):
        return config.set(prefs.CHECK_CHANNELS_EVERY_X_MN, value)
    def getMoviesDirectory(self):
        return config.get(prefs.MOVIES_DIRECTORY)
    def changeMoviesDirectory(self, path, migrate):
        app.changeMoviesDirectory(path, migrate)
    def getLimitUpstream(self):
        return config.get(prefs.LIMIT_UPSTREAM)
    def setLimitUpstream(self, value):
        config.set(prefs.LIMIT_UPSTREAM, value)
    def getLimitUpstreamAmount(self):
        return config.get(prefs.UPSTREAM_LIMIT_IN_KBS)
    def setLimitUpstreamAmount(self, value):
        return config.set(prefs.UPSTREAM_LIMIT_IN_KBS, value)
    def getMaxManual(self):
        return config.get(prefs.MAX_MANUAL_DOWNLOADS)
    def setMaxManual(self, value):
        return config.set(prefs.MAX_MANUAL_DOWNLOADS, value)
    def startPrefs(self):
        startPrefs()
    def updatePrefs(self):
        endPrefs()
    def getPreserveDiskSpace(self):
        return config.get(prefs.PRESERVE_DISK_SPACE)
    def setPreserveDiskSpace(self, value):
        config.set(prefs.PRESERVE_DISK_SPACE, value)
    def getPreserveDiskSpaceAmount(self):
        return config.get(prefs.PRESERVE_X_GB_FREE)
    def setPreserveDiskSpaceAmount(self, value):
        return config.set(prefs.PRESERVE_X_GB_FREE, value)
    def getExpireAfter(self):
        return config.get(prefs.EXPIRE_AFTER_X_DAYS)
    def setExpireAfter(self, value):
        return config.set(prefs.EXPIRE_AFTER_X_DAYS, value)
    def getSinglePlayMode(self):
        return config.get(prefs.SINGLE_VIDEO_PLAYBACK_MODE)
    def setSinglePlayMode(self, value):
        return config.set(prefs.SINGLE_VIDEO_PLAYBACK_MODE, value)
    def getResumeVideosMode(self):
        return config.get(prefs.RESUME_VIDEOS_MODE)
    def setResumeVideosMode(self, value):
        return config.set(prefs.RESUME_VIDEOS_MODE, value)
    def getBTMinPort(self):
        return config.get(prefs.BT_MIN_PORT)
    def setBTMinPort(self, value):
        return config.set(prefs.BT_MIN_PORT, value)
    def getBTMaxPort(self):
        return config.get(prefs.BT_MAX_PORT)
    def setBTMaxPort(self, value):
        return config.set(prefs.BT_MAX_PORT, value)
    def getStartupTasksDone(self):
        return config.get(prefs.STARTUP_TASKS_DONE)
    def setStartupTasksDone(self, value):
        return config.set(prefs.STARTUP_TASKS_DONE, value)

    @asUrgent
    def handleCommandLine(self, commandLine):
        # Doesn't matter if this executes before the call to
        # parseCommandLineArgs in app.py. -clahey
        singleclick.handleCommandLineArgs(getArgumentList(commandLine))

    def pageLoadFinished(self, area, url):
        eventloop.addUrgentCall(HTMLDisplay.runPageFinishCallback, 
                "%s finish callback" % area, args=(area, url))

    @asUrgent
    def openFile(self, path):
        singleclick.openFile(getLongPathName(path))

    @asUrgent
    def setVolume(self, volume):
        volume = float(volume)
        config.set(prefs.VOLUME_LEVEL, volume)
        app.controller.videoDisplay.setVolume(volume, moveSlider=False)

    @asUrgent
    def quit(self):
        app.controller.quit()

    @asUrgent
    def removeCurrentChannel(self):
        app.controller.removeCurrentFeed()

    @asUrgent
    def updateCurrentChannel(self):
        app.controller.updateCurrentFeed()

    @asUrgent
    def updateChannels(self):
        app.controller.updateAllFeeds()

    @asUrgent
    def showHelp(self):
        self.delegate.openExternalURL(config.get(prefs.HELP_URL))

    @asUrgent
    def reportBug(self):
        self.delegate.openExternalURL(config.get(prefs.BUG_REPORT_URL))

    @asUrgent
    def copyChannelLink(self):
        app.controller.copyCurrentFeedURL()

    @asUrgent
    def handleContextMenu(self, index):
        self.delegate.handleContextMenu(index)

    @asUrgent
    def handleSimpleDialog(self, id, buttonIndex):
        self.delegate.handleDialog(id, buttonIndex)

    @asUrgent
    def handleHTTPAuthDialog(self, id, buttonIndex, username, password):
        self.delegate.handleDialog(id, buttonIndex, username=username,
                password=password)

    @asUrgent
    def handleTextEntryDialog(self, id, buttonIndex, text):
        self.delegate.handleDialog(id, buttonIndex, value=text)

    @asUrgent
    def handleSearchChannelDialog(self, id, buttonIndex, term, style, loc):
        self.delegate.handleDialog(id, buttonIndex, term=term, style=style, loc=loc)

    @asUrgent
    def addChannel(self, url):
        app.controller.addAndSelectFeed(url)

    @asUrgent
    def openURL(self, url):
        self.delegate.openExternalURL(url)

    @asUrgent
    def playPause(self):
        app.controller.playbackController.playPause()

    @asUrgent
    def pause(self):
        app.controller.playbackController.pause()

    @asUrgent
    def stop(self):
        app.controller.playbackController.stop()

    @asUrgent
    def skip(self, step):
        app.controller.playbackController.skip(step)

    @asUrgent
    def skipPrevious(self):
        app.controller.playbackController.skip(-1, allowMovieReset=False)

    @asUrgent
    def onMovieFinished(self):
        app.controller.playbackController.onMovieFinished()

    @asUrgent
    def loadURLInBrowser(self, browserId, url):
        try:
            display = app.controller.frame.selectedDisplays[browserId]
        except KeyError:
            print "No HTMLDisplay for %s in loadURLInBrowser: "% browserId
        else:
            display.onURLLoad(url)

    @asUrgent
    def performSearch(self, engine, query):
        app.controller.performSearch(engine, query)

    # Returns a list of search engine titles and names
    # Should we just keep a map of engines to names?
    def getSearchEngineNames(self):
        out = []
        for engine in views.searchEngines:
            out.append(engine.name)
        return out
    def getSearchEngineTitles(self):
        out = []
        for engine in views.searchEngines:
            out.append(engine.title)
        return out

    def showCursor(self, display):
        # ShowCursor has an amazing API.  From Microsoft:
        #
        # This function sets an internal display counter that determines
        # whether the cursor should be displayed. The cursor is displayed
        # only if the display count is greater than or equal to 0. If a
        # mouse is installed, the initial display count is 0.  If no mouse
        # is installed, the display count is -1
        #
        # How do we get the initial display count?  There's no method.  We
        # assume it's 0 and the mouse is plugged in.
        if ((display and self.cursorDisplayCount >= 0) or
                (not display and self.cursorDisplayCount < 0)):
            return
        if display:
            arg = 1
        else:
            arg = 0
        self.cursorDisplayCount = ctypes.windll.user32.ShowCursor(arg)

    @asUrgent
    def createNewPlaylist(self):
        playlist.createNewPlaylist()

    @asUrgent
    def createNewPlaylistFolder(self):
        folder.createNewPlaylistFolder()

    @asUrgent
    def createNewSearchChannel(self):
        app.controller.addSearchFeed()

    @asUrgent
    def createNewChannelFolder(self):
        folder.createNewChannelFolder()

    @asUrgent
    def handleDrop(self, dropData, dropType, sourceData):
        app.controller.handleDrop(dropData, dropType, sourceData)


    @asUrgent
    def removeCurrentSelection(self):
        app.controller.removeCurrentSelection()

    
    @asUrgent
    def checkForUpdates(self):
        autoupdate.checkForUpdates()

    @asUrgent
    def removeCurrentItems(self):
        app.controller.removeCurrentItems()

    @asUrgent
    def copyCurrentItemURL(self):
        app.controller.copyCurrentItemURL()

    @asUrgent
    def selectAllItems(self):
        app.controller.selectAllItems()

    @asUrgent
    def createNewChannelFolder(self):
        folder.createNewChannelFolder()

    @asUrgent
    def createNewChannelGuide(self):
        app.controller.addAndSelectGuide()

    @asUrgent
    def createNewDownload(self):
        app.controller.newDownload()

    @asUrgent
    def importChannels(self):
        app.controller.importChannels()

    @asUrgent
    def exportChannels(self):
        app.controller.exportChannels()

    @asUrgent
    def addChannel(self):
        app.controller.addAndSelectFeed()

    @asUrgent
    def renameCurrentChannel(self):
        app.controller.renameCurrentChannel()

    @asUrgent
    def recommendCurrentChannel(self):
        print "WARNING: recommendCurrentChannel not supported"

    @asUrgent
    def renameCurrentPlaylist(self):
        app.controller.renameCurrentPlaylist()

    @asUrgent
    def removeCurrentPlaylist(self):
        app.controller.removeCurrentPlaylist()

    def openDonatePage(self):
        self.delegate.openExternalURL(config.get(prefs.DONATE_URL))

    def openBugTracker(self):
        self.delegate.openExternalURL(config.get(prefs.BUG_TRACKER_URL))

    @asUrgent
    def saveVideoFile(self, path):
        if frontend.currentVideoPath is None:
            return
        print "saving video %s to %s" % (frontend.currentVideoPath, path)
        shutil.copyfile(frontend.currentVideoPath, path)

    def startupDoSearch(self, path):
        if path.endswith(":"):
            path = path + "\\" # convert C: to C:\
        frontend.startup.doSearch(path)

    def startupCancelSearch(self):
        frontend.startup.cancelSearch()

    def getSpecialFolder(self, name):
        return platformcfg.getSpecialFolder(name)

    def extractFinish (self, duration, screenshot_success):
        app.controller.videoDisplay.extractFinish(duration, screenshot_success)

    def createProxyObjects(self):
        createProxyObjects()

    @asUrgent
    def initializeSearchEngines(self):
        # Send the search engine info to jsbridge.  This is a little tricky
        # because we need to access views.searchEngines from the main thread.
        names = []
        titles = []
        for engine in views.searchEngines:
            names.append(engine.name)
            titles.append(engine.title)
        frontend.jsBridge.setSearchEngineInfo(names, titles)
        frontend.jsBridge.setSearchEngine(searchengines.getLastEngine())

    def printOut(self, output):
        print output

    def addMenubar(self, document):
        menubarElement = document.getElementById("titlebar-menu")
        trayMenuElement = document.getElementById("traypopup")
        keysetElement = document.createElementNS(
         "http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul","keyset")

        for menu in (menubar.menubar.menus + (menubar.traymenu,)):
            for item in menu.menuitems:
                if isinstance(item, menubar.MenuItem):
                    count = 0
                    for shortcut in item.shortcuts:
                        count += 1
                        keyElement = document.createElementNS("http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul","key")
                        keyElement.setAttribute("id", "%s-key%d" % (item.action, count))
                        if len(XULKey(shortcut)) == 1:
                            keyElement.setAttribute("key", XULKey(shortcut))
                        else:
                            keyElement.setAttribute("keycode", XULKey(shortcut))
                        if XULKey(shortcut) == 'VK_SPACE':
                            # spacebar doesn't get display text for some reason
                            keyElement.setAttribute('keytext', _('Spacebar'))
                        if len(shortcut.modifiers) > 0:
                            keyElement.setAttribute("modifiers", XULModifier(shortcut))
                        keyElement.setAttribute("command", item.action)
                        keysetElement.appendChild(keyElement)
        menubarElement.appendChild(keysetElement)

        for menu in menubar.menubar.menus:
            menuElement = document.createElementNS("http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul","menu")
            menuElement.setAttribute("id", "menu-%s" % menu.action.lower())
            menuElement.setAttribute("label", XULifyLabel(menu.getLabel(menu.action)))
            if XULAccelFromLabel(menu.getLabel(menu.action)):
                menuElement.setAttribute("accesskey", XULAccelFromLabel(menu.getLabel(menu.action)))
            menupopup = document.createElementNS("http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul","menupopup")

            menupopup.setAttribute("id", "menupopup-%s" % menu.action.lower())
            menuElement.appendChild(menupopup)
            menubarElement.appendChild(menuElement)
            for item in menu.menuitems:
                if isinstance(item, menubar.Separator):
                    menuitem = document.createElementNS("http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul","menuseparator")
                else:
                    menuitem = document.createElementNS("http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul","menuitem")
                    menuitem.setAttribute("id","menuitem-%s" % item.action.lower())
                    menuitem.setAttribute("label",XULifyLabel(menu.getLabel(item.action)))
                    menuitem.setAttribute("command", item.action)
                    if XULAccelFromLabel(item.label):
                        menuitem.setAttribute("accesskey",
                                          XULAccelFromLabel(item.label))
                    if len(item.shortcuts)>0:
                        menuitem.setAttribute("key","%s-key%d"%(item.action,
                            XULDisplayedShortcut(item)))
                        
                menupopup.appendChild(menuitem)

        for item in menubar.traymenu.menuitems:
            if isinstance(item, menubar.Separator):
                menuitem = document.createElementNS("http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul","menuseparator")
            else:
                menuitem = document.createElementNS("http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul","menuitem")
                menuitem.setAttribute("id","traymenu-%s" % item.action.lower())
                menuitem.setAttribute("label",XULifyLabel(item.label))
                menuitem.setAttribute("command", item.action)
                if XULAccelFromLabel(item.label):
                    menuitem.setAttribute("accesskey",
                                          XULAccelFromLabel(item.label))
                if len(item.shortcuts)>0:
                    menuitem.setAttribute("key","%s-key%d"%(item.action,len(item.shortcuts)))
                        
            trayMenuElement.appendChild(menuitem)

    # Grab the database information, then throw it over the fence to
    # the UI thread
    @asIdle
    def updateTrayMenus(self):
        if views.initialized:
            numUnwatched = len(views.unwatchedItems)
            numDownloading = len(views.downloadingItems)
            numPaused = len(views.pausedItems)
        else:
            numPaused = numDownloading = numUnwatched = 0
        frontend.jsBridge.updateTrayMenus(numUnwatched, numDownloading, numPaused)

    # HACK ALERT - We should change this to take a dictionary instead
    # of all of the possible database variables. Since there's no
    # equivalent in XPCOM, it would be a pain, so we can wait. -- NN
    def getLabel(self,action,state,unwatched = 0,downloading = 0, paused = 0):
        variables = {}
        variables['numUnwatched'] = unwatched
        variables['numDownloading'] = downloading
        variables['numPaused'] = paused

        # Ih8XPCOM
        if len(state) == 0:
            state = None

        ret = XULifyLabel(menubar.menubar.getLabel(action,state,variables))
        if ret == action:
            ret = XULifyLabel(menubar.traymenu.getLabel(action,state, variables))
        return ret

    @asIdle
    def addDirectoryWatch(self, filename):
        feed.Feed (u"dtv:directoryfeed:%s" % (platformutils.makeURLSafe(filename),))

    @asIdle
    def removeDirectoryWatch(self, id):
        try:
            obj = database.defaultDatabase.getObjectByID (int(id))
            app.controller.removeFeeds ([obj])
	except:
	    pass

    @asIdle
    def toggleDirectoryWatchShown(self, id):
        try:
            obj = database.defaultDatabase.getObjectByID (int(id))
            obj.setVisible (not obj.visible)
        except:
            pass

    @asUrgent
    def playUnwatched(self):
        minimizer = makeService(
            "@participatoryculture.org/dtv/minimize;1",
            components.interfaces.pcfIDTVMinimize)
        if minimizer.isMinimized():
            minimizer.minimizeOrRestore()
        app.controller.frame.mainDisplayCallback(u'action:playUnwatched')

    @asIdle
    def pauseDownloads(self):
        app.controller.frame.mainDisplayCallback(u'action:pauseAll')

    @asIdle
    def resumeDownloads(self):
        app.controller.frame.mainDisplayCallback(u'action:resumeAll')

    def minimizeToTray(self):
        return config.get(prefs.MINIMIZE_TO_TRAY)

    def setMinimizeToTray(self, newSetting):
        config.set(prefs.MINIMIZE_TO_TRAY, newSetting)

    def handleKeyPress(self, keycode, shiftDown, controlDown):
        keycode_to_portable_code = {
            37: keyboard.LEFT,
            38: keyboard.UP,
            39: keyboard.RIGHT,
            40: keyboard.DOWN,
        }
        if keycode in keycode_to_portable_code:
            key = keycode_to_portable_code[keycode]
            keyboard.handleKey(key, shiftDown, controlDown)

    def handleCloseButton(self):
        if config.get(prefs.MINIMIZE_TO_TRAY_ASK_ON_CLOSE):
            self.askUserForCloseBehaviour()
        elif config.get(prefs.MINIMIZE_TO_TRAY):
            minimizer = makeService(
                    "@participatoryculture.org/dtv/minimize;1",
                    components.interfaces.pcfIDTVMinimize)
            minimizer.minimizeOrRestore()
        else:
            self.quit()

    def askUserForCloseBehaviour(self):
        title = _("Close to tray?")
        description = _("When you click the red close button, would you like Miro to close to the system tray or quit?  You can change this setting later in the Options.")

        dialog = dialogs.ChoiceDialog(title, description, 
                dialogs.BUTTON_CLOSE_TO_TRAY, dialogs.BUTTON_QUIT)
        def callback(dialog):
            if dialog.choice is None:
                return
            if dialog.choice == dialogs.BUTTON_CLOSE_TO_TRAY:
                config.set(prefs.MINIMIZE_TO_TRAY, True)
            else:
                config.set(prefs.MINIMIZE_TO_TRAY, False)
            config.set(prefs.MINIMIZE_TO_TRAY_ASK_ON_CLOSE, False)
            self.handleCloseButton()
        dialog.run(callback)
