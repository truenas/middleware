/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.form.ValidationTextBox"]){
dojo._hasResource["dijit.form.ValidationTextBox"]=true;
dojo.provide("dijit.form.ValidationTextBox");
dojo.require("dojo.i18n");
dojo.require("dijit.form.TextBox");
dojo.require("dijit.Tooltip");
dojo.requireLocalization("dijit.form","validate",null,"ROOT,ar,ca,cs,da,de,el,es,fi,fr,he,hu,it,ja,ko,nb,nl,pl,pt,pt-pt,ro,ru,sk,sl,sv,th,tr,zh,zh-tw");
dojo.declare("dijit.form.ValidationTextBox",dijit.form.TextBox,{templateString:dojo.cache("dijit.form","templates/ValidationTextBox.html","<div class=\"dijit dijitReset dijitInlineTable dijitLeft\"\n\tid=\"widget_${id}\" waiRole=\"presentation\"\n\t><div class='dijitReset dijitValidationContainer'\n\t\t><input class=\"dijitReset dijitInputField dijitValidationIcon dijitValidationInner\" value=\"&Chi; \" type=\"text\" tabIndex=\"-1\" readOnly waiRole=\"presentation\"\n\t/></div\n\t><div class=\"dijitReset dijitInputField dijitInputContainer\"\n\t\t><input class=\"dijitReset dijitInputInner\" dojoAttachPoint='textbox,focusNode' autocomplete=\"off\"\n\t\t\t${!nameAttrSetting} type='${type}'\n\t/></div\n></div>\n"),baseClass:"dijitTextBox dijitValidationTextBox",required:false,promptMessage:"",invalidMessage:"$_unset_$",missingMessage:"$_unset_$",constraints:{},regExp:".*",regExpGen:function(_1){
return this.regExp;
},state:"",tooltipPosition:[],_setValueAttr:function(){
this.inherited(arguments);
this.validate(this._focused);
},validator:function(_2,_3){
return (new RegExp("^(?:"+this.regExpGen(_3)+")"+(this.required?"":"?")+"$")).test(_2)&&(!this.required||!this._isEmpty(_2))&&(this._isEmpty(_2)||this.parse(_2,_3)!==undefined);
},_isValidSubset:function(){
return this.textbox.value.search(this._partialre)==0;
},isValid:function(_4){
return this.validator(this.textbox.value,this.constraints);
},_isEmpty:function(_5){
return /^\s*$/.test(_5);
},getErrorMessage:function(_6){
return (this.required&&this._isEmpty(this.textbox.value))?this.missingMessage:this.invalidMessage;
},getPromptMessage:function(_7){
return this.promptMessage;
},_maskValidSubsetError:true,validate:function(_8){
var _9="";
var _a=this.disabled||this.isValid(_8);
if(_a){
this._maskValidSubsetError=true;
}
var _b=this._isEmpty(this.textbox.value);
var _c=!_a&&!_b&&_8&&this._isValidSubset();
this.state=((_a||((!this._hasBeenBlurred||_8)&&_b)||_c)&&this._maskValidSubsetError)?"":"Error";
if(this.state=="Error"){
this._maskValidSubsetError=_8;
}
this._setStateClass();
dijit.setWaiState(this.focusNode,"invalid",_a?"false":"true");
if(_8){
if(this.state=="Error"){
_9=this.getErrorMessage(true);
}else{
_9=this.getPromptMessage(true);
}
this._maskValidSubsetError=true;
}
this.displayMessage(_9);
return _a;
},_message:"",displayMessage:function(_d){
if(this._message==_d){
return;
}
this._message=_d;
dijit.hideTooltip(this.domNode);
if(_d){
dijit.showTooltip(_d,this.domNode,this.tooltipPosition,!this.isLeftToRight());
}
},_refreshState:function(){
this.validate(this._focused);
this.inherited(arguments);
},constructor:function(){
this.constraints={};
},_setConstraintsAttr:function(_e){
if(!_e.locale&&this.lang){
_e.locale=this.lang;
}
this.constraints=_e;
this._computePartialRE();
},_computePartialRE:function(){
var p=this.regExpGen(this.constraints);
this.regExp=p;
var _f="";
if(p!=".*"){
this.regExp.replace(/\\.|\[\]|\[.*?[^\\]{1}\]|\{.*?\}|\(\?[=:!]|./g,function(re){
switch(re.charAt(0)){
case "{":
case "+":
case "?":
case "*":
case "^":
case "$":
case "|":
case "(":
_f+=re;
break;
case ")":
_f+="|$)";
break;
default:
_f+="(?:"+re+"|$)";
break;
}
});
}
try{
"".search(_f);
}
catch(e){
_f=this.regExp;
console.warn("RegExp error in "+this.declaredClass+": "+this.regExp);
}
this._partialre="^(?:"+_f+")$";
},postMixInProperties:function(){
this.inherited(arguments);
this.messages=dojo.i18n.getLocalization("dijit.form","validate",this.lang);
if(this.invalidMessage=="$_unset_$"){
this.invalidMessage=this.messages.invalidMessage;
}
if(!this.invalidMessage){
this.invalidMessage=this.promptMessage;
}
if(this.missingMessage=="$_unset_$"){
this.missingMessage=this.messages.missingMessage;
}
if(!this.missingMessage){
this.missingMessage=this.invalidMessage;
}
this._setConstraintsAttr(this.constraints);
},_setDisabledAttr:function(_10){
this.inherited(arguments);
this._refreshState();
},_setRequiredAttr:function(_11){
this.required=_11;
dijit.setWaiState(this.focusNode,"required",_11);
this._refreshState();
},reset:function(){
this._maskValidSubsetError=true;
this.inherited(arguments);
},_onBlur:function(){
this.displayMessage("");
this.inherited(arguments);
}});
dojo.declare("dijit.form.MappedTextBox",dijit.form.ValidationTextBox,{postMixInProperties:function(){
this.inherited(arguments);
this.nameAttrSetting="";
},serialize:function(val,_12){
return val.toString?val.toString():"";
},toString:function(){
var val=this.filter(this.get("value"));
return val!=null?(typeof val=="string"?val:this.serialize(val,this.constraints)):"";
},validate:function(){
this.valueNode.value=this.toString();
return this.inherited(arguments);
},buildRendering:function(){
this.inherited(arguments);
this.valueNode=dojo.place("<input type='hidden'"+(this.name?" name='"+this.name+"'":"")+">",this.textbox,"after");
},reset:function(){
this.valueNode.value="";
this.inherited(arguments);
}});
dojo.declare("dijit.form.RangeBoundTextBox",dijit.form.MappedTextBox,{rangeMessage:"",rangeCheck:function(_13,_14){
return ("min" in _14?(this.compare(_13,_14.min)>=0):true)&&("max" in _14?(this.compare(_13,_14.max)<=0):true);
},isInRange:function(_15){
return this.rangeCheck(this.get("value"),this.constraints);
},_isDefinitelyOutOfRange:function(){
var val=this.get("value");
var _16=false;
var _17=false;
if("min" in this.constraints){
var min=this.constraints.min;
min=this.compare(val,((typeof min=="number")&&min>=0&&val!=0)?0:min);
_16=(typeof min=="number")&&min<0;
}
if("max" in this.constraints){
var max=this.constraints.max;
max=this.compare(val,((typeof max!="number")||max>0)?max:0);
_17=(typeof max=="number")&&max>0;
}
return _16||_17;
},_isValidSubset:function(){
return this.inherited(arguments)&&!this._isDefinitelyOutOfRange();
},isValid:function(_18){
return this.inherited(arguments)&&((this._isEmpty(this.textbox.value)&&!this.required)||this.isInRange(_18));
},getErrorMessage:function(_19){
var v=this.get("value");
if(v!==null&&v!==""&&v!==undefined&&(typeof v!="number"||!isNaN(v))&&!this.isInRange(_19)){
return this.rangeMessage;
}
return this.inherited(arguments);
},postMixInProperties:function(){
this.inherited(arguments);
if(!this.rangeMessage){
this.messages=dojo.i18n.getLocalization("dijit.form","validate",this.lang);
this.rangeMessage=this.messages.rangeMessage;
}
},_setConstraintsAttr:function(_1a){
this.inherited(arguments);
if(this.focusNode){
if(this.constraints.min!==undefined){
dijit.setWaiState(this.focusNode,"valuemin",this.constraints.min);
}else{
dijit.removeWaiState(this.focusNode,"valuemin");
}
if(this.constraints.max!==undefined){
dijit.setWaiState(this.focusNode,"valuemax",this.constraints.max);
}else{
dijit.removeWaiState(this.focusNode,"valuemax");
}
}
},_setValueAttr:function(_1b,_1c){
dijit.setWaiState(this.focusNode,"valuenow",_1b);
this.inherited(arguments);
}});
}
