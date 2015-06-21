===========
pySMART
===========
Copyright (C) 2015 Marc Herndon

pySMART is a simple Python wrapper for the ``smartctl`` component of
``smartmontools``. It works under Linux and Windows, as long as smartctl is on
the system path. Running with administrative rights is strongly recommended,
as smartctl cannot accurately detect all device types or parse all SMART
information without these permissions.

With only a device's name (ie: /dev/sda, pd0), the package will create a
``Device`` object, populated with all relevant information about that
device. The documented API can then be used to query this object for
information, initiate self-tests, and perform other functions.

Usage
=====
The most common way to use pySMART is to create a logical representation of the
physical storage device that you would like to work with, as shown::

    >>> from pySMART import Device
    >>> sda = Device('/dev/sda')
    >>> sda
    <SATA device on /dev/sda mod:WDC WD5000AAKS-60Z1A0 sn:WD-WCAWFxxxxxxx>

``Device`` class members can be accessed directly, and a number of helper methods
are provided to retrieve information in bulk.  Some examples are shown below::

    >>> sda.assessment  # Query the SMART self-assessment
    'PASS'
    >>> sda.attributes[9]  # Query a single SMART attribute
    <SMART Attribute 'Power_On_Hours' 068/000 raw:23644>
    >>> sda.all_attributes()  # Print the entire SMART attribute table
    ID# ATTRIBUTE_NAME          CUR WST THR TYPE     UPDATED WHEN_FAIL    RAW
      1 Raw_Read_Error_Rate     200 200 051 Pre-fail Always  -           0
      3 Spin_Up_Time            141 140 021 Pre-fail Always  -           3908
      4 Start_Stop_Count        098 098 000 Old_age  Always  -           2690
      5 Reallocated_Sector_Ct   200 200 140 Pre-fail Always  -           0
        ... # Edited for brevity
    199 UDMA_CRC_Error_Count    200 200 000 Old_age  Always  -           0
    200 Multi_Zone_Error_Rate   200 200 000 Old_age  Offline -           0
    >>> sda.tests[0]  # Query the most recent self-test result
    <SMART Self-test [Short offline|Completed without error] hrs:23734 LBA:->
    >>> sda.all_selftests()  # Print the entire self-test log
    ID Test_Description Status                        Left Hours  1st_Error@LBA
     1 Short offline    Completed without error       00%  23734  -
     2 Short offline    Completed without error       00%  23734  -
       ... # Edited for brevity
     7 Short offline    Completed without error       00%  23726  -
     8 Short offline    Completed without error       00%  1      -

Alternatively, the package provides a ``DeviceList`` class. When instantiated,
this will auto-detect all local storage devices and create a list containing
one ``Device`` object for each detected storage device::

    >>> from pySMART import DeviceList
    >>> devlist = DeviceList()
    >>> devlist
    <DeviceList contents:
    <SAT device on /dev/sdb mod:WDC WD20EADS-00R6B0 sn:WD-WCAVYxxxxxxx>
    <SAT device on /dev/sdc mod:WDC WD20EADS-00S2B0 sn:WD-WCAVYxxxxxxx>
    <CSMI device on /dev/csmi0,0 mod:WDC WD5000AAKS-60Z1A0 sn:WD-WCAWFxxxxxxx>
    >
    >>> devlist.devices[0].attributes[5]  # Access Device data as above
    <SMART Attribute 'Reallocated_Sector_Ct' 173/140 raw:214>

Using the pySMART wrapper, Python applications be be rapidly developed to take
advantage of the powerful features of smartmontools.

Installation
============
``pySMART`` is available on PyPI and installable via ``pip``::

    python -m pip install pySMART

The only external dependency is the ``smartctl`` component of the smartmontools
package.  This should be pre-installed in most Linux distributions, or it
can be obtained through your package manager.  Likely one of the following::

    apt-get install smartmontools
        or
    yum install smartmontools

On Windows PC's, smartmontools must be downloaded and installed.  The latest
version can be obtained from the project's homepage, http://www.smartmontools.org/.

Note that after installing smartmontools on Windows, the directory containing
``smartctl.exe`` must be added to the system path, if it is not already.

Documentation
=============
API documentation for ``pySMART`` was generated using ``pdoc`` and can be
found in the /docs folder within the package archive.

Acknowledgements
================
I would like to thank the entire team behind smartmontools for creating and
maintaining such a fantastic product.

In particular I want to thank Christian Franke, who maintains the Windows port
of the software.  For several years I have written Windows batch files that
rely on smartctl.exe to automate evaluation and testing of large pools of
storage devices.  Without his work, my job would have been significantly
more miserable. :)

Having recently migrated my script development from Batch to Python for Linux
portabiity, I thought a simple wrapper for smartctl would save time in the
development of future automated test tools.

Final Note on Licensing
=======================
If you are reading this and thinking that you'd love to use pySMART if only
it weren't "restricted" by GPL licensing, please contact me. I am very
willing to make the code available privately under a more permissive
license, including for some corporate or commercial uses. I'd just like for
you to say hello first, and tell me a bit about your project and how pySMART
could fit into it. Odds are I'd be happy to help.

I've been contacted with similar requests a handful of times previously, so
I decided to add this note in case there are others out there afraid to ask.