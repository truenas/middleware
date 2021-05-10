## Query Methods

TrueNAS API has multiple query methods including `pool.query`, `disk.query`, `vm.query`, and many more.

The arguments for these methods support multiple options and filters that are similar to SQL queries.

### Query Filters

#### Basic Usage

Query Filters are primarily an array of conditions, with each condition also represented as an array.

Each condition in the filter list should compare a field with a value.

eg. Filter Syntax: `["field", "operator", value]` 

For example, to filter the data returned by `disk.query`, we provide a list of conditions:

Javascript:
    :::javascript
    [
      ["name","=","ada1"] 
    ]


#### Supported Operators
| Operator       | Description     |
| :------------- | :----------: |
| '=' |  x == y |
| '!=' |  x != y |
| '>' |  x > y |
| '>=' |  x >= y |
| '<' |  x < y |
| '<=' |  x <= y |
| '~' |  re.match(y, x) |
| 'in' |  x in y |
| 'nin' |  x not in y |
| 'rin' |  x is not None and y in x |
| 'rnin' |  x is not None and y not in x |
| '^' |  x is not None and x.startswith(y) |
| '!^' |  x is not None and not x.startswith(y) |
| '$' |  x is not None and x.endswith(y) |
| '!$' |  x is not None and not x.endswith(y) |

#### Multiple Filters

We can use `disk.query` with the "type" and "rotationrate" filters to find hard drives with a rotation rate higher than 5400 RPM:

Javascript:
    :::javascript
    [
      ["type","=","HDD"],
      ["rotationrate",">",5400] // Note that the value should be the correct type
    ]


#### Conjunctions

Queries with no defined conjunction assume `AND`. However, the conjunction `OR` is also supported by using the syntax illustrated below. We can use `chart.release.query` with `OR` to filter chart releases by name.

Javascript:
    :::javascript
    ["OR", 
      [
        ["name","=", "firstchart"],
        ["name","=", "secondchart"],
      ]
    ]


### Query Options

Query Options are objects that can further customize the results returned by a Query Method.

Properties of a Query Option include `extend | extend_context | prefix | extra | order_by | select | count | get | limit | offset`

#### Count

Use the `count` option to get the number of results returned.

Javascript:
    :::javascript
    {
      "count": true
    }


#### Limit

Use the `limit` option to limit the number of results returned.

Javascript:
    :::javascript
    {
      "limit": 5
    }


#### Offset

Use the `offset` option to remove the first items from a returned list.

Javascript:
    :::javascript
    {
      "offset": 1 // Omits the first item from the query result
    }


#### Select

Use the `select` option to specify the exact fields to return. Fields must be provided in an array of strings.

Javascript:
    :::javascript
    {
      "select": ["devname","size","rotationrate"]
    }


#### Order By

Use the `order_by` option to specify which field determines the sort order.

Javascript:
    :::javascript
    {
      "order_by": "size" // field name
    }



    




