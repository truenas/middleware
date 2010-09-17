/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.form.NumberTextBox"]){
dojo._hasResource["dijit.form.NumberTextBox"]=true;
dojo.provide("dijit.form.NumberTextBox");
dojo.require("dijit.form.ValidationTextBox");
dojo.require("dojo.number");
dojo.declare("dijit.form.NumberTextBoxMixin",null,{regExpGen:dojo.number.regexp,value:NaN,editOptions:{pattern:"#.######"},_formatter:dojo.number.format,_setConstraintsAttr:function(_1){
var _2=typeof _1.places=="number"?_1.places:0;
if(_2){
_2++;
}
if(typeof _1.max!="number"){
_1.max=9*Math.pow(10,15-_2);
}
if(typeof _1.min!="number"){
_1.min=-9*Math.pow(10,15-_2);
}
this.inherited(arguments,[_1]);
if(this.focusNode&&this.focusNode.value&&!isNaN(this.value)){
this.set("value",this.value);
}
},_onFocus:function(){
if(this.disabled){
return;
}
var _3=this.get("value");
if(typeof _3=="number"&&!isNaN(_3)){
var _4=this.format(_3,this.constraints);
if(_4!==undefined){
this.textbox.value=_4;
}
}
this.inherited(arguments);
},format:function(_5,_6){
var _7=String(_5);
if(typeof _5!="number"){
return _7;
}
if(isNaN(_5)){
return "";
}
if(!("rangeCheck" in this&&this.rangeCheck(_5,_6))&&_6.exponent!==false&&/\de[-+]?\d/i.test(_7)){
return _7;
}
if(this.editOptions&&this._focused){
_6=dojo.mixin({},_6,this.editOptions);
}
return this._formatter(_5,_6);
},parse:dojo.number.parse,_getDisplayedValueAttr:function(){
var v=this.inherited(arguments);
return isNaN(v)?this.textbox.value:v;
},filter:function(_8){
return (_8===null||_8===""||_8===undefined)?NaN:this.inherited(arguments);
},serialize:function(_9,_a){
return (typeof _9!="number"||isNaN(_9))?"":this.inherited(arguments);
},_setValueAttr:function(_b,_c,_d){
if(_b!==undefined&&_d===undefined){
_d=String(_b);
if(typeof _b=="number"){
if(isNaN(_b)){
_d="";
}else{
if(("rangeCheck" in this&&this.rangeCheck(_b,this.constraints))||this.constraints.exponent===false||!/\de[-+]?\d/i.test(_d)){
_d=undefined;
}
}
}else{
if(!_b){
_d="";
_b=NaN;
}else{
_b=undefined;
}
}
}
this.inherited(arguments,[_b,_c,_d]);
},_getValueAttr:function(){
var v=this.inherited(arguments);
if(isNaN(v)&&this.textbox.value!==""){
if(this.constraints.exponent!==false&&/\de[-+]?\d/i.test(this.textbox.value)&&(new RegExp("^"+dojo.number._realNumberRegexp(dojo.mixin({},this.constraints))+"$").test(this.textbox.value))){
var n=Number(this.textbox.value);
return isNaN(n)?undefined:n;
}else{
return undefined;
}
}else{
return v;
}
},isValid:function(_e){
if(!this._focused||this._isEmpty(this.textbox.value)){
return this.inherited(arguments);
}else{
var v=this.get("value");
if(!isNaN(v)&&this.rangeCheck(v,this.constraints)){
if(this.constraints.exponent!==false&&/\de[-+]?\d/i.test(this.textbox.value)){
return true;
}else{
return this.inherited(arguments);
}
}else{
return false;
}
}
}});
dojo.declare("dijit.form.NumberTextBox",[dijit.form.RangeBoundTextBox,dijit.form.NumberTextBoxMixin],{});
}
