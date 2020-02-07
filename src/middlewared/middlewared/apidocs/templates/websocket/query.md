## Query Methods

FreeNAS API has multiple query methods including pool.query, disk.query, vm.query and many more. 

The arguments for these methods support multiple options and filters that are similar to what is available in SQL queries.

### Query Filters

#### Basic Usage

Query Filters are primarily an array of conditions, with each condition also represented as an array. 

Each condition in the filter list should compare a field with a value.

eg. Filter Syntax: `["field", "operator", value]` 

For example to filter the data returned by `disk.query`, we provide a list of conditions. 

Javascript:
    :::javascript
    [
      ["name","=","ada1"] 
    ]

Command Line: `# midclt call disk.query '[["name", "=", "ada1"]]'`

NOTE: Supported Operators include `'=' | '!=' | '>' | '>=' | '<' | '<=' `

#### Multiple Filters

Below we can use filters together with `disk.query` to find hard drives with a rotation rate higher than 5400 RPM

Javascript:
    :::javascript
    [
      ["type","=","HDD"],
      ["rotationrate",">",5400] // Note that the value should be the correct type
    ]

Command Line: `# midclt call disk.query '[["type", "=", "HDD"],["rotationrate",">",5400]]'`

#### Conjunctions

The conjunction `OR` is also supported. We can use the filters below with jail.query to filter by release.

Not using the `OR` conjunction implies `AND`.

Javascript:
    :::javascript
    ["OR", 
      [
        ["release","=", "11.2-RELEASE"],
        ["release","=", "11.3-RELEASE"],
      ]
    ]

Command Line: `# midclt call jail.query '[["OR", [["release","=","11.2-RELEASE"],["release","=","11.3-RELEASE"]]]]'`

### Query Options

Query Options are an object you can pass to further customize the results returned by a Query Method. 

Query Option's properties include `extend | extend_context | prefix | extra | order_by | select | count | get | limit | offset`

NOTE: When using `midclt` always remember to keep options and filters separated eg. `midclt <method> '<filters>' '<options>'` 

#### Count

Use the `count` option to get the number of results returned

Javascript:
    :::javascript
    {
      "count": true
    }

Command Line: `# midclt call jail.query '[["release","=","11.2-RELEASE"]]' '{"count": true}'`

#### Limit

Use the `limit` option to limit the number of results returned.

Javascript:
    :::javascript
    {
      "limit": 5
    }

Command Line: `# midclt call jail.query '[["release","=","11.2-RELEASE"]]' '{"limit": 5}'`

#### Offset

Use the `offset` option to omit items from the beginning of the list of returned items.

Javascript:
    :::javascript
    {
      "offset": 1 // Omits the first item from the query result
    }

Command Line: `# midclt call disk.query '[]' '{"offset": 1}'

#### Select

Use the `select` option to specify exactly the fields you're interested in.

Javascript:
    :::javascript
    {
      "select": ["devname","size","rotationrate"]
    }

Command Line: `# midclt call jail.query '[["release","=","11.2-RELEASE"]]' '{"limit": 5}'`

#### Order By

Use the `order_by` option to specify which field determines the sort order

Javascript:
    :::javascript
    {
      "order_by": "size" // field name
    }

Command Line: `# midclt call disk.query '[]' '{"order_by": ["size"]}'


    




