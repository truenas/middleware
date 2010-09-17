/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit._editor.plugins.EnterKeyHandling"]){
dojo._hasResource["dijit._editor.plugins.EnterKeyHandling"]=true;
dojo.provide("dijit._editor.plugins.EnterKeyHandling");
dojo.require("dojo.window");
dojo.declare("dijit._editor.plugins.EnterKeyHandling",dijit._editor._Plugin,{blockNodeForEnter:"BR",constructor:function(_1){
if(_1){
dojo.mixin(this,_1);
}
},setEditor:function(_2){
this.editor=_2;
if(this.blockNodeForEnter=="BR"){
if(dojo.isIE){
_2.contentDomPreFilters.push(dojo.hitch(this,"regularPsToSingleLinePs"));
_2.contentDomPostFilters.push(dojo.hitch(this,"singleLinePsToRegularPs"));
_2.onLoadDeferred.addCallback(dojo.hitch(this,"_fixNewLineBehaviorForIE"));
}else{
_2.onLoadDeferred.addCallback(dojo.hitch(this,function(d){
try{
this.editor.document.execCommand("insertBrOnReturn",false,true);
}
catch(e){
}
return d;
}));
}
}else{
if(this.blockNodeForEnter){
dojo["require"]("dijit._editor.range");
var h=dojo.hitch(this,this.handleEnterKey);
_2.addKeyHandler(13,0,0,h);
_2.addKeyHandler(13,0,1,h);
this.connect(this.editor,"onKeyPressed","onKeyPressed");
}
}
},onKeyPressed:function(e){
if(this._checkListLater){
if(dojo.withGlobal(this.editor.window,"isCollapsed",dijit)){
var _3=dojo.withGlobal(this.editor.window,"getAncestorElement",dijit._editor.selection,["LI"]);
if(!_3){
dijit._editor.RichText.prototype.execCommand.call(this.editor,"formatblock",this.blockNodeForEnter);
var _4=dojo.withGlobal(this.editor.window,"getAncestorElement",dijit._editor.selection,[this.blockNodeForEnter]);
if(_4){
_4.innerHTML=this.bogusHtmlContent;
if(dojo.isIE){
var r=this.editor.document.selection.createRange();
r.move("character",-1);
r.select();
}
}else{
console.error("onKeyPressed: Cannot find the new block node");
}
}else{
if(dojo.isMoz){
if(_3.parentNode.parentNode.nodeName=="LI"){
_3=_3.parentNode.parentNode;
}
}
var fc=_3.firstChild;
if(fc&&fc.nodeType==1&&(fc.nodeName=="UL"||fc.nodeName=="OL")){
_3.insertBefore(fc.ownerDocument.createTextNode(" "),fc);
var _5=dijit.range.create(this.editor.window);
_5.setStart(_3.firstChild,0);
var _6=dijit.range.getSelection(this.editor.window,true);
_6.removeAllRanges();
_6.addRange(_5);
}
}
}
this._checkListLater=false;
}
if(this._pressedEnterInBlock){
if(this._pressedEnterInBlock.previousSibling){
this.removeTrailingBr(this._pressedEnterInBlock.previousSibling);
}
delete this._pressedEnterInBlock;
}
},bogusHtmlContent:"&nbsp;",blockNodes:/^(?:P|H1|H2|H3|H4|H5|H6|LI)$/,handleEnterKey:function(e){
var _7,_8,_9,_a=this.editor.document,br;
if(e.shiftKey){
var _b=dojo.withGlobal(this.editor.window,"getParentElement",dijit._editor.selection);
var _c=dijit.range.getAncestor(_b,this.blockNodes);
if(_c){
if(!e.shiftKey&&_c.tagName=="LI"){
return true;
}
_7=dijit.range.getSelection(this.editor.window);
_8=_7.getRangeAt(0);
if(!_8.collapsed){
_8.deleteContents();
_7=dijit.range.getSelection(this.editor.window);
_8=_7.getRangeAt(0);
}
if(dijit.range.atBeginningOfContainer(_c,_8.startContainer,_8.startOffset)){
if(e.shiftKey){
br=_a.createElement("br");
_9=dijit.range.create(this.editor.window);
_c.insertBefore(br,_c.firstChild);
_9.setStartBefore(br.nextSibling);
_7.removeAllRanges();
_7.addRange(_9);
}else{
dojo.place(br,_c,"before");
}
}else{
if(dijit.range.atEndOfContainer(_c,_8.startContainer,_8.startOffset)){
_9=dijit.range.create(this.editor.window);
br=_a.createElement("br");
if(e.shiftKey){
_c.appendChild(br);
_c.appendChild(_a.createTextNode(" "));
_9.setStart(_c.lastChild,0);
}else{
dojo.place(br,_c,"after");
_9.setStartAfter(_c);
}
_7.removeAllRanges();
_7.addRange(_9);
}else{
return true;
}
}
}else{
dijit._editor.RichText.prototype.execCommand.call(this.editor,"inserthtml","<br>");
}
return false;
}
var _d=true;
_7=dijit.range.getSelection(this.editor.window);
_8=_7.getRangeAt(0);
if(!_8.collapsed){
_8.deleteContents();
_7=dijit.range.getSelection(this.editor.window);
_8=_7.getRangeAt(0);
}
var _e=dijit.range.getBlockAncestor(_8.endContainer,null,this.editor.editNode);
var _f=_e.blockNode;
if((this._checkListLater=(_f&&(_f.nodeName=="LI"||_f.parentNode.nodeName=="LI")))){
if(dojo.isMoz){
this._pressedEnterInBlock=_f;
}
if(/^(\s|&nbsp;|\xA0|<span\b[^>]*\bclass=['"]Apple-style-span['"][^>]*>(\s|&nbsp;|\xA0)<\/span>)?(<br>)?$/.test(_f.innerHTML)){
_f.innerHTML="";
if(dojo.isWebKit){
_9=dijit.range.create(this.editor.window);
_9.setStart(_f,0);
_7.removeAllRanges();
_7.addRange(_9);
}
this._checkListLater=false;
}
return true;
}
if(!_e.blockNode||_e.blockNode===this.editor.editNode){
try{
dijit._editor.RichText.prototype.execCommand.call(this.editor,"formatblock",this.blockNodeForEnter);
}
catch(e2){
}
_e={blockNode:dojo.withGlobal(this.editor.window,"getAncestorElement",dijit._editor.selection,[this.blockNodeForEnter]),blockContainer:this.editor.editNode};
if(_e.blockNode){
if(_e.blockNode!=this.editor.editNode&&(!(_e.blockNode.textContent||_e.blockNode.innerHTML).replace(/^\s+|\s+$/g,"").length)){
this.removeTrailingBr(_e.blockNode);
return false;
}
}else{
_e.blockNode=this.editor.editNode;
}
_7=dijit.range.getSelection(this.editor.window);
_8=_7.getRangeAt(0);
}
var _10=_a.createElement(this.blockNodeForEnter);
_10.innerHTML=this.bogusHtmlContent;
this.removeTrailingBr(_e.blockNode);
if(dijit.range.atEndOfContainer(_e.blockNode,_8.endContainer,_8.endOffset)){
if(_e.blockNode===_e.blockContainer){
_e.blockNode.appendChild(_10);
}else{
dojo.place(_10,_e.blockNode,"after");
}
_d=false;
_9=dijit.range.create(this.editor.window);
_9.setStart(_10,0);
_7.removeAllRanges();
_7.addRange(_9);
if(this.editor.height){
dojo.window.scrollIntoView(_10);
}
}else{
if(dijit.range.atBeginningOfContainer(_e.blockNode,_8.startContainer,_8.startOffset)){
dojo.place(_10,_e.blockNode,_e.blockNode===_e.blockContainer?"first":"before");
if(_10.nextSibling&&this.editor.height){
_9=dijit.range.create(this.editor.window);
_9.setStart(_10.nextSibling,0);
_7.removeAllRanges();
_7.addRange(_9);
dojo.window.scrollIntoView(_10.nextSibling);
}
_d=false;
}else{
if(_e.blockNode===_e.blockContainer){
_e.blockNode.appendChild(_10);
}else{
dojo.place(_10,_e.blockNode,"after");
}
_d=false;
if(_e.blockNode.style){
if(_10.style){
if(_e.blockNode.style.cssText){
_10.style.cssText=_e.blockNode.style.cssText;
}
}
}
var rs=_8.startContainer;
if(rs&&rs.nodeType==3){
var _11,_12;
var txt=rs.nodeValue;
var _13=_a.createTextNode(txt.substring(0,_8.startOffset));
var _14=_a.createTextNode(txt.substring(_8.startOffset,txt.length));
dojo.place(_13,rs,"before");
dojo.place(_14,rs,"after");
dojo.destroy(rs);
var _15=_13.parentNode;
while(_15!==_e.blockNode){
var tg=_15.tagName;
var _16=_a.createElement(tg);
if(_15.style){
if(_16.style){
if(_15.style.cssText){
_16.style.cssText=_15.style.cssText;
}
}
}
_11=_14;
while(_11){
_12=_11.nextSibling;
_16.appendChild(_11);
_11=_12;
}
dojo.place(_16,_15,"after");
_13=_15;
_14=_16;
_15=_15.parentNode;
}
_11=_14;
if(_11.nodeType==1||(_11.nodeType==3&&_11.nodeValue)){
_10.innerHTML="";
}
while(_11){
_12=_11.nextSibling;
_10.appendChild(_11);
_11=_12;
}
}
_9=dijit.range.create(this.editor.window);
_9.setStart(_10,0);
_7.removeAllRanges();
_7.addRange(_9);
if(this.editor.height){
dijit.scrollIntoView(_10);
}
if(dojo.isMoz){
this._pressedEnterInBlock=_e.blockNode;
}
}
}
return _d;
},removeTrailingBr:function(_17){
var _18=/P|DIV|LI/i.test(_17.tagName)?_17:dijit._editor.selection.getParentOfType(_17,["P","DIV","LI"]);
if(!_18){
return;
}
if(_18.lastChild){
if((_18.childNodes.length>1&&_18.lastChild.nodeType==3&&/^[\s\xAD]*$/.test(_18.lastChild.nodeValue))||_18.lastChild.tagName=="BR"){
dojo.destroy(_18.lastChild);
}
}
if(!_18.childNodes.length){
_18.innerHTML=this.bogusHtmlContent;
}
},_fixNewLineBehaviorForIE:function(d){
var doc=this.editor.document;
if(doc.__INSERTED_EDITIOR_NEWLINE_CSS===undefined){
var _19=dojo.create("style",{type:"text/css"},doc.getElementsByTagName("head")[0]);
_19.styleSheet.cssText="p{margin:0;}";
this.editor.document.__INSERTED_EDITIOR_NEWLINE_CSS=true;
}
return d;
},regularPsToSingleLinePs:function(_1a,_1b){
function _1c(el){
function _1d(_1e){
var _1f=_1e[0].ownerDocument.createElement("p");
_1e[0].parentNode.insertBefore(_1f,_1e[0]);
dojo.forEach(_1e,function(_20){
_1f.appendChild(_20);
});
};
var _21=0;
var _22=[];
var _23;
while(_21<el.childNodes.length){
_23=el.childNodes[_21];
if(_23.nodeType==3||(_23.nodeType==1&&_23.nodeName!="BR"&&dojo.style(_23,"display")!="block")){
_22.push(_23);
}else{
var _24=_23.nextSibling;
if(_22.length){
_1d(_22);
_21=(_21+1)-_22.length;
if(_23.nodeName=="BR"){
dojo.destroy(_23);
}
}
_22=[];
}
_21++;
}
if(_22.length){
_1d(_22);
}
};
function _25(el){
var _26=null;
var _27=[];
var _28=el.childNodes.length-1;
for(var i=_28;i>=0;i--){
_26=el.childNodes[i];
if(_26.nodeName=="BR"){
var _29=_26.ownerDocument.createElement("p");
dojo.place(_29,el,"after");
if(_27.length==0&&i!=_28){
_29.innerHTML="&nbsp;";
}
dojo.forEach(_27,function(_2a){
_29.appendChild(_2a);
});
dojo.destroy(_26);
_27=[];
}else{
_27.unshift(_26);
}
}
};
var _2b=[];
var ps=_1a.getElementsByTagName("p");
dojo.forEach(ps,function(p){
_2b.push(p);
});
dojo.forEach(_2b,function(p){
var _2c=p.previousSibling;
if((_2c)&&(_2c.nodeType==1)&&(_2c.nodeName=="P"||dojo.style(_2c,"display")!="block")){
var _2d=p.parentNode.insertBefore(this.document.createElement("p"),p);
_2d.innerHTML=_1b?"":"&nbsp;";
}
_25(p);
},this.editor);
_1c(_1a);
return _1a;
},singleLinePsToRegularPs:function(_2e){
function _2f(_30){
var ps=_30.getElementsByTagName("p");
var _31=[];
for(var i=0;i<ps.length;i++){
var p=ps[i];
var _32=false;
for(var k=0;k<_31.length;k++){
if(_31[k]===p.parentNode){
_32=true;
break;
}
}
if(!_32){
_31.push(p.parentNode);
}
}
return _31;
};
function _33(_34){
return (!_34.childNodes.length||_34.innerHTML=="&nbsp;");
};
var _35=_2f(_2e);
for(var i=0;i<_35.length;i++){
var _36=_35[i];
var _37=null;
var _38=_36.firstChild;
var _39=null;
while(_38){
if(_38.nodeType!=1||_38.tagName!="P"||(_38.getAttributeNode("style")||{}).specified){
_37=null;
}else{
if(_33(_38)){
_39=_38;
_37=null;
}else{
if(_37==null){
_37=_38;
}else{
if((!_37.lastChild||_37.lastChild.nodeName!="BR")&&(_38.firstChild)&&(_38.firstChild.nodeName!="BR")){
_37.appendChild(this.editor.document.createElement("br"));
}
while(_38.firstChild){
_37.appendChild(_38.firstChild);
}
_39=_38;
}
}
}
_38=_38.nextSibling;
if(_39){
dojo.destroy(_39);
_39=null;
}
}
}
return _2e;
}});
}
