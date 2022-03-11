# CCDC Python API Dockerfile

This Dockerfile is to build the CCDC Pyhton API from a base-python artifact and a ccdc python api artifact.

## Bill of Materials

The following artifacts are required to build this container:

- [Base python artifact]()
- [CCDC Python API artifact]()

This was tested with

- base python version 4.9.2-20528 
- python api version 3.0.10

!!! Note
    Ideally the Python API artifacts would end up in artifactory as a pip installable for us to use here. Once it's in Artifactory (any format) we can enable this to be built using GitHub Actions. While the artifacts are still being pushed to the artifact share this is not possible.

## Running

To build the container, place the artifacts in the directory alongside the Dockerfile, then run:

```sh
docker build . -t csd-python-api:latest
```

One can run the container as you would any other at this point. However it is recommended to use [docker-compose](../docker-compose) instead as this manages licensing configuration and database mounts in a more user friendly way. 
