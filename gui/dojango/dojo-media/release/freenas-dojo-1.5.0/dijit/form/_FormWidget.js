/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.form._FormWidget"]){
dojo._hasResource["dijit.form._FormWidget"]=true;
dojo.provide("dijit.form._FormWidget");
dojo.require("dojo.window");
dojo.require("dijit._Widget");
dojo.require("dijit._Templated");
dojo.require("dijit._CssStateMixin");
dojo.declare("dijit.form._FormWidget",[dijit._Widget,dijit._Templated,dijit._CssStateMixin],{name:"",alt:"",value:"",type:"text",tabIndex:"0",disabled:false,intermediateChanges:false,scrollOnFocus:true,attributeMap:dojo.delegate(dijit._Widget.prototype.attributeMap,{value:"focusNode",id:"focusNode",tabIndex:"focusNode",alt:"focusNode",title:"focusNode"}),postMixInProperties:function(){
this.nameAttrSetting=this.name?("name=\""+this.name.replace(/'/g,"&quot;")+"\""):"";
this.inherited(arguments);
},postCreate:function(){
this.inherited(arguments);
this.connect(this.domNode,"onmousedown","_onMouseDown");
},_setDisabledAttr:function(_1){
this.disabled=_1;
dojo.attr(this.focusNode,"disabled",_1);
if(this.valueNode){
dojo.attr(this.valueNode,"disabled",_1);
}
dijit.setWaiState(this.focusNode,"disabled",_1);
if(_1){
this._hovering=false;
this._active=false;
var _2="tabIndex" in this.attributeMap?this.attributeMap.tabIndex:"focusNode";
dojo.forEach(dojo.isArray(_2)?_2:[_2],function(_3){
var _4=this[_3];
if(dojo.isWebKit||dijit.hasDefaultTabStop(_4)){
_4.setAttribute("tabIndex","-1");
}else{
_4.removeAttribute("tabIndex");
}
},this);
}else{
this.focusNode.setAttribute("tabIndex",this.tabIndex);
}
},setDisabled:function(_5){
dojo.deprecated("setDisabled("+_5+") is deprecated. Use set('disabled',"+_5+") instead.","","2.0");
this.set("disabled",_5);
},_onFocus:function(e){
if(this.scrollOnFocus){
dojo.window.scrollIntoView(this.domNode);
}
this.inherited(arguments);
},isFocusable:function(){
return !this.disabled&&!this.readOnly&&this.focusNode&&(dojo.style(this.domNode,"display")!="none");
},focus:function(){
dijit.focus(this.focusNode);
},compare:function(_6,_7){
if(typeof _6=="number"&&typeof _7=="number"){
return (isNaN(_6)&&isNaN(_7))?0:_6-_7;
}else{
if(_6>_7){
return 1;
}else{
if(_6<_7){
return -1;
}else{
return 0;
}
}
}
},onChange:function(_8){
},_onChangeActive:false,_handleOnChange:function(_9,_a){
this._lastValue=_9;
if(this._lastValueReported==undefined&&(_a===null||!this._onChangeActive)){
this._resetValue=this._lastValueReported=_9;
}
if((this.intermediateChanges||_a||_a===undefined)&&((typeof _9!=typeof this._lastValueReported)||this.compare(_9,this._lastValueReported)!=0)){
this._lastValueReported=_9;
if(this._onChangeActive){
if(this._onChangeHandle){
clearTimeout(this._onChangeHandle);
}
this._onChangeHandle=setTimeout(dojo.hitch(this,function(){
this._onChangeHandle=null;
this.onChange(_9);
}),0);
}
}
},create:function(){
this.inherited(arguments);
this._onChangeActive=true;
},destroy:function(){
if(this._onChangeHandle){
clearTimeout(this._onChangeHandle);
this.onChange(this._lastValueReported);
}
this.inherited(arguments);
},setValue:function(_b){
dojo.deprecated("dijit.form._FormWidget:setValue("+_b+") is deprecated.  Use set('value',"+_b+") instead.","","2.0");
this.set("value",_b);
},getValue:function(){
dojo.deprecated(this.declaredClass+"::getValue() is deprecated. Use get('value') instead.","","2.0");
return this.get("value");
},_onMouseDown:function(e){
if(!e.ctrlKey&&this.isFocusable()){
var _c=this.connect(dojo.body(),"onmouseup",function(){
if(this.isFocusable()){
this.focus();
}
this.disconnect(_c);
});
}
}});
dojo.declare("dijit.form._FormValueWidget",dijit.form._FormWidget,{readOnly:false,attributeMap:dojo.delegate(dijit.form._FormWidget.prototype.attributeMap,{value:"",readOnly:"focusNode"}),_setReadOnlyAttr:function(_d){
this.readOnly=_d;
dojo.attr(this.focusNode,"readOnly",_d);
dijit.setWaiState(this.focusNode,"readonly",_d);
},postCreate:function(){
this.inherited(arguments);
if(dojo.isIE){
this.connect(this.focusNode||this.domNode,"onkeydown",this._onKeyDown);
}
if(this._resetValue===undefined){
this._resetValue=this.value;
}
},_setValueAttr:function(_e,_f){
this.value=_e;
this._handleOnChange(_e,_f);
},_getValueAttr:function(){
return this._lastValue;
},undo:function(){
this._setValueAttr(this._lastValueReported,false);
},reset:function(){
this._hasBeenBlurred=false;
this._setValueAttr(this._resetValue,true);
},_onKeyDown:function(e){
if(e.keyCode==dojo.keys.ESCAPE&&!(e.ctrlKey||e.altKey||e.metaKey)){
var te;
if(dojo.isIE){
e.preventDefault();
te=document.createEventObject();
te.keyCode=dojo.keys.ESCAPE;
te.shiftKey=e.shiftKey;
e.srcElement.fireEvent("onkeypress",te);
}
}
},_layoutHackIE7:function(){
if(dojo.isIE==7){
var _10=this.domNode;
var _11=_10.parentNode;
var _12=_10.firstChild||_10;
var _13=_12.style.filter;
var _14=this;
while(_11&&_11.clientHeight==0){
(function ping(){
var _15=_14.connect(_11,"onscroll",function(e){
_14.disconnect(_15);
_12.style.filter=(new Date()).getMilliseconds();
setTimeout(function(){
_12.style.filter=_13;
},0);
});
})();
_11=_11.parentNode;
}
}
}});
}
