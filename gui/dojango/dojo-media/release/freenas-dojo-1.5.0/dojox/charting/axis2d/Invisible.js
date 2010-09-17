/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.charting.axis2d.Invisible"]){
dojo._hasResource["dojox.charting.axis2d.Invisible"]=true;
dojo.provide("dojox.charting.axis2d.Invisible");
dojo.require("dojox.charting.scaler.linear");
dojo.require("dojox.charting.axis2d.common");
dojo.require("dojox.charting.axis2d.Base");
dojo.require("dojo.string");
dojo.require("dojox.gfx");
dojo.require("dojox.lang.functional");
dojo.require("dojox.lang.utils");
(function(){
var dc=dojox.charting,df=dojox.lang.functional,du=dojox.lang.utils,g=dojox.gfx,_1=dc.scaler.linear,_2=du.merge,_3=4,_4=45;
dojo.declare("dojox.charting.axis2d.Invisible",dojox.charting.axis2d.Base,{defaultParams:{vertical:false,fixUpper:"none",fixLower:"none",natural:false,leftBottom:true,includeZero:false,fixed:true,majorLabels:true,minorTicks:true,minorLabels:true,microTicks:false,rotation:0},optionalParams:{min:0,max:1,from:0,to:1,majorTickStep:4,minorTickStep:2,microTickStep:1,labels:[],labelFunc:null,maxLabelSize:0},constructor:function(_5,_6){
this.opt=dojo.delegate(this.defaultParams,_6);
du.updateWithPattern(this.opt,_6,this.optionalParams);
},dependOnData:function(){
return !("min" in this.opt)||!("max" in this.opt);
},clear:function(){
delete this.scaler;
delete this.ticks;
this.dirty=true;
return this;
},initialized:function(){
return "scaler" in this&&!(this.dirty&&this.dependOnData());
},setWindow:function(_7,_8){
this.scale=_7;
this.offset=_8;
return this.clear();
},getWindowScale:function(){
return "scale" in this?this.scale:1;
},getWindowOffset:function(){
return "offset" in this?this.offset:0;
},_groupLabelWidth:function(_9,_a){
if(!_9.length){
return 0;
}
if(dojo.isObject(_9[0])){
_9=df.map(_9,function(_b){
return _b.text;
});
}
var s=_9.join("<br>");
return dojox.gfx._base._getTextBox(s,{font:_a}).w||0;
},calculate:function(_c,_d,_e,_f){
if(this.initialized()){
return this;
}
var o=this.opt;
this.labels="labels" in o?o.labels:_f;
this.scaler=_1.buildScaler(_c,_d,_e,o);
var tsb=this.scaler.bounds;
if("scale" in this){
o.from=tsb.lower+this.offset;
o.to=(tsb.upper-tsb.lower)/this.scale+o.from;
if(!isFinite(o.from)||isNaN(o.from)||!isFinite(o.to)||isNaN(o.to)||o.to-o.from>=tsb.upper-tsb.lower){
delete o.from;
delete o.to;
delete this.scale;
delete this.offset;
}else{
if(o.from<tsb.lower){
o.to+=tsb.lower-o.from;
o.from=tsb.lower;
}else{
if(o.to>tsb.upper){
o.from+=tsb.upper-o.to;
o.to=tsb.upper;
}
}
this.offset=o.from-tsb.lower;
}
this.scaler=_1.buildScaler(_c,_d,_e,o);
tsb=this.scaler.bounds;
if(this.scale==1&&this.offset==0){
delete this.scale;
delete this.offset;
}
}
var ta=this.chart.theme.axis,_10=0,_11=o.rotation%360,_12=o.font||(ta.majorTick&&ta.majorTick.font)||(ta.tick&&ta.tick.font),_13=_12?g.normalizedLength(g.splitFontString(_12).size):0,_14=Math.abs(Math.cos(_11*Math.PI/180)),_15=Math.abs(Math.sin(_11*Math.PI/180));
if(_11<0){
_11+=360;
}
if(_13){
if(this.vertical?_11!=0&&_11!=180:_11!=90&&_11!=270){
if(o.maxLabelSize){
_10=o.maxLabelSize;
}else{
if(this.labels){
_10=this._groupLabelWidth(this.labels,_12);
}else{
var _16=Math.ceil(Math.log(Math.max(Math.abs(tsb.from),Math.abs(tsb.to)))/Math.LN10),t=[];
if(tsb.from<0||tsb.to<0){
t.push("-");
}
t.push(dojo.string.rep("9",_16));
var _17=Math.floor(Math.log(tsb.to-tsb.from)/Math.LN10);
if(_17>0){
t.push(".");
t.push(dojo.string.rep("9",_17));
}
_10=dojox.gfx._base._getTextBox(t.join(""),{font:_12}).w;
}
}
}else{
_10=_13;
}
switch(_11){
case 0:
case 90:
case 180:
case 270:
break;
default:
var _18=Math.sqrt(_10*_10+_13*_13),_19=this.vertical?_13*_14+_10*_15:_10*_14+_13*_15;
_10=Math.min(_18,_19);
break;
}
}
this.scaler.minMinorStep=_10+_3;
this.ticks=_1.buildTicks(this.scaler,o);
return this;
},getScaler:function(){
return this.scaler;
},getTicks:function(){
return this.ticks;
}});
})();
}
