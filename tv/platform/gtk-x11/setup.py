#!/usr/bin/env python

# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

###############################################################################
## Paths and configuration                                                   ##
###############################################################################

# The following properties allow you to explicitly set xulrunner paths and
# library names in the case that Miro guesses them wrong for your system.
# When setting these, you must make sure that:
#
# 1. The gtkmozembed Python module is compiled against the same xulrunner
#    that you're compiling AND running Miro against.
#
# 2. That you compile and run Miro with xulrunner 1.8 OR 1.9--you can't
#    use both.


# Location of the libxpcom.so file that's used for runtime.
# This is used to set the LD_LIBRARY_PATH environment variable.
#
# It's possible that this path is already in your LD_LIBRARY_PATH in
# which case you don't have to set it at all.
#
# Leave this set to None and Miro will attempt to guess at where it
# is.  This sometimes works.  If it doesn't on your system, let us know
# and we'll try to fix the guessing code.
#
# NOTE: Make sure this comes from the same xulrunner/firefox runtime that
# Miro is compiled against.  If it's wrong, you'll likely see complaints
# of missing symbols when you try to run Miro.
#
# Examples:
# XPCOM_RUNTIME_PATH = "/usr/lib/firefox"
# XPCOM_RUNTIME_PATH = "/usr/lib/xulrunner-1.9.0.1"
XPCOM_RUNTIME_PATH = None

# Location of xulrunner/firefox components for gtkmozembed.set_comp_path.
# See documentation for set_comp_path here:
# http://www.mozilla.org/unix/gtk-embedding.html
#
# Leave this set to None and Miro will attempt to guess at where it
# is.  This sometimes works.  If it doesn't on your system, let us know
# and we'll try to fix the guessing code.
#
# Examples:
# MOZILLA_LIB_PATH = "/usr/lib/xulrunner-1.9.0.1"
MOZILLA_LIB_PATH = None

# The name of the library for the xpcom and gtkmozembed you want to compile
# against on this system.  These strings are passed to pkg-config to get all
# the information Miro needs to compile our browser widget.
#
# You should be able to do the following with the libraries you provide:
#
#    pkg-config --cflags --libs --define-variable=includetype=unstable \
#        <xpcom-library> <gtkmozembed-library>
#
# and get back lots of exciting data.
#
# Set the XULRUNNER_19 flag to True if compiling against xulrunner 1.9 or
# False if compiling against xulrunner 1.8 or some earlier version.
#
# Leave these three set to None and Miro will attempt to guess at values.
# This sometimes works.  If it doesn't on your system, let us know and we'll
# try to fix the guessing code.
#
# NOTE: If you set one of these, you should set all of them.
#
# Examples:
# XPCOM_LIB = "libxul"
# GTKMOZEMBED_LIB = "libxul"
# XULRUNNER_19 = True
#
# XPCOM_LIB = "firefox-xpcom"
# GTKMOZEMBED_LIB = "firefox-gtkmozembed"
# XULRUNNER_19 = False
XPCOM_LIB = None
GTKMOZEMBED_LIB = None
XULRUNNER_19 = None


###############################################################################
## End of configuration. No user-serviceable parts inside                    ##
###############################################################################

import sys

# verify we have required bits for compiling Miro

try:
    from Pyrex.Compiler import Version
    if Version.version.split(".") < ["0", "9", "6", "4"]:
        print "Pyrex 0.9.6.4 or greater required.  You have version %s." % Version.version
        sys.exit(1)
except ImportError:
    print "Pyrex not found.  Please install Pyrex."
    sys.exit(1)

from distutils.cmd import Command
from distutils.core import setup
from distutils.extension import Extension
from distutils.errors import DistutilsOptionError
from distutils.util import change_root
from distutils import dir_util, log, sysconfig
from glob import glob
from string import Template
import distutils.command.install_data
import os
import pwd
import subprocess
import platform
import re
import time
import shutil

from Pyrex.Distutils import build_ext

#### useful paths to have around ####
def is_root_dir(d):
    """
    bdist_rpm and possibly other commands copies setup.py into a subdir of
    platform/gtk-x11.  This makes it hard to find the root directory.  We work
    our way up the path until our is_root_dir test passes.
    """
    return os.path.exists(os.path.join(d, "MIRO_ROOT"))

