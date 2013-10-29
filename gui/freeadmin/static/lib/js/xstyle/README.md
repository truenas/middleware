Xstyle is a framework for building applications through extensible CSS. With xstyle you
can define data bindings, UI elements, variables, extensions, and shims to create modern
web applications with an elegantly simple, stylesheet driven approach. Xstyle also includes
tools for loading CSS and building and minifying CSS-driven applications.

Much of the functionality in xstyle is still pre-alpha, but this documentation is annotated 
where implementation is incomplete. 

# Why Extensible CSS with xstyle?

Modern web browsers have increasingly moved towards relying on CSS to define the 
presentation of the user interface. Furthermore, CSS is fundamentally built on the 
powerful paradigms of declarative, function reactive programming, providing similar types of
expressiveness as dependency injection systems. By adding a few simple CSS constructs,
xstyle bridges the gap to provide the capabilities for composition and modular extensions that
allow virtually unlimited expression of user interfaces, with a familiar syntax in encapsulated form. 
Xstyle goes beyond the capabilities of preprocessor because it runs in the browser and extensions
can interact with the DOM. Xstyle prevents the common abuse of HTML for UI, by allowing
the definition of UI elements with the presentation definition, where they belong, encouraging
both encapsulation and separation of concerns with intelligent organization.

# Getting Started

To start using xstyle's extensible CSS, you simply need to load the xstyle JavaScript library, <code>xstyle.js</code> 
or <code>xstyle.min.js</code> (minified) and you can start using xstyle's CSS extensions:

<pre>
&lt;style>
	/* my rules */	
&lt;/style>
&lt;script src="xstyle/xstyle.js">&lt;/script> &lt;!-- or use the minified xstyle.min.js -->
</pre>

Or xstyle can be used with an AMD module loader, like RequireJS or Dojo. Simply load the 
xstyle/main module to initiate the css extension parsing:
<pre>
&lt;style>
	/* my rules */
&lt;/style>
&lt;script src="dojo/dojo.js" data-dojo-config="async: true, deps: ['xstyle/main']">&lt;/script>
</pre>

