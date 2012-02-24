//>>built
// wrapped by build app
define("dojox/data/demos/widgets/PicasaViewList", ["dijit","dojo","dojox","dojo/require!dijit/_Templated,dijit/_Widget,dojox/data/demos/widgets/PicasaView"], function(dijit,dojo,dojox){
dojo.provide("dojox.data.demos.widgets.PicasaViewList");
dojo.require("dijit._Templated");
dojo.require("dijit._Widget");
dojo.require("dojox.data.demos.widgets.PicasaView");

dojo.declare("dojox.data.demos.widgets.PicasaViewList", [dijit._Widget, dijit._Templated], {
	//Simple demo widget that is just a list of PicasaView Widgets.

	templateString: dojo.cache("dojox", "data/demos/widgets/templates/PicasaViewList.html", "<div dojoAttachPoint=\"list\"></div>\n\n"),

	//Attach points for reference.
	listNode: null,

	postCreate: function(){
		this.fViewWidgets = [];
	},

	clearList: function(){
		while(this.list.firstChild){
			this.list.removeChild(this.list.firstChild);
		}
		for(var i = 0; i < this.fViewWidgets.length; i++){
			this.fViewWidgets[i].destroy();
		}
		this.fViewWidgets = [];
	},

	addView: function(viewData){
		 var newView  = new dojox.data.demos.widgets.PicasaView(viewData);
		 this.fViewWidgets.push(newView);
		 this.list.appendChild(newView.domNode);
	}
});

});
