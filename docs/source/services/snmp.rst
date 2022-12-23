SNMP
====

.. contents:: Table of Contents
    :depth: 3

TrueNAS uses the standard Linux `net-snmp <http://www.net-snmp.org/>`_ daemon and a custom `snmp-agent` written in
Python that exposes more properties through a custom TrueNAS MIB.

Modifying TrueNAS MIB
---------------------

You'll need to have `smitools` package installed and `libsmi2pysnmp` downloaded.

.. code-block:: bash

     wget https://raw.githubusercontent.com/xfguo/pysnmp/master/tools/libsmi2pysnmp -O /usr/bin/libsmi2pysnmp && chmod +x /usr/bin/libsmi2pysnmp

To validate custom MIB syntax use:

.. code-block:: bash

    smilint src/freenas/usr/local/share/snmp/mibs/TRUENAS-MIB.txt

All changes made to this MIB must be reflected in `src/freenas/usr/local/share/pysnmp/mibs/FREENAS-MIB.py` file that is
used by our custom `snmp-agent.py`. This file is auto-generated, just run

.. code-block:: bash

    smidump -f python /root/freenas/freenas/src/freenas/usr/local/share/snmp/mibs/TRUENAS-MIB.txt | libsmi2pysnmp > /root/freenas/freenas/src/freenas/usr/local/share/pysnmp/mibs/TRUENAS-MIB.py
