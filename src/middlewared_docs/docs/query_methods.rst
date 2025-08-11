Query Methods
-------------

TrueNAS API has multiple query methods including `pool.query`, `disk.query`, `vm.query`, and many more.

The arguments for these methods support multiple options and filters that are similar to SQL queries.

Query Filters
=============

Basic Usage
***********

Query Filters are primarily an array of conditions, with each condition also represented as an array.

Each condition in the filter list should compare a field with a value.

eg. Filter Syntax: `["field", "operator", value]`

For example, to filter the data returned by `disk.query`, we provide a list of conditions:

Javascript:

.. code:: javascript
    [
      ["name","=","ada1"]
    ]


Supported Operators
*******************

========  =====================
Operator  Javascript equivalent
========  =====================
``=``     ``x === y``
``!=``    ``x !== y``
``>``     ``x > y``
``>=``    ``x >= y``
``<``     ``x < y``
``<=``    ``x <= y``
``~``     ``y.test(x)``
``in``    ``y.includes(x)``
``nin``   ``!y.includes(x)``
``rin``   ``x != null && x.includes(y)``
``rnin``  ``x != null && !x.includes(y)``
``^``     ``x != null && x.startsWith(y)``
``!^``    ``x != null && !x.startsWith(y)``
``$``     ``x != null && x.endsWith(y)``
``!$``    ``x != null && !x.endsWith(y)``
========  =====================

Specifing the prefix 'C' will perform a case-insensitive version of the filter, e.g. `C=`.

Multiple Filters
****************

We can use `disk.query` with the "type" and "rotationrate" filters to find hard drives with a rotation rate higher than 5400 RPM:

Javascript:

.. code:: javascript
    [
      ["type","=","HDD"],
      ["rotationrate",">",5400]  // Note that the value should be the correct type
    ]


Connectives
***********

Queries with no explicitly defined logical connectives assume conjunction `AND`. The disjunction `OR` is also supported by using the syntax illustrated below. We can use `disk.query` with `OR` to filter disks by name. Note that the operand for the disjunction contains an array of conditions.

The following is a valid example.
Javascript:

.. code:: javascript
    [
      "OR",
      [
        ["name", "=", "first"],
        ["name", "=", "second"],
      ]
    ]

The following is also a valid example that returns users that are unlocked and either have password-based authentication for SSH enabled or are SMB users.
Javascript:

.. code:: javascript
    [
      [
        "OR",
        [
          ["ssh_password_enabled", "=", true],
          ["smb", "=", true]
        ]
      ],
      ["locked", "=", false]
    ]

The following is valid example that returns users who are either enabled or have password authentication enabled with two-factor authentication disabled.

Javascript:

.. code:: javascript
    [
      "OR",
      [
        [
          ["ssh_password_enabled", "=", true],
          ["twofactor_auth_configured", "=", false]
        ],
        ["enabled", "=", true],
      ]
    ]

Some additional examples of connective use are as follows.

These filters when used with `user.query` finds unlocked users with password authentication enabled and two-factor authentication disabled.

Javascript:

.. code:: javascript
    [
      ["ssh_password_enabled", "=", true],
      ["twofactor_auth_configured", "=", false],
      ["locked", "=", false]
    ]


Sub-keys in complex JSON objects may be specified by using dot (".") to indicate the key. For example the following query-filters if passed to `user.query` endpoint will return entries with a primary group ID of 3000.

Javascript:

.. code:: javascript
    [
      ["group.bsdgrp_gid", "=", 3000],
    ]

If a key contains a literal dot (".") in its name, then it must be escaped via a double backslash.

Javascript:

.. code:: javascript
    [
      ["foo\\.bar", "=", 42],
    ]


When the path to the key contains an array, an array index may be manually specified. For example, the following query-filters
if passed to the `privilege.query` endpoint will return entries where the first element of the local groups array has a name
of "myuser".

Javascript:

.. code:: javascript
    [
      ["local_groups.0.name", "=", "myuser"],
    ]

