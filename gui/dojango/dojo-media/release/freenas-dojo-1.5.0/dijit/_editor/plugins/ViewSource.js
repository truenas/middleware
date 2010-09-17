/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit._editor.plugins.ViewSource"]){
dojo._hasResource["dijit._editor.plugins.ViewSource"]=true;
dojo.provide("dijit._editor.plugins.ViewSource");
dojo.require("dojo.window");
dojo.require("dojo.i18n");
dojo.require("dijit._editor._Plugin");
dojo.require("dijit.form.Button");
dojo.requireLocalization("dijit._editor","commands",null,"ROOT,ar,ca,cs,da,de,el,es,fi,fr,he,hu,it,ja,ko,nb,nl,pl,pt,pt-pt,ro,ru,sk,sl,sv,th,tr,zh,zh-tw");
dojo.declare("dijit._editor.plugins.ViewSource",dijit._editor._Plugin,{stripScripts:true,stripComments:true,stripIFrames:true,readOnly:false,_fsPlugin:null,toggle:function(){
if(dojo.isWebKit){
this._vsFocused=true;
}
this.button.set("checked",!this.button.get("checked"));
},_initButton:function(){
var _1=dojo.i18n.getLocalization("dijit._editor","commands"),_2=this.editor;
this.button=new dijit.form.ToggleButton({label:_1["viewSource"],dir:_2.dir,lang:_2.lang,showLabel:false,iconClass:this.iconClassPrefix+" "+this.iconClassPrefix+"ViewSource",tabIndex:"-1",onChange:dojo.hitch(this,"_showSource")});
if(dojo.isIE==7){
this._ieFixNode=dojo.create("div",{style:{opacity:"0",zIndex:"-1000",position:"absolute",top:"-1000px"}},dojo.body());
}
this.button.set("readOnly",false);
},setEditor:function(_3){
this.editor=_3;
this._initButton();
this.editor.addKeyHandler(dojo.keys.F12,true,true,dojo.hitch(this,function(e){
this.button.focus();
this.toggle();
dojo.stopEvent(e);
setTimeout(dojo.hitch(this,function(){
this.editor.focus();
}),100);
}));
},_showSource:function(_4){
var ed=this.editor;
var _5=ed._plugins;
var _6;
this._sourceShown=_4;
var _7=this;
try{
if(!this.sourceArea){
this._createSourceView();
}
if(_4){
ed._sourceQueryCommandEnabled=ed.queryCommandEnabled;
ed.queryCommandEnabled=function(_8){
var _9=_8.toLowerCase();
if(_9==="viewsource"){
return true;
}else{
return false;
}
};
this.editor.onDisplayChanged();
_6=ed.get("value");
_6=this._filter(_6);
ed.set("value",_6);
this._pluginList=[];
this._disabledPlugins=dojo.filter(_5,function(p){
if(p&&p.button&&!p.button.get("disabled")&&!(p instanceof dijit._editor.plugins.ViewSource)){
p._vs_updateState=p.updateState;
p.updateState=function(){
return false;
};
p.button.set("disabled",true);
if(p.command){
switch(p.command){
case "bold":
case "italic":
case "underline":
case "strikethrough":
case "superscript":
case "subscript":
p.button.set("checked",false);
break;
default:
break;
}
}
return true;
}
});
if(this._fsPlugin){
this._fsPlugin._getAltViewNode=function(){
return _7.sourceArea;
};
}
this.sourceArea.value=_6;
var is=dojo.marginBox(ed.iframe.parentNode);
dojo.marginBox(this.sourceArea,{w:is.w,h:is.h});
dojo.style(ed.iframe,"display","none");
dojo.style(this.sourceArea,{display:"block"});
var _a=function(){
var vp=dojo.window.getBox();
if("_prevW" in this&&"_prevH" in this){
if(vp.w===this._prevW&&vp.h===this._prevH){
return;
}else{
this._prevW=vp.w;
this._prevH=vp.h;
}
}else{
this._prevW=vp.w;
this._prevH=vp.h;
}
if(this._resizer){
clearTimeout(this._resizer);
delete this._resizer;
}
this._resizer=setTimeout(dojo.hitch(this,function(){
delete this._resizer;
this._resize();
}),10);
};
this._resizeHandle=dojo.connect(window,"onresize",this,_a);
setTimeout(dojo.hitch(this,this._resize),100);
this.editor.onNormalizedDisplayChanged();
}else{
if(!ed._sourceQueryCommandEnabled){
return;
}
dojo.disconnect(this._resizeHandle);
delete this._resizeHandle;
ed.queryCommandEnabled=ed._sourceQueryCommandEnabled;
if(!this._readOnly){
_6=this.sourceArea.value;
_6=this._filter(_6);
ed.beginEditing();
ed.set("value",_6);
ed.endEditing();
}
dojo.forEach(this._disabledPlugins,function(p){
p.button.set("disabled",false);
if(p._vs_updateState){
p.updateState=p._vs_updateState;
}
});
this._disabledPlugins=null;
dojo.style(this.sourceArea,"display","none");
dojo.style(ed.iframe,"display","block");
delete ed._sourceQueryCommandEnabled;
this.editor.onDisplayChanged();
}
setTimeout(dojo.hitch(this,function(){
var _b=ed.domNode.parentNode;
if(_b){
var _c=dijit.getEnclosingWidget(_b);
if(_c&&_c.resize){
_c.resize();
}
}
ed.resize();
}),300);
}
catch(e){
console.log(e);
}
},_resize:function(){
var ed=this.editor;
var _d=ed.getHeaderHeight();
var fH=ed.getFooterHeight();
var eb=dojo.position(ed.domNode);
var _e=dojo._getPadBorderExtents(ed.iframe.parentNode);
var _f=dojo._getMarginExtents(ed.iframe.parentNode);
var _10=dojo._getPadBorderExtents(ed.domNode);
var _11=dojo._getMarginExtents(ed.domNode);
var edb={w:eb.w-(_10.w+_11.w),h:eb.h-(_d+_10.h+_11.h+fH)};
if(this._fsPlugin&&this._fsPlugin.isFullscreen){
var vp=dojo.window.getBox();
edb.w=(vp.w-_10.w);
edb.h=(vp.h-(_d+_10.h+fH));
}
if(dojo.isIE){
edb.h-=2;
}
if(this._ieFixNode){
var _12=-this._ieFixNode.offsetTop/1000;
edb.w=Math.floor((edb.w+0.9)/_12);
edb.h=Math.floor((edb.h+0.9)/_12);
}
dojo.marginBox(this.sourceArea,{w:edb.w-(_e.w+_f.w),h:edb.h-(_e.h+_f.h)});
dojo.marginBox(ed.iframe.parentNode,{h:edb.h});
},_createSourceView:function(){
var ed=this.editor;
var _13=ed._plugins;
this.sourceArea=dojo.create("textarea");
if(this.readOnly){
dojo.attr(this.sourceArea,"readOnly",true);
this._readOnly=true;
}
dojo.style(this.sourceArea,{padding:"0px",margin:"0px",borderWidth:"0px",borderStyle:"none"});
dojo.place(this.sourceArea,ed.iframe,"before");
if(dojo.isIE&&ed.iframe.parentNode.lastChild!==ed.iframe){
dojo.style(ed.iframe.parentNode.lastChild,{width:"0px",height:"0px",padding:"0px",margin:"0px",borderWidth:"0px",borderStyle:"none"});
}
ed._viewsource_oldFocus=ed.focus;
var _14=this;
ed.focus=function(){
if(_14._sourceShown){
_14.setSourceAreaCaret();
}else{
try{
if(this._vsFocused){
delete this._vsFocused;
dijit.focus(ed.editNode);
}else{
ed._viewsource_oldFocus();
}
}
catch(e){
console.log(e);
}
}
};
var i,p;
for(i=0;i<_13.length;i++){
p=_13[i];
if(p&&(p.declaredClass==="dijit._editor.plugins.FullScreen"||p.declaredClass===(dijit._scopeName+"._editor.plugins.FullScreen"))){
this._fsPlugin=p;
break;
}
}
if(this._fsPlugin){
this._fsPlugin._viewsource_getAltViewNode=this._fsPlugin._getAltViewNode;
this._fsPlugin._getAltViewNode=function(){
return _14._sourceShown?_14.sourceArea:this._viewsource_getAltViewNode();
};
}
this.connect(this.sourceArea,"onkeydown",dojo.hitch(this,function(e){
if(this._sourceShown&&e.keyCode==dojo.keys.F12&&e.ctrlKey&&e.shiftKey){
this.button.focus();
this.button.set("checked",false);
setTimeout(dojo.hitch(this,function(){
ed.focus();
}),100);
dojo.stopEvent(e);
}
}));
},_stripScripts:function(_15){
if(_15){
_15=_15.replace(/<\s*script[^>]*>((.|\s)*?)<\\?\/\s*script\s*>/ig,"");
_15=_15.replace(/<\s*script\b([^<>]|\s)*>?/ig,"");
_15=_15.replace(/<[^>]*=(\s|)*[("|')]javascript:[^$1][(\s|.)]*[$1][^>]*>/ig,"");
}
return _15;
},_stripComments:function(_16){
if(_16){
_16=_16.replace(/<!--(.|\s){1,}?-->/g,"");
}
return _16;
},_stripIFrames:function(_17){
if(_17){
_17=_17.replace(/<\s*iframe[^>]*>((.|\s)*?)<\\?\/\s*iframe\s*>/ig,"");
}
return _17;
},_filter:function(_18){
if(_18){
if(this.stripScripts){
_18=this._stripScripts(_18);
}
if(this.stripComments){
_18=this._stripComments(_18);
}
if(this.stripIFrames){
_18=this._stripIFrames(_18);
}
}
return _18;
},setSourceAreaCaret:function(){
var win=dojo.global;
var _19=this.sourceArea;
dijit.focus(_19);
if(this._sourceShown&&!this.readOnly){
if(dojo.isIE){
if(this.sourceArea.createTextRange){
var _1a=_19.createTextRange();
_1a.collapse(true);
_1a.moveStart("character",-99999);
_1a.moveStart("character",0);
_1a.moveEnd("character",0);
_1a.select();
}
}else{
if(win.getSelection){
if(_19.setSelectionRange){
_19.setSelectionRange(0,0);
}
}
}
}
},destroy:function(){
if(this._ieFixNode){
dojo.body().removeChild(this._ieFixNode);
}
if(this._resizer){
clearTimeout(this._resizer);
delete this._resizer;
}
if(this._resizeHandle){
dojo.disconnect(this._resizeHandle);
delete this._resizeHandle;
}
this.inherited(arguments);
}});
dojo.subscribe(dijit._scopeName+".Editor.getPlugin",null,function(o){
if(o.plugin){
return;
}
var _1b=o.args.name.toLowerCase();
if(_1b==="viewsource"){
o.plugin=new dijit._editor.plugins.ViewSource({readOnly:("readOnly" in o.args)?o.args.readOnly:false,stripComments:("stripComments" in o.args)?o.args.stripComments:true,stripScripts:("stripScripts" in o.args)?o.args.stripScripts:true,stripIFrames:("stripIFrames" in o.args)?o.args.stripIFrames:true});
}
});
}
