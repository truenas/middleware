/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit._Widget"]){
dojo._hasResource["dijit._Widget"]=true;
dojo.provide("dijit._Widget");
dojo.require("dijit._base");
dojo.connect(dojo,"_connect",function(_1,_2){
if(_1&&dojo.isFunction(_1._onConnect)){
_1._onConnect(_2);
}
});
dijit._connectOnUseEventHandler=function(_3){
};
dijit._lastKeyDownNode=null;
if(dojo.isIE){
(function(){
var _4=function(_5){
dijit._lastKeyDownNode=_5.srcElement;
};
dojo.doc.attachEvent("onkeydown",_4);
dojo.addOnWindowUnload(function(){
dojo.doc.detachEvent("onkeydown",_4);
});
})();
}else{
dojo.doc.addEventListener("keydown",function(_6){
dijit._lastKeyDownNode=_6.target;
},true);
}
(function(){
var _7={},_8=function(_9){
var dc=_9.declaredClass;
if(!_7[dc]){
var r=[],_a,_b=_9.constructor.prototype;
for(var _c in _b){
if(dojo.isFunction(_b[_c])&&(_a=_c.match(/^_set([a-zA-Z]*)Attr$/))&&_a[1]){
r.push(_a[1].charAt(0).toLowerCase()+_a[1].substr(1));
}
}
_7[dc]=r;
}
return _7[dc]||[];
};
dojo.declare("dijit._Widget",null,{id:"",lang:"",dir:"","class":"",style:"",title:"",tooltip:"",baseClass:"",srcNodeRef:null,domNode:null,containerNode:null,attributeMap:{id:"",dir:"",lang:"","class":"",style:"",title:""},_deferredConnects:{onClick:"",onDblClick:"",onKeyDown:"",onKeyPress:"",onKeyUp:"",onMouseMove:"",onMouseDown:"",onMouseOut:"",onMouseOver:"",onMouseLeave:"",onMouseEnter:"",onMouseUp:""},onClick:dijit._connectOnUseEventHandler,onDblClick:dijit._connectOnUseEventHandler,onKeyDown:dijit._connectOnUseEventHandler,onKeyPress:dijit._connectOnUseEventHandler,onKeyUp:dijit._connectOnUseEventHandler,onMouseDown:dijit._connectOnUseEventHandler,onMouseMove:dijit._connectOnUseEventHandler,onMouseOut:dijit._connectOnUseEventHandler,onMouseOver:dijit._connectOnUseEventHandler,onMouseLeave:dijit._connectOnUseEventHandler,onMouseEnter:dijit._connectOnUseEventHandler,onMouseUp:dijit._connectOnUseEventHandler,_blankGif:(dojo.config.blankGif||dojo.moduleUrl("dojo","resources/blank.gif")).toString(),postscript:function(_d,_e){
this.create(_d,_e);
},create:function(_f,_10){
this.srcNodeRef=dojo.byId(_10);
this._connects=[];
this._subscribes=[];
this._deferredConnects=dojo.clone(this._deferredConnects);
for(var _11 in this.attributeMap){
delete this._deferredConnects[_11];
}
for(_11 in this._deferredConnects){
if(this[_11]!==dijit._connectOnUseEventHandler){
delete this._deferredConnects[_11];
}
}
if(this.srcNodeRef&&(typeof this.srcNodeRef.id=="string")){
this.id=this.srcNodeRef.id;
}
if(_f){
this.params=_f;
dojo.mixin(this,_f);
}
this.postMixInProperties();
if(!this.id){
this.id=dijit.getUniqueId(this.declaredClass.replace(/\./g,"_"));
}
dijit.registry.add(this);
this.buildRendering();
if(this.domNode){
this._applyAttributes();
var _12=this.srcNodeRef;
if(_12&&_12.parentNode){
_12.parentNode.replaceChild(this.domNode,_12);
}
for(_11 in this.params){
this._onConnect(_11);
}
}
if(this.domNode){
this.domNode.setAttribute("widgetId",this.id);
}
this.postCreate();
if(this.srcNodeRef&&!this.srcNodeRef.parentNode){
delete this.srcNodeRef;
}
this._created=true;
},_applyAttributes:function(){
var _13=function(_14,_15){
if((_15.params&&_14 in _15.params)||_15[_14]){
_15.set(_14,_15[_14]);
}
};
for(var _16 in this.attributeMap){
_13(_16,this);
}
dojo.forEach(_8(this),function(a){
if(!(a in this.attributeMap)){
_13(a,this);
}
},this);
},postMixInProperties:function(){
},buildRendering:function(){
this.domNode=this.srcNodeRef||dojo.create("div");
},postCreate:function(){
if(this.baseClass){
var _17=this.baseClass.split(" ");
if(!this.isLeftToRight()){
_17=_17.concat(dojo.map(_17,function(_18){
return _18+"Rtl";
}));
}
dojo.addClass(this.domNode,_17);
}
},startup:function(){
this._started=true;
},destroyRecursive:function(_19){
this._beingDestroyed=true;
this.destroyDescendants(_19);
this.destroy(_19);
},destroy:function(_1a){
this._beingDestroyed=true;
this.uninitialize();
var d=dojo,dfe=d.forEach,dun=d.unsubscribe;
dfe(this._connects,function(_1b){
dfe(_1b,d.disconnect);
});
dfe(this._subscribes,function(_1c){
dun(_1c);
});
dfe(this._supportingWidgets||[],function(w){
if(w.destroyRecursive){
w.destroyRecursive();
}else{
if(w.destroy){
w.destroy();
}
}
});
this.destroyRendering(_1a);
dijit.registry.remove(this.id);
this._destroyed=true;
},destroyRendering:function(_1d){
if(this.bgIframe){
this.bgIframe.destroy(_1d);
delete this.bgIframe;
}
if(this.domNode){
if(_1d){
dojo.removeAttr(this.domNode,"widgetId");
}else{
dojo.destroy(this.domNode);
}
delete this.domNode;
}
if(this.srcNodeRef){
if(!_1d){
dojo.destroy(this.srcNodeRef);
}
delete this.srcNodeRef;
}
},destroyDescendants:function(_1e){
dojo.forEach(this.getChildren(),function(_1f){
if(_1f.destroyRecursive){
_1f.destroyRecursive(_1e);
}
});
},uninitialize:function(){
return false;
},onFocus:function(){
},onBlur:function(){
},_onFocus:function(e){
this.onFocus();
},_onBlur:function(){
this.onBlur();
},_onConnect:function(_20){
if(_20 in this._deferredConnects){
var _21=this[this._deferredConnects[_20]||"domNode"];
this.connect(_21,_20.toLowerCase(),_20);
delete this._deferredConnects[_20];
}
},_setClassAttr:function(_22){
var _23=this[this.attributeMap["class"]||"domNode"];
dojo.removeClass(_23,this["class"]);
this["class"]=_22;
dojo.addClass(_23,_22);
},_setStyleAttr:function(_24){
var _25=this[this.attributeMap.style||"domNode"];
if(dojo.isObject(_24)){
dojo.style(_25,_24);
}else{
if(_25.style.cssText){
_25.style.cssText+="; "+_24;
}else{
_25.style.cssText=_24;
}
}
this.style=_24;
},setAttribute:function(_26,_27){
dojo.deprecated(this.declaredClass+"::setAttribute(attr, value) is deprecated. Use set() instead.","","2.0");
this.set(_26,_27);
},_attrToDom:function(_28,_29){
var _2a=this.attributeMap[_28];
dojo.forEach(dojo.isArray(_2a)?_2a:[_2a],function(_2b){
var _2c=this[_2b.node||_2b||"domNode"];
var _2d=_2b.type||"attribute";
switch(_2d){
case "attribute":
if(dojo.isFunction(_29)){
_29=dojo.hitch(this,_29);
}
var _2e=_2b.attribute?_2b.attribute:(/^on[A-Z][a-zA-Z]*$/.test(_28)?_28.toLowerCase():_28);
dojo.attr(_2c,_2e,_29);
break;
case "innerText":
_2c.innerHTML="";
_2c.appendChild(dojo.doc.createTextNode(_29));
break;
case "innerHTML":
_2c.innerHTML=_29;
break;
case "class":
dojo.removeClass(_2c,this[_28]);
dojo.addClass(_2c,_29);
break;
}
},this);
this[_28]=_29;
},attr:function(_2f,_30){
if(dojo.config.isDebug){
var _31=arguments.callee._ach||(arguments.callee._ach={}),_32=(arguments.callee.caller||"unknown caller").toString();
if(!_31[_32]){
dojo.deprecated(this.declaredClass+"::attr() is deprecated. Use get() or set() instead, called from "+_32,"","2.0");
_31[_32]=true;
}
}
var _33=arguments.length;
if(_33>=2||typeof _2f==="object"){
return this.set.apply(this,arguments);
}else{
return this.get(_2f);
}
},get:function(_34){
var _35=this._getAttrNames(_34);
return this[_35.g]?this[_35.g]():this[_34];
},set:function(_36,_37){
if(typeof _36==="object"){
for(var x in _36){
this.set(x,_36[x]);
}
return this;
}
var _38=this._getAttrNames(_36);
if(this[_38.s]){
var _39=this[_38.s].apply(this,Array.prototype.slice.call(arguments,1));
}else{
if(_36 in this.attributeMap){
this._attrToDom(_36,_37);
}
var _3a=this[_36];
this[_36]=_37;
}
return _39||this;
},_attrPairNames:{},_getAttrNames:function(_3b){
var apn=this._attrPairNames;
if(apn[_3b]){
return apn[_3b];
}
var uc=_3b.charAt(0).toUpperCase()+_3b.substr(1);
return (apn[_3b]={n:_3b+"Node",s:"_set"+uc+"Attr",g:"_get"+uc+"Attr"});
},toString:function(){
return "[Widget "+this.declaredClass+", "+(this.id||"NO ID")+"]";
},getDescendants:function(){
return this.containerNode?dojo.query("[widgetId]",this.containerNode).map(dijit.byNode):[];
},getChildren:function(){
return this.containerNode?dijit.findWidgets(this.containerNode):[];
},nodesWithKeyClick:["input","button"],connect:function(obj,_3c,_3d){
var d=dojo,dc=d._connect,_3e=[];
if(_3c=="ondijitclick"){
if(dojo.indexOf(this.nodesWithKeyClick,obj.nodeName.toLowerCase())==-1){
var m=d.hitch(this,_3d);
_3e.push(dc(obj,"onkeydown",this,function(e){
if((e.keyCode==d.keys.ENTER||e.keyCode==d.keys.SPACE)&&!e.ctrlKey&&!e.shiftKey&&!e.altKey&&!e.metaKey){
dijit._lastKeyDownNode=e.target;
e.preventDefault();
}
}),dc(obj,"onkeyup",this,function(e){
if((e.keyCode==d.keys.ENTER||e.keyCode==d.keys.SPACE)&&e.target===dijit._lastKeyDownNode&&!e.ctrlKey&&!e.shiftKey&&!e.altKey&&!e.metaKey){
dijit._lastKeyDownNode=null;
return m(e);
}
}));
}
_3c="onclick";
}
_3e.push(dc(obj,_3c,this,_3d));
this._connects.push(_3e);
return _3e;
},disconnect:function(_3f){
for(var i=0;i<this._connects.length;i++){
if(this._connects[i]==_3f){
dojo.forEach(_3f,dojo.disconnect);
this._connects.splice(i,1);
return;
}
}
},subscribe:function(_40,_41){
var d=dojo,_42=d.subscribe(_40,this,_41);
this._subscribes.push(_42);
return _42;
},unsubscribe:function(_43){
for(var i=0;i<this._subscribes.length;i++){
if(this._subscribes[i]==_43){
dojo.unsubscribe(_43);
this._subscribes.splice(i,1);
return;
}
}
},isLeftToRight:function(){
return this.dir?(this.dir=="ltr"):dojo._isBodyLtr();
},isFocusable:function(){
return this.focus&&(dojo.style(this.domNode,"display")!="none");
},placeAt:function(_44,_45){
if(_44.declaredClass&&_44.addChild){
_44.addChild(this,_45);
}else{
dojo.place(this.domNode,_44,_45);
}
return this;
},_onShow:function(){
this.onShow();
},onShow:function(){
},onHide:function(){
},onClose:function(){
return true;
}});
})();
}
