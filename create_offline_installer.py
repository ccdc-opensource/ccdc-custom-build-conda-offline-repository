"""Fetch the conda packages required to run the API and associated scripts and copy them to the installer directory.
This works by installing a temporary miniconda, downloading the required packages and all dependencies,
then copying the newly downloaded packages, which are those not already provided by the miniconda install.
"""
import glob
import os
import platform
import requests
import shutil
import subprocess
import sys
import time
import tempfile
import re
import pathlib

# Pass the required miniconda installer version from devops pipelines variables
def miniconda_installer_version():
    return os.environ.get('MINICONDA_INSTALLER_VERSION', 'py37_4.9.2')

def required_offline_conda_packages():
    # these are the packages that we recommend for using the API
    # https://downloads.ccdc.cam.ac.uk/documentation/API/installation_notes.html#using-conda

    # Please ensure that these versions are consistent with those in
    # https://github.com/ccdc-confidential/cpp-apps-main/blob/main/wrapping/ccdc/requirements.txt
    api_pkgs = [
        'pillow<9.0',
        'six',
        'lxml==4.6.3',
        'numpy==1.21.3', # also used in mercury scripts
        'pytest',
        'pandas==1.2.5', # also used in mercury scripts
        'xgboost==1.5.0', # equivalent to py-xgboost, but more used
        'scikit-learn==0.24.2',
    ]

    # these packages are required by other scripts that we distribute
    # Please ensure that these versions are consistent with those in
    # https://github.com/ccdc-confidential/cpp-apps-main/blob/main/mercury/python-scripts-requirements.txt
    script_pkgs = [
        'docxtpl==0.11.5', # reports
        # matplotlib-base. Like matplotlib, minus the Qt dependency!!!!
        # changing this to matplotlib breaks the build on Linux so beware.
        'matplotlib-base==3.4.3', # also used in mercury scripts
        'Jinja2', # crystallisability_prediction.py, solvate_prediction.py
        'scipy==1.7.1',
        'tensorflow==1.14.0', # For aromatic analyser script
        'xlsxwriter==3.0.1',
    ]

    return api_pkgs + script_pkgs

# Pass the build id from devops pipelines variables
# Make sure the resulting artefact is clearly labeled if produced on a developer machine
def build_id():
    return os.environ.get('BUILD_BUILDID', 'DEVELOPER_VERSION')

# Pass the operating system name from devops pipelines variables
# Make sure the resulting artefact is clearly labeled if produced on a developer machine
def build_osname():
    return os.environ.get('BUILDOSNAME', 'for_my_developer_os')


IS_WINDOWS = sys.platform == 'win32'