You will also need to make sure you have installed the [put-selector](https://github.com/kriszyp/put-selector)
package, as xstyle depends on it.

Using a module loader is beneficial, as it provides for automatic loading of extension
modules when they are used in CSS.

Xstyle also includes a CSS loader, for dynamically loading CSS as a dependency of modules.
See the AMD Plugin Loader section for more information.

Xstyle supports all modern browsers, and Internet Explorer back to version 8 
(although in IE8, it is not possible to use xstyle CSS directly in style tags, all xstyle CSS
must exist in CSS files). 

# Using Xstyle CSS

Once you have loaded the xstyle script or module, you can begin to use xstyle's extensible CSS,
making use of new definitions to develop your application within CSS.

## New Definitions

The key building block in xstyle is an extension for creating new definitions for features like
user defined properties. In traditional CSS, all properties, functions, and other 
constructs are defined by the browser, and stylesheet rules are limited to using 
these predefined properties. In xstyle, new properties, functions, and other elements can be defined with 
extensible meaning. New definitions may be used as shims (to fill in for standard properties
on other browsers), they may be compositions of other properties, or provide entirely new concepts.
Since definitions can be constructed using JavaScript modules that can interact with
the DOM, there is virtually no limit to the what can be created.

To create a new definition, we simply use the <code>=</code> operator to assign a name to
our new definition and assign an expression to indicate its meaning. For example, xstyle provides a property
definition expression that will automatically add a vendor specific prefix (like <code>-webkit-</code>) to a property.
We can create such a property:

	transition = prefix;

New properties can be defined anywhere in a stylesheet, including at the top level (amongst
rules), within rules (or nested rules), or even directly in property names. At the top level, a new definition makes
the definition or property available for use anywhere below the definition. Defined within a rule, the 
new definition is available only within that rule declaration (or nested rules or extending rules) 
below the definition. For example, we could use this property definition in a rule, to have
xstyle automatically generate vendor specific properties for the transition property 
(including -webkit-transition, -moz-transition, etc.):

	transition = prefix;
	.content {
		transition: color 0.5s;
	}

Since property definitions can be used directly within a property name, we could inline the 
definition to more succinctly write the same transition:
  
	.content {
		transition=prefix: color 0.5s;
	}

When using property definitions for shimming properties, we generally only want to apply
the shim (vendor prefixing in the example above) if the standard property is not available.
We can conditionally define a new property only if the property has not already been defined
(by the browser or a previous definition) with the =? operator. We could update the 
example above to use the standard 'transition' without prefixing if available:

	.content {
		transition=?prefix: color 0.5s;
	}

However, shimming is only the beginning of what we can do with xstyle. We can also 
create new definitions with custom behavior implemented in JavaScript module, which can 
in turn create other custom rules or affect interaction with the DOM. We can use
rules as a definitions or JavaScript modules for more customized behavior:

	my-custom-property = module('my/module');
	
We look at how how to implement a module in more detail later.

## Rule Definitions and Mixins

We can also create a new definitions as a composition of other properties, like a rule declaration.
Such definitions can be used as properties, to mix in their properties, they can
be used as base rules for extension, or they can be referred to like elements in
element generation (see below). For example, we could create a new definition
based on absolute positioning:

	absolutely = {
		top: 50px;
		left: 50px;
		position: absolute;
	}

We could then style a class by mixing in our new definition. We do this simply by including 
the using the definition as a property in our rule. If we want to simply mix in the properties
as defined in the base definition, we set the value to "defaults":
	
	.my-class {
		absolutely: defaults;
	}

We can also override properties from our definition:

	.my-class {
		absolutely: default;
		top: 60px;
	}

And, we can do this shorthand, by putting values directly in the "absolutely" property. The
values are then assigned to the composite properties in order of declaration. For example:
  
	.my-class {
		absolutely: 60px 70px;
	}

Would be the same as:

	.my-class {
		absolutely: default;
		top: 60px;
		bottom: 70px;
	}

## Extending Rules

We can also create rule definitions that extend other rule definitions. We do this simply
by referencing the base definition after the '=' and before the rule declaration:

	absolutely-green = absolutely {
		background-color: green;
	}

We can also extend from multiple base definitions. We do this by comma delimiting
all the base definitions we want to inherit from. For example, we could alternately create our
absolutely positioned element with green background from two other definitions:

	green-background = {
		background-color: green;
	}
	absolutely-green = absolutely, green-background {}

This provides similar functionality as using the base definition as a property, but there 
are a couple of important distinctions. First, extensions will inherit all the definitions within
the base definition, whereas property mixins only inherit the property values (and their
meaning according to their own definitions). This means that if you have assigned
a new definition within a base rule definition, you can reference that definition in your
property definitions or element references.

The second capability that extending rules provides (that is not a part of property mixins),
is that you can refer to any tag or class selector as the base definition, and that tag or class will be used
when the definition is referenced in element generation (see next section). For example,
we can create our own big-header definition that inherits from an h1:
  
	big-header = h1 {
		font-size: 4em;
	}

## Element Generation

With xstyle, you can declare the creation of DOM elements within rules, allowing for the creation
of complex presentation components. This can be thought of as templating functionality 
(using CSS selector syntax, similar to jade), with reactive capabilities. This not only 
simplifies the creation and composition of UI components, it helps to keep cleaner semantics in HTML, 
and provides better encapsulation.

To create an element, we use the => operator, followed a selector designating the 
tag of the element to create along with class names, id, and attributes to assign to the element.
For example, we could create a &lt;div> with an class name of "tile" inside of any element
with a class name of "all-tiles":

	.all-tiles {
		=> div.tile;
	}

You can create elements with ids and attributes as well, using standard selector syntax.
This will create a div with an id of "help" and a title of "Information":

	.all-tiles {
		=> div#help[title=Information];
	}

Element generation can also generate multiple elements, and take advantage of indentation 
to indicate the hierarchy of the elements. Deeper indentation indicates child elements,
and shallower indentation can be used to generate parents. For example, we could 
create a simple hierarchy:

	.simple {
		=>
			div.parent1
				div.child
					div.grandchild
			div.parent2
				div.another-child
	} 


Or, we could create a two by two table:

	table.two-row {
		=>
			tr 
				td
				td
			tr 
				td
				td;
	}  

We could also generate text nodes inside elements with quoted strings. We could create
an h1 header with some text like:

	header {
		=> h1 'The header of the page';

Xstyle will automatically handle applying any previously done element generation rules
within the generation of other elements. For example, if we were to create a 
table.two-row element, with the element generation definition above, we can also
use this in another element generation. For example:

	.content {
		=> table.two-row; /* <- this will be expanded to create two rows */ 

As mentioned in the rule definition section, we can also reference any rule definitions
within our element generation. For example, we could reference the "big-header"
definition we created above, which will generate an &lt;h1> element with a font-size
of 4em:
	
	.content {
		=> big-header;
	}

## Nested Rules

With xstyle, you can nest CSS rules, allowing for multiple definitions using a given selector
prefix. For example, suppose we want to define several rules for elements within
.my-form. We can do so with nested rules:

	.my-form {
		input {
			/* this rule's selector is equivalent to .my-form input */ 
		}
		selector {
			/* this rule's selector is equivalent to .my-form select */ 
		}
	}

Using nesting rules can reduce typing, add better organization, and make it easier to refactor stylesheets.

### Nested Element Generation

Nesting rules is particularly useful in combination with element generation, as we can
define the CSS for the generated elements without having to manually create and
synchronize an element identifier or selector with another CSS rule.

	.content {
		=> 
			h1 {
				color: green;
			}
			p 'Blue Paragraph' {
				color: blue;
			};
	}

We can nest element generation and CSS rules in any combination that we want, allowing
us to create sophisticated UI elements in a single modular unit. 

## Predefined Property Definitions

Xstyle includes several predefined, or intrinsic definitions for properties. These can and usually
are assigned to other names to create property definitions for use in rules. The next 
few sections describe these provided definitions.

One feature of the application of property definitions in xstyle is that when a property
with dashes in it, is encountered in a rule, xstyle will first look for a definition that 
matches the full name, and then progressively remove the dash-delimited tokens from the 
right to apply. For example, if we defined a property <code>custom</code>, than it our definition
would be applied for <code>custom-foo</code> as well as <code>custom</code>.    

### var - Variables

Properties can be used as variables that can be referenced from other properties in CSS stylesheets. 
For many, this concept may be very familiar from CSS preprocessors, 
and the recent addition in modern browsers according to the W3C specification. 
To create a variable property, we define our property by assigning it <code>var</code>. For 
example, we could create a variable:

	highlight-color=var: blue;

To reference the variable and use the value in another property, xstyle uses the standard W3C
syntax, referencing the variable with a <code>var(variable-name)</code> syntax:

	.highlight {
		background-color: var(highlight-color);
	}

A variable can be declared at the top level, as well inside rules. A variable can referenced
that is within the current rule or any parent rule (see nested rules) including the top level.

### prefix - Vendor Prefixing

This definition will create a property like the declared property, except a vendor prefix
will be added that corresponds to the browser's vendor. The prefixes are -webkit- for
WebKit browsers, -moz- for Firefox, and -ms- for IE. A typical usage is:

	border-radius = prefix;
	
	border-radius: 5px;

(functionality has been implemented)

### content - Insertion Point

This definition represents a reference to the contents of node prior to element generation.
This can be used within element generation to bring in the contents of the target.
For example:

	.greeting {
		=> h1 'Welcome:', content;
	}

We could then have some HTML that starts as:

	&lt;div class="greeting">John Doe&lt;/div>

And then xstyle would convert this to:

	&lt;div class="greeting">&lt;h1>Welcome:&lt;/h1>John Doe&lt;/div>

(not fully implemented)

### on - Event Handling

The "on" definition makes it possible to register handlers directly from rules. This property
definition does not need to be assigned to a new name. It utilizes sub-property names
to specify the event to listen for. The property name should be the form of <code>on-&lt;event-name></code>.
The value of the property should be a definition (or an expression) pointing to a function,
that should be executed in response to the event. For example, to register 
a <code>click</code> handler, we could write a property:

	on-click: click-handler;

See the Data Bindings section below, as you will probably want to access sub-properties of
definitions for your event handlers.

(implemented, lightly tested)

### margin, padding, border, etc. - Nested Definitions

Xstyle extends the margin, padding, and other properties to support nested rules to
specify the individual sides, or sub-properties of these properties. For example,
we could specify the margin-left and margin-right by writing:

	margin: {
		left: 10px;
		right: 20px;
	};

(not implemented)

## Data Binding

We can combine property definitions with element generation to create data bindings. With data
bindings, an element can be generated and the contents can be bound to a variable.
A basic example of a data binding would be to create a variable with a string value:

	first-name = 'John';
	
	div.content {
		=> span(first-name);
	}

The contents of the span that was created would then be set to the value of firstName. Changes in the
value of the firstName would automatically be updated in the span's contents.

We can also bind variables to inputs, and then the binding will work two ways, not only can 
changes in the variable be reflected in the input, but user edits to the value will be updated
to the variable. For example:

	first-name = 'John';
	
	div.content {
		=> input[type=text](first-name);
	}

This provides the foundation for wiring components to data sources. We can also assign
variables to modules, providing an interface between JavaScript-driven data and the UI.
We bind a variable to a module like this:

	person = module('data/person');
 
We can then bind to the object returned from the module. We use a / operator to refer
to properties of an object:

	form.content {
		=> 
			label 'First Name:',
			input[type=text](person/firstName),
			label 'Last Name:',
			input[type=text](person/lastName);
	}

### Attribute Binding

All elements have default binding. For input elements, bindings are bound to the input's 
"value" attribute, for other elements, to the text content of the element. However,
you can also bind to specific attributes of an element as well. This accomplished
by placing the parenthesis embedded binding reference in an attribute selector generator.
For example, we could bind the href of an anchor element to a variable:

	targetUrl = 'http://target/';
	.content {
		=> a[href=(targetUrl)];
	}

This functionality is implemented and has been lightly tested.

### List Binding

Not only can we bind scalar values to elements, we can also bind lists or array to elements
to generate a list of children elements corresponding to each item in an array. We bind
arrays just like we do scalar values. For example, we could easily output an array
of strings as a list like:

	.content {
		=> ul(array-of-items);
	}

Xstyle will iterate through the array, outputting a &lt;li/> element for each item, with the contents
corresponding to the item value. Different elements have different rendering for arrays, 
&lt;ul> and &lt;ol> elements will have have &lt;li> children, &lt;select>'s will have &lt;option> children,
and most others will have &lt;div> children.

You can also declare your own rendering of children by defining an "each" property for the 
targeted element. The
value of the each property should be a generating selector (just as we use with the => operator).
The item for each iteration in the array can be referenced with the "item" reference.
For example, we could generate a paragraph tag for each item:

	.content {
		=> div(array-of-items) {
			each: p(item);
		}
	}

This makes it possible to render arrays of objects. For example, we could render
a table of objects, where the first column corresponds to the "name" property of the
items in the array, and the second column corresponds to the "age" property:

	.content {
		=> table(array-of-people) {
			each: tr {
				=> 
					td(item/name), 
					td(item/age);
			};
		};
	}

### Expressions

Data bindings can include more than just a plain variable reference, we can also write
expressions that include other JavaScript operators. For example, we could bind
to the value of concatenation of two strings (again a live binding, automatically updated if either
variable or property changes):

	h1.name {
		=> span(person/firstName + person/lastName);
	}

This functionality is implemented and has been lightly tested.

## Creating Components

By combining the ability to create new definitions, bindings, and variables, we can create 
new encapsulated components with CSS. For example, here we create a component
that renders an h1 and p element with content, as defined by the component.

	my-component {
		=> 
			h1 (label),
			p (content);
		label=var: 'Default Label';
		content=var: 'Default Content';
		background-color: #ddf;
	}

We can then use this component as building block in our application:

	body {
		=> my-component {
			label: 'My Label';
		}
	}

## Shims

Xstyle can also be used to define extensions can be used for filling in missing functionality in browsers. Xstyle's default stylesheet
provides shims for a few commonly used properties that are missing in some older browsers,
including box-shadow, transform, and border-radius. For example, we can write:

	@import "xstyle/shims.css";
	.my-class {
		box-shadow: 10px 10px 5px #888888;
		transform: rotate(10deg);
	}

Here, we can use newer CSS properties like 'box-shadow' and 'transform' and Xstyle
will shim (or "polyfill" or "fix") older browsers for you, transforming these to 
MS filters for older versions of Internet Explorer. 

## Definition Modules

While xstyles provides predefined expressions for new definitions, we can also 
define new definitions with our own custom JavaScript modules. To define a new property
with a JavaScript module, we use the module('module-id') as the property definition:

	my-new-property = module('package/module-id');
	
If you are using an AMD loader, xstyle will load the target module id and use this to handle
the property. If you are not using an AMD module loader, you can still simply include a script
with a define call:

define('package/module-id', {
	/* module property definition */
});

The module can return an object (or provide an object to the define call), that has
methods that to be called when the property is used in stylesheets. The following
methods are defined:

* <code>module.put(value, rule, name)</code> - This is called whenever the property is used within a rule. The
<code>value</code> argument is the property value in the rule, and the <code>rule</code>
argument is the Rule object.  
* <code>module.receive(callback, rule, name)</code> - This is called when a property is accessed from a 
binding, to receive the current value. The callback should be called wheneve the value
is changed in the future.
* <code>module.forElement(element)</code> - If the value of a property is dependent on the element
that the rule is being applied, the module object may provide a forElement(element)
function that would return an object with the same methods as described here for the 
module. It should be noted that there is additional processing overhead, since every
element needs to be processed individually with this approach.  
* <code>module.get(name)</code> - This is called when a property is accessed using the my-new-property/sub-property
syntax.
* <code>module.call(rule, args,...)</code> - This is called when the definition is used a function, like
my-new-property()

The Rule object has the following properties and methods that can be used by the module:

* <code>setValue(name, value)</code> - This performs the action of adding a new property value to 
a rule. If there are any definition for the property, there are then executed.
* <code>setStyle(name, value)</code> - This sets a style on the native CSSOM rule object for the this rule. You can
apply additional native CSS properties directly by setting properties on the style object:

	rule.setStyle('color', 'red');

## Pseudo Definitions

We can create new definitions for pseudo selectors. Pseudo selector definitions begin
with a colon. For example, we can could create a custom pseudo selector:

	:custom = module('my-package/custom');  

The module's returned object should have a pseudo method that will be called for handling
rule's with the defined pseudo selector.

Again, we can use a conditional operator if we only want to implement the pseudo if it
has not already been provided by the browser. For example, if wanted to shim support
for the :enabled pseudo, we could implement a shim module and conditionally load it:

	:enabled =? module('my-package/enabled');

## Scoped Blocks Xstyle and Disabling Parsing

With xstyle, you can define blocks of CSS that have their own nested scope (without
a nested rule), to declare definitions without affecting other stylesheets. A new scope
can be started by using the <code>@xstyle start</code> directive to start a scoped block
and the <code>@xstyle end</code> to end a scoped block:

	@xstyle start;
	box-shadow = prefix;
	/* box-shadow will have vendor-prefixing applied */
	@xstyle end;
	/* box-shadow will be ignored again */

Also, you may wish to completely disable xstyle, or import a stylesheet that should not be parsed
by xstyle. This may be due to conflicts with properties, or other issues. Xstyle parsing can be
turned off by using:

	@xstyle end;

And it can be turned back on with:

	@xstyle start;

You can also use the <code>@xstyle start</code> and <code>end</code> directives to
create nested scopes. For example, you might wish to apply to a shim to all CSS (without 
nesting it in an inner rule), and you can do so by using this directive:

	@xstyle start;
	some-variable=var: some value;
	@import 'stylesheet-that-uses-some-variable.css';
	@xstyle end;
	/* any definition above won't affect CSS below */
	

### Included Shim Stylesheets

The shims.css stylesheet also defines shims for pseudo selectors including hover and focus.
By @import'ing shims.css into a stylesheet, these shims will be defined and we can using.
The rule definitions are transitive, so if stylesheet A @import's stylesheet B, which @import's
shims.css, both A and B stylesheets will have the shims applied. If another stylesheet C is
later independently loaded and it doesn't import any stylesheets, none of the shims
will be applied to it.

#### Available Shims (and limitations)
The following experimental shim modules come with Xstyle:
* shim/transition - This provides animated CSS property changes to emulates the CSS transition property.
* shim/boxOffsets - This provides absolute positioning in older versions of IE to emulate
bottom and right CSS properties.

#### Available Extensions

The following (mostly experimental) extension modules come with Xstyle:
* ext/pseudo - This modules provides emulation of hover, focus and other pseudos that
are not present in older versions of IE.
* ext/scrollbar - This module provides scrollbar measurement so that elements can be sized
based on the size of the scrollbar.
* ext/supported - Matches elements that have native support in the browser. For example:
	range:unsupported {
		/* styling for browsers that don't support range */
	}
	range:supported {
		/* styling for browsers that do support range */
	}
 
* ext/widget - This module can instantiate widgets to be applied to elements that match
a rule's selector. This is designed to instantiate widgets with the form of Widget(params, targetNode),
and can be used to instantiate Dojo's Dijit widgets.


## Widgets

One of the extensions included in xstyle is a property for declaring
widgets that follow the Dojo widget API (like Dijit widgets). This extension module is
available in the xstyle/ext/widget module. This can assigned as a new property definition 
and then the property can be used with a 
nested rule with sub-property definitions corresponding to the properties that should
be passed to the widget. There should also be a "type" property that indicates
the id of the module with the widget to load. For example, we could add a "widget"
property definition:

	widget = module('xstyle/ext/widget');

And then we could create progress bar using dijit/ProgressBar, using the "widget" property
in a rule:


	.my-progress-bar {
		widget: {
			type: dijit/ProgressBar;
			maximum: 20;
			value: 10;
		}
	}

# Build

This functionality is partially implemented.

Xstyle includes built tools that serve several purposes. First, they provide CSS aggregation,
combining @import'ed stylesheets into parent stylesheets to reduce requests. Second,
it will perform CSS minification, eliminating unnecessary whitespace and comments.
Xstyle will also isolate extensions into a special property that allows the xstyle parser
to run signficantly faster with a built stylesheet. To run the build tool, run the build.js
with node, providing a path to a stylesheet or directory of stylesheets to process, and 
a target to save the stylesheet to. For example, if we want to build app.css, we could do:

	node build.js app.css ../built/app.css

The xstyle build tool is also capable of inline resources like images directly in the stylesheet
with data: URLs. This can be very useful for reducing the number of requests. To mark resources for inlining, simply append a hash of #inline to the URL of the resource.
For example, if we had a background image pointing back.png, we could write the following rule

	.content {
		background: url(back.png#inline);
	}

When the build tool runs, this URL will be transformed to a data URL, and no extra request
will be necessary to fetch this background image. While this can reduce the number of
requests, this is best used for images that are small and very likely to be used. Since
the URL is inline in the stylesheet, it increases the load time of the stylesheet, and 
if the image might not be used or is large, this may be more detrimental than the 
improved overall load time afforded by the reduced requests.

# AMD Plugin Loader

You can also use Xstyle as a CSS loader plugin for AMD loaders like Dojo and RequireJS. 
To use the CSS loader, use the AMD plugin syntax, with xstyle/css as the plugin loader
and the path to the stylesheet afterwards:

	require(['xstyle/css!path/to/stylesheet.css'], function(){
		// after after css is loaded
	});

Note, that simply using the plugin loader will not load xstyle, and trigger parsing of the stylesheet,
so you will not be able to use the extensions, unless you have specifically included
the xstyle module as well.

This functionality is implemented and has been well tested.

# Building with AMD Plugin

When used as an AMD plugin, xstyle can also integrate with a Dojo build, automatically
including CSS dependencies of modules in a build. To run utilize xstyle in a Dojo build,
you need to include the xstyle AMD build plugin. This can be specified in your build profile:

	plugins: {
		"xstyle/css": "xstyle/build/amd-css"
	},

After that, you can simply run a build as normal, and the CSS dependencies will 
automatically be inlined in the built layer.

While inlining CSS text in a JavaScript built layer is the easiest approach, and can also
help reduce the number of requests, it is generally preferable to keep CSS in stylesheets,
and leverage browser's optimized patterns for loading stylesheets. This can be accomplished
as well with the integrated Dojo build. You simply need to specify a target stylesheet
in the layer definition in the build profile:

	layers: [
	{
		name: "path/to/targetModule.js",
		targetStylesheet: "my-package/css/main-stylesheet.css",
		...

When the build runs, any CSS dependencies that are encountered in modules will then
be added to main-stylesheet.js (which will be created if it does not already exist), rather 
than inlined in the JavaScript build layer. One
can still use the #inline URL directive to inline resources in combination with the AMD
build plugin.
 
## Import Correction

Another feature Xstyle provides is reliable @import behavior. Internet Explorer is not
capable of loading multiples levels deep @imports. Xstyle provides @import "flattening"
to fix this IE deficiency.

Xstyle also normalizes @import once behavior. If two stylesheets both @import the
same sheetsheet, Xstyle ensures that the @import'ed stylesheet is only imported once (by the first
stylesheet) and the second @import is removed. This is a powerful feature because
it allows stylesheets to @import another stylesheet without worrying about overriding
another stylesheet that expected to come after the target sheet due to it's @import statement.

# Additional Modules

## has-class

The has-class module provides decoration of the root &lt;html> element with class names
based on feature detection. The has-class module works in conjunction with the has()
module in Dojo (dojo/has) to detect features, and adds a class name for matches with
a "has-" prefix. For example, if we wanted to create a CSS rule that was conditional on the detection of
the "quirks" feature, first we would need to register this feature detection with the has-class module:

	define(['xstyle/has-class'], function(hasClass){
		hasClass("quirks");
	}); 

And then we could create a rule that uses this conditional class name:

	html.has-quirks .row {
		/* rule only applied if in quirks mode */
		height: auto;
	}

We can also base rules on the absence of a feature. In converse, we could create
a rule for when quirks mode is not present:

	hasClass("no-quirks");

And then use this in the selector:
	
	html.has-no-quirks .row {
		/* rule only applied if in quirks mode */
		width: auto;
	}

We can also base rules on a numerical feature values. We could create a rule that
just matches IE7 with:

	hasClass("ie-7");

Or version IE8 through IE10:

	hasClass("ie-8-10");

xstyle is freely available under *either* the terms of the modified BSD license *or* the
Academic Free License version 2.1. More details can be found in the [LICENSE](LICENSE).
The xstyle project follows the IP guidelines of Dojo foundation packages and all contributions require a Dojo CLA. 
If you feel compelled to make a monetary contribution, consider some of the author's [favorite
charities](http://thezyps.com/2012-giving-guide/) like [Innovations for Poverty Action](http://www.poverty-action.org/) or
the [UNFPA](http://www.friendsofunfpa.org/).