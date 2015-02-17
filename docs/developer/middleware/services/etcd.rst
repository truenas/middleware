etcd - File generation service
==============================

*etcd* is a service which handles generation of configuration files. It can
be used to bind various system configuration settings stored in database with
their representation in configuration files. Files are generated from templates
on demand (specifically, on request through RPC interfaces).

Plugins infrastructure
~~~~~~~~~~~~~~~~~~~~~~

Templates are refferred as *plugins*. They live under one directory tree,
``/usr/local/lib/etcd/plugins`` which is modeled after ``/etc`` tree. Filename
is composed of target filename (eg. ``/etc/resolv.conf``) plus extension
for desired template format. Configuration files living inside ``/usr/local/etc``
should be placed in ``/usr/local/lib/etcd/plugins/local``

Currently supported template formats:

* .mako
* .py

