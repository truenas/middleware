/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit._base.manager"]){
dojo._hasResource["dijit._base.manager"]=true;
dojo.provide("dijit._base.manager");
dojo.declare("dijit.WidgetSet",null,{constructor:function(){
this._hash={};
this.length=0;
},add:function(_1){
if(this._hash[_1.id]){
throw new Error("Tried to register widget with id=="+_1.id+" but that id is already registered");
}
this._hash[_1.id]=_1;
this.length++;
},remove:function(id){
if(this._hash[id]){
delete this._hash[id];
this.length--;
}
},forEach:function(_2,_3){
_3=_3||dojo.global;
var i=0,id;
for(id in this._hash){
_2.call(_3,this._hash[id],i++,this._hash);
}
return this;
},filter:function(_4,_5){
_5=_5||dojo.global;
var _6=new dijit.WidgetSet(),i=0,id;
for(id in this._hash){
var w=this._hash[id];
if(_4.call(_5,w,i++,this._hash)){
_6.add(w);
}
}
return _6;
},byId:function(id){
return this._hash[id];
},byClass:function(_7){
var _8=new dijit.WidgetSet(),id,_9;
for(id in this._hash){
_9=this._hash[id];
if(_9.declaredClass==_7){
_8.add(_9);
}
}
return _8;
},toArray:function(){
var ar=[];
for(var id in this._hash){
ar.push(this._hash[id]);
}
return ar;
},map:function(_a,_b){
return dojo.map(this.toArray(),_a,_b);
},every:function(_c,_d){
_d=_d||dojo.global;
var x=0,i;
for(i in this._hash){
if(!_c.call(_d,this._hash[i],x++,this._hash)){
return false;
}
}
return true;
},some:function(_e,_f){
_f=_f||dojo.global;
var x=0,i;
for(i in this._hash){
if(_e.call(_f,this._hash[i],x++,this._hash)){
return true;
}
}
return false;
}});
(function(){
dijit.registry=new dijit.WidgetSet();
var _10=dijit.registry._hash,_11=dojo.attr,_12=dojo.hasAttr,_13=dojo.style;
dijit.byId=function(id){
return typeof id=="string"?_10[id]:id;
};
var _14={};
dijit.getUniqueId=function(_15){
var id;
do{
id=_15+"_"+(_15 in _14?++_14[_15]:_14[_15]=0);
}while(_10[id]);
return dijit._scopeName=="dijit"?id:dijit._scopeName+"_"+id;
};
dijit.findWidgets=function(_16){
var _17=[];
function _18(_19){
for(var _1a=_19.firstChild;_1a;_1a=_1a.nextSibling){
if(_1a.nodeType==1){
var _1b=_1a.getAttribute("widgetId");
if(_1b){
_17.push(_10[_1b]);
}else{
_18(_1a);
}
}
}
};
_18(_16);
return _17;
};
dijit._destroyAll=function(){
dijit._curFocus=null;
dijit._prevFocus=null;
dijit._activeStack=[];
dojo.forEach(dijit.findWidgets(dojo.body()),function(_1c){
if(!_1c._destroyed){
if(_1c.destroyRecursive){
_1c.destroyRecursive();
}else{
if(_1c.destroy){
_1c.destroy();
}
}
}
});
};
if(dojo.isIE){
dojo.addOnWindowUnload(function(){
dijit._destroyAll();
});
}
dijit.byNode=function(_1d){
return _10[_1d.getAttribute("widgetId")];
};
dijit.getEnclosingWidget=function(_1e){
while(_1e){
var id=_1e.getAttribute&&_1e.getAttribute("widgetId");
if(id){
return _10[id];
}
_1e=_1e.parentNode;
}
return null;
};
var _1f=(dijit._isElementShown=function(_20){
var s=_13(_20);
return (s.visibility!="hidden")&&(s.visibility!="collapsed")&&(s.display!="none")&&(_11(_20,"type")!="hidden");
});
dijit.hasDefaultTabStop=function(_21){
switch(_21.nodeName.toLowerCase()){
case "a":
return _12(_21,"href");
case "area":
case "button":
case "input":
case "object":
case "select":
case "textarea":
return true;
case "iframe":
if(dojo.isMoz){
try{
return _21.contentDocument.designMode=="on";
}
catch(err){
return false;
}
}else{
if(dojo.isWebKit){
var doc=_21.contentDocument,_22=doc&&doc.body;
return _22&&_22.contentEditable=="true";
}else{
try{
doc=_21.contentWindow.document;
_22=doc&&doc.body;
return _22&&_22.firstChild&&_22.firstChild.contentEditable=="true";
}
catch(e){
return false;
}
}
}
default:
return _21.contentEditable=="true";
}
};
var _23=(dijit.isTabNavigable=function(_24){
if(_11(_24,"disabled")){
return false;
}else{
if(_12(_24,"tabIndex")){
return _11(_24,"tabIndex")>=0;
}else{
return dijit.hasDefaultTabStop(_24);
}
}
});
dijit._getTabNavigable=function(_25){
var _26,_27,_28,_29,_2a,_2b;
var _2c=function(_2d){
dojo.query("> *",_2d).forEach(function(_2e){
if((dojo.isIE&&_2e.scopeName!=="HTML")||!_1f(_2e)){
return;
}
if(_23(_2e)){
var _2f=_11(_2e,"tabIndex");
if(!_12(_2e,"tabIndex")||_2f==0){
if(!_26){
_26=_2e;
}
_27=_2e;
}else{
if(_2f>0){
if(!_28||_2f<_29){
_29=_2f;
_28=_2e;
}
if(!_2a||_2f>=_2b){
_2b=_2f;
_2a=_2e;
}
}
}
}
if(_2e.nodeName.toUpperCase()!="SELECT"){
_2c(_2e);
}
});
};
if(_1f(_25)){
_2c(_25);
}
return {first:_26,last:_27,lowest:_28,highest:_2a};
};
dijit.getFirstInTabbingOrder=function(_30){
var _31=dijit._getTabNavigable(dojo.byId(_30));
return _31.lowest?_31.lowest:_31.first;
};
dijit.getLastInTabbingOrder=function(_32){
var _33=dijit._getTabNavigable(dojo.byId(_32));
return _33.last?_33.last:_33.highest;
};
dijit.defaultDuration=dojo.config["defaultDuration"]||200;
})();
}
