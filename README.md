# Conda Charmer's Corner

A project to create offline miniconda installers for use by the CSD System installer

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