if IS_WINDOWS:
    # Add functionality to restore the environment after miniconda installer has messed around with it
    import ctypes
    from ctypes import wintypes
    if sys.version_info[0] >= 3:
        import winreg as reg
    else:
        import _winreg as reg

    HWND_BROADCAST = 0xffff
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    SendMessageTimeout = ctypes.windll.user32.SendMessageTimeoutW
    SendMessageTimeout.restype = None #wintypes.LRESULT
    SendMessageTimeout.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                wintypes.LPCWSTR, wintypes.UINT, wintypes.UINT, ctypes.POINTER(wintypes.DWORD)]

    def sz_expand(value, value_type):
        if value_type == reg.REG_EXPAND_SZ:
            return reg.ExpandEnvironmentStrings(value)
        else:
            return value

    def remove_from_system_path(pathname, allusers=True, path_env_var='PATH'):
        """Removes all entries from the path which match the value in 'pathname'

        You must call broadcast_environment_settings_change() after you are finished
        manipulating the environment with this and other functions.

        For example,
            # Remove Anaconda from PATH
            remove_from_system_path(r'C:\Anaconda')
            broadcast_environment_settings_change()
        """
        pathname = os.path.normcase(os.path.normpath(pathname))

        envkeys = [(reg.HKEY_CURRENT_USER, r'Environment')]
        if allusers:
            envkeys.append((reg.HKEY_LOCAL_MACHINE,
                r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'))
        for root, keyname in envkeys:
            key = reg.OpenKey(root, keyname, 0,
                    reg.KEY_QUERY_VALUE|reg.KEY_SET_VALUE)
            reg_value = None
            try:
                reg_value = reg.QueryValueEx(key, path_env_var)
            except WindowsError:
                # This will happen if we're a non-admin install and the user has
                # no PATH variable.
                reg.CloseKey(key)
                continue

            try:
                any_change = False
                results = []
                for v in reg_value[0].split(os.pathsep):
                    vexp = sz_expand(v, reg_value[1])
                    # Check if the expanded path matches the
                    # requested path in a normalized way
                    if os.path.normcase(os.path.normpath(vexp)) == pathname:
                        any_change = True
                    else:
                        # Append the original unexpanded version to the results
                        results.append(v)

                modified_path = os.pathsep.join(results)
                if any_change:
                    reg.SetValueEx(key, path_env_var, 0, reg_value[1], modified_path)
            except:
                # If there's an error (e.g. when there is no PATH for the current
                # user), continue on to try the next root/keyname pair
                reg.CloseKey(key)

    def add_to_system_path(paths, allusers=True, path_env_var='PATH'):
        """Adds the requested paths to the system PATH variable.

        You must call broadcast_environment_settings_change() after you are finished
        manipulating the environment with this and other functions.

        """
        # Make sure it's a list
        if not issubclass(type(paths), list):
            paths = [paths]

        # Ensure all the paths are valid before we start messing with the
        # registry.
        new_paths = None
        for p in paths:
            p = os.path.abspath(p)
            if not os.path.isdir(p):
                raise RuntimeError(
                    'Directory "%s" does not exist, '
                    'cannot add it to the path' % p
                )
            if new_paths:
                new_paths = new_paths + os.pathsep + p
            else:
                new_paths = p

        if allusers:
            # All Users
            root, keyname = (reg.HKEY_LOCAL_MACHINE,
                r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment')
        else:
            # Just Me
            root, keyname = (reg.HKEY_CURRENT_USER, r'Environment')

        key = reg.OpenKey(root, keyname, 0,
                reg.KEY_QUERY_VALUE|reg.KEY_SET_VALUE)

        reg_type = None
        reg_value = None
        try:
            try:
                reg_value = reg.QueryValueEx(key, path_env_var)
            except WindowsError:
                # This will happen if we're a non-admin install and the user has
                # no PATH variable; in which case, we can write our new paths
                # directly.
                reg_type = reg.REG_EXPAND_SZ
                final_value = new_paths
            else:
                reg_type = reg_value[1]
                # If we're an admin install, put us at the end of PATH.  If we're
                # a user install, throw caution to the wind and put us at the
                # start.  (This ensures we're picked up as the default python out
                # of the box, regardless of whether or not the user has other
                # pythons lying around on their PATH, which would complicate
                # things.  It's also the same behavior used on *NIX.)
                if allusers:
                    final_value = reg_value[0] + os.pathsep + new_paths
                else:
                    final_value = new_paths + os.pathsep + reg_value[0]

            reg.SetValueEx(key, path_env_var, 0, reg_type, final_value)

        finally:
            reg.CloseKey(key)

    def broadcast_environment_settings_change():
        """Broadcasts to the system indicating that master environment variables have changed.

        This must be called after using the other functions in this module to
        manipulate environment variables.
        """
        SendMessageTimeout(HWND_BROADCAST, WM_SETTINGCHANGE, 0, u'Environment',
                    SMTO_ABORTIFHUNG, 5000, ctypes.pointer(wintypes.DWORD()))

class MinicondaOfflineInstaller:
    def __init__(self):
        self.extensions = {
            'Windows': 'exe',
            'Linux': 'sh',
            'Darwin': 'sh'
        }
        self.platforms = {
            'Windows': 'Windows',
            'Linux': 'Linux',
            'Darwin': 'MacOSX'
        }
        self.architectures = {
            '64bit': 'x86_64'
        }
        self.system = platform.system()
        self.conda_python_version = '3'
        self.bitness = '64bit'
        self.distribution = 'Miniconda'
        self.conda_bz2_src_packages = os.path.join(self.build_install_dir, 'pkgs', '*.bz2')
        self.conda_conda_src_packages = os.path.join(self.build_install_dir, 'pkgs', '*.conda')

    @property
    def name(self):
        return 'miniconda3'

    @property
    def build_install_dir(self):
        '''Where the temporary conda distribution will be installed'''
        return 'build_temp'

    @property
    def artefact_id(self):
        '''The artefact identifies, based on build id and system, used to find the right files in devops pipelines'''
        return self.name + '-' + miniconda_installer_version() + '-' + build_id() + '-' + build_osname()
    
    @property
    def output_dir(self):
        '''The output directory, where the installer and the offline channel end up'''
        return os.path.join('output', self.artefact_id)

    @property
    def output_installer(self):
        '''local path to the miniconda installer'''
        return os.path.join(self.output_dir, self.installer_name)

    @property
    def output_conda_offline_channel(self):
        '''local path to the resulting offline conda installer'''
        return os.path.join(self.output_dir, 'conda_offline_channel')

    @property
    def installer_name(self):
        # (Ana|Mini)conda-<VERSION>-<PLATFORM>-<ARCHITECTURE>.<EXTENSION>
        return '{0}{1}-{2}-{3}-{4}.{5}'.format(
            self.distribution,
            self.conda_python_version,
            miniconda_installer_version(),
            self.platforms[self.system],
            self.architectures[self.bitness],
            self.extensions[self.system])

    @property
    def install_script_filename(self):
        '''the miniconda installer script used by the CSD installer'''
        return "install.{0}".format("bat" if sys.platform == 'win32' else "sh" )

    @property
    def install_script_path(self):
        '''local path to the miniconda installer script'''
        return os.path.join(self.output_dir, self.install_script_filename)

    def fetch_miniconda_installer(self):
        installer_url='https://repo.continuum.io/miniconda/%s' % self.installer_name
        print("Get %s -> %s" % (installer_url, self.output_installer))
        r = requests.get(installer_url)
        with open(self.output_installer, 'wb') as fd:
            for chunk in r.iter_content(chunk_size=128):
                fd.write(chunk)

    def clean_build_and_output(self):
        try:
            shutil.rmtree(self.output_dir)
        except:
            pass
        try:
            shutil.rmtree(self.build_install_dir)
        except:
            pass

    def conda_cleanup(self, *package_specs):
        """Remove package archives (so that we don't distribute them as they are already part of the installer)
        """
        self._run_pkg_manager('conda', ['clean', '-y', '-q', '--all'])

    def conda_update_all(self):
        """Update local packages that are part of the installer
        """
        self._run_pkg_manager('conda', ['update', '-y', '-q', '--all'])

    def conda_update_conda(self):
        """Update local packages that are part of the installer
        """
        self._run_pkg_manager('conda', ['update', '-y', '-q', 'conda'])

    def conda_install_download_only(self, *package_specs):
        """Download a conda package given its specifications.
        E.g. self.conda_install('numpy==1.9.2', 'lxml')
        """
        self._run_pkg_manager('conda', ['install', '-y', '--download-only', '-q'], *package_specs)

    def package_name(self, package_filename):
        """Return the bit of a filename before the version number starts
        """
        return re.match(r"(.*)-\d.*", package_filename).group(1)

    def channel_arch(self):
        """return the conda channel architecture required for this build
        """
        if sys.platform == 'win32':
            if self.bitness == '64bit':
                return 'win-64'
            else:
                return 'win-32'
        elif sys.platform == 'darwin':
            return 'osx-64'
        else:
            return 'linux-64'

    def conda_index(self, channel):
        """index the conda channel directory, uses a repo of magic fixes
        as discussed in https://ccdc-cambridge.slack.com/archives/C1JRZPULU/p1576008379426900
        Also comments out the addition of _libgcc_mutex from main as we only use conda-forge on linux
        """
        patch_file = os.path.join( pathlib.Path(__file__).parent.absolute(), 'repodata-hotfixes/main.py')
        updated_patch_file = os.path.join( self.build_install_dir , 'repo-patch.py')
        with open(patch_file) as f:
            s = f.read()

        if sys.platform.startswith('linux'):
            s = s.replace("if name == 'libgcc-ng':", "# if name == 'libgcc-ng':")
            s = s.replace("depends.append('_libgcc_mutex * main')", "# depends.append('_libgcc_mutex * main')")

        with open(updated_patch_file, 'w') as f:
            f.write(s)

        self._run_pkg_manager('conda', ['index', '--no-progress', '-p', updated_patch_file, channel])

    def copy_packages(self):
        """Copy packages from the miniconda install to the final installer location
        """
        conda_package_dest = os.path.join(self.output_conda_offline_channel, self.channel_arch())
        os.makedirs(conda_package_dest)

        known_packages = set()

        for conda_package in glob.glob(self.conda_bz2_src_packages):
            filename = os.path.basename(conda_package)
            known_packages.add(self.package_name(filename))
            shutil.copyfile(conda_package, os.path.join(conda_package_dest, filename))
        for conda_package in glob.glob(self.conda_conda_src_packages):
            filename = os.path.basename(conda_package)
            known_packages.add(self.package_name(filename))
            shutil.copyfile(conda_package, os.path.join(conda_package_dest, filename))
        
        print(f'Packages in {conda_package_dest}')
        for p in sorted(os.listdir(conda_package_dest)):
            print(f'  - {p}')

    windows_install_script = """@echo off
if "%~1"=="" (
  echo "install target_dir [ccdc_packages_and_package_name_pairs...]"
  goto end
)
setlocal
set installer_dir=%~dps0
set target_miniconda=%~1
echo "CCDC Miniconda installer: running installer"
start /wait "" "%installer_dir%{{ installer_exe }}" /AddToPath=0 /S /D=%~s1
if errorlevel 1 (
   echo Miniconda failed to install: %errorlevel%
   exit /b %errorlevel%
)
echo "CCDC Miniconda installer: activating conda environment"
call "%target_miniconda%\\Scripts\\activate"
echo "CCDC Miniconda installer: updating conda"
call conda update -y --channel "%installer_dir%conda_offline_channel" --offline --override-channels -q conda
echo "CCDC Miniconda installer: updating all packages"
call conda update -y --channel "%installer_dir%conda_offline_channel" --offline --override-channels -q --all
echo "CCDC Miniconda installer: installing required packages"
call conda install -y --channel "%installer_dir%conda_offline_channel" --offline --override-channels -q {{ conda_packages }}
shift
:next_package
if not "%1" == "" (
    call conda install -y --channel "%installer_dir%%1_conda_channel" --offline --override-channels -q %2
    shift
    shift
    goto next_package
)
echo "CCDC Miniconda installer: copying condarc"
copy "%installer_dir%\\condarc-for-offline-installer-creation" "%target_miniconda%\\condarc"
endlocal
:end
"""

    unix_install_script = """#!/bin/sh
if test $# -eq 0 ; then
    echo 'install target_dir [ccdc_packages_and_package_name_pairs...]'
    exit 1
fi
INSTALLER_DIR=$(dirname -- "$0")
TARGET_MINICONDA=$1
chmod +x "$INSTALLER_DIR/{{ installer_exe }}"
unset PYTHONPATH
unset PYTHONHOME
echo "CCDC Miniconda installer: running installer"
"$INSTALLER_DIR/{{ installer_exe }}" -b -p "$TARGET_MINICONDA"
echo "CCDC Miniconda installer: activating conda environment"
. "$TARGET_MINICONDA/bin/activate" ""
echo 'CCDC Miniconda installer: Updating conda'
conda update -y --channel "$INSTALLER_DIR/conda_offline_channel" --offline --override-channels -q conda
[ $? -eq 0 ] || exit $?; # exit if non-zero return code
echo 'CCDC Miniconda installer: Updating all packages'
conda update -y --channel "$INSTALLER_DIR/conda_offline_channel" --offline --override-channels -q --all
[ $? -eq 0 ] || exit $?; # exit if non-zero return code
echo 'CCDC Miniconda installer: Installing required packages'
conda install -y --channel "$INSTALLER_DIR/conda_offline_channel" --offline --override-channels -q {{ conda_packages }}
[ $? -eq 0 ] || exit $?; # exit if non-zero return code

shift
while test $# -gt 1
do
    conda install -y --channel "$INSTALLER_DIR/$1_conda_channel" --offline --override-channels -q $2
    [ $? -eq 0 ] || exit $?; # exit if non-zero return code
    shift
    shift
done
echo "CCDC Miniconda installer: copying condarc"
cp "$INSTALLER_DIR/condarc-for-offline-installer-creation" "$TARGET_MINICONDA/condarc"
"""

    def write_install_script(self):
        if sys.platform == 'win32':
            script = self.windows_install_script
        else:
            script = self.unix_install_script
        script = script.replace('{{ installer_exe }}', '"'+self.installer_name+'"')
        script = script.replace('{{ conda_packages }}', ' '.join(['"'+pkg+'"' for pkg in required_offline_conda_packages()]))
        with open(self.install_script_path, "w") as f:
            f.write(script)
        if sys.platform != 'win32':
            os.chmod(self.install_script_path, 0o755)
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'condarc-for-offline-installer-creation'), self.output_dir)

    def test_install_script(self):
        '''Run the install script on a temporary directory'''
        with tempfile.TemporaryDirectory() as tmpdirname:
            args = [
                os.path.abspath(self.install_script_path),
                os.path.join(tmpdirname, 'miniconda')
            ]
            print(args)
            print(self.output_dir)
            subprocess.check_call(args, cwd=self.output_dir)
            print('Finished install successfully')

            if sys.platform == 'win32':
                test_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'smoke_test.bat')
            else:
                test_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'smoke_test.sh')
            subprocess.check_call([test_script, os.path.join(tmpdirname, 'miniconda')])

    def pin_python_version(self):
        pinned_python = 'python 3.7'
        pin_file = os.path.join(self.build_install_dir, 'conda-meta', 'pinned')
        with open(pin_file, "w") as pinned:
            pinned.write(f"{pinned_python}\n")

    def install_miniconda(self):
        print('Running %s' % self.install_args)
        outcome = subprocess.call(self.install_args)

        if IS_WINDOWS:
            self._clean_up_system_path()

        if outcome != 0:
            raise RuntimeError('Failed to run "{0}"'.format(self.install_args))

    @property
    def install_args(self):
        if IS_WINDOWS:
            install_args = [self.output_installer,
                            '/S',     # run install in batch mode (without manual intervention)
                            '/D=' + os.path.abspath(self.build_install_dir)]
        else:
            install_args = ['sh',
                            self.output_installer,
                            '-b',     # run install in batch mode (without manual intervention)
                            '-f',     # no error if install prefix already exists
                            '-p', os.path.abspath(self.build_install_dir)]
        return install_args

    def _clean_up_system_path(self):
        """The Windows installer modifies the PATH env var, so let's
        revert that using the same mechanism.
        """
        for_all_users = (not os.path.exists(
            os.path.join(self.build_install_dir, '.nonadmin')))

        remove_from_system_path(self.build_install_dir,
                                for_all_users,
                                'PATH')
        remove_from_system_path(os.path.join(self.build_install_dir, 'Scripts'),
                                for_all_users,
                                'PATH')
        broadcast_environment_settings_change()

    def conda_install(self, *package_specs):
        """Install a conda package given its specifications.
        E.g. self.conda_install('numpy==1.9.2', 'lxml')
        """
        self._run_pkg_manager('conda', ['install', '-y', '-q'], *package_specs)

    def _run_pkg_manager(self, pkg_manager_name, extra_args, *package_specs):
        my_env = os.environ.copy()
        # Set the condarc to the channels we want
        my_env["CONDARC"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'condarc-for-offline-installer-creation')
        # add Library\bin to path so that conda can find libcrypto
        if IS_WINDOWS:
            my_env['PATH'] = "%s;%s" % (os.path.join(self.build_install_dir, 'Library', 'bin'), my_env['PATH'])
        args = [self._args_for(pkg_manager_name)] + extra_args + list(package_specs)
        outcome = subprocess.call(args, env=my_env)
        if outcome != 0:
            print('_run_pkg_manager fail info')
            print(args)
            print(my_env)
            raise RuntimeError('Could not install {0} with {1}'.format(' '.join(package_specs), pkg_manager_name))

    def _args_for(self, executable_name):
        return os.path.join(self.build_install_dir,
                            ('Scripts' if IS_WINDOWS else 'bin'),
                            executable_name + ('.exe' if IS_WINDOWS else ''))

    def check_condarc_presence(self):
        for path in [
            '/etc/conda/.condarc',
            '/etc/conda/condarc',
            '/etc/conda/condarc.d/',
            '/var/lib/conda/.condarc',
            '/var/lib/conda/condarc',
            '/var/lib/conda/condarc.d/',
            '~/.conda/.condarc',
            '~/.conda/condarc',
            '~/.conda/condarc.d/',
            '~/.condarc',
            ]:
            if os.path.exists(os.path.expanduser(path)):
                print('Conda configuration found in %s. This might affect installation of packages' % path)

    def build(self):
        #print('Test install script')
        #self.test_install_script()
        #sys.exit()

        # Set the variable in the azure pipeline so that the archiving stage later can pick up the right version
        print(f"##vso[task.setvariable variable=miniconda_installer_version]{miniconda_installer_version()}", flush=True)

        print('##[group]Cleaning up build and output directories', flush=True)
        self.clean_build_and_output()
        os.makedirs(self.build_install_dir)
        os.makedirs(self.output_dir)
        time.sleep(0.5)
        print('##[endgroup]')

        print('##[group]Getting installer', flush=True)
        self.fetch_miniconda_installer()
        time.sleep(0.5)
        print('##[endgroup]')

        print('##[group]Check there are no condarc files around', flush=True)
        self.check_condarc_presence()
        time.sleep(0.5)
        print('##[endgroup]')

        print('##[group]Install miniconda in the build directory', flush=True)
        self.install_miniconda()
        time.sleep(0.5)
        print('##[endgroup]')

        print('##[group]Remove conda packages that were part of the installer', flush=True)
        self.conda_cleanup()
        time.sleep(0.5)
        print('##[endgroup]')

        print('##[group]Update conda', flush=True)
        self.conda_update_conda()
        time.sleep(0.5)
        print('##[endgroup]')

        print('##[group]Fetch packages', flush=True)
        self.conda_install(*required_offline_conda_packages())
        time.sleep(0.5)
        print('##[endgroup]')

        print('##[group]Download updates so that we can distribute them consistently', flush=True)
        self.conda_update_all()
        time.sleep(0.5)
        print('##[endgroup]')

        print('##[group]Pin python version in the installed conda environment', flush=True)
        self.pin_python_version()
        time.sleep(0.5)
        print('##[endgroup]')

        print('##[group]Copy packages to output directory', flush=True)
        self.copy_packages()
        time.sleep(0.5)
        print('##[endgroup]')

        print('##[group]Install conda-build in order to index the offline channel', flush=True)
        self.conda_install('conda-build')
        time.sleep(0.5)
        print('##[endgroup]')

        print('##[group]Create index of offline channel', flush=True)
        self.conda_index(self.output_conda_offline_channel)
        time.sleep(0.5)
        print('##[endgroup]')

        print('##[group]Create install script', flush=True)
        self.write_install_script()
        time.sleep(0.5)
        print('##[endgroup]')

        print('##[group]Test install script', flush=True)
        self.test_install_script()
        time.sleep(0.5)
        print('##[endgroup]')

if __name__ == '__main__':
    MinicondaOfflineInstaller().build()


