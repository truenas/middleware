CPU temperature reporting on a VM
=================================

Running this script will fake a 4-core constant temperature reporting on a VM:

.. code-block:: bash

    midclt call test.set_mock reporting.cpu_temperatures 'def mock(*args): return {0: 50, 1: 60, 2: 55, 3: 55}'

To undo the fake (or before changing temperature values) run

.. code-block:: bash

    midclt call test.remove_mock reporting.cpu_temperatures
