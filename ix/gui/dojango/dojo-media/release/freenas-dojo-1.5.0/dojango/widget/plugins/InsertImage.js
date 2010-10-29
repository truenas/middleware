/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojango.widget.plugins.InsertImage"]){
dojo._hasResource["dojango.widget.plugins.InsertImage"]=true;
dojo.provide("dojango.widget.plugins.InsertImage");
dojo.require("dijit._editor.plugins.LinkDialog");
dojo.require("dojango.widget.ThumbnailPicker");
dojango.widget.plugins.InsertImageConfig={size:400,thumbHeight:75,thumbWidth:100,isHorizontal:true};
dojo.declare("dojango.widget.plugins.InsertImage",dijit._editor.plugins.LinkDialog,{command:"insertImage",linkDialogTemplate:["<div id=\"${id}_thumbPicker\" class=\"thumbPicker\" dojoType=\"dojango.widget.ThumbnailPicker\" size=\"${size}\"","thumbHeight=\"${thumbHeight}\" thumbWidth=\"${thumbWidth}\" isHorizontal=\"${isHorizontal}\" isClickable=\"true\"></div>","<label for=\"${id}_textInput\">${text}</label><input dojoType=\"dijit.form.ValidationTextBox\" required=\"true\" name=\"textInput\" id=\"${id}_textInput\"/>","<div><button dojoType=dijit.form.Button type=\"submit\">${set}</button></div>"].join(""),_picker:null,_textInput:null,_currentItem:null,_initButton:function(){
this.linkDialogTemplate=dojo.string.substitute(this.linkDialogTemplate,dojango.widget.plugins.InsertImageConfig,function(_1,_2){
return _1?_1:"${"+_2+"}";
});
this.inherited(arguments);
this._picker=dijit.byNode(dojo.query("[widgetId]",this.dropDown.domNode)[0]);
this._textInput=dijit.byNode(dojo.query("[widgetId]",this.dropDown.domNode)[1]);
dojo.subscribe(this._picker.getClickTopicName(),dojo.hitch(this,"_markSelected"));
this.dropDown.execute=dojo.hitch(this,"_customSetValue");
var _3=this;
this.dropDown.onOpen=function(){
_3._onOpenDialog();
dijit.TooltipDialog.prototype.onOpen.apply(this,arguments);
var p=_3._picker,a=p._thumbs[p._thumbIndex],b=p.thumbsNode;
if(typeof (a)!="undefined"&&typeof (b)!="undefined"){
var _4=a[p._offsetAttr]-b[p._offsetAttr];
p.thumbScroller[p._scrollAttr]=_4;
}
};
dijit.popup.prepare(this.dropDown.domNode);
this.editor.thumbnailPicker=this._picker;
},_customSetValue:function(_5){
if(!this._currentItem){
return false;
}
_5.urlInput=this._currentItem["largeUrl"]?this._currentItem["largeUrl"]:this._currentItem["url"];
this.setValue(_5);
},_markSelected:function(_6){
this._currentItem=_6;
this._textInput.attr("value",_6.title?_6.title:"");
this._picker.reset();
dojo.addClass(this._picker._thumbs[_6.index],"imgSelected");
}});
dojo.subscribe(dijit._scopeName+".Editor.getPlugin",null,function(o){
if(o.plugin){
return;
}
switch(o.args.name){
case "dojangoInsertImage":
o.plugin=new dojango.widget.plugins.InsertImage({command:"insertImage"});
}
});
}
