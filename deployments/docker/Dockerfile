FROM centos:centos7
# FROM rockylinux:8   # This works if anyone wants to use a good OS.
WORKDIR /ccdc

# To get the Docking API working quietly:
ENV CSDHOME=/ccdc
ENV XDG_RUNTIME_DIR=/tmp/runtime-root
RUN mkdir -p ${XDG_RUNTIME_DIR} && chmod 0700 ${XDG_RUNTIME_DIR}

# Install specific Python3.7 and required system packages then clean up to save space
RUN yum -y install \
    unzip \
    findutils \
    zlib-devel \
    libffi-devel \
    bzip2-devel \
    openssl-devel \
    ncurses-devel \
    sqlite-devel \
    readline-devel \
    tk-devel \
    gdbm-devel \
    libuuid-devel \
    xz-devel \
    mesa-libGL \
    libglvnd-opengl \
    && yum clean all

###############################################
#    Install Conda Python & API Components    #
###############################################

# Copy and install base python first
COPY ./csd-python-api-*.tar.gz ./csd-python-api-env.tar.gz
RUN tar -zxf ./csd-python-api-env.tar.gz && \
    cd $(find . -maxdepth 1 -type d -name 'csd-python-api*' | head -1) && \
    ./install.sh /ccdc/csd-python-api csd-python-api && \
    rm -rf /ccdc/csd-python-api-miniconda3-*-linux /ccdc/csd-python-api-env.tar.gz

# Then copy and install the CCDC Python API
COPY ./csd-python-api-*.zip ./csd-python-api-package.zip
RUN unzip ./csd-python-api-package.zip && \
    source /ccdc/csd-python-api/bin/activate && \
    conda install -c ./ccdc_conda_channel csd-python-api && \
    rm -rf ./csd-python-api-package.zip ccdc_conda_channel

# We want every invoked bash shell to have an activated python environment. 
# We also want every invocation of python to use CCDC base python
RUN echo "source /ccdc/csd-python-api/bin/activate" >> /etc/bashrc && \
    ln -s /ccdc/csd-python-api/bin/python /usr/bin/python

CMD ["tail", "-f", "/dev/null"]
