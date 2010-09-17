/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.layout.ScrollingTabController"]){
dojo._hasResource["dijit.layout.ScrollingTabController"]=true;
dojo.provide("dijit.layout.ScrollingTabController");
dojo.require("dijit.layout.TabController");
dojo.require("dijit.Menu");
dojo.declare("dijit.layout.ScrollingTabController",dijit.layout.TabController,{templateString:dojo.cache("dijit.layout","templates/ScrollingTabController.html","<div class=\"dijitTabListContainer-${tabPosition}\" style=\"visibility:hidden\">\n\t<div dojoType=\"dijit.layout._ScrollingTabControllerButton\"\n\t\t\tclass=\"tabStripButton-${tabPosition}\"\n\t\t\tid=\"${id}_menuBtn\" iconClass=\"dijitTabStripMenuIcon\"\n\t\t\tdojoAttachPoint=\"_menuBtn\" showLabel=false>&#9660;</div>\n\t<div dojoType=\"dijit.layout._ScrollingTabControllerButton\"\n\t\t\tclass=\"tabStripButton-${tabPosition}\"\n\t\t\tid=\"${id}_leftBtn\" iconClass=\"dijitTabStripSlideLeftIcon\"\n\t\t\tdojoAttachPoint=\"_leftBtn\" dojoAttachEvent=\"onClick: doSlideLeft\" showLabel=false>&#9664;</div>\n\t<div dojoType=\"dijit.layout._ScrollingTabControllerButton\"\n\t\t\tclass=\"tabStripButton-${tabPosition}\"\n\t\t\tid=\"${id}_rightBtn\" iconClass=\"dijitTabStripSlideRightIcon\"\n\t\t\tdojoAttachPoint=\"_rightBtn\" dojoAttachEvent=\"onClick: doSlideRight\" showLabel=false>&#9654;</div>\n\t<div class='dijitTabListWrapper' dojoAttachPoint='tablistWrapper'>\n\t\t<div wairole='tablist' dojoAttachEvent='onkeypress:onkeypress'\n\t\t\t\tdojoAttachPoint='containerNode' class='nowrapTabStrip'></div>\n\t</div>\n</div>\n"),useMenu:true,useSlider:true,tabStripClass:"",widgetsInTemplate:true,_minScroll:5,attributeMap:dojo.delegate(dijit._Widget.prototype.attributeMap,{"class":"containerNode"}),postCreate:function(){
this.inherited(arguments);
var n=this.domNode;
this.scrollNode=this.tablistWrapper;
this._initButtons();
if(!this.tabStripClass){
this.tabStripClass="dijitTabContainer"+this.tabPosition.charAt(0).toUpperCase()+this.tabPosition.substr(1).replace(/-.*/,"")+"None";
dojo.addClass(n,"tabStrip-disabled");
}
dojo.addClass(this.tablistWrapper,this.tabStripClass);
},onStartup:function(){
this.inherited(arguments);
dojo.style(this.domNode,"visibility","visible");
this._postStartup=true;
},onAddChild:function(_1,_2){
this.inherited(arguments);
var _3;
if(this.useMenu){
var _4=this.containerId;
_3=new dijit.MenuItem({id:_1.id+"_stcMi",label:_1.title,dir:_1.dir,lang:_1.lang,onClick:dojo.hitch(this,function(){
var _5=dijit.byId(_4);
_5.selectChild(_1);
})});
this._menuChildren[_1.id]=_3;
this._menu.addChild(_3,_2);
}
this.pane2handles[_1.id].push(this.connect(this.pane2button[_1.id],"set",function(_6,_7){
if(this._postStartup){
if(_6=="label"){
if(_3){
_3.set(_6,_7);
}
if(this._dim){
this.resize(this._dim);
}
}
}
}));
dojo.style(this.containerNode,"width",(dojo.style(this.containerNode,"width")+200)+"px");
},onRemoveChild:function(_8,_9){
var _a=this.pane2button[_8.id];
if(this._selectedTab===_a.domNode){
this._selectedTab=null;
}
if(this.useMenu&&_8&&_8.id&&this._menuChildren[_8.id]){
this._menu.removeChild(this._menuChildren[_8.id]);
this._menuChildren[_8.id].destroy();
delete this._menuChildren[_8.id];
}
this.inherited(arguments);
},_initButtons:function(){
this._menuChildren={};
this._btnWidth=0;
this._buttons=dojo.query("> .tabStripButton",this.domNode).filter(function(_b){
if((this.useMenu&&_b==this._menuBtn.domNode)||(this.useSlider&&(_b==this._rightBtn.domNode||_b==this._leftBtn.domNode))){
this._btnWidth+=dojo.marginBox(_b).w;
return true;
}else{
dojo.style(_b,"display","none");
return false;
}
},this);
if(this.useMenu){
this._menu=new dijit.Menu({id:this.id+"_menu",dir:this.dir,lang:this.lang,targetNodeIds:[this._menuBtn.domNode],leftClickToOpen:true,refocus:false});
this._supportingWidgets.push(this._menu);
}
},_getTabsWidth:function(){
var _c=this.getChildren();
if(_c.length){
var _d=_c[this.isLeftToRight()?0:_c.length-1].domNode,_e=_c[this.isLeftToRight()?_c.length-1:0].domNode;
return _e.offsetLeft+dojo.style(_e,"width")-_d.offsetLeft;
}else{
return 0;
}
},_enableBtn:function(_f){
var _10=this._getTabsWidth();
_f=_f||dojo.style(this.scrollNode,"width");
return _10>0&&_f<_10;
},resize:function(dim){
if(this.domNode.offsetWidth==0){
return;
}
this._dim=dim;
this.scrollNode.style.height="auto";
this._contentBox=dijit.layout.marginBox2contentBox(this.domNode,{h:0,w:dim.w});
this._contentBox.h=this.scrollNode.offsetHeight;
dojo.contentBox(this.domNode,this._contentBox);
var _11=this._enableBtn(this._contentBox.w);
this._buttons.style("display",_11?"":"none");
this._leftBtn.layoutAlign="left";
this._rightBtn.layoutAlign="right";
this._menuBtn.layoutAlign=this.isLeftToRight()?"right":"left";
dijit.layout.layoutChildren(this.domNode,this._contentBox,[this._menuBtn,this._leftBtn,this._rightBtn,{domNode:this.scrollNode,layoutAlign:"client"}]);
if(this._selectedTab){
if(this._anim&&this._anim.status()=="playing"){
this._anim.stop();
}
var w=this.scrollNode,sl=this._convertToScrollLeft(this._getScrollForSelectedTab());
w.scrollLeft=sl;
}
this._setButtonClass(this._getScroll());
this._postResize=true;
},_getScroll:function(){
var sl=(this.isLeftToRight()||dojo.isIE<8||(dojo.isIE&&dojo.isQuirks)||dojo.isWebKit)?this.scrollNode.scrollLeft:dojo.style(this.containerNode,"width")-dojo.style(this.scrollNode,"width")+(dojo.isIE==8?-1:1)*this.scrollNode.scrollLeft;
return sl;
},_convertToScrollLeft:function(val){
if(this.isLeftToRight()||dojo.isIE<8||(dojo.isIE&&dojo.isQuirks)||dojo.isWebKit){
return val;
}else{
var _12=dojo.style(this.containerNode,"width")-dojo.style(this.scrollNode,"width");
return (dojo.isIE==8?-1:1)*(val-_12);
}
},onSelectChild:function(_13){
var tab=this.pane2button[_13.id];
if(!tab||!_13){
return;
}
var _14=tab.domNode;
if(this._postResize&&_14!=this._selectedTab){
this._selectedTab=_14;
var sl=this._getScroll();
if(sl>_14.offsetLeft||sl+dojo.style(this.scrollNode,"width")<_14.offsetLeft+dojo.style(_14,"width")){
this.createSmoothScroll().play();
}
}
this.inherited(arguments);
},_getScrollBounds:function(){
var _15=this.getChildren(),_16=dojo.style(this.scrollNode,"width"),_17=dojo.style(this.containerNode,"width"),_18=_17-_16,_19=this._getTabsWidth();
if(_15.length&&_19>_16){
return {min:this.isLeftToRight()?0:_15[_15.length-1].domNode.offsetLeft,max:this.isLeftToRight()?(_15[_15.length-1].domNode.offsetLeft+dojo.style(_15[_15.length-1].domNode,"width"))-_16:_18};
}else{
var _1a=this.isLeftToRight()?0:_18;
return {min:_1a,max:_1a};
}
},_getScrollForSelectedTab:function(){
var w=this.scrollNode,n=this._selectedTab,_1b=dojo.style(this.scrollNode,"width"),_1c=this._getScrollBounds();
var pos=(n.offsetLeft+dojo.style(n,"width")/2)-_1b/2;
pos=Math.min(Math.max(pos,_1c.min),_1c.max);
return pos;
},createSmoothScroll:function(x){
if(arguments.length>0){
var _1d=this._getScrollBounds();
x=Math.min(Math.max(x,_1d.min),_1d.max);
}else{
x=this._getScrollForSelectedTab();
}
if(this._anim&&this._anim.status()=="playing"){
this._anim.stop();
}
var _1e=this,w=this.scrollNode,_1f=new dojo._Animation({beforeBegin:function(){
if(this.curve){
delete this.curve;
}
var _20=w.scrollLeft,_21=_1e._convertToScrollLeft(x);
_1f.curve=new dojo._Line(_20,_21);
},onAnimate:function(val){
w.scrollLeft=val;
}});
this._anim=_1f;
this._setButtonClass(x);
return _1f;
},_getBtnNode:function(e){
var n=e.target;
while(n&&!dojo.hasClass(n,"tabStripButton")){
n=n.parentNode;
}
return n;
},doSlideRight:function(e){
this.doSlide(1,this._getBtnNode(e));
},doSlideLeft:function(e){
this.doSlide(-1,this._getBtnNode(e));
},doSlide:function(_22,_23){
if(_23&&dojo.hasClass(_23,"dijitTabDisabled")){
return;
}
var _24=dojo.style(this.scrollNode,"width");
var d=(_24*0.75)*_22;
var to=this._getScroll()+d;
this._setButtonClass(to);
this.createSmoothScroll(to).play();
},_setButtonClass:function(_25){
var _26=this._getScrollBounds();
this._leftBtn.set("disabled",_25<=_26.min);
this._rightBtn.set("disabled",_25>=_26.max);
}});
dojo.declare("dijit.layout._ScrollingTabControllerButton",dijit.form.Button,{baseClass:"dijitTab tabStripButton",templateString:dojo.cache("dijit.layout","templates/_ScrollingTabControllerButton.html","<div dojoAttachEvent=\"onclick:_onButtonClick\">\n\t<div waiRole=\"presentation\" class=\"dijitTabInnerDiv\" dojoattachpoint=\"innerDiv,focusNode\">\n\t\t<div waiRole=\"presentation\" class=\"dijitTabContent dijitButtonContents\" dojoattachpoint=\"tabContent\">\n\t\t\t<img waiRole=\"presentation\" alt=\"\" src=\"${_blankGif}\" class=\"dijitTabStripIcon\" dojoAttachPoint=\"iconNode\"/>\n\t\t\t<span dojoAttachPoint=\"containerNode,titleNode\" class=\"dijitButtonText\"></span>\n\t\t</div>\n\t</div>\n</div>\n"),tabIndex:"-1"});
}
