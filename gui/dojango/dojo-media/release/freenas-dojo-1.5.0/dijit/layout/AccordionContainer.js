/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.layout.AccordionContainer"]){
dojo._hasResource["dijit.layout.AccordionContainer"]=true;
dojo.provide("dijit.layout.AccordionContainer");
dojo.require("dojo.fx");
dojo.require("dijit._Container");
dojo.require("dijit._Templated");
dojo.require("dijit._CssStateMixin");
dojo.require("dijit.layout.StackContainer");
dojo.require("dijit.layout.ContentPane");
dojo.require("dijit.layout.AccordionPane");
dojo.declare("dijit.layout.AccordionContainer",dijit.layout.StackContainer,{duration:dijit.defaultDuration,buttonWidget:"dijit.layout._AccordionButton",_verticalSpace:0,baseClass:"dijitAccordionContainer",postCreate:function(){
this.domNode.style.overflow="hidden";
this.inherited(arguments);
dijit.setWaiRole(this.domNode,"tablist");
},startup:function(){
if(this._started){
return;
}
this.inherited(arguments);
if(this.selectedChildWidget){
var _1=this.selectedChildWidget.containerNode.style;
_1.display="";
_1.overflow="auto";
this.selectedChildWidget._wrapperWidget.set("selected",true);
}
},_getTargetHeight:function(_2){
var cs=dojo.getComputedStyle(_2);
return Math.max(this._verticalSpace-dojo._getPadBorderExtents(_2,cs).h-dojo._getMarginExtents(_2,cs).h,0);
},layout:function(){
var _3=this.selectedChildWidget;
if(!_3){
return;
}
var _4=_3._wrapperWidget.domNode,_5=dojo._getMarginExtents(_4),_6=dojo._getPadBorderExtents(_4),_7=this._contentBox;
var _8=0;
dojo.forEach(this.getChildren(),function(_9){
if(_9!=_3){
_8+=dojo.marginBox(_9._wrapperWidget.domNode).h;
}
});
this._verticalSpace=_7.h-_8-_5.h-_6.h-_3._buttonWidget.getTitleHeight();
this._containerContentBox={h:this._verticalSpace,w:this._contentBox.w-_5.w-_6.w};
if(_3){
_3.resize(this._containerContentBox);
}
},_setupChild:function(_a){
_a._wrapperWidget=new dijit.layout._AccordionInnerContainer({contentWidget:_a,buttonWidget:this.buttonWidget,id:_a.id+"_wrapper",dir:_a.dir,lang:_a.lang,parent:this});
this.inherited(arguments);
},addChild:function(_b,_c){
if(this._started){
dojo.place(_b.domNode,this.containerNode,_c);
if(!_b._started){
_b.startup();
}
this._setupChild(_b);
dojo.publish(this.id+"-addChild",[_b,_c]);
this.layout();
if(!this.selectedChildWidget){
this.selectChild(_b);
}
}else{
this.inherited(arguments);
}
},removeChild:function(_d){
_d._wrapperWidget.destroy();
delete _d._wrapperWidget;
dojo.removeClass(_d.domNode,"dijitHidden");
this.inherited(arguments);
},getChildren:function(){
return dojo.map(this.inherited(arguments),function(_e){
return _e.declaredClass=="dijit.layout._AccordionInnerContainer"?_e.contentWidget:_e;
},this);
},destroy:function(){
dojo.forEach(this.getChildren(),function(_f){
_f._wrapperWidget.destroy();
});
this.inherited(arguments);
},_transition:function(_10,_11,_12){
if(this._inTransition){
return;
}
var _13=[];
var _14=this._verticalSpace;
if(_10){
_10._wrapperWidget.set("selected",true);
this._showChild(_10);
if(this.doLayout&&_10.resize){
_10.resize(this._containerContentBox);
}
var _15=_10.domNode;
dojo.addClass(_15,"dijitVisible");
dojo.removeClass(_15,"dijitHidden");
if(_12){
var _16=_15.style.overflow;
_15.style.overflow="hidden";
_13.push(dojo.animateProperty({node:_15,duration:this.duration,properties:{height:{start:1,end:this._getTargetHeight(_15)}},onEnd:function(){
_15.style.overflow=_16;
if(dojo.isIE){
setTimeout(function(){
dojo.removeClass(_15.parentNode,"dijitAccordionInnerContainerFocused");
setTimeout(function(){
dojo.addClass(_15.parentNode,"dijitAccordionInnerContainerFocused");
},0);
},0);
}
}}));
}
}
if(_11){
_11._wrapperWidget.set("selected",false);
var _17=_11.domNode;
if(_12){
var _18=_17.style.overflow;
_17.style.overflow="hidden";
_13.push(dojo.animateProperty({node:_17,duration:this.duration,properties:{height:{start:this._getTargetHeight(_17),end:1}},onEnd:function(){
dojo.addClass(_17,"dijitHidden");
dojo.removeClass(_17,"dijitVisible");
_17.style.overflow=_18;
if(_11.onHide){
_11.onHide();
}
}}));
}else{
dojo.addClass(_17,"dijitHidden");
dojo.removeClass(_17,"dijitVisible");
if(_11.onHide){
_11.onHide();
}
}
}
if(_12){
this._inTransition=true;
var _19=dojo.fx.combine(_13);
_19.onEnd=dojo.hitch(this,function(){
delete this._inTransition;
});
_19.play();
}
},_onKeyPress:function(e,_1a){
if(this._inTransition||this.disabled||e.altKey||!(_1a||e.ctrlKey)){
if(this._inTransition){
dojo.stopEvent(e);
}
return;
}
var k=dojo.keys,c=e.charOrCode;
if((_1a&&(c==k.LEFT_ARROW||c==k.UP_ARROW))||(e.ctrlKey&&c==k.PAGE_UP)){
this._adjacent(false)._buttonWidget._onTitleClick();
dojo.stopEvent(e);
}else{
if((_1a&&(c==k.RIGHT_ARROW||c==k.DOWN_ARROW))||(e.ctrlKey&&(c==k.PAGE_DOWN||c==k.TAB))){
this._adjacent(true)._buttonWidget._onTitleClick();
dojo.stopEvent(e);
}
}
}});
dojo.declare("dijit.layout._AccordionInnerContainer",[dijit._Widget,dijit._CssStateMixin],{baseClass:"dijitAccordionInnerContainer",isContainer:true,isLayoutContainer:true,buildRendering:function(){
this.domNode=dojo.place("<div class='"+this.baseClass+"'>",this.contentWidget.domNode,"after");
var _1b=this.contentWidget,cls=dojo.getObject(this.buttonWidget);
this.button=_1b._buttonWidget=(new cls({contentWidget:_1b,label:_1b.title,title:_1b.tooltip,dir:_1b.dir,lang:_1b.lang,iconClass:_1b.iconClass,id:_1b.id+"_button",parent:this.parent})).placeAt(this.domNode);
dojo.place(this.contentWidget.domNode,this.domNode);
},postCreate:function(){
this.inherited(arguments);
this.connect(this.contentWidget,"set",function(_1c,_1d){
var _1e={title:"label",tooltip:"title",iconClass:"iconClass"}[_1c];
if(_1e){
this.button.set(_1e,_1d);
}
},this);
},_setSelectedAttr:function(_1f){
this.selected=_1f;
this.button.set("selected",_1f);
if(_1f){
var cw=this.contentWidget;
if(cw.onSelected){
cw.onSelected();
}
}
},startup:function(){
this.contentWidget.startup();
},destroy:function(){
this.button.destroyRecursive();
delete this.contentWidget._buttonWidget;
delete this.contentWidget._wrapperWidget;
this.inherited(arguments);
},destroyDescendants:function(){
this.contentWidget.destroyRecursive();
}});
dojo.declare("dijit.layout._AccordionButton",[dijit._Widget,dijit._Templated,dijit._CssStateMixin],{templateString:dojo.cache("dijit.layout","templates/AccordionButton.html","<div dojoAttachEvent='onclick:_onTitleClick' class='dijitAccordionTitle'>\n\t<div dojoAttachPoint='titleNode,focusNode' dojoAttachEvent='onkeypress:_onTitleKeyPress'\n\t\t\tclass='dijitAccordionTitleFocus' wairole=\"tab\" waiState=\"expanded-false\"\n\t\t><span class='dijitInline dijitAccordionArrow' waiRole=\"presentation\"></span\n\t\t><span class='arrowTextUp' waiRole=\"presentation\">+</span\n\t\t><span class='arrowTextDown' waiRole=\"presentation\">-</span\n\t\t><img src=\"${_blankGif}\" alt=\"\" class=\"dijitIcon\" dojoAttachPoint='iconNode' style=\"vertical-align: middle\" waiRole=\"presentation\"/>\n\t\t<span waiRole=\"presentation\" dojoAttachPoint='titleTextNode' class='dijitAccordionText'></span>\n\t</div>\n</div>\n"),attributeMap:dojo.mixin(dojo.clone(dijit.layout.ContentPane.prototype.attributeMap),{label:{node:"titleTextNode",type:"innerHTML"},title:{node:"titleTextNode",type:"attribute",attribute:"title"},iconClass:{node:"iconNode",type:"class"}}),baseClass:"dijitAccordionTitle",getParent:function(){
return this.parent;
},postCreate:function(){
this.inherited(arguments);
dojo.setSelectable(this.domNode,false);
var _20=dojo.attr(this.domNode,"id").replace(" ","_");
dojo.attr(this.titleTextNode,"id",_20+"_title");
dijit.setWaiState(this.focusNode,"labelledby",dojo.attr(this.titleTextNode,"id"));
},getTitleHeight:function(){
return dojo.marginBox(this.domNode).h;
},_onTitleClick:function(){
var _21=this.getParent();
if(!_21._inTransition){
_21.selectChild(this.contentWidget,true);
dijit.focus(this.focusNode);
}
},_onTitleKeyPress:function(evt){
return this.getParent()._onKeyPress(evt,this.contentWidget);
},_setSelectedAttr:function(_22){
this.selected=_22;
dijit.setWaiState(this.focusNode,"expanded",_22);
dijit.setWaiState(this.focusNode,"selected",_22);
this.focusNode.setAttribute("tabIndex",_22?"0":"-1");
}});
}