def get_root_dir():
    root_try = os.path.abspath(os.path.dirname(__file__))
    while True:
        if is_root_dir(root_try):
            root_dir = root_try
            break
        if root_try == '/':
            raise RuntimeError("Couldn't find Miro root directory")
        root_try = os.path.abspath(os.path.join(root_try, '..'))
    return root_dir

root_dir = get_root_dir()
portable_dir = os.path.join(root_dir, 'portable')
portable_frontend_dir = os.path.join(portable_dir, 'frontends')
portable_xpcom_dir = os.path.join(portable_frontend_dir, 'widgets', 'gtk',
                                  'xpcom')
dl_daemon_dir = os.path.join(portable_dir, 'dl_daemon')
test_dir = os.path.join(portable_dir, 'test')
resource_dir = os.path.join(root_dir, 'resources')
platform_dir = os.path.join(root_dir, 'platform', 'gtk-x11')
platform_package_dir = os.path.join(platform_dir, 'plat')
platform_widgets_dir = os.path.join(platform_package_dir, 'frontends',
                                    'widgets')

# insert the root_dir to the beginning of sys.path so that we can
# pick up portable and other packages
sys.path.insert(0, root_dir)

# later when we install the portable modules, they will be in the miro package,
# but at this point, they are in a package named "portable", so let's hack it
import portable
sys.modules['miro'] = portable
import plat
sys.modules['miro'].plat = plat

# little hack to get the version from the current app.config.template
from miro import util
app_config = os.path.join(resource_dir, 'app.config.template')
appVersion = util.read_simple_config_file(app_config)['appVersion']

# RPM hack
if 'bdist_rpm' in sys.argv:
    appVersion = appVersion.replace('-', '_')

def getlogin():
    """Does a best-effort attempt to return the login of the user running the
    script.
    """
    try:
        return os.environ['LOGNAME']
    except KeyError:
        pass
    try:
        return os.environ['USER']
    except KeyError:
        pass
    pwd.getpwuid(os.getuid())[0]

def read_file(path):
    f = open(path)
    try:
        return f.read()
    finally:
        f.close()

def write_file(path, contents):
    f = open(path, 'w')
    try:
        f.write(contents)
    finally:
        f.close()

def expand_file_contents(path, **values):
    """Do a string expansion on the contents of a file using the same rules as
    string.Template from the standard library.
    """
    template = Template(read_file(path))
    expanded = template.substitute(**values)
    write_file(path, expanded)

