#!/usr/bin/env bash

# Must be run as root

dd if=/dev/zero of=cinder-volumes bs=1048576 seek=22527 count=1
lodevice=`losetup --show -f ./cinder-volumes`
pvcreate $lodevice
vgcreate cinder-volumes $lodevice
vgscan --cache
