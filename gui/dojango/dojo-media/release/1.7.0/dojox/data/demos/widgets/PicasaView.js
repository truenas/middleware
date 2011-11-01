//>>built
// wrapped by build app
define("dojox/data/demos/widgets/PicasaView", ["dijit","dojo","dojox","dojo/require!dijit/_Templated,dijit/_Widget"], function(dijit,dojo,dojox){
dojo.provide("dojox.data.demos.widgets.PicasaView");
dojo.require("dijit._Templated");
dojo.require("dijit._Widget");

dojo.declare("dojox.data.demos.widgets.PicasaView", [dijit._Widget, dijit._Templated], {
	//Simple demo widget for representing a view of a Picasa Item.

	templateString: dojo.cache("dojox", "data/demos/widgets/templates/PicasaView.html", "<table class=\"picasaView\">\n\t<tbody>\n\t\t<tr class=\"picasaTitle\">\n\t\t\t<td>\n\t\t\t\t<b>\n\t\t\t\t\tTitle:\n\t\t\t\t</b>\n\t\t\t</td>\n\t\t\t<td dojoAttachPoint=\"titleNode\">\n\t\t\t</td>\n\t\t</tr>\n\t\t<tr>\n\t\t\t<td>\n\t\t\t\t<b>\n\t\t\t\t\tAuthor:\n\t\t\t\t</b>\n\t\t\t</td>\n\t\t\t<td dojoAttachPoint=\"authorNode\">\n\t\t\t</td>\n\t\t</tr>\n\t\t<tr>\n\t\t\t<td colspan=\"2\">\n\t\t\t\t<b>\n\t\t\t\t\tSummary:\n\t\t\t\t</b>\n\t\t\t\t<span class=\"picasaSummary\" dojoAttachPoint=\"descriptionNode\"></span>\n\t\t\t</td>\n\t\t</tr>\n\t\t<tr>\n\t\t\t<td dojoAttachPoint=\"imageNode\" colspan=\"2\">\n\t\t\t</td>\n\t\t</tr>\n\t</tbody>\n</table>\n\n"),

	//Attach points for reference.
	titleNode: null,
	descriptionNode: null,
	imageNode: null,
	authorNode: null,

	title: "",
	author: "",
	imageUrl: "",
	iconUrl: "",

	postCreate: function(){
		this.titleNode.appendChild(document.createTextNode(this.title));
		this.authorNode.appendChild(document.createTextNode(this.author));
		this.descriptionNode.appendChild(document.createTextNode(this.description));
		var href = document.createElement("a");
		href.setAttribute("href", this.imageUrl);
		href.setAttribute("target", "_blank");
        var imageTag = document.createElement("img");
		imageTag.setAttribute("src", this.iconUrl);
		href.appendChild(imageTag);
		this.imageNode.appendChild(href);
	}
});

});
