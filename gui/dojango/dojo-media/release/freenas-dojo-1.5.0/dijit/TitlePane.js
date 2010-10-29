/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.TitlePane"]){
dojo._hasResource["dijit.TitlePane"]=true;
dojo.provide("dijit.TitlePane");
dojo.require("dojo.fx");
dojo.require("dijit._Templated");
dojo.require("dijit.layout.ContentPane");
dojo.require("dijit._CssStateMixin");
dojo.declare("dijit.TitlePane",[dijit.layout.ContentPane,dijit._Templated,dijit._CssStateMixin],{title:"",open:true,toggleable:true,tabIndex:"0",duration:dijit.defaultDuration,baseClass:"dijitTitlePane",templateString:dojo.cache("dijit","templates/TitlePane.html","<div>\n\t<div dojoAttachEvent=\"onclick:_onTitleClick, onkeypress:_onTitleKey\"\n\t\t\tclass=\"dijitTitlePaneTitle\" dojoAttachPoint=\"titleBarNode\">\n\t\t<div class=\"dijitTitlePaneTitleFocus\" dojoAttachPoint=\"focusNode\">\n\t\t\t<img src=\"${_blankGif}\" alt=\"\" dojoAttachPoint=\"arrowNode\" class=\"dijitArrowNode\" waiRole=\"presentation\"\n\t\t\t/><span dojoAttachPoint=\"arrowNodeInner\" class=\"dijitArrowNodeInner\"></span\n\t\t\t><span dojoAttachPoint=\"titleNode\" class=\"dijitTitlePaneTextNode\"></span>\n\t\t</div>\n\t</div>\n\t<div class=\"dijitTitlePaneContentOuter\" dojoAttachPoint=\"hideNode\" waiRole=\"presentation\">\n\t\t<div class=\"dijitReset\" dojoAttachPoint=\"wipeNode\" waiRole=\"presentation\">\n\t\t\t<div class=\"dijitTitlePaneContentInner\" dojoAttachPoint=\"containerNode\" waiRole=\"region\" tabindex=\"-1\" id=\"${id}_pane\">\n\t\t\t\t<!-- nested divs because wipeIn()/wipeOut() doesn't work right on node w/padding etc.  Put padding on inner div. -->\n\t\t\t</div>\n\t\t</div>\n\t</div>\n</div>\n"),attributeMap:dojo.delegate(dijit.layout.ContentPane.prototype.attributeMap,{title:{node:"titleNode",type:"innerHTML"},tooltip:{node:"focusNode",type:"attribute",attribute:"title"},id:""}),postCreate:function(){
if(!this.open){
this.hideNode.style.display=this.wipeNode.style.display="none";
}
if(this.toggleable){
this._trackMouseState(this.titleBarNode,"dijitTitlePaneTitle");
}
this._setCss();
dojo.setSelectable(this.titleNode,false);
var _1=this.hideNode,_2=this.wipeNode;
this._wipeIn=dojo.fx.wipeIn({node:this.wipeNode,duration:this.duration,beforeBegin:function(){
_1.style.display="";
}});
this._wipeOut=dojo.fx.wipeOut({node:this.wipeNode,duration:this.duration,onEnd:function(){
_1.style.display="none";
}});
this.inherited(arguments);
},_setOpenAttr:function(_3){
if(this.open!==_3){
this.toggle();
}
dijit.setWaiState(this.containerNode,"hidden",this.open?"false":"true");
dijit.setWaiState(this.focusNode,"pressed",this.open?"true":"false");
},_setToggleableAttr:function(_4){
this.toggleable=_4;
dijit.setWaiRole(this.focusNode,_4?"button":"heading");
if(_4){
dijit.setWaiState(this.focusNode,"controls",this.id+"_pane");
dojo.attr(this.focusNode,"tabIndex",this.tabIndex);
}else{
dojo.removeAttr(this.focusNode,"tabIndex");
}
this._setCss();
},_setContentAttr:function(_5){
if(!this.open||!this._wipeOut||this._wipeOut.status()=="playing"){
this.inherited(arguments);
}else{
if(this._wipeIn&&this._wipeIn.status()=="playing"){
this._wipeIn.stop();
}
dojo.marginBox(this.wipeNode,{h:dojo.marginBox(this.wipeNode).h});
this.inherited(arguments);
if(this._wipeIn){
this._wipeIn.play();
}else{
this.hideNode.style.display="";
}
}
},toggle:function(){
dojo.forEach([this._wipeIn,this._wipeOut],function(_6){
if(_6&&_6.status()=="playing"){
_6.stop();
}
});
var _7=this[this.open?"_wipeOut":"_wipeIn"];
if(_7){
_7.play();
}else{
this.hideNode.style.display=this.open?"":"none";
}
this.open=!this.open;
if(this.open){
this._onShow();
}else{
this.onHide();
}
this._setCss();
},_setCss:function(){
var _8=this.titleBarNode||this.focusNode;
if(this._titleBarClass){
dojo.removeClass(_8,this._titleBarClass);
}
this._titleBarClass="dijit"+(this.toggleable?"":"Fixed")+(this.open?"Open":"Closed");
dojo.addClass(_8,this._titleBarClass);
this.arrowNodeInner.innerHTML=this.open?"-":"+";
},_onTitleKey:function(e){
if(e.charOrCode==dojo.keys.ENTER||e.charOrCode==" "){
if(this.toggleable){
this.toggle();
}
dojo.stopEvent(e);
}else{
if(e.charOrCode==dojo.keys.DOWN_ARROW&&this.open){
this.containerNode.focus();
e.preventDefault();
}
}
},_onTitleClick:function(){
if(this.toggleable){
this.toggle();
}
},setTitle:function(_9){
dojo.deprecated("dijit.TitlePane.setTitle() is deprecated.  Use set('title', ...) instead.","","2.0");
this.set("title",_9);
}});
}
