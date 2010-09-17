/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.charting.Element"]){
dojo._hasResource["dojox.charting.Element"]=true;
dojo.provide("dojox.charting.Element");
dojo.require("dojox.gfx");
dojo.declare("dojox.charting.Element",null,{chart:null,group:null,htmlElements:null,dirty:true,constructor:function(_1){
this.chart=_1;
this.group=null;
this.htmlElements=[];
this.dirty=true;
},createGroup:function(_2){
if(!_2){
_2=this.chart.surface;
}
if(!this.group){
this.group=_2.createGroup();
}
return this;
},purgeGroup:function(){
this.destroyHtmlElements();
if(this.group){
this.group.clear();
this.group.removeShape();
this.group=null;
}
this.dirty=true;
return this;
},cleanGroup:function(_3){
this.destroyHtmlElements();
if(!_3){
_3=this.chart.surface;
}
if(this.group){
this.group.clear();
}else{
this.group=_3.createGroup();
}
this.dirty=true;
return this;
},destroyHtmlElements:function(){
if(this.htmlElements.length){
dojo.forEach(this.htmlElements,dojo.destroy);
this.htmlElements=[];
}
},destroy:function(){
this.purgeGroup();
},_plotFill:function(_4,_5,_6){
if(!_4||!_4.type||!_4.space){
return _4;
}
var _7=_4.space;
switch(_4.type){
case "linear":
if(_7==="plot"||_7==="shapeX"||_7==="shapeY"){
_4=dojox.gfx.makeParameters(dojox.gfx.defaultLinearGradient,_4);
_4.space=_7;
if(_7==="plot"||_7==="shapeX"){
var _8=_5.height-_6.t-_6.b;
_4.y1=_6.t+_8*_4.y1/100;
_4.y2=_6.t+_8*_4.y2/100;
}
if(_7==="plot"||_7==="shapeY"){
var _8=_5.width-_6.l-_6.r;
_4.x1=_6.l+_8*_4.x1/100;
_4.x2=_6.l+_8*_4.x2/100;
}
}
break;
case "radial":
if(_7==="plot"){
_4=dojox.gfx.makeParameters(dojox.gfx.defaultRadialGradient,_4);
_4.space=_7;
var _9=_5.width-_6.l-_6.r,_a=_5.height-_6.t-_6.b;
_4.cx=_6.l+_9*_4.cx/100;
_4.cy=_6.t+_a*_4.cy/100;
_4.r=_4.r*Math.sqrt(_9*_9+_a*_a)/200;
}
break;
case "pattern":
if(_7==="plot"||_7==="shapeX"||_7==="shapeY"){
_4=dojox.gfx.makeParameters(dojox.gfx.defaultPattern,_4);
_4.space=_7;
if(_7==="plot"||_7==="shapeX"){
var _8=_5.height-_6.t-_6.b;
_4.y=_6.t+_8*_4.y/100;
_4.height=_8*_4.height/100;
}
if(_7==="plot"||_7==="shapeY"){
var _8=_5.width-_6.l-_6.r;
_4.x=_6.l+_8*_4.x/100;
_4.width=_8*_4.width/100;
}
}
break;
}
return _4;
},_shapeFill:function(_b,_c){
if(!_b||!_b.space){
return _b;
}
var _d=_b.space;
switch(_b.type){
case "linear":
if(_d==="shape"||_d==="shapeX"||_d==="shapeY"){
_b=dojox.gfx.makeParameters(dojox.gfx.defaultLinearGradient,_b);
_b.space=_d;
if(_d==="shape"||_d==="shapeX"){
var _e=_c.width;
_b.x1=_c.x+_e*_b.x1/100;
_b.x2=_c.x+_e*_b.x2/100;
}
if(_d==="shape"||_d==="shapeY"){
var _e=_c.height;
_b.y1=_c.y+_e*_b.y1/100;
_b.y2=_c.y+_e*_b.y2/100;
}
}
break;
case "radial":
if(_d==="shape"){
_b=dojox.gfx.makeParameters(dojox.gfx.defaultRadialGradient,_b);
_b.space=_d;
_b.cx=_c.x+_c.width/2;
_b.cy=_c.y+_c.height/2;
_b.r=_b.r*_c.width/200;
}
break;
case "pattern":
if(_d==="shape"||_d==="shapeX"||_d==="shapeY"){
_b=dojox.gfx.makeParameters(dojox.gfx.defaultPattern,_b);
_b.space=_d;
if(_d==="shape"||_d==="shapeX"){
var _e=_c.width;
_b.x=_c.x+_e*_b.x/100;
_b.width=_e*_b.width/100;
}
if(_d==="shape"||_d==="shapeY"){
var _e=_c.height;
_b.y=_c.y+_e*_b.y/100;
_b.height=_e*_b.height/100;
}
}
break;
}
return _b;
},_pseudoRadialFill:function(_f,_10,_11,_12,end){
if(!_f||_f.type!=="radial"||_f.space!=="shape"){
return _f;
}
var _13=_f.space;
_f=dojox.gfx.makeParameters(dojox.gfx.defaultRadialGradient,_f);
_f.space=_13;
if(arguments.length<4){
_f.cx=_10.x;
_f.cy=_10.y;
_f.r=_f.r*_11/100;
return _f;
}
var _14=arguments.length<5?_12:(end+_12)/2;
return {type:"linear",x1:_10.x,y1:_10.y,x2:_10.x+_f.r*_11*Math.cos(_14)/100,y2:_10.y+_f.r*_11*Math.sin(_14)/100,colors:_f.colors};
return _f;
}});
}
