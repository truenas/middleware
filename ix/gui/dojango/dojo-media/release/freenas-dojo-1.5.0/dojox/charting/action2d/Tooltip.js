/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.charting.action2d.Tooltip"]){
dojo._hasResource["dojox.charting.action2d.Tooltip"]=true;
dojo.provide("dojox.charting.action2d.Tooltip");
dojo.require("dojox.charting.action2d.Base");
dojo.require("dojox.gfx.matrix");
dojo.require("dijit.Tooltip");
dojo.require("dojox.lang.functional");
dojo.require("dojox.lang.functional.scan");
dojo.require("dojox.lang.functional.fold");
(function(){
var _1=function(o){
var t=o.run&&o.run.data&&o.run.data[o.index];
if(t&&typeof t!="number"&&(t.tooltip||t.text)){
return t.tooltip||t.text;
}
if(o.element=="candlestick"){
return "<table cellpadding=\"1\" cellspacing=\"0\" border=\"0\" style=\"font-size:0.9em;\">"+"<tr><td>Open:</td><td align=\"right\"><strong>"+o.data.open+"</strong></td></tr>"+"<tr><td>High:</td><td align=\"right\"><strong>"+o.data.high+"</strong></td></tr>"+"<tr><td>Low:</td><td align=\"right\"><strong>"+o.data.low+"</strong></td></tr>"+"<tr><td>Close:</td><td align=\"right\"><strong>"+o.data.close+"</strong></td></tr>"+(o.data.mid!==undefined?"<tr><td>Mid:</td><td align=\"right\"><strong>"+o.data.mid+"</strong></td></tr>":"")+"</table>";
}
return o.element=="bar"?o.x:o.y;
};
var df=dojox.lang.functional,m=dojox.gfx.matrix,_2=Math.PI/4,_3=Math.PI/2;
dojo.declare("dojox.charting.action2d.Tooltip",dojox.charting.action2d.Base,{defaultParams:{text:_1},optionalParams:{},constructor:function(_4,_5,_6){
this.text=_6&&_6.text?_6.text:_1;
this.connect();
},process:function(o){
if(o.type==="onplotreset"||o.type==="onmouseout"){
_7(this.aroundRect);
this.aroundRect=null;
return;
}
if(!o.shape||o.type!=="onmouseover"){
return;
}
var _8={type:"rect"},_9=["after","before"];
switch(o.element){
case "marker":
_8.x=o.cx;
_8.y=o.cy;
_8.width=_8.height=1;
break;
case "circle":
_8.x=o.cx-o.cr;
_8.y=o.cy-o.cr;
_8.width=_8.height=2*o.cr;
break;
case "column":
_9=["above","below"];
case "bar":
_8=dojo.clone(o.shape.getShape());
break;
case "candlestick":
_8.x=o.x;
_8.y=o.y;
_8.width=o.width;
_8.height=o.height;
break;
default:
if(!this.angles){
if(typeof o.run.data[0]=="number"){
this.angles=df.map(df.scanl(o.run.data,"+",0),"* 2 * Math.PI / this",df.foldl(o.run.data,"+",0));
}else{
this.angles=df.map(df.scanl(o.run.data,"a + b.y",0),"* 2 * Math.PI / this",df.foldl(o.run.data,"a + b.y",0));
}
}
var _a=m._degToRad(o.plot.opt.startAngle),_b=(this.angles[o.index]+this.angles[o.index+1])/2+_a;
_8.x=o.cx+o.cr*Math.cos(_b);
_8.y=o.cy+o.cr*Math.sin(_b);
_8.width=_8.height=1;
if(_b<_2){
}else{
if(_b<_3+_2){
_9=["below","above"];
}else{
if(_b<Math.PI+_2){
_9=["before","after"];
}else{
if(_b<2*Math.PI-_2){
_9=["above","below"];
}
}
}
}
break;
}
var lt=dojo.coords(this.chart.node,true);
_8.x+=lt.x;
_8.y+=lt.y;
_8.x=Math.round(_8.x);
_8.y=Math.round(_8.y);
_8.width=Math.ceil(_8.width);
_8.height=Math.ceil(_8.height);
this.aroundRect=_8;
_c(this.text(o),this.aroundRect,_9,"center");
}});
var _d=dojo.declare(dijit._MasterTooltip,{show:function(_e,_f,_10,_11){
if(this.aroundNode&&this.aroundNode===_f){
return;
}
if(this.fadeOut.status()=="playing"){
this._onDeck=arguments;
return;
}
this.containerNode.innerHTML=_e;
this.domNode.style.top=(this.domNode.offsetTop+1)+"px";
if(!this.connectorNode){
this.connectorNode=dojo.query(".dijitTooltipConnector",this.domNode)[0];
}
var _12=dojo.coords(this.connectorNode);
this.arrowWidth=_12.w,this.arrowHeight=_12.h;
this.place=(_11&&_11=="center")?this.placeChartingTooltip:dijit.placeOnScreenAroundElement,this.place(this.domNode,_f,dijit.getPopupAroundAlignment((_10&&_10.length)?_10:dijit.Tooltip.defaultPosition,this.isLeftToRight()),dojo.hitch(this,"orient"));
dojo.style(this.domNode,"opacity",0);
this.fadeIn.play();
this.isShowingNow=true;
this.aroundNode=_f;
},placeChartingTooltip:function(_13,_14,_15,_16){
return this._placeOnScreenAroundRect(_13,_14.x,_14.y,_14.width,_14.height,_15,_16);
},_placeOnScreenAroundRect:function(_17,x,y,_18,_19,_1a,_1b){
var _1c=[];
for(var _1d in _1a){
_1c.push({aroundCorner:_1d,corner:_1a[_1d],pos:{x:x+(_1d.charAt(1)=="L"?0:_18),y:y+(_1d.charAt(0)=="T"?0:_19),w:_18,h:_19}});
}
return this._place(_17,_1c,_1b);
},_place:function(_1e,_1f,_20){
var _21=dijit.getViewport();
if(!_1e.parentNode||String(_1e.parentNode.tagName).toLowerCase()!="body"){
dojo.body().appendChild(_1e);
}
var _22=null;
var _23=null,_24=null;
dojo.some(_1f,function(_25){
var _26=_25.corner;
var _27=_25.aroundCorner;
var pos=_25.pos;
if(_20){
_20(_1e,_25.aroundCorner,_26);
}
var _28=_1e.style;
var _29=_28.display;
var _2a=_28.visibility;
_28.visibility="hidden";
_28.display="";
var mb=dojo.marginBox(_1e);
_28.display=_29;
_28.visibility=_2a;
var _2b,_2c,_2d,_2e,_2f,_30,_31;
_23=null,_24=null;
if(_27.charAt(0)==_26.charAt(0)){
_2b=(_26.charAt(1)=="L"?pos.x:Math.max(_21.l,pos.x-mb.w)),_2c=(_26.charAt(0)=="T"?(pos.y+pos.h/2-mb.h/2):(pos.y-pos.h/2-mb.h/2)),_2d=(_26.charAt(1)=="L"?Math.min(_21.l+_21.w,_2b+mb.w):pos.x),_2e=_2c+mb.h,_2f=_2d-_2b,_30=_2e-_2c,_31=(mb.w-_2f)+(mb.h-_30);
_24=(mb.h-this.arrowHeight)/2;
}else{
_2b=(_26.charAt(1)=="L"?(pos.x+pos.w/2-mb.w/2):(pos.x-pos.w/2-mb.w/2)),_2c=(_26.charAt(0)=="T"?pos.y:Math.max(_21.t,pos.y-mb.h)),_2d=_2b+mb.w,_2e=(_26.charAt(0)=="T"?Math.min(_21.t+_21.h,_2c+mb.h):pos.y),_2f=_2d-_2b,_30=_2e-_2c,_31=(mb.w-_2f)+(mb.h-_30);
_23=(mb.w-this.arrowWidth)/2;
}
if(_22==null||_31<_22.overflow){
_22={corner:_26,aroundCorner:_25.aroundCorner,x:_2b,y:_2c,w:_2f,h:_30,overflow:_31};
}
return !_31;
},this);
_1e.style.left=_22.x+"px";
_1e.style.top=_22.y+"px";
this.connectorNode.style.top="";
this.connectorNode.style.left="";
if(_24){
this.connectorNode.style.top=_24+"px";
}
if(_23){
this.connectorNode.style.left=_23+"px";
}
if(_22.overflow&&_20){
_20(_1e,_22.aroundCorner,_22.corner);
}
return _22;
}});
var _32=null;
function _c(_33,_34,_35,_36){
if(!_32){
_32=new _d();
}
return _32.show(_33,_34,_35,_36);
};
function _7(_37){
if(!_32){
_32=new _d();
}
return _32.hide(_37);
};
})();
}
