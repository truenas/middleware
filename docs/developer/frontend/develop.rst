.. highlight:: javascript
   :linenothreshold: 5

Developing for FreeNAS 10
=========================

Make Changes
------------

You're now ready to begin developing the new FreeNAS GUI. After running
``grunt``, any changes you make to watched files will immediately be
copied to the FreeNAS instance and if necessary, node will be restarted
to implement the changes.

If you don't need to modify your existing grunt config because your dev
environment is stable, you can run ``grunt --silent`` to skip the user
interaction.
