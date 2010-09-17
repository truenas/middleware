/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.form.Button"]){
dojo._hasResource["dijit.form.Button"]=true;
dojo.provide("dijit.form.Button");
dojo.require("dijit.form._FormWidget");
dojo.require("dijit._Container");
dojo.require("dijit._HasDropDown");
dojo.declare("dijit.form.Button",dijit.form._FormWidget,{label:"",showLabel:true,iconClass:"",type:"button",baseClass:"dijitButton",templateString:dojo.cache("dijit.form","templates/Button.html","<span class=\"dijit dijitReset dijitInline\"\n\t><span class=\"dijitReset dijitInline dijitButtonNode\"\n\t\tdojoAttachEvent=\"ondijitclick:_onButtonClick\"\n\t\t><span class=\"dijitReset dijitStretch dijitButtonContents\"\n\t\t\tdojoAttachPoint=\"titleNode,focusNode\"\n\t\t\twaiRole=\"button\" waiState=\"labelledby-${id}_label\"\n\t\t\t><span class=\"dijitReset dijitInline dijitIcon\" dojoAttachPoint=\"iconNode\"></span\n\t\t\t><span class=\"dijitReset dijitToggleButtonIconChar\">&#x25CF;</span\n\t\t\t><span class=\"dijitReset dijitInline dijitButtonText\"\n\t\t\t\tid=\"${id}_label\"\n\t\t\t\tdojoAttachPoint=\"containerNode\"\n\t\t\t></span\n\t\t></span\n\t></span\n\t><input ${!nameAttrSetting} type=\"${type}\" value=\"${value}\" class=\"dijitOffScreen\"\n\t\tdojoAttachPoint=\"valueNode\"\n/></span>\n"),attributeMap:dojo.delegate(dijit.form._FormWidget.prototype.attributeMap,{value:"valueNode",iconClass:{node:"iconNode",type:"class"}}),_onClick:function(e){
if(this.disabled){
return false;
}
this._clicked();
return this.onClick(e);
},_onButtonClick:function(e){
if(this._onClick(e)===false){
e.preventDefault();
}else{
if(this.type=="submit"&&!(this.valueNode||this.focusNode).form){
for(var _1=this.domNode;_1.parentNode;_1=_1.parentNode){
var _2=dijit.byNode(_1);
if(_2&&typeof _2._onSubmit=="function"){
_2._onSubmit(e);
break;
}
}
}else{
if(this.valueNode){
this.valueNode.click();
e.preventDefault();
}
}
}
},_fillContent:function(_3){
if(_3&&(!this.params||!("label" in this.params))){
this.set("label",_3.innerHTML);
}
},postCreate:function(){
dojo.setSelectable(this.focusNode,false);
this.inherited(arguments);
},_setShowLabelAttr:function(_4){
if(this.containerNode){
dojo.toggleClass(this.containerNode,"dijitDisplayNone",!_4);
}
this.showLabel=_4;
},onClick:function(e){
return true;
},_clicked:function(e){
},setLabel:function(_5){
dojo.deprecated("dijit.form.Button.setLabel() is deprecated.  Use set('label', ...) instead.","","2.0");
this.set("label",_5);
},_setLabelAttr:function(_6){
this.containerNode.innerHTML=this.label=_6;
if(this.showLabel==false&&!this.params.title){
this.titleNode.title=dojo.trim(this.containerNode.innerText||this.containerNode.textContent||"");
}
}});
dojo.declare("dijit.form.DropDownButton",[dijit.form.Button,dijit._Container,dijit._HasDropDown],{baseClass:"dijitDropDownButton",templateString:dojo.cache("dijit.form","templates/DropDownButton.html","<span class=\"dijit dijitReset dijitInline\"\n\t><span class='dijitReset dijitInline dijitButtonNode'\n\t\tdojoAttachEvent=\"ondijitclick:_onButtonClick\" dojoAttachPoint=\"_buttonNode\"\n\t\t><span class=\"dijitReset dijitStretch dijitButtonContents\"\n\t\t\tdojoAttachPoint=\"focusNode,titleNode,_arrowWrapperNode\"\n\t\t\twaiRole=\"button\" waiState=\"haspopup-true,labelledby-${id}_label\"\n\t\t\t><span class=\"dijitReset dijitInline dijitIcon\"\n\t\t\t\tdojoAttachPoint=\"iconNode\"\n\t\t\t></span\n\t\t\t><span class=\"dijitReset dijitInline dijitButtonText\"\n\t\t\t\tdojoAttachPoint=\"containerNode,_popupStateNode\"\n\t\t\t\tid=\"${id}_label\"\n\t\t\t></span\n\t\t\t><span class=\"dijitReset dijitInline dijitArrowButtonInner\"></span\n\t\t\t><span class=\"dijitReset dijitInline dijitArrowButtonChar\">&#9660;</span\n\t\t></span\n\t></span\n\t><input ${!nameAttrSetting} type=\"${type}\" value=\"${value}\" class=\"dijitOffScreen\"\n\t\tdojoAttachPoint=\"valueNode\"\n/></span>\n"),_fillContent:function(){
if(this.srcNodeRef){
var _7=dojo.query("*",this.srcNodeRef);
dijit.form.DropDownButton.superclass._fillContent.call(this,_7[0]);
this.dropDownContainer=this.srcNodeRef;
}
},startup:function(){
if(this._started){
return;
}
if(!this.dropDown){
var _8=dojo.query("[widgetId]",this.dropDownContainer)[0];
this.dropDown=dijit.byNode(_8);
delete this.dropDownContainer;
}
dijit.popup.moveOffScreen(this.dropDown.domNode);
this.inherited(arguments);
},isLoaded:function(){
var _9=this.dropDown;
return (!_9.href||_9.isLoaded);
},loadDropDown:function(){
var _a=this.dropDown;
if(!_a){
return;
}
if(!this.isLoaded()){
var _b=dojo.connect(_a,"onLoad",this,function(){
dojo.disconnect(_b);
this.openDropDown();
});
_a.refresh();
}else{
this.openDropDown();
}
},isFocusable:function(){
return this.inherited(arguments)&&!this._mouseDown;
}});
dojo.declare("dijit.form.ComboButton",dijit.form.DropDownButton,{templateString:dojo.cache("dijit.form","templates/ComboButton.html","<table class=\"dijit dijitReset dijitInline dijitLeft\"\n\tcellspacing='0' cellpadding='0' waiRole=\"presentation\"\n\t><tbody waiRole=\"presentation\"><tr waiRole=\"presentation\"\n\t\t><td class=\"dijitReset dijitStretch dijitButtonNode\" dojoAttachPoint=\"buttonNode\" dojoAttachEvent=\"ondijitclick:_onButtonClick,onkeypress:_onButtonKeyPress\"\n\t\t><div id=\"${id}_button\" class=\"dijitReset dijitButtonContents\"\n\t\t\tdojoAttachPoint=\"titleNode\"\n\t\t\twaiRole=\"button\" waiState=\"labelledby-${id}_label\"\n\t\t\t><div class=\"dijitReset dijitInline dijitIcon\" dojoAttachPoint=\"iconNode\" waiRole=\"presentation\"></div\n\t\t\t><div class=\"dijitReset dijitInline dijitButtonText\" id=\"${id}_label\" dojoAttachPoint=\"containerNode\" waiRole=\"presentation\"></div\n\t\t></div\n\t\t></td\n\t\t><td id=\"${id}_arrow\" class='dijitReset dijitRight dijitButtonNode dijitArrowButton'\n\t\t\tdojoAttachPoint=\"_popupStateNode,focusNode,_buttonNode\"\n\t\t\tdojoAttachEvent=\"onkeypress:_onArrowKeyPress\"\n\t\t\ttitle=\"${optionsTitle}\"\n\t\t\twaiRole=\"button\" waiState=\"haspopup-true\"\n\t\t\t><div class=\"dijitReset dijitArrowButtonInner\" waiRole=\"presentation\"></div\n\t\t\t><div class=\"dijitReset dijitArrowButtonChar\" waiRole=\"presentation\">&#9660;</div\n\t\t></td\n\t\t><td style=\"display:none !important;\"\n\t\t\t><input ${!nameAttrSetting} type=\"${type}\" value=\"${value}\" dojoAttachPoint=\"valueNode\"\n\t\t/></td></tr></tbody\n></table>\n"),attributeMap:dojo.mixin(dojo.clone(dijit.form.Button.prototype.attributeMap),{id:"",tabIndex:["focusNode","titleNode"],title:"titleNode"}),optionsTitle:"",baseClass:"dijitComboButton",cssStateNodes:{"buttonNode":"dijitButtonNode","titleNode":"dijitButtonContents","_popupStateNode":"dijitDownArrowButton"},_focusedNode:null,_onButtonKeyPress:function(_c){
if(_c.charOrCode==dojo.keys[this.isLeftToRight()?"RIGHT_ARROW":"LEFT_ARROW"]){
dijit.focus(this._popupStateNode);
dojo.stopEvent(_c);
}
},_onArrowKeyPress:function(_d){
if(_d.charOrCode==dojo.keys[this.isLeftToRight()?"LEFT_ARROW":"RIGHT_ARROW"]){
dijit.focus(this.titleNode);
dojo.stopEvent(_d);
}
},focus:function(_e){
dijit.focus(_e=="start"?this.titleNode:this._popupStateNode);
}});
dojo.declare("dijit.form.ToggleButton",dijit.form.Button,{baseClass:"dijitToggleButton",checked:false,attributeMap:dojo.mixin(dojo.clone(dijit.form.Button.prototype.attributeMap),{checked:"focusNode"}),_clicked:function(_f){
this.set("checked",!this.checked);
},_setCheckedAttr:function(_10,_11){
this.checked=_10;
dojo.attr(this.focusNode||this.domNode,"checked",_10);
dijit.setWaiState(this.focusNode||this.domNode,"pressed",_10);
this._handleOnChange(_10,_11);
},setChecked:function(_12){
dojo.deprecated("setChecked("+_12+") is deprecated. Use set('checked',"+_12+") instead.","","2.0");
this.set("checked",_12);
},reset:function(){
this._hasBeenBlurred=false;
this.set("checked",this.params.checked||false);
}});
}
