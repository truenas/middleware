XStyle is a framework for shimming (or polyfilling) and extending CSS, to efficiently support various 
plugins for additional CSS functionality and backwards compatibility of newer features.

A simple example of using XStyle to shim CSS:
<pre>
<style>
@import "/path/to/xstyle/shims.css";
.my-class {
	box-shadow: 10px 10px 5px #888888;
	transform: rotate(10deg);
}
</style>
<script src="xstyle/xstyle.js"></script>
</pre>
Here, we can use newer CSS properties like 'box-shadow' and 'transform' and XStyle
will shim (or "polyfill" or "fix") older browsers for you. XStyle will scan your stylesheet, load the shims.css which defines the CSS extensions
for the rules for shimming, and process the stylesheet. 

You can also use XStyle as a CSS loader plugin for AMD loaders like Dojo and RequireJS:
<pre>
define(["xstyle!./path/to/example.css"], function(){
	// module starts after css is loaded
});
</pre>

XStyle is plugin based so that new shims and extensions can be selected and combined
without incurring additional CSS parsing overhead. XStyle is designed to allow for plugins to be 
registered to handle different CSS properties, so that the shims and extensions that are
applied can be explicilty controlled for each stylesheet.

The shims.css stylesheet (referenced in the example above) includes a number of out
of the box shims to upgrade older browsers for modern CSS properties including: opacity, 
bottom, right, transition, border-radius, box-shadow, box-sizing, border-image, transform.
The shims.css stylesheet also defines shims for pseudo selectors including hover and focus.
By @import'ing shims.css into a stylesheet, these shims will be defined and we can using.
The rule definitions are transitive, so if stylesheet A @import's stylesheet B, which @import's
shims.css, both A and B stylesheets will have the shims applied. If another stylesheet C is
later independently loaded and it doesn't import any stylesheets, none of the shims
will be applied to it.

XStyle also includes an ext.css stylesheet that enables a number of CSS extensions
including :supported and :unsupported pseudo selectors, and an -x-widget CSS property
for instantiated widgets. 

We can also explicitly define exactly which properties and other CSS elements to shim 
or extend. The XStyle parser looks for extension rules. The first rule is x-property
which defines how a CSS property should be handled. A rule with an 'x-property' selector
make define properties with values indicating how the corresponding CSS property 
should be handled. Let's look at a simplified example from shims.css to see how we 
could shim the 'box-shadow' property to use an IE filter:
<pre>
x-property {
	box-shadow: require(xstyle/shim/ie-filter);
}		
</pre>
Here we defined that the CSS property 'box-shadow' should be handled by the 'xstyle/shim/ie-filter' 
module. The ie-filter module converts the CSS property to an MS filter property so that
we can enable a box shadow in IE. Now, we could later create a rule that uses this property:
<pre>
.my-box: {
	box-shadow: 10px 10px 5px #888888;
}
</pre>
However, this was indeed a simplified. For shims, we usually only want to apply the 
shimming module if the property is not natively supported. We can do this with the
default and prefix property values. The rule in shims.css looks like this:
<pre>
x-property {
	box-shadow: default, prefix, require(xstyle/shim/ie-filter);
}		
</pre>
This extension rule includes multiple, comma separated values. The first value is 'default'.
This indicates that first XStyle should check if the 'box-shadow' is natively supported
by the browser in standard form. If it is, then no further extensions or modifications to the CSS are applied.
The next value is 'prefix'. This indicates that first XStyle should check if the 'box-shadow' 
is supported by the browser with a vendor prefix (like -webkit- or -moz-). If it is, then 
the vendor prefix is added to the CSS property to enable it. Finally, if 'box-shadow' is
not supported in standard form or with a vendor prefix, then the ie-filter module is
loaded to apply the MS filter.
 
<h1>Import Fixing</h1>
Another feature XStyle provides is reliable @import behavior. Internet Explorer is not
capable of loading multiples levels deep @imports. XStyle provides @import "flattening"
to fix this IE deficiency.

XStyle also normalizes @import once behavior. If two stylesheets both @import the
same sheetsheet, XStyle ensures that the @import'ed stylesheet is only imported once (by the first
stylesheet) and the second @import is removed. This is a powerful feature because
it allows stylesheets to @import another stylesheet without worrying about overriding
another stylesheet that expected to come after the target sheet due to it's @import statement.

<h1>Available Shims (and limitations)</h1>
The following shim modules come with XStyle:
* xstyle - XStyle itself provide vendor prefix shimming with the prefix property. This is
used to shim border-radius, box-shadow, box-sizing, and border-image.
* shim/ie-filter - This creates MS filters to emulate standard CSS properties. This is used to shim
box-shadow and transform.
* shim/transition - This provides animated CSS property changes to emulates the CSS transition property.
* shim/boxOffsets - This provides absolute positioning in older versions of IE to emulate
bottom and right CSS properties.

<h1>Available Extensions</h1>
The following shim modules come with XStyle:
* ext/pseudo - This modules provides emulation of hover, focus and other pseudos that
are not present in older versions of IE.
* ext/scrollbar - This module provides scrollbar measurement so that elements can be sized
based on the size of the scrollbar.
* ext/supported - 
* ext/widget - This module can instantiate widgets to be applied to elements that match
a rule's selector. This is designed to instantiate widgets with the form of Widget(params, targetNode),
and can be used to instantiate Dojo's Dijit widgets.


<h1>Creating Extension Modules</h1>
XStyle is a plugin-based and you are encouraged to create your own CSS extension modules/plugins.
An extension module that handles extension properties should return an object with an 
onProperty function that will be called each time the extension property is encountered.
The onProperty function has the signature:
<pre>
onProperty(name, value, rule);
</pre>
Where 'name' is the CSS property name, 'value' is the value of the property, and 'rule'
is an object representing the whole rule. The onProperty function can return CSS properties
in text form to easily provide substitutionary CSS.

Extension modules may need to do more sophisticated interaction than just CSS replacement.
If an extension module needs to actually interact with and manipulate the DOM, it may
use the 'elemental' module to add an element renderer that will be executed for each
DOM element that matches the rule's selector.
