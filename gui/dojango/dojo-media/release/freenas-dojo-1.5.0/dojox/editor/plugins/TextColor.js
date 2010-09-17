/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.editor.plugins.TextColor"]){
dojo._hasResource["dojox.editor.plugins.TextColor"]=true;
dojo.provide("dojox.editor.plugins.TextColor");
dojo.require("dijit._editor._Plugin");
dojo.require("dijit.TooltipDialog");
dojo.require("dijit.form.Button");
dojo.require("dojox.widget.ColorPicker");
dojo.require("dojo.i18n");
dojo.requireLocalization("dojox.editor.plugins","TextColor",null,"ROOT,ro");
dojo.experimental("dojox.editor.plugins.TextColor");
dojo.declare("dojox.editor.plugins._TextColorDropDown",[dijit._Widget,dijit._Templated],{templateString:"<div style='display: none; position: absolute; top: -10000; z-index: -10000'>"+"<div dojoType='dijit.TooltipDialog' dojoAttachPoint='dialog' class='dojoxEditorColorPicker'>"+"<div dojoType='dojox.widget.ColorPicker' dojoAttachPoint='_colorPicker'></div>"+"<br>"+"<center>"+"<button dojoType='dijit.form.Button' type='button' dojoAttachPoint='_setButton'>${setButtonText}</button>"+"&nbsp;"+"<button dojoType='dijit.form.Button' type='button' dojoAttachPoint='_cancelButton'>${cancelButtonText}</button>"+"</center>"+"</div>"+"</div>",widgetsInTemplate:true,constructor:function(){
var _1=dojo.i18n.getLocalization("dojox.editor.plugins","TextColor");
dojo.mixin(this,_1);
},startup:function(){
if(!this._started){
this.inherited(arguments);
this.connect(this._setButton,"onClick",dojo.hitch(this,function(){
this.onChange(this.get("value"));
}));
this.connect(this._cancelButton,"onClick",dojo.hitch(this,function(){
dijit.popup.close(this.dialog);
this.onCancel();
}));
dojo.style(this.domNode,"display","block");
}
},_setValueAttr:function(_2,_3){
this._colorPicker.set("value",_2,_3);
},_getValueAttr:function(){
return this._colorPicker.get("value");
},onChange:function(_4){
},onCancel:function(){
}});
dojo.declare("dojox.editor.plugins.TextColor",dijit._editor._Plugin,{buttonClass:dijit.form.DropDownButton,useDefaultCommand:false,constructor:function(){
this._picker=new dojox.editor.plugins._TextColorDropDown();
dojo.body().appendChild(this._picker.domNode);
this._picker.startup();
this.dropDown=this._picker.dialog;
this.connect(this._picker,"onChange",function(_5){
this.editor.execCommand(this.command,_5);
});
this.connect(this._picker,"onCancel",function(){
this.editor.focus();
});
},updateState:function(){
var _6=this.editor;
var _7=this.command;
if(!_6||!_6.isLoaded||!_7.length){
return;
}
var _8;
if(this.button){
try{
_8=_6.queryCommandValue(_7)||"";
}
catch(e){
_8="";
}
}
if(_8==""){
_8="#000000";
}
if(_8=="transparent"){
_8="#ffffff";
}
if(typeof _8=="string"){
if(_8.indexOf("rgb")>-1){
_8=dojo.colorFromRgb(_8).toHex();
}
}else{
_8=((_8&255)<<16)|(_8&65280)|((_8&16711680)>>>16);
_8=_8.toString(16);
_8="#000000".slice(0,7-_8.length)+_8;
}
if(_8!==this._picker.get("value")){
this._picker.set("value",_8,false);
}
},destroy:function(){
this.inherited(arguments);
this._picker.destroyRecursive();
delete this._picker;
}});
dojo.subscribe(dijit._scopeName+".Editor.getPlugin",null,function(o){
if(o.plugin){
return;
}
switch(o.args.name){
case "foreColor":
case "hiliteColor":
o.plugin=new dojox.editor.plugins.TextColor({command:o.args.name});
}
});
}
