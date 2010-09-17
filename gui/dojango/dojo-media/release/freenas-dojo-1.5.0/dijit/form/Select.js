/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.form.Select"]){
dojo._hasResource["dijit.form.Select"]=true;
dojo.provide("dijit.form.Select");
dojo.require("dijit.form._FormSelectWidget");
dojo.require("dijit._HasDropDown");
dojo.require("dijit.Menu");
dojo.require("dijit.Tooltip");
dojo.requireLocalization("dijit.form","validate",null,"ROOT,ar,ca,cs,da,de,el,es,fi,fr,he,hu,it,ja,ko,nb,nl,pl,pt,pt-pt,ro,ru,sk,sl,sv,th,tr,zh,zh-tw");
dojo.declare("dijit.form._SelectMenu",dijit.Menu,{buildRendering:function(){
this.inherited(arguments);
var o=(this.menuTableNode=this.domNode);
var n=(this.domNode=dojo.create("div",{style:{overflowX:"hidden",overflowY:"scroll"}}));
if(o.parentNode){
o.parentNode.replaceChild(n,o);
}
dojo.removeClass(o,"dijitMenuTable");
n.className=o.className+" dijitSelectMenu";
o.className="dijitReset dijitMenuTable";
dijit.setWaiRole(o,"listbox");
dijit.setWaiRole(n,"presentation");
n.appendChild(o);
},resize:function(mb){
if(mb){
dojo.marginBox(this.domNode,mb);
if("w" in mb){
this.menuTableNode.style.width="100%";
}
}
}});
dojo.declare("dijit.form.Select",[dijit.form._FormSelectWidget,dijit._HasDropDown],{baseClass:"dijitSelect",templateString:dojo.cache("dijit.form","templates/Select.html","<table class=\"dijit dijitReset dijitInline dijitLeft\"\n\tdojoAttachPoint=\"_buttonNode,tableNode,focusNode\" cellspacing='0' cellpadding='0'\n\twaiRole=\"combobox\" waiState=\"haspopup-true\"\n\t><tbody waiRole=\"presentation\"><tr waiRole=\"presentation\"\n\t\t><td class=\"dijitReset dijitStretch dijitButtonContents dijitButtonNode\" waiRole=\"presentation\"\n\t\t\t><span class=\"dijitReset dijitInline dijitButtonText\"  dojoAttachPoint=\"containerNode,_popupStateNode\"></span\n\t\t\t><input type=\"hidden\" ${!nameAttrSetting} dojoAttachPoint=\"valueNode\" value=\"${value}\" waiState=\"hidden-true\"\n\t\t/></td><td class=\"dijitReset dijitRight dijitButtonNode dijitArrowButton dijitDownArrowButton\"\n\t\t\t\tdojoAttachPoint=\"titleNode\" waiRole=\"presentation\"\n\t\t\t><div class=\"dijitReset dijitArrowButtonInner\" waiRole=\"presentation\"></div\n\t\t\t><div class=\"dijitReset dijitArrowButtonChar\" waiRole=\"presentation\">&#9660;</div\n\t\t></td\n\t></tr></tbody\n></table>\n"),attributeMap:dojo.mixin(dojo.clone(dijit.form._FormSelectWidget.prototype.attributeMap),{style:"tableNode"}),required:false,state:"",tooltipPosition:[],emptyLabel:"",_isLoaded:false,_childrenLoaded:false,_fillContent:function(){
this.inherited(arguments);
if(this.options.length&&!this.value&&this.srcNodeRef){
var si=this.srcNodeRef.selectedIndex;
this.value=this.options[si!=-1?si:0].value;
}
this.dropDown=new dijit.form._SelectMenu({id:this.id+"_menu"});
dojo.addClass(this.dropDown.domNode,this.baseClass+"Menu");
},_getMenuItemForOption:function(_1){
if(!_1.value){
return new dijit.MenuSeparator();
}else{
var _2=dojo.hitch(this,"_setValueAttr",_1);
var _3=new dijit.MenuItem({option:_1,label:_1.label,onClick:_2,disabled:_1.disabled||false});
dijit.setWaiRole(_3.focusNode,"listitem");
return _3;
}
},_addOptionItem:function(_4){
if(this.dropDown){
this.dropDown.addChild(this._getMenuItemForOption(_4));
}
},_getChildren:function(){
if(!this.dropDown){
return [];
}
return this.dropDown.getChildren();
},_loadChildren:function(_5){
if(_5===true){
if(this.dropDown){
delete this.dropDown.focusedChild;
}
if(this.options.length){
this.inherited(arguments);
}else{
dojo.forEach(this._getChildren(),function(_6){
_6.destroyRecursive();
});
var _7=new dijit.MenuItem({label:"&nbsp;"});
this.dropDown.addChild(_7);
}
}else{
this._updateSelection();
}
var _8=this.options.length;
this._isLoaded=false;
this._childrenLoaded=true;
if(!this._loadingStore){
this._setValueAttr(this.value);
}
},_setValueAttr:function(_9){
this.inherited(arguments);
dojo.attr(this.valueNode,"value",this.get("value"));
},_setDisplay:function(_a){
this.containerNode.innerHTML="<span class=\"dijitReset dijitInline "+this.baseClass+"Label\">"+(_a||this.emptyLabel||"&nbsp;")+"</span>";
dijit.setWaiState(this.focusNode,"valuetext",(_a||this.emptyLabel||"&nbsp;"));
},validate:function(_b){
var _c=this.isValid(_b);
this.state=_c?"":"Error";
this._setStateClass();
dijit.setWaiState(this.focusNode,"invalid",_c?"false":"true");
var _d=_c?"":this._missingMsg;
if(this._message!==_d){
this._message=_d;
dijit.hideTooltip(this.domNode);
if(_d){
dijit.showTooltip(_d,this.domNode,this.tooltipPosition,!this.isLeftToRight());
}
}
return _c;
},isValid:function(_e){
return (!this.required||!(/^\s*$/.test(this.value)));
},reset:function(){
this.inherited(arguments);
dijit.hideTooltip(this.domNode);
this.state="";
this._setStateClass();
delete this._message;
},postMixInProperties:function(){
this.inherited(arguments);
this._missingMsg=dojo.i18n.getLocalization("dijit.form","validate",this.lang).missingMessage;
},postCreate:function(){
this.inherited(arguments);
if(this.tableNode.style.width){
dojo.addClass(this.domNode,this.baseClass+"FixedWidth");
}
},isLoaded:function(){
return this._isLoaded;
},loadDropDown:function(_f){
this._loadChildren(true);
this._isLoaded=true;
_f();
},closeDropDown:function(){
this.inherited(arguments);
if(this.dropDown&&this.dropDown.menuTableNode){
this.dropDown.menuTableNode.style.width="";
}
},uninitialize:function(_10){
if(this.dropDown&&!this.dropDown._destroyed){
this.dropDown.destroyRecursive(_10);
delete this.dropDown;
}
this.inherited(arguments);
}});
}
