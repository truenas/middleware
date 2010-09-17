/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit._CssStateMixin"]){
dojo._hasResource["dijit._CssStateMixin"]=true;
dojo.provide("dijit._CssStateMixin");
dojo.declare("dijit._CssStateMixin",[],{cssStateNodes:{},postCreate:function(){
this.inherited(arguments);
dojo.forEach(["onmouseenter","onmouseleave","onmousedown"],function(e){
this.connect(this.domNode,e,"_cssMouseEvent");
},this);
this.connect(this,"set",function(_1,_2){
if(arguments.length>=2&&{disabled:true,readOnly:true,checked:true,selected:true}[_1]){
this._setStateClass();
}
});
dojo.forEach(["_onFocus","_onBlur"],function(ap){
this.connect(this,ap,"_setStateClass");
},this);
for(var ap in this.cssStateNodes){
this._trackMouseState(this[ap],this.cssStateNodes[ap]);
}
this._setStateClass();
},_cssMouseEvent:function(_3){
if(!this.disabled){
switch(_3.type){
case "mouseenter":
case "mouseover":
this._hovering=true;
this._active=this._mouseDown;
break;
case "mouseleave":
case "mouseout":
this._hovering=false;
this._active=false;
break;
case "mousedown":
this._active=true;
this._mouseDown=true;
var _4=this.connect(dojo.body(),"onmouseup",function(){
this._active=false;
this._mouseDown=false;
this._setStateClass();
this.disconnect(_4);
});
break;
}
this._setStateClass();
}
},_setStateClass:function(){
var _5=this.baseClass.split(" ");
function _6(_7){
_5=_5.concat(dojo.map(_5,function(c){
return c+_7;
}),"dijit"+_7);
};
if(!this.isLeftToRight()){
_6("Rtl");
}
if(this.checked){
_6("Checked");
}
if(this.state){
_6(this.state);
}
if(this.selected){
_6("Selected");
}
if(this.disabled){
_6("Disabled");
}else{
if(this.readOnly){
_6("ReadOnly");
}else{
if(this._active){
_6("Active");
}else{
if(this._hovering){
_6("Hover");
}
}
}
}
if(this._focused){
_6("Focused");
}
var tn=this.stateNode||this.domNode,_8={};
dojo.forEach(tn.className.split(" "),function(c){
_8[c]=true;
});
if("_stateClasses" in this){
dojo.forEach(this._stateClasses,function(c){
delete _8[c];
});
}
dojo.forEach(_5,function(c){
_8[c]=true;
});
var _9=[];
for(var c in _8){
_9.push(c);
}
tn.className=_9.join(" ");
this._stateClasses=_5;
},_trackMouseState:function(_a,_b){
var _c=false,_d=false,_e=false;
var _f=this,cn=dojo.hitch(this,"connect",_a);
function _10(){
var _11=("disabled" in _f&&_f.disabled)||("readonly" in _f&&_f.readonly);
dojo.toggleClass(_a,_b+"Hover",_c&&!_d&&!_11);
dojo.toggleClass(_a,_b+"Active",_d&&!_11);
dojo.toggleClass(_a,_b+"Focused",_e&&!_11);
};
cn("onmouseenter",function(){
_c=true;
_10();
});
cn("onmouseleave",function(){
_c=false;
_d=false;
_10();
});
cn("onmousedown",function(){
_d=true;
_10();
});
cn("onmouseup",function(){
_d=false;
_10();
});
cn("onfocus",function(){
_e=true;
_10();
});
cn("onblur",function(){
_e=false;
_10();
});
this.connect(this,"set",function(_12,_13){
if(_12=="disabled"||_12=="readOnly"){
_10();
}
});
}});
}
