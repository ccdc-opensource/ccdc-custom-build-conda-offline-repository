# Conda Charmer's Corner

A project to create offline miniconda installers for use by the CSD System installer

## Getting Started

- Clone this repository locally
- run git submodule update to fetch the repodata-hotfixes repository contents
- Create a python3 virtualenv
- pip install -r requirements.txt
- run with python create_offline_installer.py

## Changing the list of packages

- increase the MinicondaOfflineInstaller.ccdc_version variable as the output will be different
- change the base_conda_packages list in the MinicondaOfflineInstaller class
- run create_offline_installer.py
- joy

## Changing the miniconda version

- change the MinicondaOfflineInstaller.version variable
- reset the MinicondaOfflineInstaller.ccdc_version variable to '-1'
