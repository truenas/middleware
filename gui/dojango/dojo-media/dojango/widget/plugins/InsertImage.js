dojo.provide("dojango.widget.plugins.InsertImage");

dojo.require("dijit._editor.plugins.LinkDialog");
dojo.require("dojango.widget.ThumbnailPicker");

dojango.widget.plugins.InsertImageConfig = {
	// these values just can be overwritten, when the plugin is loaded synchronous
	size:400,
	thumbHeight:75,
	thumbWidth:100,
	isHorizontal:true
}

dojo.declare("dojango.widget.plugins.InsertImage",
	dijit._editor.plugins.LinkDialog,
	{
		// summary:
		//	An editor plugin that uses dojox.image.ThumbailPicker to select an image and inserting it into the editor.
		//	Populates the ThumbnailPicker as the editor attribute "thumbnailPicker", where you can attach your store
		//	via setDataStore. For store examples look at the dojox.image.ThumbnailPicker tests.
		//	The InsertImage plugin simply extends the LinkDialog plugin which already contains the functionality
		//	for inserting an image.
		//
		// example:
		// |	// these css files are required:
		// |	// <link rel="stylesheet" href="%{DOJOX_URL}/image/resources/image.css">
		// |	// <link rel="stylesheet" href="%{DOJANGO_URL}/widget/resources/ThumbnailPicker.css">
		// |	dojo.require("dijit.Editor");
		// |	dojo.require("dojango.widget.plugins.InsertImage");
		// |	dojo.require("dojox.data.FlickrRestStore");
		// |	
		// |	var flickrRestStore = new dojox.data.FlickrRestStore();
		// |	var req = {
		// |		query: {
		// |			apikey: "8c6803164dbc395fb7131c9d54843627", tags: ["dojobeer"]
		// |		},
		// |		count: 20
		// |	};
		// |	var editor = new dijit.Editor({}, dojo.place(dojo.body()));
		// |	editor.thumbnailPicker.setDataStore(flickrRestStore, req);
		
		//size, thumbHeight, thumbWidth, isHorizontal <= setting these additional parameters
		command: "insertImage",
		linkDialogTemplate: [
					'<div id="${id}_thumbPicker" class="thumbPicker" dojoType="dojango.widget.ThumbnailPicker" size="${size}"',
					'thumbHeight="${thumbHeight}" thumbWidth="${thumbWidth}" isHorizontal="${isHorizontal}" isClickable="true"></div>',
					'<label for="${id}_textInput">${text}</label><input dojoType="dijit.form.ValidationTextBox" required="true" name="textInput" id="${id}_textInput"/>',
					'<div><button dojoType=dijit.form.Button type="submit">${set}</button></div>'
				].join(""),
		_picker: null,
		_textInput: null,
		_currentItem: null,
		_initButton: function(){
			this.linkDialogTemplate = dojo.string.substitute(this.linkDialogTemplate,
				dojango.widget.plugins.InsertImageConfig, 
				function(value, key){
					return value ? value : "${" + key + "}"; // we keep the non-matching keys
				}
			);
			this.inherited(arguments);
			// creating a unique id should happen outside of _initButton (see LinkDialog), so accessing 
			// the widgets in the linkDialog would be easier!
			this._picker = dijit.byNode(dojo.query("[widgetId]", this.dropDown.domNode)[0]);
			this._textInput = dijit.byNode(dojo.query("[widgetId]", this.dropDown.domNode)[1]);
			
			dojo.subscribe(this._picker.getClickTopicName(), dojo.hitch(this, "_markSelected"));
			this.dropDown.execute = dojo.hitch(this, "_customSetValue");
			var _this=this;
			this.dropDown.onOpen = function(){
				_this._onOpenDialog();
				dijit.TooltipDialog.prototype.onOpen.apply(this, arguments);
				// resetting scroller (onOpen scrollLeft set to 0!)
				var p = _this._picker, a = p._thumbs[p._thumbIndex],
					b = p.thumbsNode;
				if(typeof(a) != "undefined" && typeof(b) != "undefined" ){
					var left = a[p._offsetAttr] - b[p._offsetAttr];
					p.thumbScroller[p._scrollAttr] = left;
				}
			}
			// the popup needs to be generated, so the ThumbnailPicker can align the images!
			dijit.popup.prepare(this.dropDown.domNode);
			// assigning the picker to the editor
			this.editor.thumbnailPicker = this._picker;
		},
		
		_customSetValue: function(args){
			if(! this._currentItem) {
				return false;
			}
			// pass the url of the current selected image to the setValue method
			args.urlInput = this._currentItem['largeUrl'] ? this._currentItem['largeUrl'] : this._currentItem['url'];
			this.setValue(args);
		},
		
		_markSelected: function(item){
			// url, largeUrl, title, link
			this._currentItem = item;
			this._textInput.attr("value", item.title ? item.title : "");
			this._picker.reset();
			dojo.addClass(this._picker._thumbs[item.index], "imgSelected");
		}
	}
);

// Register this plugin.
dojo.subscribe(dijit._scopeName + ".Editor.getPlugin",null,function(o){
	if(o.plugin){ return; }
	switch(o.args.name){
	case "dojangoInsertImage":
		o.plugin = new dojango.widget.plugins.InsertImage({command: "insertImage"});
	}
});