This put-selector/put module/package provides a high-performance, lightweight 
(~2KB minified, ~1KB gzipped with other code) function for creating 
and manipulating DOM elements with succinct, elegant, familiar CSS selector-based 
syntax across all browsers and platforms (including HTML generation on NodeJS). 
The single function from the module creates or updates DOM elements by providing
a series of arguments that can include reference elements, selector strings, properties,
and text content. The put() function utilizes the proven techniques for optimal performance
on modern browsers to ensure maximum speed.

Installation/Usage
----------------

The put.js module can be simply downloaded and used a plain script (creates a global 
put() function), as an AMD module (exports the put() function), or as a NodeJS (or any
server side JS environment) module.
It can also be installed with <a href="https://github.com/kriszyp/cpm">CPM</a>:

	cpm install put-selector

and then reference the "put-selector" module as a dependency.
or installed for Node with NPM:

	npm install put-selector

and then:

	put = require("put-selector");

Creating Elements
----------------

Type selector syntax (no prefix) can be used to indicate the type of element to be created. For example:

	newDiv = put("div");
	
will create a new &lt;div> element. We can put a reference element in front of the selector
string and the &lt;div> will be appended as a child to the provided element: 

	put(parent, "div"); 
	
The selector .class-name can be used to assign the class name. For example:

	put("div.my-class") 
	
would create an element &lt;div class="my-class"> (an element with a class of "my-class").

The selector #id can be used to assign an id and [name=value] can be used to 
assign additional attributes to the element. For example:

	newInput = put(parent, "input.my-input#address[type=checkbox]");

Would create an input element with a class name of "my-input", an id of "address",
and the type attribute set to "checkbox". The attribute assignment will always use 
setAttribute to assign the attribute to the element. Multiple attributes and classes
can be assigned to a single element. 

The put function returns the last top level element created or referenced from a selector. 
In the examples above, the newly create element would be returned. Note that passing 
in an existing node will not change the return value (as it is assumed you already have 
a reference to it). Also note that if you only pass existing nodes reference, the first 
passed reference will be returned.

Modifying Elements
----------------

One can also modify elements with selectors. If the tag name is omitted (and no
combinators have been used), the reference element will be modified by the selector.
For example, to add the class "foo" to element, we could write:

	put(element, ".foo"); 

Likewise, we could set attributes, here we set the "role" attribute to "presentation":

	put(element, "[role=presentation]");

And these can be combined also. For example, we could set the id and an attribute in
one statement:

	put(element, "#id[tabIndex=2]");

One can also remove classes from elements by using the "!" operator in place of a ".". 
To remove the "foo" class from an element, we could write:

	put(element, "!foo");

We can also use the "!" operator to remove attributes as well. Prepending an attribute name
with "!" within brackets will remove it. To remove the "role" attribute, we could write:

	put(element, "[!role]");

Deleting Elements
--------------

To delete an element, we can simply use the "!" operator by itself as the entire selector:

	put(elementToDelete, "!");

This will destroy the element from the DOM, using either parent innerHTML destruction (IE only, that 
reduces memory leaks in IE), or removeChild (for all other browsers).

Creating/Modifying Elements with XML Namespaces
-----------

To work with elements and attributes that are XML namespaced, start by adding the namespace using addNamespace:

	put.addNamespace("svg", "http://www.w3.org/2000/svg");
	put.addNamespace("xlink", "http://www.w3.org/1999/xlink");

From there, you can use the CSS3 selector syntax to work with elements and attributes:

	var surface = put("svg|svg[width='100'][height='100']");
	var img = put(surface, "svg|image[xlink|href='path/to/my/image.png']");

Text Content
-----------

The put() arguments may also include a subsequent string (or any primitive value including
boolean and numbers) argument immediately 
following a selector, in which case it is used as the text inside of the new/referenced element.
For example, here we could create a new &lt;div> with the text "Hello, World" inside.

	newDiv = put(parent, "div", "Hello, World");

The text is escaped, so any string will show up as is, and will not be parsed as HTML.

Children and Combinators
-----------------------

CSS combinators can be used to create child elements and sibling elements. For example,
we can use the child operator (or the descendant operator, it acts the same here) to 
create nested elements:

	spanInsideOfDiv = put(reference, "div.outer span.inner");

This would create a new span element (with a class name of "inner") as a child of a
new div element (with a class name of "outer") as a child of the reference element. The
span element would be returned. We can also use the sibling operator to reference
the last created element or the reference element. In the example we indicate that
we want to create sibling of the reference element:

	newSpan = put(reference, "+span");

Would create a new span element directly after the reference element (reference and 
newSpan would be siblings.) We can also use the "-" operator to indicate that the new element
should go before: 

	newSpan = put(reference, "-span");

This new span element will be inserted before the reference element in the DOM order.
Note that "-" is valid character in tags and classes, so it will only be interpreted as a
combinator if it is the first character or if it is preceded by a space.

The sibling operator can reference the last created element as well. For example
to add two td element to a table row:

	put(tableRow, "td+td");

The last created td will be returned.

The parent operator, "<" can be used to reference the parent of the last created 
element or reference element. In this example, we go crazy, and create a full table,
using the parent operator (applied twice) to traverse back up the DOM to create another table row
after creating a td element:

	newTable = put(referenceElement, "table.class-name#id tr td[colSpan=2]<<tr td+td<<");

We also use a parent operator twice at the end, so that we move back up two parents 
to return the table element (instead of the td element).

