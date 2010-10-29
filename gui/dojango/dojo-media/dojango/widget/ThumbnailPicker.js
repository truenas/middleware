dojo.provide("dojango.widget.ThumbnailPicker");

dojo.require("dojox.image.ThumbnailPicker");

dojango.widget._thumbNailPicker = {
	reset: dojox.image.ThumbnailPicker.prototype.reset // saving the reset method of the original picker
}

dojo.declare("dojango.widget.ThumbnailPicker",
	dojox.image.ThumbnailPicker,
	{
		setDataStore: function(dataStore, request, paramNames){
			this._reset();
			this.inherited(arguments);
		},
		
		reset: function(){
			// summary:
			// 	dijit.form._FormMixin.reset() is always calling the reset-method and it is
			// 	called everytime the tooltip is opened and is deleting all images that were loaded
			// 	previously!
			// 	we just call it, when a new data-store is set (see setDataStore)
			dojo.forEach(this._thumbs, function(item){
				dojo.removeClass(item, "imgSelected");
			});
		},
		
		_reset: dojango.widget._thumbNailPicker.reset // using the reset implementation of the original picker
	}
);