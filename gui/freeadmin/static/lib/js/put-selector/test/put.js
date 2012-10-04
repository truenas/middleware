var div = put("div");
console.assert(div.tagName.toLowerCase() == "div");
console.assert(put(div) === div);

var body = document.body;
put(body, "h1 $", "Running put() tests");

var parentDiv = div;

var span1 = put(parentDiv, "span.class-name-1.class-name-2[name=span1]");
console.assert(span1.className == "class-name-1 class-name-2");
console.assert(span1.getAttribute("name") == "span1");
console.assert(span1.parentNode == div);
put(span1, "!class-name-1.class-name-3[!name]");
console.assert(span1.className == "class-name-2 class-name-3");
put(span1, "!.class-name-3");
console.assert(span1.className == "class-name-2");
console.assert(span1.getAttribute("name") == null);
put(span1, "[name=span1]"); // readd the attribute

var defaultTag = put(parentDiv, " .class");
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

var parentDiv = put("div.parent span.first $ + span.second $<", "inside first", "inside second");
console.assert(parentDiv.firstChild.innerHTML, "inside first");
console.assert(parentDiv.lastChild.innerHTML, "inside second");

put(span3, "!"); // destroy span3
console.assert(span2.nextSibling != span3); // make sure span3 is gone

var span0 = put(span1, "-span[name=span0]");
console.assert(span0.getAttribute("name") == "span0");

var spanMinusTwo = put(span0, "-span -span");
console.assert(spanMinusTwo.nextSibling.nextSibling == span0);


var spanWithId = put(parentDiv, "span#with-id");
console.assert(spanWithId.id == "with-id");

var table = put(parentDiv, "table.class-name#id tr.class-name td[colSpan=2]<<tr.class-name td+td<<");
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

var div = put("div");
var arrayFrag = put(div, ["span.c1", "span.c2", "span.c3"]);
console.assert(arrayFrag.tagName.toLowerCase() == "div");
console.assert(div.firstChild.className == "c1");
console.assert(div.lastChild.className == "c3");

put(div, "#encode%3A%20d");
console.assert(div.id == "encode%3A%20d");

put(body, "div", {innerHTML: "finished tests, check console for errors"});
