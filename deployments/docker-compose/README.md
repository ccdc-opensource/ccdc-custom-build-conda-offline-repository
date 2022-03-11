# docker-compose for CDCC Python API

This contains all the relevant information to run the CCDC Python API in a container and manage that using docker-compose. Specific information about the CSD and licensing can be found in their own officail documentaiton.

## Running docker-compose

This pulls images from Artifactory, so first log in to the repo using your credentials:

```sh
docker login ccdc-docker-internal-artifactory.ccdc.cam.ac.uk
```

To bring up the container you then run:

```sh
docker-compose up -d
```

To create a shell within the container:

```sh
docker-compose exec ccdc-python-api /bin/bash
```

This will automatically source the virtual environment so any invocations of `python` will be that which already containes the CCDC Python API and relevant packages.

If you want to run a particular script against the API, you can run this without going into the container. For the file `test.py` in a local directory:

```sh
docker-compose run -v ./test.py:/ccdc/test.py ccdc-python-api python test.py
```

## Configuring the Container


### Licensing

An appropriate license needs to be set for the Python API. This is achieved through environment variables in the docker-compose file. At the top of the file there are common variables that get set in each container shown below:

```
x-common-variables: &common-variables
  CCDC_LICENSING_CONFIGURATION: "$CCDC_LICENSE"
```

Here `$CCDC_LICENSE` needs to be replaced with the full licensing string. For internal development purposes this will be in the format: `la-code;ABC123-...-XYZ789;service=ccdc-test-on-premise`. Alternatively, this can be set as a local environment variable `export CCDC_LICENSE=<license_string>` and docker-compose will pick this up and populate it. 

!!! Note
    If you change the value in the docker-compose.yml file in this repo don't commit that change. Either copy the file elsewhere (it's portable) or use the environment variable.

### Database Configuration

Database files must be put in the `./databases` directory. This will be mounted into `/CCDC/databases/` within the container. Depending on the directory structure within, you may have to edit the environment variable `CSDHOME` at the top of docker-compose.yml to point to the appropriate folder.

For the CSD itself, this may be too large to simply have a copy of in this location. Unfortunately symbolic links do not work when mounting the file as a volume in a Docker container, what happens is the link itself gets mounted and the container is looking for the linked path within its own filesystem. Hard links do seem to work, however, but use this with caution. What is recommend for now is having the database files inside this directory where possible.
