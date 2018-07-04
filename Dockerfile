# Based on centos
FROM centos:7.4.1708
LABEL maintainers="Gorka Eguileor <geguileo@redhat.com>"
LABEL description="Cinderlib"

RUN yum -y install targetcli iscsi-initiator-utils device-mapper-multipath epel-release && \
    yum -y install python2-pip centos-release-openstack-pike && \
    yum -y install openstack-cinder python-rbd ceph-common && \
    yum clean all && \
    rm -rf /var/cache/yum && \
    pip install --no-cache-dir --process-dependency-links cinderlib 'krest>=1.3.0' 'purestorage>=1.6.0'

# Define default command
CMD ["bash"]
