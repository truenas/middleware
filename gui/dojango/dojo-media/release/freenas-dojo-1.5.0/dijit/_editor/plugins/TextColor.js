/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit._editor.plugins.TextColor"]){
dojo._hasResource["dijit._editor.plugins.TextColor"]=true;
dojo.provide("dijit._editor.plugins.TextColor");
dojo.require("dijit._editor._Plugin");
dojo.require("dijit.ColorPalette");
dojo.declare("dijit._editor.plugins.TextColor",dijit._editor._Plugin,{buttonClass:dijit.form.DropDownButton,useDefaultCommand:false,constructor:function(){
this.dropDown=new dijit.ColorPalette();
this.connect(this.dropDown,"onChange",function(_1){
this.editor.execCommand(this.command,_1);
});
},updateState:function(){
var _2=this.editor;
var _3=this.command;
if(!_2||!_2.isLoaded||!_3.length){
return;
}
if(this.button){
var _4;
try{
_4=_2.queryCommandValue(_3)||"";
}
catch(e){
_4="";
}
}
if(_4==""){
_4="#000000";
}
if(_4=="transparent"){
_4="#ffffff";
}
if(typeof _4=="string"){
if(_4.indexOf("rgb")>-1){
_4=dojo.colorFromRgb(_4).toHex();
}
}else{
_4=((_4&255)<<16)|(_4&65280)|((_4&16711680)>>>16);
_4=_4.toString(16);
_4="#000000".slice(0,7-_4.length)+_4;
}
if(_4!==this.dropDown.get("value")){
this.dropDown.set("value",_4,false);
}
}});
dojo.subscribe(dijit._scopeName+".Editor.getPlugin",null,function(o){
if(o.plugin){
return;
}
switch(o.args.name){
case "foreColor":
case "hiliteColor":
o.plugin=new dijit._editor.plugins.TextColor({command:o.args.name});
}
});
}
