# Conda Charmer's Corner

A project to create offline miniconda installers for use by the CSD System installer

Please follow (this workflow)[https://confluence.ccdc.cam.ac.uk/x/HBV_/] when making changes to the repository.

## Getting Started

- Clone this repository locally
- run git submodule update to fetch the repodata-hotfixes repository contents
- Create a python3 virtualenv
- pip install -r requirements.txt
- run with python create_offline_installer.py

## Changing the list of packages

- change the required_offline_conda_packages method
- run create_offline_installer.py
- push
- joy

## Changing the miniconda version

- change the default version in the miniconda_installer_version method
- test locally
- push
- edit the conda-offline-repository-creation pipeline, select variables and update the miniconda_installer_version variable to match the new version
- wait for the build
- joy

## Uploading the artefacts to build servers

### Windows

- Upload (as buildman) the contents of the zip file to \\synology02\x-mirror\x_mirror\buildman\tools\miniconda3

### Linux

- convert the zip file to a tar.gz archive
- upload the tar.gz file to artifactory here: https://artifactory.ccdc.cam.ac.uk/webapp/#/artifacts/browse/tree/General/ccdc-3rd-party-centos-6-builds
- update the roles\install_third_party\vars\main.yml file in the build_machines mercurial repository

### MacOS

- extract the contents of the zip file in /local/buildman/tools/miniconda3 on buildmac13 and buildmac15

Remember to wait for the daily x-mirror script and the linux build machine ansible updates to kick in before changing cppbuilds_shared/buildtool/environment/setup.py!!!!!

## What is the reason for the repodata-hotfixes external repository?

The initial version of this script would only use the main conda repositories to build the offline channel. These repositories contain multiple versions of packages that will not install cleanly in offline mode, unless the resulting channel files are patches with some workarounds.
The details were not documented extensively and can be found by reading through the discussion in (this bug report in the conda project)[https://github.com/conda/conda/issues/8090].

Since we started using the conda-forge channels to provide packages like docxtpl etc, and we used strict priority in favour of conda-forge channels, the fixes are no longer required.
The workaround however will be kept and commented out (see the def conda_index(self, channel): method) and the link to the external repository kept, in case we move to using the main repositories again.

There is a high chance that this will no longer be a requirement with conda 5, when that comes out. In that case, the .gitmodules file can be removed (and this will remove the repodata-hotfixes subrepository) and the commented out line removed too.