# JSON-RPC done right #
a leightweight JSON-RPC client and server implementation for PHP 5

Tivoka is a powerful, specification compatible and object-oriented JSON-RPC implementation for PHP with a simple API.  
It allows you to choose between [JSON-RPC 1.0](http://json-rpc.org/wiki/specification) and [JSON-RPC 2.0](http://jsonrpc.org/specification) specs.

 - Download [latest version](https://github.com/marcelklehr/tivoka/zipball/2.0.0) or install it through PEAR (see below)
 - Have a look at the [documentation](https://github.com/marcelklehr/tivoka/wiki)
 - Submit any bugs, suggestions or questions to the [Issue Tracker](http://github.com/marcelklehr/tivoka/issues)

Learn more about JSON-RPC at <http://jsonrpc.org/>.

## Examples ##
These are just some quick examples. For more details see the [website](http://marcelklehr.github.com/tivoka/).

Using make a request

```php
<?php
$target = 'http://exapmle.com/api';
$request = Tivoka::connect($target)->sendRequest($id = 42, 'substract', array(51, 9));
print $request->result;// 42
?>
```

Creating a server

```php
<?php
Tivoka::createServer(array(
	'substract' => function($req) {
		$result = $req->params[0] - $request->params[1];
		return $req->result($result);
	}
));
?>
```

## Installing through PEAR

Run the following commands in the console:

```
pear channel-discover pearhub.org
pear install pearhub/tivoka
```

(*You might have to use `sudo` on a UNIX machine.*)

## License ##
**GNU General Public License** - as published by the Free Software Foundation; either version 3 of the License, or (at your option) any later version.  
See the `LICENSE` file.

## Changelog ##

2.0.2

 * Introduced new directory structure
 * Fixed #10
 * Some Exception messages changed slightly to be more specific

***

2.0.1

 * Patched http method spelling (make uppercase, so all servers accept it)

***

2.0.0

 * complete Code base rework
 * major API change
 * removed Response Class
 * Added aa number of shortcuts
 * Implemented native remote interface

***