Finally, we can use the comma operator to create multiple elements, each basing their selector 
scope on the reference element. For example we could add two more rows to our table
without having to use the double parent operator:

	put(newTable, "tr td,tr td+td");

Appending/Inserting Existing Elements
---------------------------------

Existing elements may be referenced in the arguments after selectors as well as before.
If an existing element is included in the arguments after a selector, the existing element will
be appended to the last create/referenced element or it will be inserted according to
a trailing combinator. For example, we could create a &lt;div> and then append 
the "child" element to the new &lt;div>: 

	put("div", child);

Or we can do a simple append of an existing element to another element:

	put(parent, child);

We could also do this more explicitly by using a child descendant, '>' (which has the
same meaning as a space operator, and is the default action between arguments in put-selector):

	put(parent, ">", child);

We could also use sibling combinators to place the referenced element. We could place
the "second" element after (as the next sibling) the "first" element (which needs a parent
in order to have a sibling):
 
	put(first, "+", second);

Or we could create a &lt;div> and place "first" before it using the previous sibling combinator:

	put(parent, "div.second -", first);

The put() function takes an unlimited number of arguments, so we could combine as
many selectors and elements as we want: 

	put(parent, "div.child", grandchild, "div.great-grandchild", gggrandchild);
	
Variable Substitution
-------------------

The put() function also supports variable substitution, by using the "$" symbol in selectors.
The "$" can be used for attribute values and to represent text content. When a "$"
is encountered in a selector, the next argument value is consumed and used in it's
place. To create an element with a title that comes from the variable "title", we could write:

	put("div[title=$]", title);

The value of title may have any characters (including ']'), no escaping is needed. 
This approach can simplify selector string construction and avoids the need for complicated
escaping mechanisms.

The "$" may be used as a child entity to indicate text content. For example, we could
create a set of &lt;span> element that each have content to be substituted:

	put("span.first-name $, span.last-name $, span.age $", firstName, lastName, age);

Assigning Properties
------------------

The put() function can also take an object with properties to be set on the new/referenced
element. For example, we could write:

	newDiv = put(parent, "div", {
		tabIndex: 1,
		innerHTML: "Hello, World"
	});

Which is identical to writing (all the properties are set using direct property access, not setAttribute):

	newDiv = put(parent, "div");
	newDiv.tabIndex = 1;
	newDiv.innerHTML = "Hello, World";

NodeJS/Server Side HTML Generation
----------------------------

While the put() function directly creates DOM elements in the browser, the put() function
can be used to generate HTML on the server, in NodeJS. When no DOM is available, 
a fast lightweight pseudo-DOM is created that can generate HTML as a string or into a stream.
The API is still the same, but the put() function returns pseudo-elements with a 
toString() method that can be called to return the HTML and sendTo method to direct
generated elements to a stream on the fly. For example:

	put("div.test").toString() -> '<div class="test"></div>' 

To use put() streaming, we create and element and call sendTo with a target stream.
In streaming mode, the elements are written to the stream as they are added to the
parent DOM structure. This approach is much more efficient because very little
needs to be kept in memory, the HTML can be immediately flushed to the network as it is created.
Once an element is added to the streamed DOM structure,
it is immediately sent to the stream, and it's attributes and classes can no longer be
altered. There are two methods on elements available for streaming purposes:

	element.sendTo(stream)
	
The sendTo(stream) method will begin streaming the element to the target stream,
and any children that are added to the element will be streamed as well.

	element.end(leaveOpen) 

The end(leaveOpen) method will end the current streaming, closing all the necessary
tags and closing the stream (unless the argument is true). 

The returned elements also include a put() method so you can directly add to or apply
CSS selector-based additions to elements, for example:

	element.put('div.test'); // create a &lt;div class="test">&lt;/div> as a child of element

Here is an example of how we could create a full page in NodeJS that is streamed to 
the response:

	var http = require('http');
	var put = require('put-selector');
	http.createServer(function (req, res) {
		res.writeHead(200, {'Content-Type': 'text/html'});
		var page = put('html').sendTo(res); // create an HTML page, and pipe to the response 
		page.put('head script[src=app.js]'); // each element is sent immediately
		page.put('body div.content', 'Hello, World');
		page.end(); // close all the tags, and end the stream
	}).listen(80);

On the server, there are some limitations to put(). The server side DOM emulation
is designed to be very fast and light and therefore omits much of the standard DOM
functionality, and only what is needed for put() is implemented. Elements can
not be moved or removed. DOM creation and updating is still supported in string
generation mode, but only creation is supported in streaming mode. Also, setting 
object properties is mostly ignored (because only attributes are part of HTML), except
you can set the innerHTML of an element. 

Proper Creation of Inputs
-------------------------

Older versions of Internet Explorer have a bug in assigning a "name" attribute to input after it
has been created, and requires a special creation technique. The put() function handles
this for you as long as you specify the name of the input in the property assignment
object after the selector string. For example, this input creation will properly work
on all browsers, including IE:

	newInput = put("input[type=checkbox]", {name: "works"});

Using on Different document
-------------------------

If you are using multiple frames in your web page, you may encounter a situation where
you want to use put-selector to make DOM changes on a different HTML document.
You can create a separate instance of the put() function for a separate document by
calling the put.forDocument(document) function. For example:

	put2 = put.forDocument(frames[1].document);
	put2("div") <- creates a div element that belongs to the document in the second frame.
	put("div") <- the original put still functions on the main document for this window/context 
