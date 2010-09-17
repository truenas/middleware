/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.mobile._base"]){
dojo._hasResource["dojox.mobile._base"]=true;
dojo.provide("dojox.mobile._base");
dojo.require("dijit._Widget");
dojo.declare("dojox.mobile.View",dijit._Widget,{selected:false,keepScrollPos:true,_started:false,constructor:function(_1,_2){
if(_2){
dojo.byId(_2).style.visibility="hidden";
}
},buildRendering:function(){
this.domNode=this.containerNode=this.srcNodeRef||dojo.doc.createElement("DIV");
this.domNode.className="mblView";
this.connect(this.domNode,"webkitAnimationEnd","onAnimationEnd");
this.connect(this.domNode,"webkitAnimationStart","onAnimationStart");
var id=location.href.match(/#(\w+)([^\w=]|$)/)?RegExp.$1:null;
this._visible=this.selected&&!id||this.id==id;
if(this.selected){
dojox.mobile._defaultView=this;
}
},startup:function(){
if(this._started){
return;
}
var _3=this;
setTimeout(function(){
if(!_3._visible){
_3.domNode.style.display="none";
}else{
dojox.mobile._currentView=_3;
_3.onStartView();
}
_3.domNode.style.visibility="visible";
},dojo.isIE?100:0);
this._started=true;
},onStartView:function(){
},onBeforeTransitionIn:function(_4,_5,_6,_7,_8){
},onAfterTransitionIn:function(_9,_a,_b,_c,_d){
},onBeforeTransitionOut:function(_e,_f,_10,_11,_12){
},onAfterTransitionOut:function(_13,dir,_14,_15,_16){
},_saveState:function(_17,dir,_18,_19,_1a){
this._context=_19;
this._method=_1a;
if(_18=="none"||!dojo.isWebKit){
_18=null;
}
this._moveTo=_17;
this._dir=dir;
this._transition=_18;
this._arguments=[];
var i;
for(i=0;i<arguments.length;i++){
this._arguments.push(arguments[i]);
}
this._args=[];
if(_19||_1a){
for(i=5;i<arguments.length;i++){
this._args.push(arguments[i]);
}
}
},performTransition:function(_1b,dir,_1c,_1d,_1e){
if(dojo.hash){
if(typeof (_1b)=="string"&&_1b.charAt(0)=="#"&&!dojox.mobile._params){
dojox.mobile._params=[];
for(var i=0;i<arguments.length;i++){
dojox.mobile._params.push(arguments[i]);
}
dojo.hash(_1b);
return;
}
}
this._saveState.apply(this,arguments);
var _1f;
if(_1b){
if(typeof (_1b)=="string"){
_1b.match(/(\w+)/);
_1f=RegExp.$1;
}else{
_1f=_1b;
}
}else{
if(!this._dummyNode){
this._dummyNode=dojo.doc.createElement("DIV");
dojo.body().appendChild(this._dummyNode);
}
_1f=this._dummyNode;
}
var _20=this.domNode;
_1f=this.toNode=dojo.byId(_1f);
if(!_1f){
alert("dojox.mobile.View#performTransition: destination view not found: "+_1f);
}
_1f.style.visibility="hidden";
_1f.style.display="";
this.onBeforeTransitionOut.apply(this,arguments);
var _21=dijit.byNode(_1f);
if(_21&&_21.onBeforeTransitionIn){
if(this.keepScrollPos&&!dijit.getEnclosingWidget(this.domNode.parentNode)){
var _22=dojo.body().scrollTop||dojo.doc.documentElement.scrollTop||window.pageYOffset||0;
if(dir==1){
_1f.style.top="0px";
if(_22>1){
_20.style.top=-_22+"px";
if(dojo.config["mblHideAddressBar"]!==false){
setTimeout(function(){
window.scrollTo(0,1);
},0);
}
}
}else{
if(_22>1||_1f.offsetTop!==0){
var _23=-_1f.offsetTop;
_1f.style.top="0px";
_20.style.top=_23-_22+"px";
if(dojo.config["mblHideAddressBar"]!==false&&_23>0){
setTimeout(function(){
window.scrollTo(0,_23+1);
},0);
}
}
}
}else{
_1f.style.top="0px";
}
_21.onBeforeTransitionIn.apply(this,arguments);
}
_1f.style.display="none";
_1f.style.visibility="visible";
this._doTransition(_20,_1f,_1c,dir);
},_doTransition:function(_24,_25,_26,dir){
var rev=(dir==-1)?" reverse":"";
_25.style.display="";
if(_26){
dojo.addClass(_24,_26+" out"+rev);
dojo.addClass(_25,_26+" in"+rev);
}else{
this.domNode.style.display="none";
this.invokeCallback();
}
},onAnimationStart:function(e){
},onAnimationEnd:function(e){
var _27=false;
if(dojo.hasClass(this.domNode,"out")){
_27=true;
this.domNode.style.display="none";
dojo.forEach([this._transition,"in","out","reverse"],function(s){
dojo.removeClass(this.domNode,s);
},this);
}
if(e.animationName.indexOf("shrink")===0){
var li=e.target;
li.style.display="none";
dojo.removeClass(li,"mblCloseContent");
}
if(_27){
this.invokeCallback();
}
this.domNode&&(this.domNode.className="mblView");
},invokeCallback:function(){
this.onAfterTransitionOut.apply(this,this._arguments);
var _28=dijit.byNode(this.toNode);
if(_28&&_28.onAfterTransitionIn){
_28.onAfterTransitionIn.apply(this,this._arguments);
}
if(dojo.hash){
dojox.mobile._currentView=_28;
}
var c=this._context,m=this._method;
if(!c&&!m){
return;
}
if(!m){
m=c;
c=null;
}
c=c||dojo.global;
if(typeof (m)=="string"){
c[m].apply(c,this._args);
}else{
m.apply(c,this._args);
}
},addChild:function(_29){
this.containerNode.appendChild(_29.domNode);
}});
dojo.declare("dojox.mobile.Heading",dijit._Widget,{back:"",href:"",moveTo:"",transition:"slide",label:"",buildRendering:function(){
this.domNode=this.containerNode=this.srcNodeRef||dojo.doc.createElement("H1");
this.domNode.className="mblHeading";
this._view=this.domNode.parentNode&&dijit.byNode(this.domNode.parentNode);
if(this.label){
this.domNode.innerHTML=this.label;
}else{
this.label=this.domNode.innerHTML;
}
if(this.back){
var _2a=dojo.doc.createElement("DIV");
_2a.className="mblArrowButtonHead";
var _2b=this._body=dojo.doc.createElement("DIV");
_2b.className="mblArrowButtonBody mblArrowButtonText";
_2b.innerHTML=this.back;
this.connect(_2b,"onclick","onClick");
var _2c=dojo.doc.createElement("DIV");
_2c.className="mblArrowButtonNeck";
this.domNode.appendChild(_2a);
this.domNode.appendChild(_2b);
this.domNode.appendChild(_2c);
this.setLabel(this.label);
}
},onClick:function(e){
var h1=this.domNode;
dojo.addClass(h1,"mblArrowButtonSelected");
setTimeout(function(){
dojo.removeClass(h1,"mblArrowButtonSelected");
},1000);
this.goTo(this.moveTo,this.href);
},setLabel:function(_2d){
if(_2d!=this.label){
this.label=_2d;
this.domNode.firstChild.nodeValue=_2d;
}
var s=this.domNode.style;
if(this.label.length>12){
var h=this.domNode.cloneNode(true);
h.style.visibility="hidden";
dojo.body().appendChild(h);
var b=h.childNodes[2];
s.paddingLeft=b.offsetWidth+30+"px";
s.textAlign="left";
dojo.body().removeChild(h);
h=null;
}else{
s.paddingLeft="";
s.textAlign="";
}
},goTo:function(_2e,_2f){
if(!this._view){
this._view=dijit.byNode(this.domNode.parentNode);
}
if(_2f){
this._view.performTransition(null,-1,this.transition,this,function(){
location.href=_2f;
});
}else{
if(dojox.mobile.app){
dojo.publish("/dojox/mobile/app/goback");
}else{
this._view.performTransition(_2e,-1,this.transition);
}
}
}});
dojo.declare("dojox.mobile.RoundRect",dijit._Widget,{shadow:false,buildRendering:function(){
this.domNode=this.containerNode=this.srcNodeRef||dojo.doc.createElement("DIV");
this.domNode.className=this.shadow?"mblRoundRect mblShadow":"mblRoundRect";
}});
dojo.declare("dojox.mobile.RoundRectCategory",dijit._Widget,{label:"",buildRendering:function(){
this.domNode=this.containerNode=this.srcNodeRef||dojo.doc.createElement("H2");
this.domNode.className="mblRoundRectCategory";
if(this.label){
this.domNode.innerHTML=this.label;
}else{
this.label=this.domNode.innerHTML;
}
}});
dojo.declare("dojox.mobile.EdgeToEdgeCategory",dojox.mobile.RoundRectCategory,{buildRendering:function(){
this.inherited(arguments);
this.domNode.className="mblEdgeToEdgeCategory";
}});
dojo.declare("dojox.mobile.RoundRectList",dijit._Widget,{transition:"slide",iconBase:"",iconPos:"",buildRendering:function(){
this.domNode=this.containerNode=this.srcNodeRef||dojo.doc.createElement("UL");
this.domNode.className="mblRoundRectList";
},addChild:function(_30){
this.containerNode.appendChild(_30.domNode);
_30.inheritParams();
_30.setIcon();
}});
dojo.declare("dojox.mobile.EdgeToEdgeList",dojox.mobile.RoundRectList,{buildRendering:function(){
this.inherited(arguments);
this.domNode.className="mblEdgeToEdgeList";
}});
dojo.declare("dojox.mobile.AbstractItem",dijit._Widget,{icon:"",iconPos:"",href:"",moveTo:"",clickable:false,url:"",transition:"",callback:null,sync:true,label:"",inheritParams:function(){
var _31=this.getParentWidget();
if(_31){
if(!this.transition){
this.transition=_31.transition;
}
if(!this.icon){
this.icon=_31.iconBase;
}
if(!this.iconPos){
this.iconPos=_31.iconPos;
}
}
},transitionTo:function(_32,_33,url){
var n=this.domNode.parentNode;
var w;
while(true){
w=dijit.getEnclosingWidget(n);
if(!w){
return;
}
if(w.performTransition){
break;
}
n=w.domNode.parentNode;
}
if(_33){
w.performTransition(null,1,this.transition,this,function(){
location.href=_33;
});
return;
}
if(url){
var id;
if(dojox.mobile._viewMap&&dojox.mobile._viewMap[url]){
id=dojox.mobile._viewMap[url];
}else{
var _34=this._text;
if(!_34){
if(this.sync){
_34=dojo.trim(dojo._getText(url));
}else{
var _35=dojox.mobile.ProgressIndicator.getInstance();
dojo.body().appendChild(_35.domNode);
_35.start();
var xhr=dojo.xhrGet({url:url,handleAs:"text"});
xhr.addCallback(dojo.hitch(this,function(_36,_37){
_35.stop();
if(_36){
this._text=_36;
this.transitionTo(_32,_33,url);
}
}));
xhr.addErrback(function(_38){
_35.stop();
alert("Failed to load "+url+"\n"+(_38.description||_38));
});
return;
}
}
this._text=null;
id=this._parse(_34);
if(!dojox.mobile._viewMap){
dojox.mobile._viewMap=[];
}
dojox.mobile._viewMap[url]=id;
}
_32=id;
}
w.performTransition(_32,1,this.transition,this.callback&&this,this.callback);
},_parse:function(_39){
var _3a=dojo.create("DIV");
var _3b;
if(_39.charAt(0)=="<"){
_3a.innerHTML=_39;
_3b=_3a.firstChild;
if(!_3b&&_3b.nodeType!=1){
alert("dojox.mobile.AbstractItem#transitionTo: invalid view content");
return;
}
_3b.setAttribute("_started","true");
_3b.style.visibility="hidden";
dojo.body().appendChild(_3a);
(dojox.mobile.parser||dojo.parser).parse(_3a);
}else{
if(_39.charAt(0)=="{"){
dojo.body().appendChild(_3a);
this._ws=[];
_3b=this._instantiate(eval("("+_39+")"),_3a);
for(var i=0;i<this._ws.length;i++){
var w=this._ws[i];
w.startup&&!w._started&&(!w.getParent||!w.getParent())&&w.startup();
}
this._ws=null;
}
}
_3b.style.display="none";
_3b.style.visibility="visible";
var id=_3b.id;
return dojo.hash?"#"+id:id;
},_instantiate:function(obj,_3c,_3d){
var _3e;
for(var key in obj){
if(key.charAt(0)=="@"){
continue;
}
var cls=dojo.getObject(key);
if(!cls){
continue;
}
var _3f={};
var _40=cls.prototype;
var _41=dojo.isArray(obj[key])?obj[key]:[obj[key]];
for(var i=0;i<_41.length;i++){
for(var _42 in _41[i]){
if(_42.charAt(0)=="@"){
var val=_41[i][_42];
_42=_42.substring(1);
if(typeof _40[_42]=="string"){
_3f[_42]=val;
}else{
if(typeof _40[_42]=="number"){
_3f[_42]=val-0;
}else{
if(typeof _40[_42]=="boolean"){
_3f[_42]=(val!="false");
}else{
if(typeof _40[_42]=="object"){
_3f[_42]=eval("("+val+")");
}
}
}
}
}
}
_3e=new cls(_3f,_3c);
if(!_3c){
this._ws.push(_3e);
}
if(_3d&&_3d.addChild){
_3d.addChild(_3e);
}
this._instantiate(_41[i],null,_3e);
}
}
return _3e&&_3e.domNode;
},getParentWidget:function(){
var ref=this.srcNodeRef||this.domNode;
return ref&&ref.parentNode?dijit.getEnclosingWidget(ref.parentNode):null;
}});
dojo.declare("dojox.mobile.ListItem",dojox.mobile.AbstractItem,{rightText:"",btnClass:"",anchorLabel:false,buildRendering:function(){
this.inheritParams();
var a=this.anchorNode=dojo.create("A");
a.className="mblListItemAnchor";
var box=dojo.create("DIV");
box.className="mblListItemTextBox";
if(this.anchorLabel){
box.style.cursor="pointer";
}
var r=this.srcNodeRef;
if(r){
for(var i=0,len=r.childNodes.length;i<len;i++){
box.appendChild(r.removeChild(r.firstChild));
}
}
if(this.label){
box.appendChild(dojo.doc.createTextNode(this.label));
}
a.appendChild(box);
if(this.rightText){
var txt=dojo.create("DIV");
txt.className="mblRightText";
txt.innerHTML=this.rightText;
a.appendChild(txt);
}
if(this.moveTo||this.href||this.url||this.clickable){
var _43=dojo.create("DIV");
_43.className="mblArrow";
a.appendChild(_43);
this.connect(a,"onclick","onClick");
}else{
if(this.btnClass){
var div=this.btnNode=dojo.create("DIV");
div.className=this.btnClass+" mblRightButton";
div.appendChild(dojo.create("DIV"));
div.appendChild(dojo.create("P"));
var _44=dojo.create("DIV");
_44.className="mblRightButtonContainer";
_44.appendChild(div);
a.appendChild(_44);
dojo.addClass(a,"mblListItemAnchorHasRightButton");
setTimeout(function(){
_44.style.width=div.offsetWidth+"px";
_44.style.height=div.offsetHeight+"px";
if(dojo.isIE){
a.parentNode.style.height=a.parentNode.offsetHeight+"px";
}
});
}
}
if(this.anchorLabel){
box.style.display="inline";
}
var li=this.domNode=this.containerNode=this.srcNodeRef||dojo.doc.createElement("LI");
li.className="mblListItem";
li.appendChild(a);
this.setIcon();
},setIcon:function(){
if(this.iconNode){
return;
}
var a=this.anchorNode;
if(this.icon&&this.icon!="none"){
var img=this.iconNode=dojo.create("IMG");
img.className="mblListItemIcon";
img.src=this.icon;
this.domNode.insertBefore(img,a);
dojox.mobile.setupIcon(this.iconNode,this.iconPos);
dojo.removeClass(a,"mblListItemAnchorNoIcon");
}else{
dojo.addClass(a,"mblListItemAnchorNoIcon");
}
},onClick:function(e){
if(this.anchorLabel){
for(var p=e.target;p.tagName!="LI";p=p.parentNode){
if(p.className=="mblListItemTextBox"){
dojo.addClass(p,"mblListItemTextBoxSelected");
setTimeout(function(){
dojo.removeClass(p,"mblListItemTextBoxSelected");
},1000);
this.onAnchorLabelClicked(e);
return;
}
}
}
var a=e.currentTarget;
var li=a.parentNode;
dojo.addClass(li,"mblItemSelected");
setTimeout(function(){
dojo.removeClass(li,"mblItemSelected");
},1000);
this.transitionTo(this.moveTo,this.href,this.url);
},onAnchorLabelClicked:function(e){
}});
dojo.declare("dojox.mobile.Switch",dijit._Widget,{value:"on",leftLabel:"ON",rightLabel:"OFF",_width:53,buildRendering:function(){
this.domNode=this.srcNodeRef||dojo.doc.createElement("DIV");
this.domNode.className="mblSwitch";
this.domNode.innerHTML="<div class=\"mblSwitchInner\">"+"<div class=\"mblSwitchBg mblSwitchBgLeft\">"+"<div class=\"mblSwitchText mblSwitchTextLeft\">"+this.leftLabel+"</div>"+"</div>"+"<div class=\"mblSwitchBg mblSwitchBgRight\">"+"<div class=\"mblSwitchText mblSwitchTextRight\">"+this.rightLabel+"</div>"+"</div>"+"<div class=\"mblSwitchKnob\"></div>"+"</div>";
var n=this.inner=this.domNode.firstChild;
this.left=n.childNodes[0];
this.right=n.childNodes[1];
this.knob=n.childNodes[2];
dojo.addClass(this.domNode,(this.value=="on")?"mblSwitchOn":"mblSwitchOff");
this[this.value=="off"?"left":"right"].style.display="none";
},postCreate:function(){
this.connect(this.knob,"onclick","onClick");
this.connect(this.knob,"touchstart","onTouchStart");
this.connect(this.knob,"mousedown","onTouchStart");
},_changeState:function(_45){
this.inner.style.left="";
dojo.addClass(this.domNode,"mblSwitchAnimation");
dojo.removeClass(this.domNode,(_45=="on")?"mblSwitchOff":"mblSwitchOn");
dojo.addClass(this.domNode,(_45=="on")?"mblSwitchOn":"mblSwitchOff");
var _46=this;
setTimeout(function(){
_46[_45=="off"?"left":"right"].style.display="none";
dojo.removeClass(_46.domNode,"mblSwitchAnimation");
},300);
},onClick:function(e){
if(this._moved){
return;
}
this.value=(this.value=="on")?"off":"on";
this._changeState(this.value);
this.onStateChanged(this.value);
},onTouchStart:function(e){
this._moved=false;
this.innerStartX=this.inner.offsetLeft;
if(e.targetTouches){
this.touchStartX=e.targetTouches[0].clientX;
this._conn1=dojo.connect(this.inner,"touchmove",this,"onTouchMove");
this._conn2=dojo.connect(this.inner,"touchend",this,"onTouchEnd");
}
this.left.style.display="block";
this.right.style.display="block";
return false;
},onTouchMove:function(e){
e.preventDefault();
var dx;
if(e.targetTouches){
if(e.targetTouches.length!=1){
return false;
}
dx=e.targetTouches[0].clientX-this.touchStartX;
}else{
dx=e.clientX-this.touchStartX;
}
var pos=this.innerStartX+dx;
var d=10;
if(pos<=-(this._width-d)){
pos=-this._width;
}
if(pos>=-d){
pos=0;
}
this.inner.style.left=pos+"px";
this._moved=true;
return true;
},onTouchEnd:function(e){
dojo.disconnect(this._conn1);
dojo.disconnect(this._conn2);
if(this.innerStartX==this.inner.offsetLeft){
return;
}
var _47=(this.inner.offsetLeft<-(this._width/2))?"off":"on";
this._changeState(_47);
if(_47!=this.value){
this.value=_47;
this.onStateChanged(this.value);
}
},onStateChanged:function(_48){
}});
dojo.declare("dojox.mobile.IconContainer",dijit._Widget,{defaultIcon:"",transition:"below",pressedIconOpacity:0.4,iconBase:"",iconPos:"",back:"Home",label:"My Application",single:false,buildRendering:function(){
this.domNode=this.containerNode=this.srcNodeRef||dojo.doc.createElement("UL");
this.domNode.className="mblIconContainer";
var t=this._terminator=dojo.create("LI");
t.className="mblIconItemTerminator";
t.innerHTML="&nbsp;";
this.domNode.appendChild(t);
},_setupSubNodes:function(ul){
var len=this.domNode.childNodes.length-1;
for(i=0;i<len;i++){
child=this.domNode.childNodes[i];
if(child.nodeType!=1){
continue;
}
w=dijit.byNode(child);
if(this.single){
w.subNode.firstChild.style.display="none";
}
ul.appendChild(w.subNode);
}
},startup:function(){
var ul,i,len,_49,w;
if(this.transition=="below"){
this._setupSubNodes(this.domNode);
}else{
var _4a=new dojox.mobile.View({id:this.id+"_mblApplView"});
var _4b=this;
_4a.onAfterTransitionIn=function(_4c,dir,_4d,_4e,_4f){
_4b._opening._open_1();
};
_4a.domNode.style.visibility="hidden";
var _50=_4a._heading=new dojox.mobile.Heading({back:this.back,label:this.label,moveTo:this.domNode.parentNode.id,transition:this.transition});
_4a.addChild(_50);
ul=dojo.doc.createElement("UL");
ul.className="mblIconContainer";
ul.style.marginTop="0px";
this._setupSubNodes(ul);
_4a.domNode.appendChild(ul);
dojo.doc.body.appendChild(_4a.domNode);
}
},closeAll:function(){
var len=this.domNode.childNodes.length;
for(var i=0;i<len;i++){
child=this.domNode.childNodes[i];
if(child.nodeType!=1){
continue;
}
if(child==this._terminator){
break;
}
w=dijit.byNode(child);
w.containerNode.parentNode.style.display="none";
w.setOpacity(w.iconNode,1);
}
},addChild:function(_51){
this.domNode.insertBefore(_51.domNode,this._terminator);
_51.transition=this.transition;
if(this.transition=="below"){
this.domNode.appendChild(_51.subNode);
}
_51.inheritParams();
_51.setIcon();
}});
dojo.declare("dojox.mobile.IconItem",dojox.mobile.AbstractItem,{lazy:false,requires:"",timeout:10,templateString:"<li class=\"mblIconItem\">"+"<div class=\"mblIconArea\" dojoAttachPoint=\"iconDivNode\">"+"<div><img src=\"${icon}\" dojoAttachPoint=\"iconNode\"></div>${label}"+"</div>"+"</li>",templateStringSub:"<li class=\"mblIconItemSub\" lazy=\"${lazy}\" style=\"display:none;\" dojoAttachPoint=\"contentNode\">"+"<h2 class=\"mblIconContentHeading\" dojoAttachPoint=\"closeNode\">"+"<div class=\"mblBlueMinusButton\" style=\"position:absolute;left:4px;top:2px;\" dojoAttachPoint=\"closeIconNode\"><div></div></div>${label}"+"</h2>"+"<div class=\"mblContent\" dojoAttachPoint=\"containerNode\"></div>"+"</li>",createTemplate:function(s){
dojo.forEach(["lazy","icon","label"],function(v){
while(s.indexOf("${"+v+"}")!=-1){
s=s.replace("${"+v+"}",this[v]);
}
},this);
var div=dojo.doc.createElement("DIV");
div.innerHTML=s;
var _52=div.getElementsByTagName("*");
var i,len,s1;
len=_52.length;
for(i=0;i<len;i++){
s1=_52[i].getAttribute("dojoAttachPoint");
if(s1){
this[s1]=_52[i];
}
}
var _53=div.removeChild(div.firstChild);
div=null;
return _53;
},buildRendering:function(){
this.inheritParams();
this.domNode=this.createTemplate(this.templateString);
this.subNode=this.createTemplate(this.templateStringSub);
this.subNode._parentNode=this.domNode;
if(this.srcNodeRef){
for(var i=0,len=this.srcNodeRef.childNodes.length;i<len;i++){
this.containerNode.appendChild(this.srcNodeRef.removeChild(this.srcNodeRef.firstChild));
}
this.srcNodeRef.parentNode.replaceChild(this.domNode,this.srcNodeRef);
this.srcNodeRef=null;
}
this.setIcon();
},setIcon:function(){
this.iconNode.src=this.icon;
dojox.mobile.setupIcon(this.iconNode,this.iconPos);
},postCreate:function(){
this.connect(this.iconNode,"onmousedown","onMouseDownIcon");
this.connect(this.iconNode,"onclick","iconClicked");
this.connect(this.closeIconNode,"onclick","closeIconClicked");
this.connect(this.iconNode,"onerror","onError");
},highlight:function(){
dojo.addClass(this.iconDivNode,"mblVibrate");
if(this.timeout>0){
var _54=this;
setTimeout(function(){
_54.unhighlight();
},this.timeout*1000);
}
},unhighlight:function(){
dojo.removeClass(this.iconDivNode,"mblVibrate");
},setOpacity:function(_55,val){
_55.style.opacity=val;
_55.style.mozOpacity=val;
_55.style.khtmlOpacity=val;
_55.style.webkitOpacity=val;
},instantiateWidget:function(e){
var _56=this.containerNode.getElementsByTagName("*");
var len=_56.length;
var s;
for(var i=0;i<len;i++){
s=_56[i].getAttribute("dojoType");
if(s){
dojo["require"](s);
}
}
if(len>0){
(dojox.mobile.parser||dojo.parser).parse(this.containerNode);
}
this.lazy=false;
},isOpen:function(e){
return this.containerNode.style.display!="none";
},onMouseDownIcon:function(e){
this.setOpacity(this.iconNode,this.getParentWidget().pressedIconOpacity);
},iconClicked:function(e){
if(e){
setTimeout(dojo.hitch(this,function(d){
this.iconClicked();
}),0);
return;
}
if(this.moveTo||this.href||this.url){
this.transitionTo(this.moveTo,this.href,this.url);
setTimeout(dojo.hitch(this,function(d){
this.setOpacity(this.iconNode,1);
}),1500);
}else{
this.open();
}
},closeIconClicked:function(e){
if(e){
setTimeout(dojo.hitch(this,function(d){
this.closeIconClicked();
}),0);
return;
}
this.close();
},open:function(){
var _57=this.getParentWidget();
if(this.transition=="below"){
if(_57.single){
_57.closeAll();
this.setOpacity(this.iconNode,this.getParentWidget().pressedIconOpacity);
}
this._open_1();
}else{
_57._opening=this;
if(_57.single){
_57.closeAll();
var _58=dijit.byId(_57.id+"_mblApplView");
_58._heading.setLabel(this.label);
}
this.transitionTo(_57.id+"_mblApplView");
}
},_open_1:function(){
this.contentNode.style.display="";
this.unhighlight();
if(this.lazy){
if(this.requires){
dojo.forEach(this.requires.split(/,/),function(c){
dojo["require"](c);
});
}
this.instantiateWidget();
}
this.contentNode.scrollIntoView();
this.onOpen();
},close:function(){
if(dojo.isWebKit){
var t=this.domNode.parentNode.offsetWidth/8;
var y=this.iconNode.offsetLeft;
var pos=0;
for(var i=1;i<=3;i++){
if(t*(2*i-1)<y&&y<=t*(2*(i+1)-1)){
pos=i;
break;
}
}
dojo.addClass(this.containerNode.parentNode,"mblCloseContent mblShrink"+pos);
}else{
this.containerNode.parentNode.style.display="none";
}
this.setOpacity(this.iconNode,1);
this.onClose();
},onOpen:function(){
},onClose:function(){
},onError:function(){
this.iconNode.src=this.getParentWidget().defaultIcon;
}});
dojo.declare("dojox.mobile.Button",dijit._Widget,{btnClass:"mblBlueButton",duration:1000,label:null,buildRendering:function(){
this.domNode=this.containerNode=this.srcNodeRef||dojo.doc.createElement("BUTTON");
this.domNode.className="mblButton "+this.btnClass;
if(this.label){
this.domNode.innerHTML=this.label;
}
this.connect(this.domNode,"onclick","onClick");
},onClick:function(e){
var _59=this.domNode;
var c="mblButtonSelected "+this.btnClass+"Selected";
dojo.addClass(_59,c);
setTimeout(function(){
dojo.removeClass(_59,c);
},this.duration);
}});
dojo.declare("dojox.mobile.TabContainer",dijit._Widget,{iconBase:"",iconPos:"",buildRendering:function(){
var _5a=this.domNode=this.srcNodeRef;
_5a.className="mblTabContainer";
var _5b=this.tabHeaderNode=dojo.doc.createElement("DIV");
var _5c=this.containerNode=dojo.doc.createElement("DIV");
for(var i=0,len=_5a.childNodes.length;i<len;i++){
_5c.appendChild(_5a.removeChild(_5a.firstChild));
}
_5b.className="mblTabPanelHeader";
_5b.align="center";
_5a.appendChild(_5b);
_5c.className="mblTabPanelPane";
_5a.appendChild(_5c);
},startup:function(){
this.createTabButtons();
this.inherited(arguments);
},createTabButtons:function(){
var div=dojo.doc.createElement("DIV");
div.align="center";
var tbl=dojo.doc.createElement("TABLE");
var _5d=tbl.insertRow(-1).insertCell(-1);
var _5e=this.containerNode.childNodes;
for(var i=0;i<_5e.length;i++){
var _5f=_5e[i];
if(_5f.nodeType!=1){
continue;
}
var _60=dijit.byNode(_5f);
if(_60.selected||!this._selectedPane){
this._selectedPane=_60;
}
_5f.style.display="none";
var tab=dojo.doc.createElement("DIV");
tab.className="mblTabButton";
if(_60.icon){
var _61=dojo.create("DIV");
var img=dojo.create("IMG");
_61.className="mblTabButtonImgDiv";
img.src=_60.icon;
dojox.mobile.setupIcon(img,_60.iconPos);
_61.appendChild(img);
tab.appendChild(_61);
}
tab.appendChild(dojo.doc.createTextNode(_60.label));
tab.pane=_60;
_60.tab=tab;
this.connect(tab,"onclick","onTabClick");
_5d.appendChild(tab);
}
div.appendChild(tbl);
this.tabHeaderNode.appendChild(div);
this.selectTab(this._selectedPane.tab);
},selectTab:function(tab){
this._selectedPane.domNode.style.display="none";
dojo.removeClass(this._selectedPane.tab,"mblTabButtonSelected");
this._selectedPane=tab.pane;
this._selectedPane.domNode.style.display="";
dojo.addClass(tab,"mblTabButtonSelected");
},onTabClick:function(e){
var tab=e.currentTarget;
dojo.addClass(tab,"mblTabButtonHighlighted");
setTimeout(function(){
dojo.removeClass(tab,"mblTabButtonHighlighted");
},200);
this.selectTab(tab);
}});
dojo.declare("dojox.mobile.TabPane",dijit._Widget,{label:"",icon:"",iconPos:"",selected:false,inheritParams:function(){
var _62=this.getParentWidget();
if(_62){
if(!this.icon){
this.icon=_62.iconBase;
}
if(!this.iconPos){
this.iconPos=_62.iconPos;
}
}
},buildRendering:function(){
this.inheritParams();
this.domNode=this.containerNode=this.srcNodeRef||dojo.doc.createElement("DIV");
this.domNode.className="mblTabPane";
},getParentWidget:function(){
var ref=this.srcNodeRef||this.domNode;
return ref&&ref.parentNode?dijit.getEnclosingWidget(ref.parentNode):null;
}});
dojo.declare("dojox.mobile.ProgressIndicator",null,{interval:100,colors:["#C0C0C0","#C0C0C0","#C0C0C0","#C0C0C0","#C0C0C0","#C0C0C0","#B8B9B8","#AEAFAE","#A4A5A4","#9A9A9A","#8E8E8E","#838383"],_bars:[],constructor:function(){
this.domNode=dojo.create("DIV");
this.domNode.className="mblProgContainer";
for(var i=0;i<12;i++){
var div=dojo.create("DIV");
div.className="mblProg mblProg"+i;
this.domNode.appendChild(div);
this._bars.push(div);
}
},start:function(){
var _63=0;
var _64=this;
this.timer=setInterval(function(){
_63--;
_63=_63<0?11:_63;
var c=_64.colors;
for(var i=0;i<12;i++){
var idx=(_63+i)%12;
_64._bars[i].style.backgroundColor=c[idx];
}
},this.interval);
},stop:function(){
if(this.timer){
clearInterval(this.timer);
}
this.timer=null;
if(this.domNode.parentNode){
this.domNode.parentNode.removeChild(this.domNode);
}
}});
dojox.mobile.ProgressIndicator._instance=null;
dojox.mobile.ProgressIndicator.getInstance=function(){
if(!dojox.mobile.ProgressIndicator._instance){
dojox.mobile.ProgressIndicator._instance=new dojox.mobile.ProgressIndicator();
}
return dojox.mobile.ProgressIndicator._instance;
};
dojox.mobile.addClass=function(){
var _65=document.getElementsByTagName("link");
for(var i=0,len=_65.length;i<len;i++){
if(_65[i].href.match(/dojox\/mobile\/themes\/(\w+)\//)){
dojox.mobile.theme=RegExp.$1;
dojo.addClass(dojo.body(),dojox.mobile.theme);
break;
}
}
};
dojox.mobile.setupIcon=function(_66,_67){
if(_66&&_67){
var arr=dojo.map(_67.split(/[ ,]/),function(_68){
return _68-0;
});
var t=arr[0];
var r=arr[1]+arr[2];
var b=arr[0]+arr[3];
var l=arr[1];
_66.style.clip="rect("+t+"px "+r+"px "+b+"px "+l+"px)";
_66.style.top=-t+"px";
_66.style.left=-l+"px";
}
};
dojo._loaders.unshift(function(){
var _69=dojo.body().getElementsByTagName("*");
var i,len,s;
len=_69.length;
for(i=0;i<len;i++){
s=_69[i].getAttribute("dojoType");
if(s){
if(_69[i].parentNode.getAttribute("lazy")=="true"){
_69[i].setAttribute("__dojoType",s);
_69[i].removeAttribute("dojoType");
}
}
}
});
dojo.addOnLoad(function(){
dojox.mobile.addClass();
if(dojo.config["mblApplyPageStyles"]!==false){
dojo.addClass(dojo.doc.documentElement,"mobile");
}
if(dojo.config["mblHideAddressBar"]!==false){
var _6a=function(){
setTimeout(function(){
scrollTo(0,1);
},100);
};
_6a();
}
var _6b=dojo.body().getElementsByTagName("*");
var i,len=_6b.length,s;
for(i=0;i<len;i++){
s=_6b[i].getAttribute("__dojoType");
if(s){
_6b[i].setAttribute("dojoType",s);
_6b[i].removeAttribute("__dojoType");
}
}
if(dojo.hash){
var _6c=function(_6d){
var arr;
arr=dijit.findWidgets(_6d);
var _6e=arr;
for(var i=0;i<_6e.length;i++){
arr=arr.concat(_6c(_6e[i].containerNode));
}
return arr;
};
dojo.subscribe("/dojo/hashchange",null,function(_6f){
var _70=dojox.mobile._currentView;
if(!_70){
return;
}
var _71=dojox.mobile._params;
if(!_71){
var _72=_6f?_6f:dojox.mobile._defaultView.id;
var _73=_6c(_70.domNode);
var dir=1,_74="slide";
for(i=0;i<_73.length;i++){
var w=_73[i];
if("#"+_72==w.moveTo){
_74=w.transition;
dir=(w instanceof dojox.mobile.Heading)?-1:1;
break;
}
}
_71=[_72,dir,_74];
}
_70.performTransition.apply(_70,_71);
dojox.mobile._params=null;
});
}
dojo.body().style.visibility="visible";
});
dijit.getEnclosingWidget=function(_75){
while(_75&&_75.tagName!=="BODY"){
if(_75.getAttribute&&_75.getAttribute("widgetId")){
return dijit.registry.byId(_75.getAttribute("widgetId"));
}
_75=_75._parentNode||_75.parentNode;
}
return null;
};
}
