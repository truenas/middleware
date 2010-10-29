/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojango.widget.ThumbnailPicker"]){
dojo._hasResource["dojango.widget.ThumbnailPicker"]=true;
dojo.provide("dojango.widget.ThumbnailPicker");
dojo.require("dojox.image.ThumbnailPicker");
dojango.widget._thumbNailPicker={reset:dojox.image.ThumbnailPicker.prototype.reset};
dojo.declare("dojango.widget.ThumbnailPicker",dojox.image.ThumbnailPicker,{setDataStore:function(_1,_2,_3){
this._reset();
this.inherited(arguments);
},reset:function(){
dojo.forEach(this._thumbs,function(_4){
dojo.removeClass(_4,"imgSelected");
});
},_reset:dojango.widget._thumbNailPicker.reset});
}
