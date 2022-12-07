# FreeNAS REST API test
This is the folder of all tests for FreeNAS REST API testing.

## Dependency REST API tests

### Require dependency run

```
Python 3 pip
samba
sshpass
smbclient
snmpwalk
```

### Installing of dependency on FreeBSD base OS

#### Require packages
`pkg install py39-pip samba* sshpass net-snmp pkgconf libiscsi`

In middleware/tests run the command bellow

`pip install -r requirements.txt`

### Installing of dependency on Debian base OS

#### Require packages

`apt install python3-pip samba smbclient sshpass snmp libiscsi-dev`

In middleware/tests run the command bellow

`pip3 install -r requirements.txt`


## Running REST API test
All the test suite is run from runtests.py the usage of runtests.py is as follow:

```
freenas/tests/api% ./runtest.py
Usage for ./runtest.py:
Mandatory option
    --ip <###.###.###.###>     - IP of the FreeNAS
    --password <root password> - Password of the FreeNAS root user
    --interface <interface>    - The interface that FreeNAS is run one

Optional option
    --test <test name>         - Test name (Network, ALL)
    --api <version number>     - API version number (1.0, 2.0)

```

### Example of command

The default command API test default to API v1.0:

`./runtests.py --ip 192.168.2.45 --interface em0 --password testing`

Command to run REST API v2.0 test:

`./runtests.py --ip 192.168.2.45 --interface em0 --password testing --api 2.0`

Command to run a specific REST API v1.0 or v2.0 test:

`./runtests.py --ip 192.168.2.45 --interface em0 --password testing --api 1.0 --test network`


## How REST API tests should be written?

REST API test code should be written with flake8 standard. All code lines should be under 80 character per line.

### Code example
```
#!/usr/bin/env python3.6

import sys
import os
from time import sleep

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, DELETE, GET, PUT


def test_01_creating_a_new_boot_environment():
    payload = {"name": "bootenv01", "source": "default"}
    results = POST("/bootenv/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_02_look_new_bootenv_is_created():
    assert len(GET('/bootenv?name=bootenv01').json()) == 1


def test_03_activate_bootenv01():
    payload = None
    results = POST("/bootenv/id/bootenv01/activate/", payload)
    assert results.status_code == 200, results.text


# Update tests
def test_04_cloning_a_new_boot_environment():
    payload = {"name": "bootenv02", "source": "bootenv01"}
    results = POST("/bootenv/", payload)
    assert results.status_code == 200, results.text
```

