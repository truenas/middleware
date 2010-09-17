/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojango.form.Form"]){
dojo._hasResource["dojango.form.Form"]=true;
dojo.provide("dojango.form.Form");
dojo.require("dijit.form.Form");
dojo.require("dojo.date.stamp");
dojo.declare("dojango.form.Form",dijit.form.Form,{_getDojangoValueAttr:function(){
var _1=this.attr("value");
return dojango.form.converter.convert_values(_1);
}});
dojango.form.converter={convert_values:function(_2){
for(var i in _2){
if(_2[i]&&!_2[i].getDate&&dojo.isObject(_2[i])&&!dojo.isArray(_2[i])){
_2[i]=dojo.toJson(this._convert_value(_2[i]));
}else{
_2[i]=this._convert_value(_2[i]);
}
}
return _2;
},_convert_value:function(_3){
if(_3&&_3.getDate){
_3=dojo.date.stamp.toISOString(_3);
if(typeof (_3)!="undefined"){
_3=_3.substring(0,_3.length-6);
}
}else{
if(dojo.isString(_3)){
_3=_3;
_3=_3.replace("<br _moz_editor_bogus_node=\"TRUE\" />","");
}else{
if(dojo.isArray(_3)){
for(var i=0,l=_3.length;i<l;i++){
_3[i]=this._convert_value(_3[i]);
}
}else{
if(typeof (_3)=="number"&&isNaN(_3)){
_3="";
}else{
if(dojo.isObject(_3)){
for(var i in _3){
_3[i]=this._convert_value(_3[i]);
}
}else{
if(typeof (_3)=="undefined"){
_3="";
}
}
}
}
}
}
return _3;
}};
}