def get_command_output(cmd, warnOnStderr=True, warnOnReturnCode=True):
    """Wait for a command and return its output.  Check for common errors and
    raise an exception if one of these occurs.
    """
    p = subprocess.Popen(cmd, shell=True, close_fds=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    if warnOnStderr and stderr != '':
        raise RuntimeError("%s outputted the following error:\n%s" % (cmd, stderr))
    if warnOnReturnCode and p.returncode != 0:
        raise RuntimeError("%s had non-zero return code %d" % (cmd, p.returncode))
    return stdout

def parse_pkg_config(command, components, options_dict = None):
    """Helper function to parse compiler/linker arguments from
    pkg-config/mozilla-config and update include_dirs, library_dirs, etc.

    We return a dict with the following keys, which match up with keyword
    arguments to the setup function: include_dirs, library_dirs, libraries,
    extra_compile_args.

    Command is the command to run (pkg-config, mozilla-config, etc).
    Components is a string that lists the components to get options for.

    If options_dict is passed in, we add options to it, instead of starting
    from scratch.
    """
    if options_dict is None:
        options_dict = {
            'include_dirs' : [],
            'library_dirs' : [],
            'runtime_dirs' : [],
            'libraries' : [],
            'extra_compile_args' : []
        }
    commandLine = "%s --cflags --libs %s" % (command, components)
    output = get_command_output(commandLine).strip()
    for comp in output.split():
        prefix, rest = comp[:2], comp[2:]
        if prefix == '-I':
            options_dict['include_dirs'].append(rest)
        elif prefix == '-L':
            options_dict['library_dirs'].append(rest)
        elif prefix == '-l':
            options_dict['libraries'].append(rest)
        else:
            options_dict['extra_compile_args'].append(comp)

    commandLine = "%s --variable=libdir %s" % (command, components)
    output = get_command_output(commandLine).strip()
    options_dict['runtime_dirs'].append(output)

    return options_dict

def package_exists(package_name):
    """
    Return True if the package is present in the system.  False otherwise.
    The check is made with pkg-config.
    """
    # pkg-config returns 0 if the package is present
    return subprocess.call(['pkg-config', '--exists', package_name]) == 0

def generate_miro(xpcom_path):
    # build a miro script that wraps the miro.real script with an LD_LIBRARY_PATH
    # environment variable to pick up the xpcom we decided to use.
    runtimelib = ""

    f = open(os.path.join(platform_dir, "miro"), "w")
    if xpcom_path:
        runtimelib = "GRE_HOME=%s MOZILLA_FIVE_HOME=%s LD_LIBRARY_PATH=%s " % (xpcom_path, xpcom_path, xpcom_path)

    f.write( \
"""#!/bin/sh
# This file is generated by setup.py.
DEBUG=0

for arg in $@
do
    case $arg in
    "--debug")    DEBUG=1;;
    esac
done

if [ $DEBUG = 1 ]
then
    echo "DEBUGGING MODE."
    PYTHON=`which python`
    GDB=`which gdb`

    if [ -z $GDB ]
    then
        echo "gdb cannot be found on your path.  aborting....";
        exit;
    fi

    %(runtimelib)s$GDB -ex 'set breakpoint pending on' -ex 'run' --args $PYTHON ./miro.real --sync "$@"
else
    %(runtimelib)smiro.real "$@"
fi
""" % { "runtimelib": runtimelib})
    f.close()


#### MozillaBrowser Extension ####
def get_mozilla_stuff():
    if XPCOM_LIB and GTKMOZEMBED_LIB and XULRUNNER_19 != None:
        print "\nUsing XPCOM_LIB, GTKMOZEMBED_LIB and XULRUNNER_19 values...."
        xulrunner19 = XULRUNNER_19
        xpcom_lib = XPCOM_LIB
        gtkmozembed_lib = GTKMOZEMBED_LIB

    else:
        print "\nTrying to figure out xpcom_lib, gtkmozembed_lib, and xulrunner_19 values...."
        xulrunner19 = False
        if package_exists('libxul'):
            xulrunner19 = True
            xpcom_lib = 'libxul'
            gtkmozembed_lib = 'libxul'

        elif package_exists('xulrunner-xpcom'):
            xpcom_lib = 'xulrunner-xpcom'
            gtkmozembed_lib = 'xulrunner-gtkmozembed'

        elif package_exists('seamonkey-xpcom'):
            xpcom_lib = 'seamonkey-xpcom'
            gtkmozembed_lib = 'seamonkey-gtkmozembed'

        elif package_exists('mozilla-xpcom'):
            xpcom_lib = 'mozilla-xpcom'
            gtkmozembed_lib = 'mozilla-gtkmozembed'

        elif package_exists('firefox-xpcom'):
            xpcom_lib = 'firefox-xpcom'
            gtkmozembed_lib = 'firefox-gtkmozembed'

        else:
            print "Can't find libxul, xulrunner-xpcom, seamonkey-xpcom, mozilla-xpcom or firefox-xpcom"
            print "One of these is required."
            sys.exit(1)

    print "using xpcom_lib: ", repr(xpcom_lib)
    print "using gtkmozembed_lib: ", repr(gtkmozembed_lib)
    print "using xulrunner19: ", repr(xulrunner19)

    # use the XPCOM_RUNTIME_PATH that's set if there's one that's set
    if XPCOM_RUNTIME_PATH:
        print "\nUsing XPCOM_RUNTIME_PATH value...."
        xpcom_runtime_path = XPCOM_RUNTIME_PATH
    else:
        print "\nTrying to figure out xpcom_runtime_path value...."
        xpcom_runtime_path = get_command_output("pkg-config --variable=libdir %s" % xpcom_lib).strip()
    print "using xpcom_runtime_path: ", repr(xpcom_runtime_path)

    mozilla_browser_options = parse_pkg_config("pkg-config",
            "gtk+-2.0 glib-2.0 pygtk-2.0 --define-variable=includetype=unstable %s %s" % (gtkmozembed_lib, xpcom_lib))

    if MOZILLA_LIB_PATH:
        print "\nUsing MOZILLA_LIB_PATH value...."
        mozilla_lib_path = MOZILLA_LIB_PATH
    else:
        print "\nTrying to figure out mozilla_lib_path value...."
        mozilla_lib_path = parse_pkg_config('pkg-config', '%s' % gtkmozembed_lib)['library_dirs']
        mozilla_lib_path = mozilla_lib_path[0]
    print "using mozilla_lib_path: ", repr(mozilla_lib_path)

    mozilla_runtime_path = parse_pkg_config('pkg-config', gtkmozembed_lib)['runtime_dirs']

    # Find the base mozilla directory, and add the subdirs we need.
    def allInDir(directory, subdirs):
        for subdir in subdirs:
            if not os.path.exists(os.path.join(directory, subdir)):
                return False
        return True

    xpcom_includes = parse_pkg_config("pkg-config", xpcom_lib)

    # xulrunner 1.9 has a different directory structure where all the headers
    # are in the same directory and that's already in include_dirs.  so we don't
    # need to do this.
    if not xulrunner19:
        mozIncludeBase = None
        for dir in xpcom_includes['include_dirs']:
            if allInDir(dir, ['dom', 'gfx', 'widget']):
                # we can be pretty confident that dir is the mozilla/firefox/xulrunner
                # base include directory
                mozIncludeBase = dir
                break

        if mozIncludeBase is not None:
            for subdir in ['dom', 'gfx', 'widget', 'commandhandler', 'uriloader',
                           'webbrwsr', 'necko', 'windowwatcher', 'unstable',
                           'embed_base']:
                path = os.path.join(mozIncludeBase, subdir)
                mozilla_browser_options['include_dirs'].append(path)

    nsI = True
    for dir in mozilla_browser_options['include_dirs']:
        if os.path.exists(os.path.join(dir, "nsIServiceManagerUtils.h")):
            nsI = True
            break
        if os.path.exists(os.path.join(dir, "nsServiceManagerUtils.h")):
            nsI = False
            break

    if nsI:
        mozilla_browser_options['extra_compile_args'].append('-DNS_I_SERVICE_MANAGER_UTILS=1')

    # define PCF_USING_XULRUNNER19 if we're on xulrunner 1.9
    if xulrunner19:
        mozilla_browser_options['extra_compile_args'].append('-DPCF_USING_XULRUNNER19=1')

    return mozilla_browser_options, mozilla_lib_path, xpcom_runtime_path, mozilla_runtime_path

mozilla_browser_options, mozilla_lib_path, xpcom_runtime_path, mozilla_runtime_path = get_mozilla_stuff()


#### Xlib Extension ####
xlib_ext = \
    Extension("miro.plat.xlibhelper",
        [ os.path.join(platform_package_dir,'xlibhelper.pyx') ],
        library_dirs = ['/usr/X11R6/lib'],
        libraries = ['X11'],
    )

pygtkhacks_ext = \
    Extension("miro.frontends.widgets.gtk.pygtkhacks",
        [ os.path.join(portable_frontend_dir, 'widgets', 'gtk',
            'pygtkhacks.pyx') ],
        **parse_pkg_config('pkg-config',
            'pygobject-2.0 gtk+-2.0 glib-2.0 gthread-2.0')
    )

mozprompt_ext = \
    Extension("miro.plat.frontends.widgets.mozprompt",
        [
            os.path.join(platform_widgets_dir, 'mozprompt.pyx'),
            os.path.join(platform_widgets_dir, 'PromptService.cc'),
        ],
        **mozilla_browser_options
    )

http_observer_options = mozilla_browser_options.copy()
http_observer_options['include_dirs'].append(portable_xpcom_dir)

httpobserver_ext = \
    Extension("miro.plat.frontends.widgets.httpobserver",
        [
            os.path.join(platform_widgets_dir, 'httpobserver.pyx'),
            os.path.join(portable_xpcom_dir, 'HttpObserver.cc'),
        ],
        **http_observer_options
    )


windowcreator_ext = \
    Extension("miro.plat.frontends.widgets.windowcreator",
        [
            os.path.join(platform_widgets_dir, 'windowcreator.pyx'),
            os.path.join(platform_widgets_dir, 'MiroWindowCreator.cc'),
        ],
        language="c++",
        **mozilla_browser_options
    )

pluginsdir_ext = \
    Extension("miro.plat.frontends.widgets.pluginsdir",
        [
            os.path.join(platform_widgets_dir, 'pluginsdir.pyx'),
            os.path.join(platform_widgets_dir, 'MiroPluginsDir.cc'),
        ],
        language="c++",
        **mozilla_browser_options
    )


#### Build the data_files list ####
def listfiles(path):
    return [f for f in glob(os.path.join(path, '*')) if os.path.isfile(f)]

data_files = []
# append the root resource directory.
# filter out app.config.template (which is handled specially)
files = [f for f in listfiles(resource_dir) \
        if os.path.basename(f) != 'app.config.template']
data_files.append(('/usr/share/miro/resources/', files))
# handle the sub directories.
for dir in ('searchengines', 'images', 'testdata',
        os.path.join('testdata', 'stripperdata'),
        os.path.join('testdata', 'locale', 'fr', 'LC_MESSAGES')):
    source_dir = os.path.join(resource_dir, dir)
    dest_dir = os.path.join('/usr/share/miro/resources/', dir)
    data_files.append((dest_dir, listfiles(source_dir)))

for mem in ["24", "48", "72", "128"]:
    d = os.path.join("icons", "hicolor", "%sx%s" % (mem, mem), "apps")
    source = os.path.join(platform_dir, d, "miro.png")
    dest = os.path.join("/usr/share/", d)
    data_files.append((dest, [source]))

# add ADOPTERS file, the desktop file, mime data, and man page
data_files += [
    ('/usr/share/miro/resources',
     [os.path.join(root_dir, 'ADOPTERS')]),
    ('/usr/share/pixmaps',
     glob(os.path.join(platform_dir, 'miro.xpm'))),
    ('/usr/share/applications',
     [os.path.join(platform_dir, 'miro.desktop')]),
    ('/usr/share/mime/packages',
     [os.path.join(platform_dir, 'miro.xml')]),
    ('/usr/share/man/man1',
     [os.path.join(platform_dir, 'miro.1.gz')]),
    ('/usr/share/man/man1',
     [os.path.join(platform_dir, 'miro.real.1.gz')]),
]


# if we're not doing "python setup.py clean", then we can do a bunch of things
# that have file-related side-effects
if not "clean" in sys.argv:
    generate_miro(xpcom_runtime_path)
    # gzip the man page
    os.system ("gzip -9 < %s > %s" % (os.path.join(platform_dir, 'miro.1'), os.path.join(platform_dir, 'miro.1.gz')))
    # copy miro.1.gz to miro.real.1.gz so that lintian complains less
    os.system ("cp %s %s" % (os.path.join(platform_dir, 'miro.1.gz'), os.path.join(platform_dir, 'miro.real.1.gz')))


#### Our specialized install_data command ####
class install_data(distutils.command.install_data.install_data):
    """install_data extends to default implementation so that it automatically
    installs app.config from app.config.template.
    """

    def install_app_config(self):
        source = os.path.join(resource_dir, 'app.config.template')
        dest = '/usr/share/miro/resources/app.config'

        config_file = util.read_simple_config_file(source)
        print "Trying to figure out the git revision...."
        if config_file["appVersion"].endswith("git"):
            revision = util.query_revision()
            if revision is None:
                revision = "unknown"
                revisionurl = "unknown"
                revisionnum = "unknown"
            else:
                revisionurl = revision[0]
                revisionnum = revision[1]
                revision = "%s - %s" % (revisionurl, revisionnum)
        else:
            revisionurl = ""
            revisionnum = ""
            revision = ""
        print "Using %s" % revisionnum

        if self.root:
            dest = change_root(self.root, dest)
        self.mkpath(os.path.dirname(dest))
        # We don't use the dist utils copy_file() because it only copies
        # the file if the timestamp is newer
        shutil.copyfile(source, dest)
        expand_file_contents(dest, APP_REVISION=revision,
                             APP_REVISION_NUM=revisionnum,
                             APP_REVISION_URL=revisionurl,
                             APP_PLATFORM='gtk-x11',
                             BUILD_MACHINE="%s@%s" % (getlogin(),
                                                      os.uname()[1]),
                             BUILD_TIME=str(time.time()),
                             MOZILLA_LIB_PATH=mozilla_runtime_path[0])
        self.outfiles.append(dest)

        locale_dir = os.path.join (resource_dir, "locale")

        for source in glob (os.path.join (locale_dir, "*.mo")):
            lang = os.path.basename(source)[:-3]
            if 'LINGUAS' in os.environ and lang not in os.environ['LINGUAS']:
                continue
            dest = '/usr/share/locale/%s/LC_MESSAGES/miro.mo' % lang
            if self.root:
                dest = change_root(self.root, dest)
            self.mkpath(os.path.dirname(dest))
            self.copy_file(source, dest)
            self.outfiles.append(dest)

    def run(self):
        distutils.command.install_data.install_data.run(self)
        self.install_app_config()


class test_system(Command):
    description = "Allows you to test configurations without compiling or running."
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        # FIXME - try importing and all that other stuff to make sure
        # we have most of the pieces here?
        pass

#### install_theme installs a specified theme .zip
class install_theme(Command):
    description = 'Install a provided theme to /usr/share/miro/themes'
    user_options = [("theme=", None, 'ZIP file containing the theme')]

    def initialize_options(self):
        self.theme = None

    def finalize_options(self):
        if self.theme is None:
            raise DistutilsOptionError, "must supply a theme ZIP file"
        if not os.path.exists(self.theme):
            raise DistutilsOptionError, "theme file does not exist"
        import zipfile
        if not zipfile.is_zipfile(self.theme):
            raise DistutilsOptionError, "theme file is not a ZIP file"
        zf = zipfile.ZipFile(self.theme)
        appConfig = zf.read('app.config')
        themeName = None
        for line in appConfig.split('\n'):
            if '=' in line:
                name, value = line.split('=', 1)
                name = name.strip()
                value = value.lstrip()
                if name == 'themeName':
                    themeName = value
        if themeName is None:
            raise DistutilsOptionError, "invalid theme file"
        self.zipfile = zf
        self.theme_name = themeName
        self.theme_dir = '/usr/share/miro/themes/%s' % themeName

    def run(self):
        if os.path.exists(self.theme_dir):
            shutil.rmtree(self.theme_dir)
        os.makedirs(self.theme_dir)
        for name in self.zipfile.namelist():
            if name.startswith('xul/'):
                # ignore XUL stuff, we don't need it on Linux
                continue
            print 'installing', os.path.join(self.theme_dir, name)
            if name[-1] == '/':
                os.makedirs(os.path.join(self.theme_dir, name))
            else:
                f = file(os.path.join(self.theme_dir, name), 'wb')
                f.write(self.zipfile.read(name))
                f.close()
        print """%s theme installed.

To use this theme, run:

    miro --theme="%s"
""" % (self.theme_name, self.theme_name)

class clean(Command):
    description = 'Cleans the build and dist directories'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        if os.path.exists('./build/'):
            print "removing build directory"
            shutil.rmtree('./build/')

        if os.path.exists('./dist/'):
            print "removing dist directory"
            shutil.rmtree('./dist/')

ext_modules = []
ext_modules.append(xlib_ext)
ext_modules.append(pygtkhacks_ext)
ext_modules.append(mozprompt_ext)
ext_modules.append(httpobserver_ext)
ext_modules.append(windowcreator_ext)
ext_modules.append(pluginsdir_ext)

#### Run setup ####
setup(name='miro',
    version=appVersion,
    author='Participatory Culture Foundation',
    author_email='feedback@pculture.org',
    url='http://www.getmiro.com/',
    download_url='http://www.getmiro.com/downloads/',
    scripts = [
        os.path.join(platform_dir, 'miro'),
        os.path.join(platform_dir, 'miro.real')
    ],
    data_files=data_files,
    ext_modules=ext_modules,
    packages = [
        'miro',
        'miro.dl_daemon',
        'miro.test',
        'miro.dl_daemon.private',
        'miro.frontends',
        'miro.frontends.cli',
        'miro.frontends.shell',
        'miro.frontends.widgets',
        'miro.frontends.widgets.gtk',
        'miro.plat',
        'miro.plat.frontends',
        'miro.plat.frontends.widgets',
        'miro.plat.renderers',
    ],
    package_dir = {
        'miro': portable_dir,
        'miro.test': test_dir,
        'miro.plat': platform_package_dir,
    },
    cmdclass = {
        'test_system': test_system,
        'build_ext': build_ext,
        'install_data': install_data,
        'install_theme': install_theme,
        'clean': clean,
    }
)