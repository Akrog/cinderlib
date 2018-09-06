#!/usr/bin/env bash
set -ev
truncate -s 10G /root/cinder-volumes
lo_dev=`losetup --show -f /root/cinder-volumes`
vgcreate cinder-volumes $lo_dev
vgscan
