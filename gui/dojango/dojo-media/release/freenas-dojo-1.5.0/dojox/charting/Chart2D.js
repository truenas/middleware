/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.charting.Chart2D"]){
dojo._hasResource["dojox.charting.Chart2D"]=true;
dojo.provide("dojox.charting.Chart2D");
dojo.require("dojox.gfx");
dojo.require("dojox.lang.functional");
dojo.require("dojox.lang.functional.fold");
dojo.require("dojox.lang.functional.reversed");
dojo.require("dojox.charting.Theme");
dojo.require("dojox.charting.Series");
dojo.require("dojox.charting.axis2d.Default");
dojo.require("dojox.charting.axis2d.Invisible");
dojo.require("dojox.charting.plot2d.Default");
dojo.require("dojox.charting.plot2d.Lines");
dojo.require("dojox.charting.plot2d.Areas");
dojo.require("dojox.charting.plot2d.Markers");
dojo.require("dojox.charting.plot2d.MarkersOnly");
dojo.require("dojox.charting.plot2d.Scatter");
dojo.require("dojox.charting.plot2d.Stacked");
dojo.require("dojox.charting.plot2d.StackedLines");
dojo.require("dojox.charting.plot2d.StackedAreas");
dojo.require("dojox.charting.plot2d.Columns");
dojo.require("dojox.charting.plot2d.StackedColumns");
dojo.require("dojox.charting.plot2d.ClusteredColumns");
dojo.require("dojox.charting.plot2d.Bars");
dojo.require("dojox.charting.plot2d.StackedBars");
dojo.require("dojox.charting.plot2d.ClusteredBars");
dojo.require("dojox.charting.plot2d.Grid");
dojo.require("dojox.charting.plot2d.Pie");
dojo.require("dojox.charting.plot2d.Bubble");
dojo.require("dojox.charting.plot2d.Candlesticks");
dojo.require("dojox.charting.plot2d.OHLC");
(function(){
var df=dojox.lang.functional,dc=dojox.charting,_1=df.lambda("item.clear()"),_2=df.lambda("item.purgeGroup()"),_3=df.lambda("item.destroy()"),_4=df.lambda("item.dirty = false"),_5=df.lambda("item.dirty = true"),_6=df.lambda("item.name");
dojo.declare("dojox.charting.Chart2D",null,{constructor:function(_7,_8){
if(!_8){
_8={};
}
this.margins=_8.margins?_8.margins:{l:10,t:10,r:10,b:10};
this.stroke=_8.stroke;
this.fill=_8.fill;
this.delayInMs=_8.delayInMs||200;
this.theme=null;
this.axes={};
this.stack=[];
this.plots={};
this.series=[];
this.runs={};
this.dirty=true;
this.coords=null;
this.node=dojo.byId(_7);
var _9=dojo.marginBox(_7);
this.surface=dojox.gfx.createSurface(this.node,_9.w||400,_9.h||300);
},destroy:function(){
dojo.forEach(this.series,_3);
dojo.forEach(this.stack,_3);
df.forIn(this.axes,_3);
this.surface.destroy();
},getCoords:function(){
if(!this.coords){
this.coords=dojo.coords(this.node,true);
}
return this.coords;
},setTheme:function(_a){
this.theme=_a.clone();
this.dirty=true;
return this;
},addAxis:function(_b,_c){
var _d;
if(!_c||!("type" in _c)){
_d=new dc.axis2d.Default(this,_c);
}else{
_d=typeof _c.type=="string"?new dc.axis2d[_c.type](this,_c):new _c.type(this,_c);
}
_d.name=_b;
_d.dirty=true;
if(_b in this.axes){
this.axes[_b].destroy();
}
this.axes[_b]=_d;
this.dirty=true;
return this;
},getAxis:function(_e){
return this.axes[_e];
},removeAxis:function(_f){
if(_f in this.axes){
this.axes[_f].destroy();
delete this.axes[_f];
this.dirty=true;
}
return this;
},addPlot:function(_10,_11){
var _12;
if(!_11||!("type" in _11)){
_12=new dc.plot2d.Default(this,_11);
}else{
_12=typeof _11.type=="string"?new dc.plot2d[_11.type](this,_11):new _11.type(this,_11);
}
_12.name=_10;
_12.dirty=true;
if(_10 in this.plots){
this.stack[this.plots[_10]].destroy();
this.stack[this.plots[_10]]=_12;
}else{
this.plots[_10]=this.stack.length;
this.stack.push(_12);
}
this.dirty=true;
return this;
},removePlot:function(_13){
if(_13 in this.plots){
var _14=this.plots[_13];
delete this.plots[_13];
this.stack[_14].destroy();
this.stack.splice(_14,1);
df.forIn(this.plots,function(idx,_15,_16){
if(idx>_14){
_16[_15]=idx-1;
}
});
this.dirty=true;
}
return this;
},getPlotOrder:function(){
return df.map(this.stack,_6);
},setPlotOrder:function(_17){
var _18={},_19=df.filter(_17,function(_1a){
if(!(_1a in this.plots)||(_1a in _18)){
return false;
}
_18[_1a]=1;
return true;
},this);
if(_19.length<this.stack.length){
df.forEach(this.stack,function(_1b){
var _1c=_1b.name;
if(!(_1c in _18)){
_19.push(_1c);
}
});
}
var _1d=df.map(_19,function(_1e){
return this.stack[this.plots[_1e]];
},this);
df.forEach(_1d,function(_1f,i){
this.plots[_1f.name]=i;
},this);
this.stack=_1d;
this.dirty=true;
return this;
},movePlotToFront:function(_20){
if(_20 in this.plots){
var _21=this.plots[_20];
if(_21){
var _22=this.getPlotOrder();
_22.splice(_21,1);
_22.unshift(_20);
return this.setPlotOrder(_22);
}
}
return this;
},movePlotToBack:function(_23){
if(_23 in this.plots){
var _24=this.plots[_23];
if(_24<this.stack.length-1){
var _25=this.getPlotOrder();
_25.splice(_24,1);
_25.push(_23);
return this.setPlotOrder(_25);
}
}
return this;
},addSeries:function(_26,_27,_28){
var run=new dc.Series(this,_27,_28);
run.name=_26;
if(_26 in this.runs){
this.series[this.runs[_26]].destroy();
this.series[this.runs[_26]]=run;
}else{
this.runs[_26]=this.series.length;
this.series.push(run);
}
this.dirty=true;
if(!("ymin" in run)&&"min" in run){
run.ymin=run.min;
}
if(!("ymax" in run)&&"max" in run){
run.ymax=run.max;
}
return this;
},removeSeries:function(_29){
if(_29 in this.runs){
var _2a=this.runs[_29],_2b=this.series[_2a].plot;
delete this.runs[_29];
this.series[_2a].destroy();
this.series.splice(_2a,1);
df.forIn(this.runs,function(idx,_2c,_2d){
if(idx>_2a){
_2d[_2c]=idx-1;
}
});
this.dirty=true;
}
return this;
},updateSeries:function(_2e,_2f){
if(_2e in this.runs){
var run=this.series[this.runs[_2e]];
run.update(_2f);
this._invalidateDependentPlots(run.plot,false);
this._invalidateDependentPlots(run.plot,true);
}
return this;
},getSeriesOrder:function(_30){
return df.map(df.filter(this.series,function(run){
return run.plot==_30;
}),_6);
},setSeriesOrder:function(_31){
var _32,_33={},_34=df.filter(_31,function(_35){
if(!(_35 in this.runs)||(_35 in _33)){
return false;
}
var run=this.series[this.runs[_35]];
if(_32){
if(run.plot!=_32){
return false;
}
}else{
_32=run.plot;
}
_33[_35]=1;
return true;
},this);
df.forEach(this.series,function(run){
var _36=run.name;
if(!(_36 in _33)&&run.plot==_32){
_34.push(_36);
}
});
var _37=df.map(_34,function(_38){
return this.series[this.runs[_38]];
},this);
this.series=_37.concat(df.filter(this.series,function(run){
return run.plot!=_32;
}));
df.forEach(this.series,function(run,i){
this.runs[run.name]=i;
},this);
this.dirty=true;
return this;
},moveSeriesToFront:function(_39){
if(_39 in this.runs){
var _3a=this.runs[_39],_3b=this.getSeriesOrder(this.series[_3a].plot);
if(_39!=_3b[0]){
_3b.splice(_3a,1);
_3b.unshift(_39);
return this.setSeriesOrder(_3b);
}
}
return this;
},moveSeriesToBack:function(_3c){
if(_3c in this.runs){
var _3d=this.runs[_3c],_3e=this.getSeriesOrder(this.series[_3d].plot);
if(_3c!=_3e[_3e.length-1]){
_3e.splice(_3d,1);
_3e.push(_3c);
return this.setSeriesOrder(_3e);
}
}
return this;
},resize:function(_3f,_40){
var box;
switch(arguments.length){
case 0:
box=dojo.marginBox(this.node);
break;
case 1:
box=_3f;
break;
default:
box={w:_3f,h:_40};
break;
}
dojo.marginBox(this.node,box);
this.surface.setDimensions(box.w,box.h);
this.dirty=true;
this.coords=null;
return this.render();
},getGeometry:function(){
var ret={};
df.forIn(this.axes,function(_41){
if(_41.initialized()){
ret[_41.name]={name:_41.name,vertical:_41.vertical,scaler:_41.scaler,ticks:_41.ticks};
}
});
return ret;
},setAxisWindow:function(_42,_43,_44,_45){
var _46=this.axes[_42];
if(_46){
_46.setWindow(_43,_44);
dojo.forEach(this.stack,function(_47){
if(_47.hAxis==_42||_47.vAxis==_42){
_47.zoom=_45;
}
});
}
return this;
},setWindow:function(sx,sy,dx,dy,_48){
if(!("plotArea" in this)){
this.calculateGeometry();
}
df.forIn(this.axes,function(_49){
var _4a,_4b,_4c=_49.getScaler().bounds,s=_4c.span/(_4c.upper-_4c.lower);
if(_49.vertical){
_4a=sy;
_4b=dy/s/_4a;
}else{
_4a=sx;
_4b=dx/s/_4a;
}
_49.setWindow(_4a,_4b);
});
dojo.forEach(this.stack,function(_4d){
_4d.zoom=_48;
});
return this;
},zoomIn:function(_4e,_4f){
var _50=this.axes[_4e];
if(_50){
var _51,_52,_53=_50.getScaler().bounds;
var _54=Math.min(_4f[0],_4f[1]);
var _55=Math.max(_4f[0],_4f[1]);
_54=_4f[0]<_53.lower?_53.lower:_54;
_55=_4f[1]>_53.upper?_53.upper:_55;
_51=(_53.upper-_53.lower)/(_55-_54);
_52=_54-_53.lower;
this.setAxisWindow(_4e,_51,_52);
this.render();
}
},calculateGeometry:function(){
if(this.dirty){
return this.fullGeometry();
}
var _56=dojo.filter(this.stack,function(_57){
return _57.dirty||(_57.hAxis&&this.axes[_57.hAxis].dirty)||(_57.vAxis&&this.axes[_57.vAxis].dirty);
},this);
_58(_56,this.plotArea);
return this;
},fullGeometry:function(){
this._makeDirty();
dojo.forEach(this.stack,_1);
if(!this.theme){
this.setTheme(new dojox.charting.Theme(dojox.charting._def));
}
dojo.forEach(this.series,function(run){
if(!(run.plot in this.plots)){
var _59=new dc.plot2d.Default(this,{});
_59.name=run.plot;
this.plots[run.plot]=this.stack.length;
this.stack.push(_59);
}
this.stack[this.plots[run.plot]].addSeries(run);
},this);
dojo.forEach(this.stack,function(_5a){
if(_5a.hAxis){
_5a.setAxis(this.axes[_5a.hAxis]);
}
if(_5a.vAxis){
_5a.setAxis(this.axes[_5a.vAxis]);
}
},this);
var dim=this.dim=this.surface.getDimensions();
dim.width=dojox.gfx.normalizedLength(dim.width);
dim.height=dojox.gfx.normalizedLength(dim.height);
df.forIn(this.axes,_1);
_58(this.stack,dim);
var _5b=this.offsets={l:0,r:0,t:0,b:0};
df.forIn(this.axes,function(_5c){
df.forIn(_5c.getOffsets(),function(o,i){
_5b[i]+=o;
});
});
df.forIn(this.margins,function(o,i){
_5b[i]+=o;
});
this.plotArea={width:dim.width-_5b.l-_5b.r,height:dim.height-_5b.t-_5b.b};
df.forIn(this.axes,_1);
_58(this.stack,this.plotArea);
return this;
},render:function(){
if(this.theme){
this.theme.clear();
}
if(this.dirty){
return this.fullRender();
}
this.calculateGeometry();
df.forEachRev(this.stack,function(_5d){
_5d.render(this.dim,this.offsets);
},this);
df.forIn(this.axes,function(_5e){
_5e.render(this.dim,this.offsets);
},this);
this._makeClean();
if(this.surface.render){
this.surface.render();
}
return this;
},fullRender:function(){
this.fullGeometry();
var _5f=this.offsets,dim=this.dim;
dojo.forEach(this.series,_2);
df.forIn(this.axes,_2);
dojo.forEach(this.stack,_2);
this.surface.clear();
var t=this.theme,_60=t.plotarea&&t.plotarea.fill,_61=t.plotarea&&t.plotarea.stroke;
if(_60){
this.surface.createRect({x:_5f.l-1,y:_5f.t-1,width:dim.width-_5f.l-_5f.r+2,height:dim.height-_5f.t-_5f.b+2}).setFill(_60);
}
if(_61){
this.surface.createRect({x:_5f.l,y:_5f.t,width:dim.width-_5f.l-_5f.r+1,height:dim.height-_5f.t-_5f.b+1}).setStroke(_61);
}
df.foldr(this.stack,function(z,_62){
return _62.render(dim,_5f),0;
},0);
_60=this.fill!==undefined?this.fill:(t.chart&&t.chart.fill);
_61=this.stroke!==undefined?this.stroke:(t.chart&&t.chart.stroke);
if(_60=="inherit"){
var _63=this.node,_60=new dojo.Color(dojo.style(_63,"backgroundColor"));
while(_60.a==0&&_63!=document.documentElement){
_60=new dojo.Color(dojo.style(_63,"backgroundColor"));
_63=_63.parentNode;
}
}
if(_60){
if(_5f.l){
this.surface.createRect({width:_5f.l,height:dim.height+1}).setFill(_60);
}
if(_5f.r){
this.surface.createRect({x:dim.width-_5f.r,width:_5f.r+1,height:dim.height+2}).setFill(_60);
}
if(_5f.t){
this.surface.createRect({width:dim.width+1,height:_5f.t}).setFill(_60);
}
if(_5f.b){
this.surface.createRect({y:dim.height-_5f.b,width:dim.width+1,height:_5f.b+2}).setFill(_60);
}
}
if(_61){
this.surface.createRect({width:dim.width-1,height:dim.height-1}).setStroke(_61);
}
df.forIn(this.axes,function(_64){
_64.render(dim,_5f);
});
this._makeClean();
if(this.surface.render){
this.surface.render();
}
return this;
},delayedRender:function(){
if(!this._delayedRenderHandle){
this._delayedRenderHandle=setTimeout(dojo.hitch(this,function(){
clearTimeout(this._delayedRenderHandle);
this._delayedRenderHandle=null;
this.render();
}),this.delayInMs);
}
return this;
},connectToPlot:function(_65,_66,_67){
return _65 in this.plots?this.stack[this.plots[_65]].connect(_66,_67):null;
},fireEvent:function(_68,_69,_6a){
if(_68 in this.runs){
var _6b=this.series[this.runs[_68]].plot;
if(_6b in this.plots){
var _6c=this.stack[this.plots[_6b]];
if(_6c){
_6c.fireEvent(_68,_69,_6a);
}
}
}
return this;
},_makeClean:function(){
dojo.forEach(this.axes,_4);
dojo.forEach(this.stack,_4);
dojo.forEach(this.series,_4);
this.dirty=false;
},_makeDirty:function(){
dojo.forEach(this.axes,_5);
dojo.forEach(this.stack,_5);
dojo.forEach(this.series,_5);
this.dirty=true;
},_invalidateDependentPlots:function(_6d,_6e){
if(_6d in this.plots){
var _6f=this.stack[this.plots[_6d]],_70,_71=_6e?"vAxis":"hAxis";
if(_6f[_71]){
_70=this.axes[_6f[_71]];
if(_70&&_70.dependOnData()){
_70.dirty=true;
dojo.forEach(this.stack,function(p){
if(p[_71]&&p[_71]==_6f[_71]){
p.dirty=true;
}
});
}
}else{
_6f.dirty=true;
}
}
}});
function _72(_73){
return {min:_73.hmin,max:_73.hmax};
};
function _74(_75){
return {min:_75.vmin,max:_75.vmax};
};
function _76(_77,h){
_77.hmin=h.min;
_77.hmax=h.max;
};
function _78(_79,v){
_79.vmin=v.min;
_79.vmax=v.max;
};
function _7a(_7b,_7c){
if(_7b&&_7c){
_7b.min=Math.min(_7b.min,_7c.min);
_7b.max=Math.max(_7b.max,_7c.max);
}
return _7b||_7c;
};
function _58(_7d,_7e){
var _7f={},_80={};
dojo.forEach(_7d,function(_81){
var _82=_7f[_81.name]=_81.getSeriesStats();
if(_81.hAxis){
_80[_81.hAxis]=_7a(_80[_81.hAxis],_72(_82));
}
if(_81.vAxis){
_80[_81.vAxis]=_7a(_80[_81.vAxis],_74(_82));
}
});
dojo.forEach(_7d,function(_83){
var _84=_7f[_83.name];
if(_83.hAxis){
_76(_84,_80[_83.hAxis]);
}
if(_83.vAxis){
_78(_84,_80[_83.vAxis]);
}
_83.initializeScalers(_7e,_84);
});
};
})();
}
