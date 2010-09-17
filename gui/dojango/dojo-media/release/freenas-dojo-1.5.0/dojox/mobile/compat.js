/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.mobile.compat"]){
dojo._hasResource["dojox.mobile.compat"]=true;
dojo.provide("dojox.mobile.compat");
dojo.require("dojo._base.fx");
dojo.require("dojo.fx");
dojo.require("dojox.fx.flip");
dojo.extend(dojox.mobile.View,{_doTransition:function(_1,_2,_3,_4){
var _5;
this.wakeUp(_2);
if(!_3||_3=="none"){
_2.style.display="";
_1.style.display="none";
_2.style.left="0px";
this.invokeCallback();
}else{
if(_3=="slide"){
var w=_1.offsetWidth;
var s1=dojo.fx.slideTo({node:_1,duration:400,left:-w*_4,top:_1.offsetTop});
var s2=dojo.fx.slideTo({node:_2,duration:400,left:0});
_2.style.position="absolute";
_2.style.left=w*_4+"px";
_2.style.display="";
_5=dojo.fx.combine([s1,s2]);
dojo.connect(_5,"onEnd",this,function(){
_1.style.display="none";
_2.style.position="relative";
this.invokeCallback();
});
_5.play();
}else{
if(_3=="flip"){
_5=dojox.fx.flip({node:_1,dir:"right",depth:0.5,duration:400});
_2.style.position="absolute";
_2.style.left="0px";
dojo.connect(_5,"onEnd",this,function(){
_1.style.display="none";
_2.style.position="relative";
_2.style.display="";
this.invokeCallback();
});
_5.play();
}else{
if(_3=="fade"){
_5=dojo.fx.chain([dojo.fadeOut({node:_1,duration:600}),dojo.fadeIn({node:_2,duration:600})]);
_2.style.position="absolute";
_2.style.left="0px";
_2.style.display="";
dojo.style(_2,"opacity",0);
dojo.connect(_5,"onEnd",this,function(){
_1.style.display="none";
_2.style.position="relative";
dojo.style(_1,"opacity",1);
this.invokeCallback();
});
_5.play();
}
}
}
}
},wakeUp:function(_6){
if(dojo.isIE&&!_6._wokeup){
_6._wokeup=true;
var _7=_6.style.display;
_6.style.display="";
var _8=_6.getElementsByTagName("*");
for(var i=0,_9=_8.length;i<_9;i++){
var _a=_8[i].style.display;
_8[i].style.display="none";
_8[i].style.display="";
_8[i].style.display=_a;
}
_6.style.display=_7;
}
}});
dojo.extend(dojox.mobile.Switch,{buildRendering:function(){
this.domNode=this.srcNodeRef||dojo.doc.createElement("DIV");
this.domNode.className="mblSwitch";
this.domNode.innerHTML="<div class=\"mblSwitchInner\">"+"<div class=\"mblSwitchBg mblSwitchBgLeft\">"+"<div class=\"mblSwitchCorner mblSwitchCorner1T\"></div>"+"<div class=\"mblSwitchCorner mblSwitchCorner2T\"></div>"+"<div class=\"mblSwitchCorner mblSwitchCorner3T\"></div>"+"<div class=\"mblSwitchText mblSwitchTextLeft\">"+this.leftLabel+"</div>"+"<div class=\"mblSwitchCorner mblSwitchCorner1B\"></div>"+"<div class=\"mblSwitchCorner mblSwitchCorner2B\"></div>"+"<div class=\"mblSwitchCorner mblSwitchCorner3B\"></div>"+"</div>"+"<div class=\"mblSwitchBg mblSwitchBgRight\">"+"<div class=\"mblSwitchCorner mblSwitchCorner1T\"></div>"+"<div class=\"mblSwitchCorner mblSwitchCorner2T\"></div>"+"<div class=\"mblSwitchCorner mblSwitchCorner3T\"></div>"+"<div class=\"mblSwitchText mblSwitchTextRight\">"+this.rightLabel+"</div>"+"<div class=\"mblSwitchCorner mblSwitchCorner1B\"></div>"+"<div class=\"mblSwitchCorner mblSwitchCorner2B\"></div>"+"<div class=\"mblSwitchCorner mblSwitchCorner3B\"></div>"+"</div>"+"<div class=\"mblSwitchKnobContainer\">"+"<div class=\"mblSwitchCorner mblSwitchCorner1T\"></div>"+"<div class=\"mblSwitchCorner mblSwitchCorner2T\"></div>"+"<div class=\"mblSwitchCorner mblSwitchCorner3T\"></div>"+"<div class=\"mblSwitchKnob\"></div>"+"<div class=\"mblSwitchCorner mblSwitchCorner1B\"></div>"+"<div class=\"mblSwitchCorner mblSwitchCorner2B\"></div>"+"<div class=\"mblSwitchCorner mblSwitchCorner3B\"></div>"+"</div>"+"</div>";
var n=this.inner=this.domNode.firstChild;
this.left=n.childNodes[0];
this.right=n.childNodes[1];
this.knob=n.childNodes[2];
dojo.addClass(this.domNode,(this.value=="on")?"mblSwitchOn":"mblSwitchOff");
this[this.value=="off"?"left":"right"].style.display="none";
},_changeState:function(_b){
if(!this.inner.parentNode||!this.inner.parentNode.tagName){
dojo.addClass(this.domNode,(_b=="on")?"mblSwitchOn":"mblSwitchOff");
return;
}
var _c;
if(this.inner.offsetLeft==0){
if(_b=="on"){
return;
}
_c=-53;
}else{
if(_b=="off"){
return;
}
_c=0;
}
var a=dojo.fx.slideTo({node:this.inner,duration:500,left:_c});
var _d=this;
dojo.connect(a,"onEnd",function(){
_d[_b=="off"?"left":"right"].style.display="none";
});
a.play();
}});
if(dojo.isIE){
dojo.extend(dojox.mobile.RoundRect,{buildRendering:function(){
dojox.mobile.createRoundRect(this);
this.domNode.className="mblRoundRect";
}});
dojox.mobile.RoundRectList._addChild=dojox.mobile.RoundRectList.prototype.addChild;
dojo.extend(dojox.mobile.RoundRectList,{buildRendering:function(){
dojox.mobile.createRoundRect(this,true);
this.domNode.className="mblRoundRectList";
},postCreate:function(){
this.redrawBorders();
},addChild:function(_e){
dojox.mobile.RoundRectList._addChild.apply(this,arguments);
this.redrawBorders();
if(dojox.mobile.applyPngFilter){
dojox.mobile.applyPngFilter(_e.domNode);
}
},redrawBorders:function(){
var _f=false;
for(var i=this.containerNode.childNodes.length-1;i>=0;i--){
var c=this.containerNode.childNodes[i];
if(c.tagName=="LI"){
c.style.borderBottomStyle=_f?"solid":"none";
_f=true;
}
}
}});
dojo.extend(dojox.mobile.EdgeToEdgeList,{buildRendering:function(){
this.domNode=this.containerNode=this.srcNodeRef||dojo.doc.createElement("UL");
this.domNode.className="mblEdgeToEdgeList";
}});
dojox.mobile.IconContainer._addChild=dojox.mobile.IconContainer.prototype.addChild;
dojo.extend(dojox.mobile.IconContainer,{addChild:function(_10){
dojox.mobile.IconContainer._addChild.apply(this,arguments);
if(dojox.mobile.applyPngFilter){
dojox.mobile.applyPngFilter(_10.domNode);
}
}});
dojo.mixin(dojox.mobile,{createRoundRect:function(_11,_12){
var i;
_11.domNode=dojo.doc.createElement("DIV");
_11.domNode.style.padding="0px";
_11.domNode.style.backgroundColor="transparent";
_11.domNode.style.borderStyle="none";
_11.containerNode=dojo.doc.createElement(_12?"UL":"DIV");
_11.containerNode.className="mblRoundRectContainer";
if(_11.srcNodeRef){
_11.srcNodeRef.parentNode.replaceChild(_11.domNode,_11.srcNodeRef);
for(i=0,len=_11.srcNodeRef.childNodes.length;i<len;i++){
_11.containerNode.appendChild(_11.srcNodeRef.removeChild(_11.srcNodeRef.firstChild));
}
_11.srcNodeRef=null;
}
_11.domNode.appendChild(_11.containerNode);
for(i=0;i<=5;i++){
var top=dojo.create("DIV");
top.className="mblRoundCorner mblRoundCorner"+i+"T";
_11.domNode.insertBefore(top,_11.containerNode);
var _13=dojo.create("DIV");
_13.className="mblRoundCorner mblRoundCorner"+i+"B";
_11.domNode.appendChild(_13);
}
}});
}
if(dojo.isIE<=6){
dojox.mobile.applyPngFilter=function(_14){
_14=_14||dojo.body();
var _15=_14.getElementsByTagName("IMG");
var _16=dojo.moduleUrl("dojo","resources/blank.gif");
for(var i=0,len=_15.length;i<len;i++){
var img=_15[i];
var w=img.offsetWidth;
var h=img.offsetHeight;
if(w===0||h===0){
return;
}
var src=img.src;
if(src.indexOf("resources/blank.gif")!=-1){
continue;
}
img.src=_16;
img.runtimeStyle.filter="progid:DXImageTransform.Microsoft.AlphaImageLoader(src='"+src+"')";
img.style.width=w+"px";
img.style.height=h+"px";
}
};
}
dojox.mobile.loadCss=function(_17){
if(!dojo.global._loadedCss){
var obj={};
dojo.forEach(dojo.doc.getElementsByTagName("link"),function(_18){
obj[_18.href]=true;
});
dojo.global._loadedCss=obj;
}
if(!dojo.isArray(_17)){
_17=[_17];
}
for(var i=0;i<_17.length;i++){
var _19=_17[i];
if(!dojo.global._loadedCss[_19]){
dojo.global._loadedCss[_19]=true;
if(dojo.doc.createStyleSheet){
setTimeout(function(_1a){
return function(){
dojo.doc.createStyleSheet(_1a);
};
}(_19),0);
}else{
var _1b=dojo.doc.createElement("link");
_1b.href=_19;
_1b.type="text/css";
_1b.rel="stylesheet";
var _1c=dojo.doc.getElementsByTagName("head")[0];
_1c.appendChild(_1b);
}
}
}
};
dojox.mobile.loadCompatCssFiles=function(){
var _1d=dojo.doc.getElementsByTagName("link");
for(var i=0,len=_1d.length;i<len;i++){
var _1e=_1d[i].href;
if((_1e.indexOf("/mobile/themes/")!=-1||location.href.indexOf("/mobile/tests/")!=-1)&&_1e.substring(_1e.length-4)==".css"){
var _1f=_1e.substring(0,_1e.length-4)+"-compat.css";
dojox.mobile.loadCss(_1f);
}
}
};
dojo.addOnLoad(function(){
dojox.mobile.loadCompatCssFiles();
if(dojox.mobile.applyPngFilter){
dojox.mobile.applyPngFilter();
}
});
}
