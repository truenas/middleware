/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.gfx.svg"]){
dojo._hasResource["dojox.gfx.svg"]=true;
dojo.provide("dojox.gfx.svg");
dojo.require("dojox.gfx._base");
dojo.require("dojox.gfx.shape");
dojo.require("dojox.gfx.path");
(function(){
var d=dojo,g=dojox.gfx,gs=g.shape,_1=g.svg;
_1.useSvgWeb=(typeof (window.svgweb)!=="undefined");
var _2=function(ns,_3){
if(dojo.doc.createElementNS){
return dojo.doc.createElementNS(ns,_3);
}else{
return dojo.doc.createElement(_3);
}
};
var _4=function(_5){
if(_1.useSvgWeb){
return dojo.doc.createTextNode(_5,true);
}else{
return dojo.doc.createTextNode(_5);
}
};
var _6=function(){
if(_1.useSvgWeb){
return dojo.doc.createDocumentFragment(true);
}else{
return dojo.doc.createDocumentFragment();
}
};
_1.xmlns={xlink:"http://www.w3.org/1999/xlink",svg:"http://www.w3.org/2000/svg"};
_1.getRef=function(_7){
if(!_7||_7=="none"){
return null;
}
if(_7.match(/^url\(#.+\)$/)){
return d.byId(_7.slice(5,-1));
}
if(_7.match(/^#dojoUnique\d+$/)){
return d.byId(_7.slice(1));
}
return null;
};
_1.dasharray={solid:"none",shortdash:[4,1],shortdot:[1,1],shortdashdot:[4,1,1,1],shortdashdotdot:[4,1,1,1,1,1],dot:[1,3],dash:[4,3],longdash:[8,3],dashdot:[4,3,1,3],longdashdot:[8,3,1,3],longdashdotdot:[8,3,1,3,1,3]};
d.extend(g.Shape,{setFill:function(_8){
if(!_8){
this.fillStyle=null;
this.rawNode.setAttribute("fill","none");
this.rawNode.setAttribute("fill-opacity",0);
return this;
}
var f;
var _9=function(x){
this.setAttribute(x,f[x].toFixed(8));
};
if(typeof (_8)=="object"&&"type" in _8){
switch(_8.type){
case "linear":
f=g.makeParameters(g.defaultLinearGradient,_8);
var _a=this._setFillObject(f,"linearGradient");
d.forEach(["x1","y1","x2","y2"],_9,_a);
break;
case "radial":
f=g.makeParameters(g.defaultRadialGradient,_8);
var _a=this._setFillObject(f,"radialGradient");
d.forEach(["cx","cy","r"],_9,_a);
break;
case "pattern":
f=g.makeParameters(g.defaultPattern,_8);
var _b=this._setFillObject(f,"pattern");
d.forEach(["x","y","width","height"],_9,_b);
break;
}
this.fillStyle=f;
return this;
}
var f=g.normalizeColor(_8);
this.fillStyle=f;
this.rawNode.setAttribute("fill",f.toCss());
this.rawNode.setAttribute("fill-opacity",f.a);
this.rawNode.setAttribute("fill-rule","evenodd");
return this;
},setStroke:function(_c){
var rn=this.rawNode;
if(!_c){
this.strokeStyle=null;
rn.setAttribute("stroke","none");
rn.setAttribute("stroke-opacity",0);
return this;
}
if(typeof _c=="string"||d.isArray(_c)||_c instanceof d.Color){
_c={color:_c};
}
var s=this.strokeStyle=g.makeParameters(g.defaultStroke,_c);
s.color=g.normalizeColor(s.color);
if(s){
rn.setAttribute("stroke",s.color.toCss());
rn.setAttribute("stroke-opacity",s.color.a);
rn.setAttribute("stroke-width",s.width);
rn.setAttribute("stroke-linecap",s.cap);
if(typeof s.join=="number"){
rn.setAttribute("stroke-linejoin","miter");
rn.setAttribute("stroke-miterlimit",s.join);
}else{
rn.setAttribute("stroke-linejoin",s.join);
}
var da=s.style.toLowerCase();
if(da in _1.dasharray){
da=_1.dasharray[da];
}
if(da instanceof Array){
da=d._toArray(da);
for(var i=0;i<da.length;++i){
da[i]*=s.width;
}
if(s.cap!="butt"){
for(var i=0;i<da.length;i+=2){
da[i]-=s.width;
if(da[i]<1){
da[i]=1;
}
}
for(var i=1;i<da.length;i+=2){
da[i]+=s.width;
}
}
da=da.join(",");
}
rn.setAttribute("stroke-dasharray",da);
rn.setAttribute("dojoGfxStrokeStyle",s.style);
}
return this;
},_getParentSurface:function(){
var _d=this.parent;
for(;_d&&!(_d instanceof g.Surface);_d=_d.parent){
}
return _d;
},_setFillObject:function(f,_e){
var _f=_1.xmlns.svg;
this.fillStyle=f;
var _10=this._getParentSurface(),_11=_10.defNode,_12=this.rawNode.getAttribute("fill"),ref=_1.getRef(_12);
if(ref){
_12=ref;
if(_12.tagName.toLowerCase()!=_e.toLowerCase()){
var id=_12.id;
_12.parentNode.removeChild(_12);
_12=_2(_f,_e);
_12.setAttribute("id",id);
_11.appendChild(_12);
}else{
while(_12.childNodes.length){
_12.removeChild(_12.lastChild);
}
}
}else{
_12=_2(_f,_e);
_12.setAttribute("id",g._base._getUniqueId());
_11.appendChild(_12);
}
if(_e=="pattern"){
_12.setAttribute("patternUnits","userSpaceOnUse");
var img=_2(_f,"image");
img.setAttribute("x",0);
img.setAttribute("y",0);
img.setAttribute("width",f.width.toFixed(8));
img.setAttribute("height",f.height.toFixed(8));
img.setAttributeNS(_1.xmlns.xlink,"xlink:href",f.src);
_12.appendChild(img);
}else{
_12.setAttribute("gradientUnits","userSpaceOnUse");
for(var i=0;i<f.colors.length;++i){
var c=f.colors[i],t=_2(_f,"stop"),cc=c.color=g.normalizeColor(c.color);
t.setAttribute("offset",c.offset.toFixed(8));
t.setAttribute("stop-color",cc.toCss());
t.setAttribute("stop-opacity",cc.a);
_12.appendChild(t);
}
}
this.rawNode.setAttribute("fill","url(#"+_12.getAttribute("id")+")");
this.rawNode.removeAttribute("fill-opacity");
this.rawNode.setAttribute("fill-rule","evenodd");
return _12;
},_applyTransform:function(){
var _13=this.matrix;
if(_13){
var tm=this.matrix;
this.rawNode.setAttribute("transform","matrix("+tm.xx.toFixed(8)+","+tm.yx.toFixed(8)+","+tm.xy.toFixed(8)+","+tm.yy.toFixed(8)+","+tm.dx.toFixed(8)+","+tm.dy.toFixed(8)+")");
}else{
this.rawNode.removeAttribute("transform");
}
return this;
},setRawNode:function(_14){
var r=this.rawNode=_14;
if(this.shape.type!="image"){
r.setAttribute("fill","none");
}
r.setAttribute("fill-opacity",0);
r.setAttribute("stroke","none");
r.setAttribute("stroke-opacity",0);
r.setAttribute("stroke-width",1);
r.setAttribute("stroke-linecap","butt");
r.setAttribute("stroke-linejoin","miter");
r.setAttribute("stroke-miterlimit",4);
},setShape:function(_15){
this.shape=g.makeParameters(this.shape,_15);
for(var i in this.shape){
if(i!="type"){
this.rawNode.setAttribute(i,this.shape[i]);
}
}
this.bbox=null;
return this;
},_moveToFront:function(){
this.rawNode.parentNode.appendChild(this.rawNode);
return this;
},_moveToBack:function(){
this.rawNode.parentNode.insertBefore(this.rawNode,this.rawNode.parentNode.firstChild);
return this;
}});
dojo.declare("dojox.gfx.Group",g.Shape,{constructor:function(){
_1.Container._init.call(this);
},setRawNode:function(_16){
this.rawNode=_16;
}});
g.Group.nodeType="g";
dojo.declare("dojox.gfx.Rect",gs.Rect,{setShape:function(_17){
this.shape=g.makeParameters(this.shape,_17);
this.bbox=null;
for(var i in this.shape){
if(i!="type"&&i!="r"){
this.rawNode.setAttribute(i,this.shape[i]);
}
}
if(this.shape.r){
this.rawNode.setAttribute("ry",this.shape.r);
this.rawNode.setAttribute("rx",this.shape.r);
}
return this;
}});
g.Rect.nodeType="rect";
g.Ellipse=gs.Ellipse;
g.Ellipse.nodeType="ellipse";
g.Circle=gs.Circle;
g.Circle.nodeType="circle";
g.Line=gs.Line;
g.Line.nodeType="line";
dojo.declare("dojox.gfx.Polyline",gs.Polyline,{setShape:function(_18,_19){
if(_18&&_18 instanceof Array){
this.shape=g.makeParameters(this.shape,{points:_18});
if(_19&&this.shape.points.length){
this.shape.points.push(this.shape.points[0]);
}
}else{
this.shape=g.makeParameters(this.shape,_18);
}
this.bbox=null;
this._normalizePoints();
var _1a=[],p=this.shape.points;
for(var i=0;i<p.length;++i){
_1a.push(p[i].x.toFixed(8),p[i].y.toFixed(8));
}
this.rawNode.setAttribute("points",_1a.join(" "));
return this;
}});
g.Polyline.nodeType="polyline";
dojo.declare("dojox.gfx.Image",gs.Image,{setShape:function(_1b){
this.shape=g.makeParameters(this.shape,_1b);
this.bbox=null;
var _1c=this.rawNode;
for(var i in this.shape){
if(i!="type"&&i!="src"){
_1c.setAttribute(i,this.shape[i]);
}
}
_1c.setAttribute("preserveAspectRatio","none");
_1c.setAttributeNS(_1.xmlns.xlink,"xlink:href",this.shape.src);
return this;
}});
g.Image.nodeType="image";
dojo.declare("dojox.gfx.Text",gs.Text,{setShape:function(_1d){
this.shape=g.makeParameters(this.shape,_1d);
this.bbox=null;
var r=this.rawNode,s=this.shape;
r.setAttribute("x",s.x);
r.setAttribute("y",s.y);
r.setAttribute("text-anchor",s.align);
r.setAttribute("text-decoration",s.decoration);
r.setAttribute("rotate",s.rotated?90:0);
r.setAttribute("kerning",s.kerning?"auto":0);
r.setAttribute("text-rendering","optimizeLegibility");
if(r.firstChild){
r.firstChild.nodeValue=s.text;
}else{
r.appendChild(_4(s.text));
}
return this;
},getTextWidth:function(){
var _1e=this.rawNode,_1f=_1e.parentNode,_20=_1e.cloneNode(true);
_20.style.visibility="hidden";
var _21=0,_22=_20.firstChild.nodeValue;
_1f.appendChild(_20);
if(_22!=""){
while(!_21){
if(_20.getBBox){
_21=parseInt(_20.getBBox().width);
}else{
_21=68;
}
}
}
_1f.removeChild(_20);
return _21;
}});
g.Text.nodeType="text";
dojo.declare("dojox.gfx.Path",g.path.Path,{_updateWithSegment:function(_23){
g.Path.superclass._updateWithSegment.apply(this,arguments);
if(typeof (this.shape.path)=="string"){
this.rawNode.setAttribute("d",this.shape.path);
}
},setShape:function(_24){
g.Path.superclass.setShape.apply(this,arguments);
this.rawNode.setAttribute("d",this.shape.path);
return this;
}});
g.Path.nodeType="path";
dojo.declare("dojox.gfx.TextPath",g.path.TextPath,{_updateWithSegment:function(_25){
g.Path.superclass._updateWithSegment.apply(this,arguments);
this._setTextPath();
},setShape:function(_26){
g.Path.superclass.setShape.apply(this,arguments);
this._setTextPath();
return this;
},_setTextPath:function(){
if(typeof this.shape.path!="string"){
return;
}
var r=this.rawNode;
if(!r.firstChild){
var tp=_2(_1.xmlns.svg,"textPath"),tx=_4("");
tp.appendChild(tx);
r.appendChild(tp);
}
var ref=r.firstChild.getAttributeNS(_1.xmlns.xlink,"href"),_27=ref&&_1.getRef(ref);
if(!_27){
var _28=this._getParentSurface();
if(_28){
var _29=_28.defNode;
_27=_2(_1.xmlns.svg,"path");
var id=g._base._getUniqueId();
_27.setAttribute("id",id);
_29.appendChild(_27);
r.firstChild.setAttributeNS(_1.xmlns.xlink,"xlink:href","#"+id);
}
}
if(_27){
_27.setAttribute("d",this.shape.path);
}
},_setText:function(){
var r=this.rawNode;
if(!r.firstChild){
var tp=_2(_1.xmlns.svg,"textPath"),tx=_4("");
tp.appendChild(tx);
r.appendChild(tp);
}
r=r.firstChild;
var t=this.text;
r.setAttribute("alignment-baseline","middle");
switch(t.align){
case "middle":
r.setAttribute("text-anchor","middle");
r.setAttribute("startOffset","50%");
break;
case "end":
r.setAttribute("text-anchor","end");
r.setAttribute("startOffset","100%");
break;
default:
r.setAttribute("text-anchor","start");
r.setAttribute("startOffset","0%");
break;
}
r.setAttribute("baseline-shift","0.5ex");
r.setAttribute("text-decoration",t.decoration);
r.setAttribute("rotate",t.rotated?90:0);
r.setAttribute("kerning",t.kerning?"auto":0);
r.firstChild.data=t.text;
}});
g.TextPath.nodeType="text";
dojo.declare("dojox.gfx.Surface",gs.Surface,{constructor:function(){
_1.Container._init.call(this);
},destroy:function(){
this.defNode=null;
this.inherited(arguments);
},setDimensions:function(_2a,_2b){
if(!this.rawNode){
return this;
}
this.rawNode.setAttribute("width",_2a);
this.rawNode.setAttribute("height",_2b);
return this;
},getDimensions:function(){
var t=this.rawNode?{width:g.normalizedLength(this.rawNode.getAttribute("width")),height:g.normalizedLength(this.rawNode.getAttribute("height"))}:null;
return t;
}});
g.createSurface=function(_2c,_2d,_2e){
var s=new g.Surface();
s.rawNode=_2(_1.xmlns.svg,"svg");
if(_2d){
s.rawNode.setAttribute("width",_2d);
}
if(_2e){
s.rawNode.setAttribute("height",_2e);
}
var _2f=_2(_1.xmlns.svg,"defs");
s.rawNode.appendChild(_2f);
s.defNode=_2f;
s._parent=d.byId(_2c);
s._parent.appendChild(s.rawNode);
return s;
};
_1.Font={_setFont:function(){
var f=this.fontStyle;
this.rawNode.setAttribute("font-style",f.style);
this.rawNode.setAttribute("font-variant",f.variant);
this.rawNode.setAttribute("font-weight",f.weight);
this.rawNode.setAttribute("font-size",f.size);
this.rawNode.setAttribute("font-family",f.family);
}};
_1.Container={_init:function(){
gs.Container._init.call(this);
},openBatch:function(){
this.fragment=_6();
},closeBatch:function(){
if(this.fragment){
this.rawNode.appendChild(this.fragment);
delete this.fragment;
}
},add:function(_30){
if(this!=_30.getParent()){
if(this.fragment){
this.fragment.appendChild(_30.rawNode);
}else{
this.rawNode.appendChild(_30.rawNode);
}
gs.Container.add.apply(this,arguments);
}
return this;
},remove:function(_31,_32){
if(this==_31.getParent()){
if(this.rawNode==_31.rawNode.parentNode){
this.rawNode.removeChild(_31.rawNode);
}
if(this.fragment&&this.fragment==_31.rawNode.parentNode){
this.fragment.removeChild(_31.rawNode);
}
gs.Container.remove.apply(this,arguments);
}
return this;
},clear:function(){
var r=this.rawNode;
while(r.lastChild){
r.removeChild(r.lastChild);
}
var _33=this.defNode;
if(_33){
while(_33.lastChild){
_33.removeChild(_33.lastChild);
}
r.appendChild(_33);
}
return gs.Container.clear.apply(this,arguments);
},_moveChildToFront:gs.Container._moveChildToFront,_moveChildToBack:gs.Container._moveChildToBack};
d.mixin(gs.Creator,{createObject:function(_34,_35){
if(!this.rawNode){
return null;
}
var _36=new _34(),_37=_2(_1.xmlns.svg,_34.nodeType);
_36.setRawNode(_37);
_36.setShape(_35);
this.add(_36);
return _36;
}});
d.extend(g.Text,_1.Font);
d.extend(g.TextPath,_1.Font);
d.extend(g.Group,_1.Container);
d.extend(g.Group,gs.Creator);
d.extend(g.Surface,_1.Container);
d.extend(g.Surface,gs.Creator);
if(_1.useSvgWeb){
g.createSurface=function(_38,_39,_3a){
var s=new g.Surface();
if(!_39||!_3a){
var pos=d.position(_38);
_39=_39||pos.w;
_3a=_3a||pos.h;
}
_38=d.byId(_38);
var id=_38.id?_38.id+"_svgweb":g._base._getUniqueId();
var _3b=_2(_1.xmlns.svg,"svg");
_3b.id=id;
_3b.setAttribute("width",_39);
_3b.setAttribute("height",_3a);
svgweb.appendChild(_3b,_38);
_3b.addEventListener("SVGLoad",function(){
s.rawNode=this;
s.isLoaded=true;
var _3c=_2(_1.xmlns.svg,"defs");
s.rawNode.appendChild(_3c);
s.defNode=_3c;
if(s.onLoad){
s.onLoad(s);
}
},false);
s.isLoaded=false;
return s;
};
dojo.extend(dojox.gfx.shape.Surface,{destroy:function(){
var _3d=this.rawNode;
svgweb.removeChild(_3d,_3d.parentNode);
}});
gs._eventsProcessing.connect=function(_3e,_3f,_40){
if(_3e.substring(0,2)==="on"){
_3e=_3e.substring(2);
}
if(arguments.length==2){
_40=_3f;
}else{
_40=d.hitch(_3f,_40);
}
this.getEventSource().addEventListener(_3e,_40,false);
return [this,_3e,_40];
};
gs._eventsProcessing.disconnect=function(_41){
this.getEventSource().removeEventListener(_41[1],_41[2],false);
delete _41[0];
};
dojo.extend(dojox.gfx.Shape,dojox.gfx.shape._eventsProcessing);
dojo.extend(dojox.gfx.shape.Surface,dojox.gfx.shape._eventsProcessing);
}
})();
}
