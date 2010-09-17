/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.layout.StackContainer"]){
dojo._hasResource["dijit.layout.StackContainer"]=true;
dojo.provide("dijit.layout.StackContainer");
dojo.require("dijit._Templated");
dojo.require("dijit.layout._LayoutWidget");
dojo.requireLocalization("dijit","common",null,"ROOT,ar,ca,cs,da,de,el,es,fi,fr,he,hu,it,ja,ko,nb,nl,pl,pt,pt-pt,ro,ru,sk,sl,sv,th,tr,zh,zh-tw");
dojo.require("dojo.cookie");
dojo.declare("dijit.layout.StackContainer",dijit.layout._LayoutWidget,{doLayout:true,persist:false,baseClass:"dijitStackContainer",postCreate:function(){
this.inherited(arguments);
dojo.addClass(this.domNode,"dijitLayoutContainer");
dijit.setWaiRole(this.containerNode,"tabpanel");
this.connect(this.domNode,"onkeypress",this._onKeyPress);
},startup:function(){
if(this._started){
return;
}
var _1=this.getChildren();
dojo.forEach(_1,this._setupChild,this);
if(this.persist){
this.selectedChildWidget=dijit.byId(dojo.cookie(this.id+"_selectedChild"));
}else{
dojo.some(_1,function(_2){
if(_2.selected){
this.selectedChildWidget=_2;
}
return _2.selected;
},this);
}
var _3=this.selectedChildWidget;
if(!_3&&_1[0]){
_3=this.selectedChildWidget=_1[0];
_3.selected=true;
}
dojo.publish(this.id+"-startup",[{children:_1,selected:_3}]);
this.inherited(arguments);
},resize:function(){
var _4=this.selectedChildWidget;
if(_4&&!this._hasBeenShown){
this._hasBeenShown=true;
this._showChild(_4);
}
this.inherited(arguments);
},_setupChild:function(_5){
this.inherited(arguments);
dojo.removeClass(_5.domNode,"dijitVisible");
dojo.addClass(_5.domNode,"dijitHidden");
_5.domNode.title="";
},addChild:function(_6,_7){
this.inherited(arguments);
if(this._started){
dojo.publish(this.id+"-addChild",[_6,_7]);
this.layout();
if(!this.selectedChildWidget){
this.selectChild(_6);
}
}
},removeChild:function(_8){
this.inherited(arguments);
if(this._started){
dojo.publish(this.id+"-removeChild",[_8]);
}
if(this._beingDestroyed){
return;
}
if(this.selectedChildWidget===_8){
this.selectedChildWidget=undefined;
if(this._started){
var _9=this.getChildren();
if(_9.length){
this.selectChild(_9[0]);
}
}
}
if(this._started){
this.layout();
}
},selectChild:function(_a,_b){
_a=dijit.byId(_a);
if(this.selectedChildWidget!=_a){
this._transition(_a,this.selectedChildWidget,_b);
this.selectedChildWidget=_a;
dojo.publish(this.id+"-selectChild",[_a]);
if(this.persist){
dojo.cookie(this.id+"_selectedChild",this.selectedChildWidget.id);
}
}
},_transition:function(_c,_d){
if(_d){
this._hideChild(_d);
}
this._showChild(_c);
if(_c.resize){
if(this.doLayout){
_c.resize(this._containerContentBox||this._contentBox);
}else{
_c.resize();
}
}
},_adjacent:function(_e){
var _f=this.getChildren();
var _10=dojo.indexOf(_f,this.selectedChildWidget);
_10+=_e?1:_f.length-1;
return _f[_10%_f.length];
},forward:function(){
this.selectChild(this._adjacent(true),true);
},back:function(){
this.selectChild(this._adjacent(false),true);
},_onKeyPress:function(e){
dojo.publish(this.id+"-containerKeyPress",[{e:e,page:this}]);
},layout:function(){
if(this.doLayout&&this.selectedChildWidget&&this.selectedChildWidget.resize){
this.selectedChildWidget.resize(this._containerContentBox||this._contentBox);
}
},_showChild:function(_11){
var _12=this.getChildren();
_11.isFirstChild=(_11==_12[0]);
_11.isLastChild=(_11==_12[_12.length-1]);
_11.selected=true;
dojo.removeClass(_11.domNode,"dijitHidden");
dojo.addClass(_11.domNode,"dijitVisible");
_11._onShow();
},_hideChild:function(_13){
_13.selected=false;
dojo.removeClass(_13.domNode,"dijitVisible");
dojo.addClass(_13.domNode,"dijitHidden");
_13.onHide();
},closeChild:function(_14){
var _15=_14.onClose(this,_14);
if(_15){
this.removeChild(_14);
_14.destroyRecursive();
}
},destroyDescendants:function(_16){
dojo.forEach(this.getChildren(),function(_17){
this.removeChild(_17);
_17.destroyRecursive(_16);
},this);
}});
dojo.require("dijit.layout.StackController");
dojo.extend(dijit._Widget,{selected:false,closable:false,iconClass:"",showTitle:true});
}
