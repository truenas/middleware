/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.Tooltip"]){
dojo._hasResource["dijit.Tooltip"]=true;
dojo.provide("dijit.Tooltip");
dojo.require("dijit._Widget");
dojo.require("dijit._Templated");
dojo.declare("dijit._MasterTooltip",[dijit._Widget,dijit._Templated],{duration:dijit.defaultDuration,templateString:dojo.cache("dijit","templates/Tooltip.html","<div class=\"dijitTooltip dijitTooltipLeft\" id=\"dojoTooltip\">\n\t<div class=\"dijitTooltipContainer dijitTooltipContents\" dojoAttachPoint=\"containerNode\" waiRole='alert'></div>\n\t<div class=\"dijitTooltipConnector\"></div>\n</div>\n"),postCreate:function(){
dojo.body().appendChild(this.domNode);
this.bgIframe=new dijit.BackgroundIframe(this.domNode);
this.fadeIn=dojo.fadeIn({node:this.domNode,duration:this.duration,onEnd:dojo.hitch(this,"_onShow")});
this.fadeOut=dojo.fadeOut({node:this.domNode,duration:this.duration,onEnd:dojo.hitch(this,"_onHide")});
},show:function(_1,_2,_3,_4){
if(this.aroundNode&&this.aroundNode===_2){
return;
}
if(this.fadeOut.status()=="playing"){
this._onDeck=arguments;
return;
}
this.containerNode.innerHTML=_1;
var _5=dijit.placeOnScreenAroundElement(this.domNode,_2,dijit.getPopupAroundAlignment((_3&&_3.length)?_3:dijit.Tooltip.defaultPosition,!_4),dojo.hitch(this,"orient"));
dojo.style(this.domNode,"opacity",0);
this.fadeIn.play();
this.isShowingNow=true;
this.aroundNode=_2;
},orient:function(_6,_7,_8){
_6.className="dijitTooltip "+{"BL-TL":"dijitTooltipBelow dijitTooltipABLeft","TL-BL":"dijitTooltipAbove dijitTooltipABLeft","BR-TR":"dijitTooltipBelow dijitTooltipABRight","TR-BR":"dijitTooltipAbove dijitTooltipABRight","BR-BL":"dijitTooltipRight","BL-BR":"dijitTooltipLeft"}[_7+"-"+_8];
},_onShow:function(){
if(dojo.isIE){
this.domNode.style.filter="";
}
},hide:function(_9){
if(this._onDeck&&this._onDeck[1]==_9){
this._onDeck=null;
}else{
if(this.aroundNode===_9){
this.fadeIn.stop();
this.isShowingNow=false;
this.aroundNode=null;
this.fadeOut.play();
}else{
}
}
},_onHide:function(){
this.domNode.style.cssText="";
this.containerNode.innerHTML="";
if(this._onDeck){
this.show.apply(this,this._onDeck);
this._onDeck=null;
}
}});
dijit.showTooltip=function(_a,_b,_c,_d){
if(!dijit._masterTT){
dijit._masterTT=new dijit._MasterTooltip();
}
return dijit._masterTT.show(_a,_b,_c,_d);
};
dijit.hideTooltip=function(_e){
if(!dijit._masterTT){
dijit._masterTT=new dijit._MasterTooltip();
}
return dijit._masterTT.hide(_e);
};
dojo.declare("dijit.Tooltip",dijit._Widget,{label:"",showDelay:400,connectId:[],position:[],constructor:function(){
this._nodeConnectionsById={};
},_setConnectIdAttr:function(_f){
for(var _10 in this._nodeConnectionsById){
this.removeTarget(_10);
}
dojo.forEach(dojo.isArrayLike(_f)?_f:[_f],this.addTarget,this);
},_getConnectIdAttr:function(){
var ary=[];
for(var id in this._nodeConnectionsById){
ary.push(id);
}
return ary;
},addTarget:function(id){
var _11=dojo.byId(id);
if(!_11){
return;
}
if(_11.id in this._nodeConnectionsById){
return;
}
this._nodeConnectionsById[_11.id]=[this.connect(_11,"onmouseenter","_onTargetMouseEnter"),this.connect(_11,"onmouseleave","_onTargetMouseLeave"),this.connect(_11,"onfocus","_onTargetFocus"),this.connect(_11,"onblur","_onTargetBlur")];
},removeTarget:function(_12){
var id=_12.id||_12;
if(id in this._nodeConnectionsById){
dojo.forEach(this._nodeConnectionsById[id],this.disconnect,this);
delete this._nodeConnectionsById[id];
}
},postCreate:function(){
dojo.addClass(this.domNode,"dijitTooltipData");
},startup:function(){
this.inherited(arguments);
var ids=this.connectId;
dojo.forEach(dojo.isArrayLike(ids)?ids:[ids],this.addTarget,this);
},_onTargetMouseEnter:function(e){
this._onHover(e);
},_onTargetMouseLeave:function(e){
this._onUnHover(e);
},_onTargetFocus:function(e){
this._focus=true;
this._onHover(e);
},_onTargetBlur:function(e){
this._focus=false;
this._onUnHover(e);
},_onHover:function(e){
if(!this._showTimer){
var _13=e.target;
this._showTimer=setTimeout(dojo.hitch(this,function(){
this.open(_13);
}),this.showDelay);
}
},_onUnHover:function(e){
if(this._focus){
return;
}
if(this._showTimer){
clearTimeout(this._showTimer);
delete this._showTimer;
}
this.close();
},open:function(_14){
if(this._showTimer){
clearTimeout(this._showTimer);
delete this._showTimer;
}
dijit.showTooltip(this.label||this.domNode.innerHTML,_14,this.position,!this.isLeftToRight());
this._connectNode=_14;
this.onShow(_14,this.position);
},close:function(){
if(this._connectNode){
dijit.hideTooltip(this._connectNode);
delete this._connectNode;
this.onHide();
}
if(this._showTimer){
clearTimeout(this._showTimer);
delete this._showTimer;
}
},onShow:function(_15,_16){
},onHide:function(){
},uninitialize:function(){
this.close();
this.inherited(arguments);
}});
dijit.Tooltip.defaultPosition=["after","before"];
}
