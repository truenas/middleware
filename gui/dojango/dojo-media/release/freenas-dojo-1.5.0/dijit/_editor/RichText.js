/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit._editor.RichText"]){
dojo._hasResource["dijit._editor.RichText"]=true;
dojo.provide("dijit._editor.RichText");
dojo.require("dijit._Widget");
dojo.require("dijit._CssStateMixin");
dojo.require("dijit._editor.selection");
dojo.require("dijit._editor.range");
dojo.require("dijit._editor.html");
if(!dojo.config["useXDomain"]||dojo.config["allowXdRichTextSave"]){
if(dojo._postLoad){
(function(){
var _1=dojo.doc.createElement("textarea");
_1.id=dijit._scopeName+"._editor.RichText.savedContent";
dojo.style(_1,{display:"none",position:"absolute",top:"-100px",height:"3px",width:"3px"});
dojo.body().appendChild(_1);
})();
}else{
try{
dojo.doc.write("<textarea id=\""+dijit._scopeName+"._editor.RichText.savedContent\" "+"style=\"display:none;position:absolute;top:-100px;left:-100px;height:3px;width:3px;overflow:hidden;\"></textarea>");
}
catch(e){
}
}
}
dojo.declare("dijit._editor.RichText",[dijit._Widget,dijit._CssStateMixin],{constructor:function(_2){
this.contentPreFilters=[];
this.contentPostFilters=[];
this.contentDomPreFilters=[];
this.contentDomPostFilters=[];
this.editingAreaStyleSheets=[];
this.events=[].concat(this.events);
this._keyHandlers={};
this.contentPreFilters.push(dojo.hitch(this,"_preFixUrlAttributes"));
if(dojo.isMoz){
this.contentPreFilters.push(this._normalizeFontStyle);
this.contentPostFilters.push(this._removeMozBogus);
}
if(dojo.isWebKit){
this.contentPreFilters.push(this._removeWebkitBogus);
this.contentPostFilters.push(this._removeWebkitBogus);
}
if(dojo.isIE){
this.contentPostFilters.push(this._normalizeFontStyle);
}
if(_2&&dojo.isString(_2.value)){
this.value=_2.value;
}
this.onLoadDeferred=new dojo.Deferred();
},baseClass:"dijitEditor",inheritWidth:false,focusOnLoad:false,name:"",styleSheets:"",_content:"",height:"300px",minHeight:"1em",isClosed:true,isLoaded:false,_SEPARATOR:"@@**%%__RICHTEXTBOUNDRY__%%**@@",onLoadDeferred:null,isTabIndent:false,disableSpellCheck:false,postCreate:function(){
if("textarea"==this.domNode.tagName.toLowerCase()){
console.warn("RichText should not be used with the TEXTAREA tag.  See dijit._editor.RichText docs.");
}
this.inherited(arguments);
dojo.publish(dijit._scopeName+"._editor.RichText::init",[this]);
this.open();
this.setupDefaultShortcuts();
},setupDefaultShortcuts:function(){
var _3=dojo.hitch(this,function(_4,_5){
return function(){
return !this.execCommand(_4,_5);
};
});
var _6={b:_3("bold"),i:_3("italic"),u:_3("underline"),a:_3("selectall"),s:function(){
this.save(true);
},m:function(){
this.isTabIndent=!this.isTabIndent;
},"1":_3("formatblock","h1"),"2":_3("formatblock","h2"),"3":_3("formatblock","h3"),"4":_3("formatblock","h4"),"\\":_3("insertunorderedlist")};
if(!dojo.isIE){
_6.Z=_3("redo");
}
for(var _7 in _6){
this.addKeyHandler(_7,true,false,_6[_7]);
}
},events:["onKeyPress","onKeyDown","onKeyUp","onClick"],captureEvents:[],_editorCommandsLocalized:false,_localizeEditorCommands:function(){
if(this._editorCommandsLocalized){
return;
}
this._editorCommandsLocalized=true;
var _8=["div","p","pre","h1","h2","h3","h4","h5","h6","ol","ul","address"];
var _9="",_a,i=0;
while((_a=_8[i++])){
if(_a.charAt(1)!="l"){
_9+="<"+_a+"><span>content</span></"+_a+"><br/>";
}else{
_9+="<"+_a+"><li>content</li></"+_a+"><br/>";
}
}
var _b=dojo.doc.createElement("div");
dojo.style(_b,{position:"absolute",top:"-2000px"});
dojo.doc.body.appendChild(_b);
_b.innerHTML=_9;
var _c=_b.firstChild;
while(_c){
dijit._editor.selection.selectElement(_c.firstChild);
dojo.withGlobal(this.window,"selectElement",dijit._editor.selection,[_c.firstChild]);
var _d=_c.tagName.toLowerCase();
this._local2NativeFormatNames[_d]=document.queryCommandValue("formatblock");
this._native2LocalFormatNames[this._local2NativeFormatNames[_d]]=_d;
_c=_c.nextSibling.nextSibling;
}
dojo.body().removeChild(_b);
},open:function(_e){
if(!this.onLoadDeferred||this.onLoadDeferred.fired>=0){
this.onLoadDeferred=new dojo.Deferred();
}
if(!this.isClosed){
this.close();
}
dojo.publish(dijit._scopeName+"._editor.RichText::open",[this]);
this._content="";
if(arguments.length==1&&_e.nodeName){
this.domNode=_e;
}
var dn=this.domNode;
var _f;
if(dojo.isString(this.value)){
_f=this.value;
delete this.value;
dn.innerHTML="";
}else{
if(dn.nodeName&&dn.nodeName.toLowerCase()=="textarea"){
var ta=(this.textarea=dn);
this.name=ta.name;
_f=ta.value;
dn=this.domNode=dojo.doc.createElement("div");
dn.setAttribute("widgetId",this.id);
ta.removeAttribute("widgetId");
dn.cssText=ta.cssText;
dn.className+=" "+ta.className;
dojo.place(dn,ta,"before");
var _10=dojo.hitch(this,function(){
dojo.style(ta,{display:"block",position:"absolute",top:"-1000px"});
if(dojo.isIE){
var s=ta.style;
this.__overflow=s.overflow;
s.overflow="hidden";
}
});
if(dojo.isIE){
setTimeout(_10,10);
}else{
_10();
}
if(ta.form){
dojo.connect(ta.form,"onsubmit",this,function(){
ta.value=this.getValue();
});
}
}else{
_f=dijit._editor.getChildrenHtml(dn);
dn.innerHTML="";
}
}
var _11=dojo.contentBox(dn);
this._oldHeight=_11.h;
this._oldWidth=_11.w;
this.savedContent=_f;
if(dn.nodeName&&dn.nodeName=="LI"){
dn.innerHTML=" <br>";
}
this.header=dn.ownerDocument.createElement("div");
dn.appendChild(this.header);
this.editingArea=dn.ownerDocument.createElement("div");
dn.appendChild(this.editingArea);
this.footer=dn.ownerDocument.createElement("div");
dn.appendChild(this.footer);
if(this.name!==""&&(!dojo.config["useXDomain"]||dojo.config["allowXdRichTextSave"])){
var _12=dojo.byId(dijit._scopeName+"._editor.RichText.savedContent");
if(_12.value!==""){
var _13=_12.value.split(this._SEPARATOR),i=0,dat;
while((dat=_13[i++])){
var _14=dat.split(":");
if(_14[0]==this.name){
_f=_14[1];
_13.splice(i,1);
break;
}
}
}
dojo.addOnUnload(dojo.hitch(this,"_saveContent"));
}
this.isClosed=false;
var ifr=(this.editorObject=this.iframe=dojo.doc.createElement("iframe"));
ifr.id=this.id+"_iframe";
this._iframeSrc=this._getIframeDocTxt();
ifr.style.border="none";
ifr.style.width="100%";
if(this._layoutMode){
ifr.style.height="100%";
}else{
if(dojo.isIE>=7){
if(this.height){
ifr.style.height=this.height;
}
if(this.minHeight){
ifr.style.minHeight=this.minHeight;
}
}else{
ifr.style.height=this.height?this.height:this.minHeight;
}
}
ifr.frameBorder=0;
ifr._loadFunc=dojo.hitch(this,function(win){
this.window=win;
this.document=this.window.document;
if(dojo.isIE){
this._localizeEditorCommands();
}
this.onLoad(_f);
});
var s="javascript:parent."+dijit._scopeName+".byId(\""+this.id+"\")._iframeSrc";
ifr.setAttribute("src",s);
this.editingArea.appendChild(ifr);
if(dn.nodeName=="LI"){
dn.lastChild.style.marginTop="-1.2em";
}
dojo.addClass(this.domNode,this.baseClass);
},_local2NativeFormatNames:{},_native2LocalFormatNames:{},_getIframeDocTxt:function(){
var _15=dojo.getComputedStyle(this.domNode);
var _16="";
var _17=true;
if(dojo.isIE||(!this.height&&!dojo.isMoz)){
_16="<div id='dijitEditorBody'></div>";
_17=false;
}else{
if(dojo.isMoz){
this._cursorToStart=true;
_16="&nbsp;";
}
}
var _18=[_15.fontWeight,_15.fontSize,_15.fontFamily].join(" ");
var _19=_15.lineHeight;
if(_19.indexOf("px")>=0){
_19=parseFloat(_19)/parseFloat(_15.fontSize);
}else{
if(_19.indexOf("em")>=0){
_19=parseFloat(_19);
}else{
_19="normal";
}
}
var _1a="";
var _1b=this;
this.style.replace(/(^|;)\s*(line-|font-?)[^;]+/ig,function(_1c){
_1c=_1c.replace(/^;/ig,"")+";";
var s=_1c.split(":")[0];
if(s){
s=dojo.trim(s);
s=s.toLowerCase();
var i;
var sC="";
for(i=0;i<s.length;i++){
var c=s.charAt(i);
switch(c){
case "-":
i++;
c=s.charAt(i).toUpperCase();
default:
sC+=c;
}
}
dojo.style(_1b.domNode,sC,"");
}
_1a+=_1c+";";
});
var _1d=dojo.query("label[for=\""+this.id+"\"]");
return [this.isLeftToRight()?"<html>\n<head>\n":"<html dir='rtl'>\n<head>\n",(dojo.isMoz&&_1d.length?"<title>"+_1d[0].innerHTML+"</title>\n":""),"<meta http-equiv='Content-Type' content='text/html'>\n","<style>\n","\tbody,html {\n","\t\tbackground:transparent;\n","\t\tpadding: 1px 0 0 0;\n","\t\tmargin: -1px 0 0 0;\n",((dojo.isWebKit)?"\t\twidth: 100%;\n":""),((dojo.isWebKit)?"\t\theight: 100%;\n":""),"\t}\n","\tbody{\n","\t\ttop:0px;\n","\t\tleft:0px;\n","\t\tright:0px;\n","\t\tfont:",_18,";\n",((this.height||dojo.isOpera)?"":"\t\tposition: fixed;\n"),"\t\tmin-height:",this.minHeight,";\n","\t\tline-height:",_19,";\n","\t}\n","\tp{ margin: 1em 0; }\n",(!_17&&!this.height?"\tbody,html {overflow-y: hidden;}\n":""),"\t#dijitEditorBody{overflow-x: auto; overflow-y:"+(this.height?"auto;":"hidden;")+"}\n","\tli > ul:-moz-first-node, li > ol:-moz-first-node{ padding-top: 1.2em; }\n","\tli{ min-height:1.2em; }\n","</style>\n",this._applyEditingAreaStyleSheets(),"\n","</head>\n<body ",(_17?"id='dijitEditorBody' ":""),"onload='frameElement._loadFunc(window,document)' style='"+_1a+"'>",_16,"</body>\n</html>"].join("");
},_applyEditingAreaStyleSheets:function(){
var _1e=[];
if(this.styleSheets){
_1e=this.styleSheets.split(";");
this.styleSheets="";
}
_1e=_1e.concat(this.editingAreaStyleSheets);
this.editingAreaStyleSheets=[];
var _1f="",i=0,url;
while((url=_1e[i++])){
var _20=(new dojo._Url(dojo.global.location,url)).toString();
this.editingAreaStyleSheets.push(_20);
_1f+="<link rel=\"stylesheet\" type=\"text/css\" href=\""+_20+"\"/>";
}
return _1f;
},addStyleSheet:function(uri){
var url=uri.toString();
if(url.charAt(0)=="."||(url.charAt(0)!="/"&&!uri.host)){
url=(new dojo._Url(dojo.global.location,url)).toString();
}
if(dojo.indexOf(this.editingAreaStyleSheets,url)>-1){
return;
}
this.editingAreaStyleSheets.push(url);
this.onLoadDeferred.addCallback(dojo.hitch(function(){
if(this.document.createStyleSheet){
this.document.createStyleSheet(url);
}else{
var _21=this.document.getElementsByTagName("head")[0];
var _22=this.document.createElement("link");
_22.rel="stylesheet";
_22.type="text/css";
_22.href=url;
_21.appendChild(_22);
}
}));
},removeStyleSheet:function(uri){
var url=uri.toString();
if(url.charAt(0)=="."||(url.charAt(0)!="/"&&!uri.host)){
url=(new dojo._Url(dojo.global.location,url)).toString();
}
var _23=dojo.indexOf(this.editingAreaStyleSheets,url);
if(_23==-1){
return;
}
delete this.editingAreaStyleSheets[_23];
dojo.withGlobal(this.window,"query",dojo,["link:[href=\""+url+"\"]"]).orphan();
},disabled:false,_mozSettingProps:{"styleWithCSS":false},_setDisabledAttr:function(_24){
this.disabled=_24;
if(!this.isLoaded){
return;
}
_24=!!_24;
if(dojo.isIE||dojo.isWebKit||dojo.isOpera){
var _25=dojo.isIE&&(this.isLoaded||!this.focusOnLoad);
if(_25){
this.editNode.unselectable="on";
}
this.editNode.contentEditable=!_24;
if(_25){
var _26=this;
setTimeout(function(){
_26.editNode.unselectable="off";
},0);
}
}else{
try{
this.document.designMode=(_24?"off":"on");
}
catch(e){
return;
}
if(!_24&&this._mozSettingProps){
var ps=this._mozSettingProps;
for(var n in ps){
if(ps.hasOwnProperty(n)){
try{
this.document.execCommand(n,false,ps[n]);
}
catch(e2){
}
}
}
}
}
this._disabledOK=true;
},onLoad:function(_27){
if(!this.window.__registeredWindow){
this.window.__registeredWindow=true;
this._iframeRegHandle=dijit.registerIframe(this.iframe);
}
if(!dojo.isIE&&(this.height||dojo.isMoz)){
this.editNode=this.document.body;
}else{
this.editNode=this.document.body.firstChild;
var _28=this;
if(dojo.isIE){
var _29=(this.tabStop=dojo.doc.createElement("<div tabIndex=-1>"));
this.editingArea.appendChild(_29);
this.iframe.onfocus=function(){
_28.editNode.setActive();
};
}
}
this.focusNode=this.editNode;
var _2a=this.events.concat(this.captureEvents);
var ap=this.iframe?this.document:this.editNode;
dojo.forEach(_2a,function(_2b){
this.connect(ap,_2b.toLowerCase(),_2b);
},this);
if(dojo.isIE){
this.connect(this.document,"onmousedown","_onIEMouseDown");
this.editNode.style.zoom=1;
}else{
this.connect(this.document,"onmousedown",function(){
delete this._cursorToStart;
});
}
if(dojo.isWebKit){
this._webkitListener=this.connect(this.document,"onmouseup","onDisplayChanged");
}
if(dojo.isIE){
try{
this.document.execCommand("RespectVisibilityInDesign",true,null);
}
catch(e){
}
}
this.isLoaded=true;
this.set("disabled",this.disabled);
var _2c=dojo.hitch(this,function(){
this.setValue(_27);
if(this.onLoadDeferred){
this.onLoadDeferred.callback(true);
}
this.onDisplayChanged();
if(this.focusOnLoad){
dojo.addOnLoad(dojo.hitch(this,function(){
setTimeout(dojo.hitch(this,"focus"),this.updateInterval);
}));
}
this.savedContent=this.getValue(true);
});
if(this.setValueDeferred){
this.setValueDeferred.addCallback(_2c);
}else{
_2c();
}
},onKeyDown:function(e){
if(e.keyCode===dojo.keys.TAB&&this.isTabIndent){
dojo.stopEvent(e);
if(this.queryCommandEnabled((e.shiftKey?"outdent":"indent"))){
this.execCommand((e.shiftKey?"outdent":"indent"));
}
}
if(dojo.isIE){
if(e.keyCode==dojo.keys.TAB&&!this.isTabIndent){
if(e.shiftKey&&!e.ctrlKey&&!e.altKey){
this.iframe.focus();
}else{
if(!e.shiftKey&&!e.ctrlKey&&!e.altKey){
this.tabStop.focus();
}
}
}else{
if(e.keyCode===dojo.keys.BACKSPACE&&this.document.selection.type==="Control"){
dojo.stopEvent(e);
this.execCommand("delete");
}else{
if((65<=e.keyCode&&e.keyCode<=90)||(e.keyCode>=37&&e.keyCode<=40)){
e.charCode=e.keyCode;
this.onKeyPress(e);
}
}
}
}
return true;
},onKeyUp:function(e){
return;
},setDisabled:function(_2d){
dojo.deprecated("dijit.Editor::setDisabled is deprecated","use dijit.Editor::attr(\"disabled\",boolean) instead",2);
this.set("disabled",_2d);
},_setValueAttr:function(_2e){
this.setValue(_2e);
},_setDisableSpellCheckAttr:function(_2f){
if(this.document){
dojo.attr(this.document.body,"spellcheck",!_2f);
}else{
this.onLoadDeferred.addCallback(dojo.hitch(this,function(){
dojo.attr(this.document.body,"spellcheck",!_2f);
}));
}
this.disableSpellCheck=_2f;
},onKeyPress:function(e){
var c=(e.keyChar&&e.keyChar.toLowerCase())||e.keyCode,_30=this._keyHandlers[c],_31=arguments;
if(_30&&!e.altKey){
dojo.some(_30,function(h){
if(!(h.shift^e.shiftKey)&&!(h.ctrl^(e.ctrlKey||e.metaKey))){
if(!h.handler.apply(this,_31)){
e.preventDefault();
}
return true;
}
},this);
}
if(!this._onKeyHitch){
this._onKeyHitch=dojo.hitch(this,"onKeyPressed");
}
setTimeout(this._onKeyHitch,1);
return true;
},addKeyHandler:function(key,_32,_33,_34){
if(!dojo.isArray(this._keyHandlers[key])){
this._keyHandlers[key]=[];
}
this._keyHandlers[key].push({shift:_33||false,ctrl:_32||false,handler:_34});
},onKeyPressed:function(){
this.onDisplayChanged();
},onClick:function(e){
this.onDisplayChanged(e);
},_onIEMouseDown:function(e){
if(!this._focused&&!this.disabled){
this.focus();
}
},_onBlur:function(e){
this.inherited(arguments);
var _35=this.getValue(true);
if(_35!=this.savedContent){
this.onChange(_35);
this.savedContent=_35;
}
},_onFocus:function(e){
if(!this.disabled){
if(!this._disabledOK){
this.set("disabled",false);
}
this.inherited(arguments);
}
},blur:function(){
if(!dojo.isIE&&this.window.document.documentElement&&this.window.document.documentElement.focus){
this.window.document.documentElement.focus();
}else{
if(dojo.doc.body.focus){
dojo.doc.body.focus();
}
}
},focus:function(){
if(!this.isLoaded){
this.focusOnLoad=true;
return;
}
if(this._cursorToStart){
delete this._cursorToStart;
if(this.editNode.childNodes){
this.placeCursorAtStart();
return;
}
}
if(!dojo.isIE){
dijit.focus(this.iframe);
}else{
if(this.editNode&&this.editNode.focus){
this.iframe.fireEvent("onfocus",document.createEventObject());
}
}
},updateInterval:200,_updateTimer:null,onDisplayChanged:function(e){
if(this._updateTimer){
clearTimeout(this._updateTimer);
}
if(!this._updateHandler){
this._updateHandler=dojo.hitch(this,"onNormalizedDisplayChanged");
}
this._updateTimer=setTimeout(this._updateHandler,this.updateInterval);
},onNormalizedDisplayChanged:function(){
delete this._updateTimer;
},onChange:function(_36){
},_normalizeCommand:function(cmd,_37){
var _38=cmd.toLowerCase();
if(_38=="formatblock"){
if(dojo.isSafari&&_37===undefined){
_38="heading";
}
}else{
if(_38=="hilitecolor"&&!dojo.isMoz){
_38="backcolor";
}
}
return _38;
},_qcaCache:{},queryCommandAvailable:function(_39){
var ca=this._qcaCache[_39];
if(ca!==undefined){
return ca;
}
return (this._qcaCache[_39]=this._queryCommandAvailable(_39));
},_queryCommandAvailable:function(_3a){
var ie=1;
var _3b=1<<1;
var _3c=1<<2;
var _3d=1<<3;
var _3e=1<<4;
function _3f(_40){
return {ie:Boolean(_40&ie),mozilla:Boolean(_40&_3b),webkit:Boolean(_40&_3c),webkit420:Boolean(_40&_3e),opera:Boolean(_40&_3d)};
};
var _41=null;
switch(_3a.toLowerCase()){
case "bold":
case "italic":
case "underline":
case "subscript":
case "superscript":
case "fontname":
case "fontsize":
case "forecolor":
case "hilitecolor":
case "justifycenter":
case "justifyfull":
case "justifyleft":
case "justifyright":
case "delete":
case "selectall":
case "toggledir":
_41=_3f(_3b|ie|_3c|_3d);
break;
case "createlink":
case "unlink":
case "removeformat":
case "inserthorizontalrule":
case "insertimage":
case "insertorderedlist":
case "insertunorderedlist":
case "indent":
case "outdent":
case "formatblock":
case "inserthtml":
case "undo":
case "redo":
case "strikethrough":
case "tabindent":
_41=_3f(_3b|ie|_3d|_3e);
break;
case "blockdirltr":
case "blockdirrtl":
case "dirltr":
case "dirrtl":
case "inlinedirltr":
case "inlinedirrtl":
_41=_3f(ie);
break;
case "cut":
case "copy":
case "paste":
_41=_3f(ie|_3b|_3e);
break;
case "inserttable":
_41=_3f(_3b|ie);
break;
case "insertcell":
case "insertcol":
case "insertrow":
case "deletecells":
case "deletecols":
case "deleterows":
case "mergecells":
case "splitcell":
_41=_3f(ie|_3b);
break;
default:
return false;
}
return (dojo.isIE&&_41.ie)||(dojo.isMoz&&_41.mozilla)||(dojo.isWebKit&&_41.webkit)||(dojo.isWebKit>420&&_41.webkit420)||(dojo.isOpera&&_41.opera);
},execCommand:function(_42,_43){
var _44;
this.focus();
_42=this._normalizeCommand(_42,_43);
if(_43!==undefined){
if(_42=="heading"){
throw new Error("unimplemented");
}else{
if((_42=="formatblock")&&dojo.isIE){
_43="<"+_43+">";
}
}
}
var _45="_"+_42+"Impl";
if(this[_45]){
_44=this[_45](_43);
}else{
_43=arguments.length>1?_43:null;
if(_43||_42!="createlink"){
_44=this.document.execCommand(_42,false,_43);
}
}
this.onDisplayChanged();
return _44;
},queryCommandEnabled:function(_46){
if(this.disabled||!this._disabledOK){
return false;
}
_46=this._normalizeCommand(_46);
if(dojo.isMoz||dojo.isWebKit){
if(_46=="unlink"){
return this._sCall("hasAncestorElement",["a"]);
}else{
if(_46=="inserttable"){
return true;
}
}
}
if(dojo.isWebKit){
if(_46=="copy"){
_46="cut";
}else{
if(_46=="paste"){
return true;
}
}
}
var _47=dojo.isIE?this.document.selection.createRange():this.document;
try{
return _47.queryCommandEnabled(_46);
}
catch(e){
return false;
}
},queryCommandState:function(_48){
if(this.disabled||!this._disabledOK){
return false;
}
_48=this._normalizeCommand(_48);
try{
return this.document.queryCommandState(_48);
}
catch(e){
return false;
}
},queryCommandValue:function(_49){
if(this.disabled||!this._disabledOK){
return false;
}
var r;
_49=this._normalizeCommand(_49);
if(dojo.isIE&&_49=="formatblock"){
r=this._native2LocalFormatNames[this.document.queryCommandValue(_49)];
}else{
if(dojo.isMoz&&_49==="hilitecolor"){
var _4a;
try{
_4a=this.document.queryCommandValue("styleWithCSS");
}
catch(e){
_4a=false;
}
this.document.execCommand("styleWithCSS",false,true);
r=this.document.queryCommandValue(_49);
this.document.execCommand("styleWithCSS",false,_4a);
}else{
r=this.document.queryCommandValue(_49);
}
}
return r;
},_sCall:function(_4b,_4c){
return dojo.withGlobal(this.window,_4b,dijit._editor.selection,_4c);
},placeCursorAtStart:function(){
this.focus();
var _4d=false;
if(dojo.isMoz){
var _4e=this.editNode.firstChild;
while(_4e){
if(_4e.nodeType==3){
if(_4e.nodeValue.replace(/^\s+|\s+$/g,"").length>0){
_4d=true;
this._sCall("selectElement",[_4e]);
break;
}
}else{
if(_4e.nodeType==1){
_4d=true;
var tg=_4e.tagName?_4e.tagName.toLowerCase():"";
if(/br|input|img|base|meta|area|basefont|hr|link/.test(tg)){
this._sCall("selectElement",[_4e]);
}else{
this._sCall("selectElementChildren",[_4e]);
}
break;
}
}
_4e=_4e.nextSibling;
}
}else{
_4d=true;
this._sCall("selectElementChildren",[this.editNode]);
}
if(_4d){
this._sCall("collapse",[true]);
}
},placeCursorAtEnd:function(){
this.focus();
var _4f=false;
if(dojo.isMoz){
var _50=this.editNode.lastChild;
while(_50){
if(_50.nodeType==3){
if(_50.nodeValue.replace(/^\s+|\s+$/g,"").length>0){
_4f=true;
this._sCall("selectElement",[_50]);
break;
}
}else{
if(_50.nodeType==1){
_4f=true;
if(_50.lastChild){
this._sCall("selectElement",[_50.lastChild]);
}else{
this._sCall("selectElement",[_50]);
}
break;
}
}
_50=_50.previousSibling;
}
}else{
_4f=true;
this._sCall("selectElementChildren",[this.editNode]);
}
if(_4f){
this._sCall("collapse",[false]);
}
},getValue:function(_51){
if(this.textarea){
if(this.isClosed||!this.isLoaded){
return this.textarea.value;
}
}
return this._postFilterContent(null,_51);
},_getValueAttr:function(){
return this.getValue(true);
},setValue:function(_52){
if(!this.isLoaded){
this.onLoadDeferred.addCallback(dojo.hitch(this,function(){
this.setValue(_52);
}));
return;
}
this._cursorToStart=true;
if(this.textarea&&(this.isClosed||!this.isLoaded)){
this.textarea.value=_52;
}else{
_52=this._preFilterContent(_52);
var _53=this.isClosed?this.domNode:this.editNode;
if(!_52&&dojo.isWebKit){
_52="&nbsp;";
}
_53.innerHTML=_52;
this._preDomFilterContent(_53);
}
this.onDisplayChanged();
},replaceValue:function(_54){
if(this.isClosed){
this.setValue(_54);
}else{
if(this.window&&this.window.getSelection&&!dojo.isMoz){
this.setValue(_54);
}else{
if(this.window&&this.window.getSelection){
_54=this._preFilterContent(_54);
this.execCommand("selectall");
if(!_54){
this._cursorToStart=true;
_54="&nbsp;";
}
this.execCommand("inserthtml",_54);
this._preDomFilterContent(this.editNode);
}else{
if(this.document&&this.document.selection){
this.setValue(_54);
}
}
}
}
},_preFilterContent:function(_55){
var ec=_55;
dojo.forEach(this.contentPreFilters,function(ef){
if(ef){
ec=ef(ec);
}
});
return ec;
},_preDomFilterContent:function(dom){
dom=dom||this.editNode;
dojo.forEach(this.contentDomPreFilters,function(ef){
if(ef&&dojo.isFunction(ef)){
ef(dom);
}
},this);
},_postFilterContent:function(dom,_56){
var ec;
if(!dojo.isString(dom)){
dom=dom||this.editNode;
if(this.contentDomPostFilters.length){
if(_56){
dom=dojo.clone(dom);
}
dojo.forEach(this.contentDomPostFilters,function(ef){
dom=ef(dom);
});
}
ec=dijit._editor.getChildrenHtml(dom);
}else{
ec=dom;
}
if(!dojo.trim(ec.replace(/^\xA0\xA0*/,"").replace(/\xA0\xA0*$/,"")).length){
ec="";
}
dojo.forEach(this.contentPostFilters,function(ef){
ec=ef(ec);
});
return ec;
},_saveContent:function(e){
var _57=dojo.byId(dijit._scopeName+"._editor.RichText.savedContent");
if(_57.value){
_57.value+=this._SEPARATOR;
}
_57.value+=this.name+":"+this.getValue(true);
},escapeXml:function(str,_58){
str=str.replace(/&/gm,"&amp;").replace(/</gm,"&lt;").replace(/>/gm,"&gt;").replace(/"/gm,"&quot;");
if(!_58){
str=str.replace(/'/gm,"&#39;");
}
return str;
},getNodeHtml:function(_59){
dojo.deprecated("dijit.Editor::getNodeHtml is deprecated","use dijit._editor.getNodeHtml instead",2);
return dijit._editor.getNodeHtml(_59);
},getNodeChildrenHtml:function(dom){
dojo.deprecated("dijit.Editor::getNodeChildrenHtml is deprecated","use dijit._editor.getChildrenHtml instead",2);
return dijit._editor.getChildrenHtml(dom);
},close:function(_5a){
if(this.isClosed){
return false;
}
if(!arguments.length){
_5a=true;
}
this._content=this.getValue();
var _5b=(this.savedContent!=this._content);
if(this.interval){
clearInterval(this.interval);
}
if(this._webkitListener){
this.disconnect(this._webkitListener);
delete this._webkitListener;
}
if(dojo.isIE){
this.iframe.onfocus=null;
}
this.iframe._loadFunc=null;
if(this._iframeRegHandle){
dijit.unregisterIframe(this._iframeRegHandle);
delete this._iframeRegHandle;
}
if(this.textarea){
var s=this.textarea.style;
s.position="";
s.left=s.top="";
if(dojo.isIE){
s.overflow=this.__overflow;
this.__overflow=null;
}
this.textarea.value=_5a?this._content:this.savedContent;
dojo.destroy(this.domNode);
this.domNode=this.textarea;
}else{
this.domNode.innerHTML=_5a?this._content:this.savedContent;
}
delete this.iframe;
dojo.removeClass(this.domNode,this.baseClass);
this.isClosed=true;
this.isLoaded=false;
delete this.editNode;
delete this.focusNode;
if(this.window&&this.window._frameElement){
this.window._frameElement=null;
}
this.window=null;
this.document=null;
this.editingArea=null;
this.editorObject=null;
return _5b;
},destroy:function(){
if(!this.isClosed){
this.close(false);
}
this.inherited(arguments);
},_removeMozBogus:function(_5c){
return _5c.replace(/\stype="_moz"/gi,"").replace(/\s_moz_dirty=""/gi,"").replace(/_moz_resizing="(true|false)"/gi,"");
},_removeWebkitBogus:function(_5d){
_5d=_5d.replace(/\sclass="webkit-block-placeholder"/gi,"");
_5d=_5d.replace(/\sclass="apple-style-span"/gi,"");
return _5d;
},_normalizeFontStyle:function(_5e){
return _5e.replace(/<(\/)?strong([ \>])/gi,"<$1b$2").replace(/<(\/)?em([ \>])/gi,"<$1i$2");
},_preFixUrlAttributes:function(_5f){
return _5f.replace(/(?:(<a(?=\s).*?\shref=)("|')(.*?)\2)|(?:(<a\s.*?href=)([^"'][^ >]+))/gi,"$1$4$2$3$5$2 _djrealurl=$2$3$5$2").replace(/(?:(<img(?=\s).*?\ssrc=)("|')(.*?)\2)|(?:(<img\s.*?src=)([^"'][^ >]+))/gi,"$1$4$2$3$5$2 _djrealurl=$2$3$5$2");
},_inserthorizontalruleImpl:function(_60){
if(dojo.isIE){
return this._inserthtmlImpl("<hr>");
}
return this.document.execCommand("inserthorizontalrule",false,_60);
},_unlinkImpl:function(_61){
if((this.queryCommandEnabled("unlink"))&&(dojo.isMoz||dojo.isWebKit)){
var a=this._sCall("getAncestorElement",["a"]);
this._sCall("selectElement",[a]);
return this.document.execCommand("unlink",false,null);
}
return this.document.execCommand("unlink",false,_61);
},_hilitecolorImpl:function(_62){
var _63;
if(dojo.isMoz){
this.document.execCommand("styleWithCSS",false,true);
_63=this.document.execCommand("hilitecolor",false,_62);
this.document.execCommand("styleWithCSS",false,false);
}else{
_63=this.document.execCommand("hilitecolor",false,_62);
}
return _63;
},_backcolorImpl:function(_64){
if(dojo.isIE){
_64=_64?_64:null;
}
return this.document.execCommand("backcolor",false,_64);
},_forecolorImpl:function(_65){
if(dojo.isIE){
_65=_65?_65:null;
}
return this.document.execCommand("forecolor",false,_65);
},_inserthtmlImpl:function(_66){
_66=this._preFilterContent(_66);
var rv=true;
if(dojo.isIE){
var _67=this.document.selection.createRange();
if(this.document.selection.type.toUpperCase()=="CONTROL"){
var n=_67.item(0);
while(_67.length){
_67.remove(_67.item(0));
}
n.outerHTML=_66;
}else{
_67.pasteHTML(_66);
}
_67.select();
}else{
if(dojo.isMoz&&!_66.length){
this._sCall("remove");
}else{
rv=this.document.execCommand("inserthtml",false,_66);
}
}
return rv;
},getHeaderHeight:function(){
return this._getNodeChildrenHeight(this.header);
},getFooterHeight:function(){
return this._getNodeChildrenHeight(this.footer);
},_getNodeChildrenHeight:function(_68){
var h=0;
if(_68&&_68.childNodes){
var i;
for(i=0;i<_68.childNodes.length;i++){
var _69=dojo.position(_68.childNodes[i]);
h+=_69.h;
}
}
return h;
}});
}
