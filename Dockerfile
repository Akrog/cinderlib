# Based on centos this image builds cinderlib master with Cinder master branch
FROM centos:7
ARG VERSION
ARG RELEASE
LABEL maintainers="Gorka Eguileor <geguileo@redhat.com>" \
      description="Cinderlib" \
      version=${VERSION:-master}

RUN yum -y install targetcli iscsi-initiator-utils device-mapper-multipath epel-release lvm2 which && \
    yum -y install python2-pip python-devel gcc openssl-devel pywbem && \
    yum -y install python-rbd ceph-common git && \
    # Need new setuptools version or we'll get "SyntaxError: '<' operator not allowed in environment markers" when installing Cinder
    pip install 'setuptools>=38.6.0' && \
    git clone 'https://github.com/openstack/cinder.git' && \
    pip install --no-cache-dir cinder/ && \
    pip install --no-cache-dir 'krest>=1.3.0' 'purestorage>=1.6.0' 'pyxcli>=1.1.5' 'pyOpenSSL>=1.0.0' && \
    rm -rf cinder && \
    yum -y remove git python-devel gcc openssl-devel && \
    yum clean all && \
    rm -rf /var/cache/yum

# Copy cinderlib
COPY . /cinderlib

RUN pip install --no-cache-dir /cinderlib/ && \
    rm -rf /cinderlib

# Define default command
CMD ["bash"]