Alternatively, an asterisk (`*`) may be substituted for the array index, which match any entry where an array member has a key matching the value. for example, the following query-filters if passed to the `privilege.query` endpoint will return entries where any member of the local groups array has a `name` key with the value of `myuser`.

Javascript:

.. code:: javascript
    [
      ["local_groups.*.name", "=", "myuser"],
    ]


Datetime information
********************

Some query results may include datetime information encoded in JSON object via
key with designator `.$date`. In this case, query filter using an ISO-8601
timestamp may be used. For example:

Javascript:

.. code:: javascript
    [
      ['timestamp.$date', '>', '2023-12-18T16:15:35+00:00']
    ]


Query Options
=============

Query Options are objects that can further customize the results returned by a Query Method.

Properties of a Query Option include `extend | extend_context | prefix | extra | order_by | select | count | get | limit | offset`

Count
*****

Use the `count` option to get the number of results returned.

Javascript:

.. code:: javascript
    {
      "count": true
    }


Limit
*****

Use the `limit` option to limit the number of results returned.

Javascript:

.. code:: javascript
    {
      "limit": 5
    }


Offset
******

Use the `offset` option to remove the first items from a returned list.

Javascript:

.. code:: javascript
    {
      "offset": 1  // Omits the first item from the query result
    }


Select
******

Use the `select` option to specify the exact fields to return. Fields must be provided in an array of strings. The dot character (".") may be used to explicitly select only subkeys of the query result.

Fields returned may be renamed by specifing an array containing two strings with the first string being the field to select from results list and the second string indicating the new name to provide it.

Javascript:

.. code:: javascript
    {
      "select": ["devname", "size", "rotationrate"]
    }


Javascript:

.. code:: javascript
    {
      "select": [
        "Authentication.status",
        "Authentication.localAddress",
        "Authentication.clientAccount"
      ]
    }


Javascript:

.. code:: javascript
    {
      "select": [
        ["Authentication.status", "status"],
        ["Authentication.localAddress", "address"],
        ["Authentication.clientAccount", "username"]
      ]
    }


Order By
********

Use the `order_by` option to specify which field determines the sort order. Fields must be provided in an
array of strings.

The following prefixes may be applied to the field name:

`-` reverse sort direction.

`nulls_first:` place any NULL values at head of results list.

`nulls_last:` place any NULL values at tail of results list.

Javascript:

.. code:: javascript
    {
      "order_by": ["size", "-devname", "nulls_first:-expiretime"]
    }


Sample SQL statements translated into Query Filters and Query Options
*********************************************************************

NOTE: these are examples of syntax translation, they are not intended as queries
to perform on the TrueNAS server.


"SELECT * FROM table;"
^^^^^^^^^^^^^^^^^^^^^^

`query-filters`

Javascript:

.. code:: javascript
    []


`query-options`

Javascript:

.. code:: javascript
    {}


"SELECT username,uid FROM table WHERE builtin=FALSE ORDER BY -uid;"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`query-filters`

Javascript:

.. code:: javascript
    [
      ["builtin", "=", false],
    ]

`query-options`

Javascript:

.. code:: javascript
    {
      "select": [
        "username",
        "uid"
      ],
      "order_by": [
        "-uid"
      ]
    }


"SELECT username AS locked_user,uid FROM table WHERE builtin=FALSE AND locked=TRUE;"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`query-filters`

Javascript:

.. code:: javascript
    [
      ["builtin", "=", false],
      ["locked", "=", true]
    ]

`query-options`

Javascript:

.. code:: javascript
    {
      "select": [
        [
          "username",
          "locked_user"
        ],
        "uid"
      ],
    }


"SELECT username FROM table WHERE builtin=False OR (locked=FALSE AND ssh=TRUE);"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`query-filters`

Javascript:

.. code:: javascript
    [
      [
        "OR",
        [
          ["builtin", "=", false],
          [
            ["locked", "=", false],
            ["ssh", "=" true]
          ]
        ]
      ],
    ]

`query-options`

Javascript:

.. code:: javascript
    {
      "select": [
        "username"
      ],
    }
