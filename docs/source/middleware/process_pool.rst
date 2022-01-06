Process Pool
############

.. contents:: Table of Contents
    :depth: 4

Some python libraries (namely, `py-libzfs`) are not thread-safe. Methods that use such libraries should be executed in a
separate process to avoid non-safe behavior.

Middleware services that include these methods are marked with `process_pool = True`. All their synchronous methods are
executed in a shared process pool:

  .. literalinclude:: /../../src/middlewared/middlewared/main.py
      :pyobject: Middleware.__init_procpool
      :caption:

Eliminating deadlocks
*********************

All asynchronous methods of process pool-powered services (including inherited ones) need to have their synchronous
version named `{method}__sync`. The most important example is `CRUDService.get_instance__sync`.

Why is this needed? Imagine we have a `ZFSSnapshot` service that uses a process pool. Let's say its `create` method
calls `zfs.snapshot.get_instance` to return the result. That call will have to be forwarded to the main middleware
process, which will call `zfs.snapshot.query` in the process pool. If the process pool is already exhausted, it will
lead to a deadlock.

By executing a synchronous implementation of the same method in the same process pool we eliminate **Hold and wait**
condition and prevent deadlock situation from arising.
