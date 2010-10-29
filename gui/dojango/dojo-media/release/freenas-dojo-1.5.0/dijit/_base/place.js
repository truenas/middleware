/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit._base.place"]){
dojo._hasResource["dijit._base.place"]=true;
dojo.provide("dijit._base.place");
dojo.require("dojo.window");
dojo.require("dojo.AdapterRegistry");
dijit.getViewport=function(){
return dojo.window.getBox();
};
dijit.placeOnScreen=function(_1,_2,_3,_4){
var _5=dojo.map(_3,function(_6){
var c={corner:_6,pos:{x:_2.x,y:_2.y}};
if(_4){
c.pos.x+=_6.charAt(1)=="L"?_4.x:-_4.x;
c.pos.y+=_6.charAt(0)=="T"?_4.y:-_4.y;
}
return c;
});
return dijit._place(_1,_5);
};
dijit._place=function(_7,_8,_9){
var _a=dojo.window.getBox();
if(!_7.parentNode||String(_7.parentNode.tagName).toLowerCase()!="body"){
dojo.body().appendChild(_7);
}
var _b=null;
dojo.some(_8,function(_c){
var _d=_c.corner;
var _e=_c.pos;
if(_9){
_9(_7,_c.aroundCorner,_d);
}
var _f=_7.style;
var _10=_f.display;
var _11=_f.visibility;
_f.visibility="hidden";
_f.display="";
var mb=dojo.marginBox(_7);
_f.display=_10;
_f.visibility=_11;
var _12=Math.max(_a.l,_d.charAt(1)=="L"?_e.x:(_e.x-mb.w)),_13=Math.max(_a.t,_d.charAt(0)=="T"?_e.y:(_e.y-mb.h)),_14=Math.min(_a.l+_a.w,_d.charAt(1)=="L"?(_12+mb.w):_e.x),_15=Math.min(_a.t+_a.h,_d.charAt(0)=="T"?(_13+mb.h):_e.y),_16=_14-_12,_17=_15-_13,_18=(mb.w-_16)+(mb.h-_17);
if(_b==null||_18<_b.overflow){
_b={corner:_d,aroundCorner:_c.aroundCorner,x:_12,y:_13,w:_16,h:_17,overflow:_18};
}
return !_18;
});
_7.style.left=_b.x+"px";
_7.style.top=_b.y+"px";
if(_b.overflow&&_9){
_9(_7,_b.aroundCorner,_b.corner);
}
return _b;
};
dijit.placeOnScreenAroundNode=function(_19,_1a,_1b,_1c){
_1a=dojo.byId(_1a);
var _1d=_1a.style.display;
_1a.style.display="";
var _1e=dojo.position(_1a,true);
_1a.style.display=_1d;
return dijit._placeOnScreenAroundRect(_19,_1e.x,_1e.y,_1e.w,_1e.h,_1b,_1c);
};
dijit.placeOnScreenAroundRectangle=function(_1f,_20,_21,_22){
return dijit._placeOnScreenAroundRect(_1f,_20.x,_20.y,_20.width,_20.height,_21,_22);
};
dijit._placeOnScreenAroundRect=function(_23,x,y,_24,_25,_26,_27){
var _28=[];
for(var _29 in _26){
_28.push({aroundCorner:_29,corner:_26[_29],pos:{x:x+(_29.charAt(1)=="L"?0:_24),y:y+(_29.charAt(0)=="T"?0:_25)}});
}
return dijit._place(_23,_28,_27);
};
dijit.placementRegistry=new dojo.AdapterRegistry();
dijit.placementRegistry.register("node",function(n,x){
return typeof x=="object"&&typeof x.offsetWidth!="undefined"&&typeof x.offsetHeight!="undefined";
},dijit.placeOnScreenAroundNode);
dijit.placementRegistry.register("rect",function(n,x){
return typeof x=="object"&&"x" in x&&"y" in x&&"width" in x&&"height" in x;
},dijit.placeOnScreenAroundRectangle);
dijit.placeOnScreenAroundElement=function(_2a,_2b,_2c,_2d){
return dijit.placementRegistry.match.apply(dijit.placementRegistry,arguments);
};
dijit.getPopupAroundAlignment=function(_2e,_2f){
var _30={};
dojo.forEach(_2e,function(pos){
switch(pos){
case "after":
_30[_2f?"BR":"BL"]=_2f?"BL":"BR";
break;
case "before":
_30[_2f?"BL":"BR"]=_2f?"BR":"BL";
break;
case "below":
_30[_2f?"BL":"BR"]=_2f?"TL":"TR";
_30[_2f?"BR":"BL"]=_2f?"TR":"TL";
break;
case "above":
default:
_30[_2f?"TL":"TR"]=_2f?"BL":"BR";
_30[_2f?"TR":"TL"]=_2f?"BR":"BL";
break;
}
});
return _30;
};
}
