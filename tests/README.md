# FreeNAS REST API test
This is the folder of all tests for FreeNAS REST API testing.

## Dependency REST API tests

### Require dependency run

```
Python 3.6
Pytest
Requests
```

### Extra for manual debugging

```
IPython
```

### Installing of dependency on FreeBSD/TrueOS/Trident/GhostBSD

#### Require packages
`pkg install python36 py36-pytest py36-requests`

#### Extra packages
`pkg install py36-ipython`

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

## Running manual REST API test with IPython
Once runtest.py is run, it did generate all configuration, and running IPython can be run to debug REST API or just to run manual REST API.

### Example
```
ipython-3.6         Fri Sep  7 12:32:12 2018
Password:
Python 3.6.6 (default, Jul 30 2018, 22:10:00)
Type "copyright", "credits" or "license" for more information.

IPython 5.8.0 -- An enhanced Interactive Python.
?         -> Introduction and overview of IPython's features.
%quickref -> Quick reference.
help      -> Python's own help system.
object?   -> Details about 'object', use 'object??' for extra details.

In [1]: from functions import GET, POST, PUT, DELETE

In [2]: GET("/bootenv/").json()
Out[2]:
[{'realname': 'default',
  'name': 'default',
  'active': 'NR',
  'mountpoint': '/',
  'space': '883.8M',
  'created': {'$date': 1536319800000},
  'keep': None,
  'rawspace': '926877696',
  'id': 'default'},
 {'realname': 'Initial-Install',
  'name': 'Initial-Install',
  'active': '-',
  'mountpoint': '-',
  'space': '1.8M',
  'created': {'$date': 1536319980000},
  'keep': None,
  'rawspace': '1024',
  'id': 'Initial-Install'}]

In [3]: payload = {"name": "bootenv1", "source": "default"}

In [4]: results = POST("/bootenv/", payload)

In [5]: results
Out[5]: <Response [200]>

In [6]: results.json()
Out[6]: 'bootenv1'

In [7]: results.text
Out[7]: '"bootenv1"'

In [8]: results.status_code
Out[8]: 200

In [9]:
```

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

