var div = put("div");
console.assert(div.tagName.toLowerCase() == "div");

var body = document.body;
put(body, "h1 $", "Running put() tests");

var parent = div;

var span1 = put(parent, "span.class-name-1.class-name-2[name=span1]");
console.assert(span1.className == "class-name-1 class-name-2");
console.assert(span1.getAttribute("name") == "span1");
console.assert(span1.parentNode == div);
put(span1, "!class-name-1.class-name-3[!name]");
console.assert(span1.className == "class-name-2 class-name-3");
console.assert(span1.getAttribute("name") == null);
put(span1, "[name=span1]"); // readd the attribute

var defaultTag = put(parent, " .class");
console.assert(defaultTag.tagName.toLowerCase() == "div");
var span2, span3 = put(span1, "+span[name=span2] + span[name=span3]");
console.assert(span3.getAttribute("name") == "span3");
console.assert((span2 = span3.previousSibling).getAttribute("name") == "span2");
console.assert(span3.previousSibling.previousSibling.getAttribute("name") == "span1");
var span4 = put(span2, ">", span3, "span.$[name=$]", "span3-child", "span4");
console.assert(span3.parentNode == span2);
console.assert(span4.parentNode == span3);
console.assert(span4.className == "span3-child");
console.assert(span4.getAttribute('name') == "span4");
put(span2, "+", span3, "+", span4);
console.assert(span2.nextSibling == span3);
console.assert(span3.nextSibling == span4);

put(span3, "!"); // destroy span3
console.assert(span2.nextSibling != span3); // make sure span3 is gone


var span0 = put(span1, "-span[name=span0]");
console.assert(span0.getAttribute("name") == "span0");

var spanWithId = put(parent, "span#with-id");
console.assert(spanWithId.id == "with-id");

var table = put(parent, "table.class-name#id tr.class-name td[colSpan=2]<<tr.class-name td+td<<");
console.assert(table.tagName.toLowerCase() == "table");
console.assert(table.childNodes.length == 2);
console.assert(table.firstChild.className == "class-name");
console.assert(table.firstChild.childNodes.length == 1);
console.assert(table.lastChild.className == "class-name");
console.assert(table.lastChild.childNodes.length == 2);

put(table, "tr>td,tr>td+td");
console.assert(table.childNodes.length == 4);
console.assert(table.lastChild.childNodes.length == 2);

var checkbox = put(div, "input[type=checkbox][checked]");
console.assert(checkbox.type == "checkbox");
console.assert(checkbox.getAttribute("checked") == "checked");

put(body, "div", {innerHTML: "finished tests, check console for errors"});