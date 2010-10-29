/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.layout.BorderContainer"]){
dojo._hasResource["dijit.layout.BorderContainer"]=true;
dojo.provide("dijit.layout.BorderContainer");
dojo.require("dijit.layout._LayoutWidget");
dojo.require("dojo.cookie");
dojo.declare("dijit.layout.BorderContainer",dijit.layout._LayoutWidget,{design:"headline",gutters:true,liveSplitters:true,persist:false,baseClass:"dijitBorderContainer",_splitterClass:"dijit.layout._Splitter",postMixInProperties:function(){
if(!this.gutters){
this.baseClass+="NoGutter";
}
this.inherited(arguments);
},postCreate:function(){
this.inherited(arguments);
this._splitters={};
this._splitterThickness={};
},startup:function(){
if(this._started){
return;
}
dojo.forEach(this.getChildren(),this._setupChild,this);
this.inherited(arguments);
},_setupChild:function(_1){
var _2=_1.region;
if(_2){
this.inherited(arguments);
dojo.addClass(_1.domNode,this.baseClass+"Pane");
var _3=this.isLeftToRight();
if(_2=="leading"){
_2=_3?"left":"right";
}
if(_2=="trailing"){
_2=_3?"right":"left";
}
this["_"+_2]=_1.domNode;
this["_"+_2+"Widget"]=_1;
if((_1.splitter||this.gutters)&&!this._splitters[_2]){
var _4=dojo.getObject(_1.splitter?this._splitterClass:"dijit.layout._Gutter");
var _5=new _4({id:_1.id+"_splitter",container:this,child:_1,region:_2,live:this.liveSplitters});
_5.isSplitter=true;
this._splitters[_2]=_5.domNode;
dojo.place(this._splitters[_2],_1.domNode,"after");
_5.startup();
}
_1.region=_2;
}
},_computeSplitterThickness:function(_6){
this._splitterThickness[_6]=this._splitterThickness[_6]||dojo.marginBox(this._splitters[_6])[(/top|bottom/.test(_6)?"h":"w")];
},layout:function(){
for(var _7 in this._splitters){
this._computeSplitterThickness(_7);
}
this._layoutChildren();
},addChild:function(_8,_9){
this.inherited(arguments);
if(this._started){
this.layout();
}
},removeChild:function(_a){
var _b=_a.region;
var _c=this._splitters[_b];
if(_c){
dijit.byNode(_c).destroy();
delete this._splitters[_b];
delete this._splitterThickness[_b];
}
this.inherited(arguments);
delete this["_"+_b];
delete this["_"+_b+"Widget"];
if(this._started){
this._layoutChildren();
}
dojo.removeClass(_a.domNode,this.baseClass+"Pane");
},getChildren:function(){
return dojo.filter(this.inherited(arguments),function(_d){
return !_d.isSplitter;
});
},getSplitter:function(_e){
var _f=this._splitters[_e];
return _f?dijit.byNode(_f):null;
},resize:function(_10,_11){
if(!this.cs||!this.pe){
var _12=this.domNode;
this.cs=dojo.getComputedStyle(_12);
this.pe=dojo._getPadExtents(_12,this.cs);
this.pe.r=dojo._toPixelValue(_12,this.cs.paddingRight);
this.pe.b=dojo._toPixelValue(_12,this.cs.paddingBottom);
dojo.style(_12,"padding","0px");
}
this.inherited(arguments);
},_layoutChildren:function(_13,_14){
if(!this._borderBox||!this._borderBox.h){
return;
}
var _15=(this.design=="sidebar");
var _16=0,_17=0,_18=0,_19=0;
var _1a={},_1b={},_1c={},_1d={},_1e=(this._center&&this._center.style)||{};
var _1f=/left|right/.test(_13);
var _20=!_13||(!_1f&&!_15);
var _21=!_13||(_1f&&_15);
if(this._top){
_1a=(_13=="top"||_21)&&this._top.style;
_16=_13=="top"?_14:dojo.marginBox(this._top).h;
}
if(this._left){
_1b=(_13=="left"||_20)&&this._left.style;
_18=_13=="left"?_14:dojo.marginBox(this._left).w;
}
if(this._right){
_1c=(_13=="right"||_20)&&this._right.style;
_19=_13=="right"?_14:dojo.marginBox(this._right).w;
}
if(this._bottom){
_1d=(_13=="bottom"||_21)&&this._bottom.style;
_17=_13=="bottom"?_14:dojo.marginBox(this._bottom).h;
}
var _22=this._splitters;
var _23=_22.top,_24=_22.bottom,_25=_22.left,_26=_22.right;
var _27=this._splitterThickness;
var _28=_27.top||0,_29=_27.left||0,_2a=_27.right||0,_2b=_27.bottom||0;
if(_29>50||_2a>50){
setTimeout(dojo.hitch(this,function(){
this._splitterThickness={};
for(var _2c in this._splitters){
this._computeSplitterThickness(_2c);
}
this._layoutChildren();
}),50);
return false;
}
var pe=this.pe;
var _2d={left:(_15?_18+_29:0)+pe.l+"px",right:(_15?_19+_2a:0)+pe.r+"px"};
if(_23){
dojo.mixin(_23.style,_2d);
_23.style.top=_16+pe.t+"px";
}
if(_24){
dojo.mixin(_24.style,_2d);
_24.style.bottom=_17+pe.b+"px";
}
_2d={top:(_15?0:_16+_28)+pe.t+"px",bottom:(_15?0:_17+_2b)+pe.b+"px"};
if(_25){
dojo.mixin(_25.style,_2d);
_25.style.left=_18+pe.l+"px";
}
if(_26){
dojo.mixin(_26.style,_2d);
_26.style.right=_19+pe.r+"px";
}
dojo.mixin(_1e,{top:pe.t+_16+_28+"px",left:pe.l+_18+_29+"px",right:pe.r+_19+_2a+"px",bottom:pe.b+_17+_2b+"px"});
var _2e={top:_15?pe.t+"px":_1e.top,bottom:_15?pe.b+"px":_1e.bottom};
dojo.mixin(_1b,_2e);
dojo.mixin(_1c,_2e);
_1b.left=pe.l+"px";
_1c.right=pe.r+"px";
_1a.top=pe.t+"px";
_1d.bottom=pe.b+"px";
if(_15){
_1a.left=_1d.left=_18+_29+pe.l+"px";
_1a.right=_1d.right=_19+_2a+pe.r+"px";
}else{
_1a.left=_1d.left=pe.l+"px";
_1a.right=_1d.right=pe.r+"px";
}
var _2f=this._borderBox.h-pe.t-pe.b,_30=_2f-(_16+_28+_17+_2b),_31=_15?_2f:_30;
var _32=this._borderBox.w-pe.l-pe.r,_33=_32-(_18+_29+_19+_2a),_34=_15?_33:_32;
var dim={top:{w:_34,h:_16},bottom:{w:_34,h:_17},left:{w:_18,h:_31},right:{w:_19,h:_31},center:{h:_30,w:_33}};
if(_13){
var _35=this["_"+_13+"Widget"],mb={};
mb[/top|bottom/.test(_13)?"h":"w"]=_14;
_35.resize?_35.resize(mb,dim[_35.region]):dojo.marginBox(_35.domNode,mb);
}
var _36=dojo.isIE<8||(dojo.isIE&&dojo.isQuirks)||dojo.some(this.getChildren(),function(_37){
return _37.domNode.tagName=="TEXTAREA"||_37.domNode.tagName=="INPUT";
});
if(_36){
var _38=function(_39,_3a,_3b){
if(_39){
(_39.resize?_39.resize(_3a,_3b):dojo.marginBox(_39.domNode,_3a));
}
};
if(_25){
_25.style.height=_31;
}
if(_26){
_26.style.height=_31;
}
_38(this._leftWidget,{h:_31},dim.left);
_38(this._rightWidget,{h:_31},dim.right);
if(_23){
_23.style.width=_34;
}
if(_24){
_24.style.width=_34;
}
_38(this._topWidget,{w:_34},dim.top);
_38(this._bottomWidget,{w:_34},dim.bottom);
_38(this._centerWidget,dim.center);
}else{
var _3c=!_13||(/top|bottom/.test(_13)&&this.design!="sidebar"),_3d=!_13||(/left|right/.test(_13)&&this.design=="sidebar"),_3e={center:true,left:_3c,right:_3c,top:_3d,bottom:_3d};
dojo.forEach(this.getChildren(),function(_3f){
if(_3f.resize&&_3e[_3f.region]){
_3f.resize(null,dim[_3f.region]);
}
},this);
}
},destroy:function(){
for(var _40 in this._splitters){
var _41=this._splitters[_40];
dijit.byNode(_41).destroy();
dojo.destroy(_41);
}
delete this._splitters;
delete this._splitterThickness;
this.inherited(arguments);
}});
dojo.extend(dijit._Widget,{region:"",splitter:false,minSize:0,maxSize:Infinity});
dojo.require("dijit._Templated");
dojo.declare("dijit.layout._Splitter",[dijit._Widget,dijit._Templated],{live:true,templateString:"<div class=\"dijitSplitter\" dojoAttachEvent=\"onkeypress:_onKeyPress,onmousedown:_startDrag,onmouseenter:_onMouse,onmouseleave:_onMouse\" tabIndex=\"0\" waiRole=\"separator\"><div class=\"dijitSplitterThumb\"></div></div>",postCreate:function(){
this.inherited(arguments);
this.horizontal=/top|bottom/.test(this.region);
dojo.addClass(this.domNode,"dijitSplitter"+(this.horizontal?"H":"V"));
this._factor=/top|left/.test(this.region)?1:-1;
this._cookieName=this.container.id+"_"+this.region;
if(this.container.persist){
var _42=dojo.cookie(this._cookieName);
if(_42){
this.child.domNode.style[this.horizontal?"height":"width"]=_42;
}
}
},_computeMaxSize:function(){
var dim=this.horizontal?"h":"w",_43=this.container._splitterThickness[this.region];
var _44={left:"right",right:"left",top:"bottom",bottom:"top",leading:"trailing",trailing:"leading"},_45=this.container["_"+_44[this.region]];
var _46=dojo.contentBox(this.container.domNode)[dim]-(_45?dojo.marginBox(_45)[dim]:0)-20-_43*2;
return Math.min(this.child.maxSize,_46);
},_startDrag:function(e){
if(!this.cover){
this.cover=dojo.doc.createElement("div");
dojo.addClass(this.cover,"dijitSplitterCover");
dojo.place(this.cover,this.child.domNode,"after");
}
dojo.addClass(this.cover,"dijitSplitterCoverActive");
if(this.fake){
dojo.destroy(this.fake);
}
if(!(this._resize=this.live)){
(this.fake=this.domNode.cloneNode(true)).removeAttribute("id");
dojo.addClass(this.domNode,"dijitSplitterShadow");
dojo.place(this.fake,this.domNode,"after");
}
dojo.addClass(this.domNode,"dijitSplitterActive");
dojo.addClass(this.domNode,"dijitSplitter"+(this.horizontal?"H":"V")+"Active");
if(this.fake){
dojo.removeClass(this.fake,"dijitSplitterHover");
dojo.removeClass(this.fake,"dijitSplitter"+(this.horizontal?"H":"V")+"Hover");
}
var _47=this._factor,max=this._computeMaxSize(),min=this.child.minSize||20,_48=this.horizontal,_49=_48?"pageY":"pageX",_4a=e[_49],_4b=this.domNode.style,dim=_48?"h":"w",_4c=dojo.marginBox(this.child.domNode)[dim],_4d=this.region,_4e=parseInt(this.domNode.style[_4d],10),_4f=this._resize,_50=this.child.domNode,_51=dojo.hitch(this.container,this.container._layoutChildren),de=dojo.doc;
this._handlers=(this._handlers||[]).concat([dojo.connect(de,"onmousemove",this._drag=function(e,_52){
var _53=e[_49]-_4a,_54=_47*_53+_4c,_55=Math.max(Math.min(_54,max),min);
if(_4f||_52){
_51(_4d,_55);
}
_4b[_4d]=_47*_53+_4e+(_55-_54)+"px";
}),dojo.connect(de,"ondragstart",dojo.stopEvent),dojo.connect(dojo.body(),"onselectstart",dojo.stopEvent),dojo.connect(de,"onmouseup",this,"_stopDrag")]);
dojo.stopEvent(e);
},_onMouse:function(e){
var o=(e.type=="mouseover"||e.type=="mouseenter");
dojo.toggleClass(this.domNode,"dijitSplitterHover",o);
dojo.toggleClass(this.domNode,"dijitSplitter"+(this.horizontal?"H":"V")+"Hover",o);
},_stopDrag:function(e){
try{
if(this.cover){
dojo.removeClass(this.cover,"dijitSplitterCoverActive");
}
if(this.fake){
dojo.destroy(this.fake);
}
dojo.removeClass(this.domNode,"dijitSplitterActive");
dojo.removeClass(this.domNode,"dijitSplitter"+(this.horizontal?"H":"V")+"Active");
dojo.removeClass(this.domNode,"dijitSplitterShadow");
this._drag(e);
this._drag(e,true);
}
finally{
this._cleanupHandlers();
delete this._drag;
}
if(this.container.persist){
dojo.cookie(this._cookieName,this.child.domNode.style[this.horizontal?"height":"width"],{expires:365});
}
},_cleanupHandlers:function(){
dojo.forEach(this._handlers,dojo.disconnect);
delete this._handlers;
},_onKeyPress:function(e){
this._resize=true;
var _56=this.horizontal;
var _57=1;
var dk=dojo.keys;
switch(e.charOrCode){
case _56?dk.UP_ARROW:dk.LEFT_ARROW:
_57*=-1;
case _56?dk.DOWN_ARROW:dk.RIGHT_ARROW:
break;
default:
return;
}
var _58=dojo.marginBox(this.child.domNode)[_56?"h":"w"]+this._factor*_57;
this.container._layoutChildren(this.region,Math.max(Math.min(_58,this._computeMaxSize()),this.child.minSize));
dojo.stopEvent(e);
},destroy:function(){
this._cleanupHandlers();
delete this.child;
delete this.container;
delete this.cover;
delete this.fake;
this.inherited(arguments);
}});
dojo.declare("dijit.layout._Gutter",[dijit._Widget,dijit._Templated],{templateString:"<div class=\"dijitGutter\" waiRole=\"presentation\"></div>",postCreate:function(){
this.horizontal=/top|bottom/.test(this.region);
dojo.addClass(this.domNode,"dijitGutter"+(this.horizontal?"H":"V"));
}});
}
