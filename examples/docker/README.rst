==============
Docker example
==============

This Vagrant file deploys a small VM (1GB and 1CPU) with cinderlib in a
container and with LVM properly configured to be used by the container.

This makes it really easy to use the containerized version of cinderlib:

.. code-block:: shell

   $ vagrant up
   $ vagrant ssh -c 'sudo docker exec -it cinderlib python'


Once we've run those two commands we are in a Python interpreter shell and can
run Python code to use the LVM backend:

.. code-block:: python

   import cinderlib as cl

   # Initialize the LVM driver
   lvm = cl.Backend(volume_driver='cinder.volume.drivers.lvm.LVMVolumeDriver',
                    volume_group='cinder-volumes',
                    target_protocol='iscsi',
                    target_helper='lioadm',
                    volume_backend_name='lvm_iscsi')

   # Create a 1GB volume
   vol = lvm.create_volume(1)

   # Export, initialize, and do a local attach of the volume
   attach = vol.attach()

   print('Volume %s attached to %s' % (vol.id, attach.path))

   # Detach it
   vol.detach()

   # Delete it
   vol.delete()
