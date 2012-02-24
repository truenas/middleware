//>>built
// wrapped by build app
define("dojox/data/demos/widgets/FileView", ["dijit","dojo","dojox","dojo/require!dijit/_Templated,dijit/_Widget"], function(dijit,dojo,dojox){
dojo.provide("dojox.data.demos.widgets.FileView");
dojo.require("dijit._Templated");
dojo.require("dijit._Widget");

dojo.declare("dojox.data.demos.widgets.FileView", [dijit._Widget, dijit._Templated], {
	//Simple demo widget for representing a view of a Flickr Item.

	templateString: dojo.cache("dojox", "data/demos/widgets/templates/FileView.html", "<div class=\"fileView\">\n\t<div class=\"fileViewTitle\">File Details:</div>\n\t<table class=\"fileViewTable\">\n\t\t<tbody>\n\t\t\t<tr class=\"fileName\">\n\t\t\t\t<td>\n\t\t\t\t\t<b>\n\t\t\t\t\t\tName:\n\t\t\t\t\t</b>\n\t\t\t\t</td>\n\t\t\t\t<td dojoAttachPoint=\"nameNode\">\n\t\t\t\t</td>\n\t\t\t</tr>\n\t\t\t<tr>\n\t\t\t\t<td>\n\t\t\t\t\t<b>\n\t\t\t\t\t\tPath:\n\t\t\t\t\t</b>\n\t\t\t\t</td>\n\t\t\t\t<td dojoAttachPoint=\"pathNode\">\n\t\t\t\t</td>\n\t\t\t</tr>\n\t\t\t<tr>\n\t\t\t\t<td>\n\t\t\t\t\t<b>\n\t\t\t\t\t\tSize:\n\t\t\t\t\t</b>\n\t\t\t\t</td>\n\t\t\t\t<td>\n\t\t\t\t\t<span dojoAttachPoint=\"sizeNode\"></span>&nbsp;bytes.\n\t\t\t\t</td>\n\t\t\t</tr>\n\t\t\t<tr>\n\t\t\t\t<td>\n\t\t\t\t\t<b>\n\t\t\t\t\t\tIs Directory:\n\t\t\t\t\t</b>\n\t\t\t\t</td>\n\t\t\t\t<td dojoAttachPoint=\"directoryNode\">\n\t\t\t\t</td>\n\t\t\t</tr>\n\t\t\t<tr>\n\t\t\t\t<td>\n\t\t\t\t\t<b>\n\t\t\t\t\t\tParent Directory:\n\t\t\t\t\t</b>\n\t\t\t\t</td>\n\t\t\t\t<td dojoAttachPoint=\"parentDirNode\">\n\t\t\t\t</td>\n\t\t\t</tr>\n\t\t\t<tr>\n\t\t\t\t<td>\n\t\t\t\t\t<b>\n\t\t\t\t\t\tChildren:\n\t\t\t\t\t</b>\n\t\t\t\t</td>\n\t\t\t\t<td dojoAttachPoint=\"childrenNode\">\n\t\t\t\t</td>\n\t\t\t</tr>\n\t\t</tbody>\n\t</table>\n</div>\n"),

	//Attach points for reference.
	titleNode: null,
	descriptionNode: null,
	imageNode: null,
	authorNode: null,

	name: "",
	path: "",
	size: 0,
	directory: false,
	parentDir: "",
	children: [],

	postCreate: function(){
		this.nameNode.appendChild(document.createTextNode(this.name));
		this.pathNode.appendChild(document.createTextNode(this.path));
		this.sizeNode.appendChild(document.createTextNode(this.size));
		this.directoryNode.appendChild(document.createTextNode(this.directory));
		this.parentDirNode.appendChild(document.createTextNode(this.parentDir));
		if (this.children && this.children.length > 0) {
			var i;
			for (i = 0; i < this.children.length; i++) {
				var tNode = document.createTextNode(this.children[i]);
				this.childrenNode.appendChild(tNode);
				if (i < (this.children.length - 1)) {
					this.childrenNode.appendChild(document.createElement("br"));
				}
			}
		}
	}
});

});
