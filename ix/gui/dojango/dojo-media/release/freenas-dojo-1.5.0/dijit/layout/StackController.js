/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.layout.StackController"]){
dojo._hasResource["dijit.layout.StackController"]=true;
dojo.provide("dijit.layout.StackController");
dojo.require("dijit._Widget");
dojo.require("dijit._Templated");
dojo.require("dijit._Container");
dojo.require("dijit.form.ToggleButton");
dojo.requireLocalization("dijit","common",null,"ROOT,ar,ca,cs,da,de,el,es,fi,fr,he,hu,it,ja,ko,nb,nl,pl,pt,pt-pt,ro,ru,sk,sl,sv,th,tr,zh,zh-tw");
dojo.declare("dijit.layout.StackController",[dijit._Widget,dijit._Templated,dijit._Container],{templateString:"<span wairole='tablist' dojoAttachEvent='onkeypress' class='dijitStackController'></span>",containerId:"",buttonWidget:"dijit.layout._StackButton",postCreate:function(){
dijit.setWaiRole(this.domNode,"tablist");
this.pane2button={};
this.pane2handles={};
this.subscribe(this.containerId+"-startup","onStartup");
this.subscribe(this.containerId+"-addChild","onAddChild");
this.subscribe(this.containerId+"-removeChild","onRemoveChild");
this.subscribe(this.containerId+"-selectChild","onSelectChild");
this.subscribe(this.containerId+"-containerKeyPress","onContainerKeyPress");
},onStartup:function(_1){
dojo.forEach(_1.children,this.onAddChild,this);
if(_1.selected){
this.onSelectChild(_1.selected);
}
},destroy:function(){
for(var _2 in this.pane2button){
this.onRemoveChild(dijit.byId(_2));
}
this.inherited(arguments);
},onAddChild:function(_3,_4){
var _5=dojo.getObject(this.buttonWidget);
var _6=new _5({id:this.id+"_"+_3.id,label:_3.title,dir:_3.dir,lang:_3.lang,showLabel:_3.showTitle,iconClass:_3.iconClass,closeButton:_3.closable,title:_3.tooltip});
dijit.setWaiState(_6.focusNode,"selected","false");
this.pane2handles[_3.id]=[this.connect(_3,"set",function(_7,_8){
var _9={title:"label",showTitle:"showLabel",iconClass:"iconClass",closable:"closeButton",tooltip:"title"}[_7];
if(_9){
_6.set(_9,_8);
}
}),this.connect(_6,"onClick",dojo.hitch(this,"onButtonClick",_3)),this.connect(_6,"onClickCloseButton",dojo.hitch(this,"onCloseButtonClick",_3))];
this.addChild(_6,_4);
this.pane2button[_3.id]=_6;
_3.controlButton=_6;
if(!this._currentChild){
_6.focusNode.setAttribute("tabIndex","0");
dijit.setWaiState(_6.focusNode,"selected","true");
this._currentChild=_3;
}
if(!this.isLeftToRight()&&dojo.isIE&&this._rectifyRtlTabList){
this._rectifyRtlTabList();
}
},onRemoveChild:function(_a){
if(this._currentChild===_a){
this._currentChild=null;
}
dojo.forEach(this.pane2handles[_a.id],this.disconnect,this);
delete this.pane2handles[_a.id];
var _b=this.pane2button[_a.id];
if(_b){
this.removeChild(_b);
delete this.pane2button[_a.id];
_b.destroy();
}
delete _a.controlButton;
},onSelectChild:function(_c){
if(!_c){
return;
}
if(this._currentChild){
var _d=this.pane2button[this._currentChild.id];
_d.set("checked",false);
dijit.setWaiState(_d.focusNode,"selected","false");
_d.focusNode.setAttribute("tabIndex","-1");
}
var _e=this.pane2button[_c.id];
_e.set("checked",true);
dijit.setWaiState(_e.focusNode,"selected","true");
this._currentChild=_c;
_e.focusNode.setAttribute("tabIndex","0");
var _f=dijit.byId(this.containerId);
dijit.setWaiState(_f.containerNode,"labelledby",_e.id);
},onButtonClick:function(_10){
var _11=dijit.byId(this.containerId);
_11.selectChild(_10);
},onCloseButtonClick:function(_12){
var _13=dijit.byId(this.containerId);
_13.closeChild(_12);
if(this._currentChild){
var b=this.pane2button[this._currentChild.id];
if(b){
dijit.focus(b.focusNode||b.domNode);
}
}
},adjacent:function(_14){
if(!this.isLeftToRight()&&(!this.tabPosition||/top|bottom/.test(this.tabPosition))){
_14=!_14;
}
var _15=this.getChildren();
var _16=dojo.indexOf(_15,this.pane2button[this._currentChild.id]);
var _17=_14?1:_15.length-1;
return _15[(_16+_17)%_15.length];
},onkeypress:function(e){
if(this.disabled||e.altKey){
return;
}
var _18=null;
if(e.ctrlKey||!e._djpage){
var k=dojo.keys;
switch(e.charOrCode){
case k.LEFT_ARROW:
case k.UP_ARROW:
if(!e._djpage){
_18=false;
}
break;
case k.PAGE_UP:
if(e.ctrlKey){
_18=false;
}
break;
case k.RIGHT_ARROW:
case k.DOWN_ARROW:
if(!e._djpage){
_18=true;
}
break;
case k.PAGE_DOWN:
if(e.ctrlKey){
_18=true;
}
break;
case k.DELETE:
if(this._currentChild.closable){
this.onCloseButtonClick(this._currentChild);
}
dojo.stopEvent(e);
break;
default:
if(e.ctrlKey){
if(e.charOrCode===k.TAB){
this.adjacent(!e.shiftKey).onClick();
dojo.stopEvent(e);
}else{
if(e.charOrCode=="w"){
if(this._currentChild.closable){
this.onCloseButtonClick(this._currentChild);
}
dojo.stopEvent(e);
}
}
}
}
if(_18!==null){
this.adjacent(_18).onClick();
dojo.stopEvent(e);
}
}
},onContainerKeyPress:function(_19){
_19.e._djpage=_19.page;
this.onkeypress(_19.e);
}});
dojo.declare("dijit.layout._StackButton",dijit.form.ToggleButton,{tabIndex:"-1",postCreate:function(evt){
dijit.setWaiRole((this.focusNode||this.domNode),"tab");
this.inherited(arguments);
},onClick:function(evt){
dijit.focus(this.focusNode);
},onClickCloseButton:function(evt){
evt.stopPropagation();
}});
}
