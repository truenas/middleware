/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit._editor._Plugin"]){
dojo._hasResource["dijit._editor._Plugin"]=true;
dojo.provide("dijit._editor._Plugin");
dojo.require("dijit._Widget");
dojo.require("dijit.form.Button");
dojo.declare("dijit._editor._Plugin",null,{constructor:function(_1,_2){
this.params=_1||{};
dojo.mixin(this,this.params);
this._connects=[];
},editor:null,iconClassPrefix:"dijitEditorIcon",button:null,command:"",useDefaultCommand:true,buttonClass:dijit.form.Button,getLabel:function(_3){
return this.editor.commands[_3];
},_initButton:function(){
if(this.command.length){
var _4=this.getLabel(this.command),_5=this.editor,_6=this.iconClassPrefix+" "+this.iconClassPrefix+this.command.charAt(0).toUpperCase()+this.command.substr(1);
if(!this.button){
var _7=dojo.mixin({label:_4,dir:_5.dir,lang:_5.lang,showLabel:false,iconClass:_6,dropDown:this.dropDown,tabIndex:"-1"},this.params||{});
this.button=new this.buttonClass(_7);
}
}
},destroy:function(){
dojo.forEach(this._connects,dojo.disconnect);
if(this.dropDown){
this.dropDown.destroyRecursive();
}
},connect:function(o,f,tf){
this._connects.push(dojo.connect(o,f,this,tf));
},updateState:function(){
var e=this.editor,c=this.command,_8,_9;
if(!e||!e.isLoaded||!c.length){
return;
}
if(this.button){
try{
_9=e.queryCommandEnabled(c);
if(this.enabled!==_9){
this.enabled=_9;
this.button.set("disabled",!_9);
}
if(typeof this.button.checked=="boolean"){
_8=e.queryCommandState(c);
if(this.checked!==_8){
this.checked=_8;
this.button.set("checked",e.queryCommandState(c));
}
}
}
catch(e){
console.log(e);
}
}
},setEditor:function(_a){
this.editor=_a;
this._initButton();
if(this.button&&this.useDefaultCommand){
if(this.editor.queryCommandAvailable(this.command)){
this.connect(this.button,"onClick",dojo.hitch(this.editor,"execCommand",this.command,this.commandArg));
}else{
this.button.domNode.style.display="none";
}
}
this.connect(this.editor,"onNormalizedDisplayChanged","updateState");
},setToolbar:function(_b){
if(this.button){
_b.addChild(this.button);
}
}});
}
