/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.charting.axis2d.Default"]){
dojo._hasResource["dojox.charting.axis2d.Default"]=true;
dojo.provide("dojox.charting.axis2d.Default");
dojo.require("dojox.charting.axis2d.Invisible");
dojo.require("dojox.charting.scaler.linear");
dojo.require("dojox.charting.axis2d.common");
dojo.require("dojo.colors");
dojo.require("dojo.string");
dojo.require("dojox.gfx");
dojo.require("dojox.lang.functional");
dojo.require("dojox.lang.utils");
(function(){
var dc=dojox.charting,du=dojox.lang.utils,g=dojox.gfx,_1=dc.scaler.linear,_2=4,_3=45;
dojo.declare("dojox.charting.axis2d.Default",dojox.charting.axis2d.Invisible,{defaultParams:{vertical:false,fixUpper:"none",fixLower:"none",natural:false,leftBottom:true,includeZero:false,fixed:true,majorLabels:true,minorTicks:true,minorLabels:true,microTicks:false,rotation:0,htmlLabels:true},optionalParams:{min:0,max:1,from:0,to:1,majorTickStep:4,minorTickStep:2,microTickStep:1,labels:[],labelFunc:null,maxLabelSize:0,stroke:{},majorTick:{},minorTick:{},microTick:{},tick:{},font:"",fontColor:""},constructor:function(_4,_5){
this.opt=dojo.delegate(this.defaultParams,_5);
du.updateWithPattern(this.opt,_5,this.optionalParams);
},getOffsets:function(){
var s=this.scaler,_6={l:0,r:0,t:0,b:0};
if(!s){
return _6;
}
var o=this.opt,_7=0,a,b,c,d,gl=dc.scaler.common.getNumericLabel,_8=0,ma=s.major,mi=s.minor,ta=this.chart.theme.axis,_9=o.font||(ta.majorTick&&ta.majorTick.font)||(ta.tick&&ta.tick.font),_a=this.chart.theme.getTick("major",o),_b=this.chart.theme.getTick("minor",o),_c=_9?g.normalizedLength(g.splitFontString(_9).size):0,_d=o.rotation%360,_e=o.leftBottom,_f=Math.abs(Math.cos(_d*Math.PI/180)),_10=Math.abs(Math.sin(_d*Math.PI/180));
if(_d<0){
_d+=360;
}
if(_c){
if(o.maxLabelSize){
_7=o.maxLabelSize;
}else{
if(this.labels){
_7=this._groupLabelWidth(this.labels,_9);
}else{
_7=this._groupLabelWidth([gl(ma.start,ma.prec,o),gl(ma.start+ma.count*ma.tick,ma.prec,o),gl(mi.start,mi.prec,o),gl(mi.start+mi.count*mi.tick,mi.prec,o)],_9);
}
}
if(this.vertical){
var _11=_e?"l":"r";
switch(_d){
case 0:
case 180:
_6[_11]=_7;
_6.t=_6.b=_c/2;
break;
case 90:
case 270:
_6[_11]=_c;
_6.t=_6.b=_7/2;
break;
default:
if(_d<=_3||(180<_d&&_d<=(180+_3))){
_6[_11]=_c*_10/2+_7*_f;
_6[_e?"t":"b"]=_c*_f/2+_7*_10;
_6[_e?"b":"t"]=_c*_f/2;
}else{
if(_d>(360-_3)||(180>_d&&_d>(180-_3))){
_6[_11]=_c*_10/2+_7*_f;
_6[_e?"b":"t"]=_c*_f/2+_7*_10;
_6[_e?"t":"b"]=_c*_f/2;
}else{
if(_d<90||(180<_d&&_d<270)){
_6[_11]=_c*_10+_7*_f;
_6[_e?"t":"b"]=_c*_f+_7*_10;
}else{
_6[_11]=_c*_10+_7*_f;
_6[_e?"b":"t"]=_c*_f+_7*_10;
}
}
}
break;
}
_6[_11]+=_2+Math.max(_a.length,_b.length);
}else{
var _11=_e?"b":"t";
switch(_d){
case 0:
case 180:
_6[_11]=_c;
_6.l=_6.r=_7/2;
break;
case 90:
case 270:
_6[_11]=_7;
_6.l=_6.r=_c/2;
break;
default:
if((90-_3)<=_d&&_d<=90||(270-_3)<=_d&&_d<=270){
_6[_11]=_c*_10/2+_7*_f;
_6[_e?"r":"l"]=_c*_f/2+_7*_10;
_6[_e?"l":"r"]=_c*_f/2;
}else{
if(90<=_d&&_d<=(90+_3)||270<=_d&&_d<=(270+_3)){
_6[_11]=_c*_10/2+_7*_f;
_6[_e?"l":"r"]=_c*_f/2+_7*_10;
_6[_e?"r":"l"]=_c*_f/2;
}else{
if(_d<_3||(180<_d&&_d<(180-_3))){
_6[_11]=_c*_10+_7*_f;
_6[_e?"r":"l"]=_c*_f+_7*_10;
}else{
_6[_11]=_c*_10+_7*_f;
_6[_e?"l":"r"]=_c*_f+_7*_10;
}
}
}
break;
}
_6[_11]+=_2+Math.max(_a.length,_b.length);
}
}
if(_7){
this._cachedLabelWidth=_7;
}
return _6;
},render:function(dim,_12){
if(!this.dirty){
return this;
}
var o=this.opt,ta=this.chart.theme.axis,_13=o.leftBottom,_14=o.rotation%360,_15,_16,_17,_18,_19,_1a,_1b,_1c=o.font||(ta.majorTick&&ta.majorTick.font)||(ta.tick&&ta.tick.font),_1d=o.fontColor||(ta.majorTick&&ta.majorTick.fontColor)||(ta.tick&&ta.tick.fontColor)||"black",_1e=this.chart.theme.getTick("major",o),_1f=this.chart.theme.getTick("minor",o),_20=this.chart.theme.getTick("micro",o),_21=Math.max(_1e.length,_1f.length,_20.length),_22="stroke" in o?o.stroke:ta.stroke,_23=_1c?g.normalizedLength(g.splitFontString(_1c).size):0;
if(_14<0){
_14+=360;
}
if(this.vertical){
_15={y:dim.height-_12.b};
_16={y:_12.t};
_17={x:0,y:-1};
_1a={x:0,y:0};
_18={x:1,y:0};
_19={x:_2,y:0};
switch(_14){
case 0:
_1b="end";
_1a.y=_23*0.4;
break;
case 90:
_1b="middle";
_1a.x=-_23;
break;
case 180:
_1b="start";
_1a.y=-_23*0.4;
break;
case 270:
_1b="middle";
break;
default:
if(_14<_3){
_1b="end";
_1a.y=_23*0.4;
}else{
if(_14<90){
_1b="end";
_1a.y=_23*0.4;
}else{
if(_14<(180-_3)){
_1b="start";
}else{
if(_14<(180+_3)){
_1b="start";
_1a.y=-_23*0.4;
}else{
if(_14<270){
_1b="start";
_1a.x=_13?0:_23*0.4;
}else{
if(_14<(360-_3)){
_1b="end";
_1a.x=_13?0:_23*0.4;
}else{
_1b="end";
_1a.y=_23*0.4;
}
}
}
}
}
}
}
if(_13){
_15.x=_16.x=_12.l;
_18.x=-1;
_19.x=-_19.x;
}else{
_15.x=_16.x=dim.width-_12.r;
switch(_1b){
case "start":
_1b="end";
break;
case "end":
_1b="start";
break;
case "middle":
_1a.x+=_23;
break;
}
}
}else{
_15={x:_12.l};
_16={x:dim.width-_12.r};
_17={x:1,y:0};
_1a={x:0,y:0};
_18={x:0,y:1};
_19={x:0,y:_2};
switch(_14){
case 0:
_1b="middle";
_1a.y=_23;
break;
case 90:
_1b="start";
_1a.x=-_23*0.4;
break;
case 180:
_1b="middle";
break;
case 270:
_1b="end";
_1a.x=_23*0.4;
break;
default:
if(_14<(90-_3)){
_1b="start";
_1a.y=_13?_23:0;
}else{
if(_14<(90+_3)){
_1b="start";
_1a.x=-_23*0.4;
}else{
if(_14<180){
_1b="start";
_1a.y=_13?0:-_23;
}else{
if(_14<(270-_3)){
_1b="end";
_1a.y=_13?0:-_23;
}else{
if(_14<(270+_3)){
_1b="end";
_1a.y=_13?_23*0.4:0;
}else{
_1b="end";
_1a.y=_13?_23:0;
}
}
}
}
}
}
if(_13){
_15.y=_16.y=dim.height-_12.b;
}else{
_15.y=_16.y=_12.t;
_18.y=-1;
_19.y=-_19.y;
switch(_1b){
case "start":
_1b="end";
break;
case "end":
_1b="start";
break;
case "middle":
_1a.y-=_23;
break;
}
}
}
this.cleanGroup();
try{
var s=this.group,c=this.scaler,t=this.ticks,_24,f=_1.getTransformerFromModel(this.scaler),_25=(dojox.gfx.renderer=="canvas"),_26=_25||!_14&&this.opt.htmlLabels&&!dojo.isIE&&!dojo.isOpera?"html":"gfx",dx=_18.x*_1e.length,dy=_18.y*_1e.length;
s.createLine({x1:_15.x,y1:_15.y,x2:_16.x,y2:_16.y}).setStroke(_22);
dojo.forEach(t.major,function(_27){
var _28=f(_27.value),_29,x=_15.x+_17.x*_28,y=_15.y+_17.y*_28;
s.createLine({x1:x,y1:y,x2:x+dx,y2:y+dy}).setStroke(_1e);
if(_27.label){
_29=dc.axis2d.common.createText[_26](this.chart,s,x+dx+_19.x+(_14?0:_1a.x),y+dy+_19.y+(_14?0:_1a.y),_1b,_27.label,_1c,_1d);
if(_26=="html"){
this.htmlElements.push(_29);
}else{
if(_14){
_29.setTransform([{dx:_1a.x,dy:_1a.y},g.matrix.rotategAt(_14,x+dx+_19.x,y+dy+_19.y)]);
}
}
}
},this);
dx=_18.x*_1f.length;
dy=_18.y*_1f.length;
_24=c.minMinorStep<=c.minor.tick*c.bounds.scale;
dojo.forEach(t.minor,function(_2a){
var _2b=f(_2a.value),_2c,x=_15.x+_17.x*_2b,y=_15.y+_17.y*_2b;
s.createLine({x1:x,y1:y,x2:x+dx,y2:y+dy}).setStroke(_1f);
if(_24&&_2a.label){
_2c=dc.axis2d.common.createText[_26](this.chart,s,x+dx+_19.x+(_14?0:_1a.x),y+dy+_19.y+(_14?0:_1a.y),_1b,_2a.label,_1c,_1d);
if(_26=="html"){
this.htmlElements.push(_2c);
}else{
if(_14){
_2c.setTransform([{dx:_1a.x,dy:_1a.y},g.matrix.rotategAt(_14,x+dx+_19.x,y+dy+_19.y)]);
}
}
}
},this);
dx=_18.x*_20.length;
dy=_18.y*_20.length;
dojo.forEach(t.micro,function(_2d){
var _2e=f(_2d.value),_2f,x=_15.x+_17.x*_2e,y=_15.y+_17.y*_2e;
s.createLine({x1:x,y1:y,x2:x+dx,y2:y+dy}).setStroke(_20);
},this);
}
catch(e){
}
this.dirty=false;
return this;
}});
})();
}
