/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.form.ComboBox"]){
dojo._hasResource["dijit.form.ComboBox"]=true;
dojo.provide("dijit.form.ComboBox");
dojo.require("dojo.window");
dojo.require("dojo.regexp");
dojo.require("dojo.data.util.simpleFetch");
dojo.require("dojo.data.util.filter");
dojo.require("dijit._CssStateMixin");
dojo.require("dijit.form._FormWidget");
dojo.require("dijit.form.ValidationTextBox");
dojo.requireLocalization("dijit.form","ComboBox",null,"ROOT,ar,ca,cs,da,de,el,es,fi,fr,he,hu,it,ja,ko,nb,nl,pl,pt,pt-pt,ro,ru,sk,sl,sv,th,tr,zh,zh-tw");
dojo.declare("dijit.form.ComboBoxMixin",null,{item:null,pageSize:Infinity,store:null,fetchProperties:{},query:{},autoComplete:true,highlightMatch:"first",searchDelay:100,searchAttr:"name",labelAttr:"",labelType:"text",queryExpr:"${0}*",ignoreCase:true,hasDownArrow:true,templateString:dojo.cache("dijit.form","templates/ComboBox.html","<div class=\"dijit dijitReset dijitInlineTable dijitLeft\"\n\tid=\"widget_${id}\"\n\tdojoAttachPoint=\"comboNode\" waiRole=\"combobox\"\n\t><div class='dijitReset dijitRight dijitButtonNode dijitArrowButton dijitDownArrowButton dijitArrowButtonContainer'\n\t\tdojoAttachPoint=\"downArrowNode\" waiRole=\"presentation\"\n\t\tdojoAttachEvent=\"onmousedown:_onArrowMouseDown\"\n\t\t><input class=\"dijitReset dijitInputField dijitArrowButtonInner\" value=\"&#9660; \" type=\"text\" tabIndex=\"-1\" readOnly waiRole=\"presentation\"\n\t\t\t${_buttonInputDisabled}\n\t/></div\n\t><div class='dijitReset dijitValidationContainer'\n\t\t><input class=\"dijitReset dijitInputField dijitValidationIcon dijitValidationInner\" value=\"&Chi; \" type=\"text\" tabIndex=\"-1\" readOnly waiRole=\"presentation\"\n\t/></div\n\t><div class=\"dijitReset dijitInputField dijitInputContainer\"\n\t\t><input class='dijitReset dijitInputInner' ${!nameAttrSetting} type=\"text\" autocomplete=\"off\"\n\t\t\tdojoAttachEvent=\"onkeypress:_onKeyPress,compositionend\"\n\t\t\tdojoAttachPoint=\"textbox,focusNode\" waiRole=\"textbox\" waiState=\"haspopup-true,autocomplete-list\"\n\t/></div\n></div>\n"),baseClass:"dijitTextBox dijitComboBox",cssStateNodes:{"downArrowNode":"dijitDownArrowButton"},_getCaretPos:function(_1){
var _2=0;
if(typeof (_1.selectionStart)=="number"){
_2=_1.selectionStart;
}else{
if(dojo.isIE){
var tr=dojo.doc.selection.createRange().duplicate();
var _3=_1.createTextRange();
tr.move("character",0);
_3.move("character",0);
try{
_3.setEndPoint("EndToEnd",tr);
_2=String(_3.text).replace(/\r/g,"").length;
}
catch(e){
}
}
}
return _2;
},_setCaretPos:function(_4,_5){
_5=parseInt(_5);
dijit.selectInputText(_4,_5,_5);
},_setDisabledAttr:function(_6){
this.inherited(arguments);
dijit.setWaiState(this.comboNode,"disabled",_6);
},_abortQuery:function(){
if(this.searchTimer){
clearTimeout(this.searchTimer);
this.searchTimer=null;
}
if(this._fetchHandle){
if(this._fetchHandle.abort){
this._fetchHandle.abort();
}
this._fetchHandle=null;
}
},_onInput:function(_7){
if(!this.searchTimer&&(_7.type=="paste"||_7.type=="input")&&this._lastInput!=this.textbox.value){
this.searchTimer=setTimeout(dojo.hitch(this,function(){
this._onKeyPress({charOrCode:229});
}),100);
}
this.inherited(arguments);
},_onKeyPress:function(_8){
var _9=_8.charOrCode;
if(_8.altKey||((_8.ctrlKey||_8.metaKey)&&(_9!="x"&&_9!="v"))||_9==dojo.keys.SHIFT){
return;
}
var _a=false;
var _b="_startSearchFromInput";
var pw=this._popupWidget;
var dk=dojo.keys;
var _c=null;
this._prev_key_backspace=false;
this._abortQuery();
if(this._isShowingNow){
pw.handleKey(_9);
_c=pw.getHighlightedOption();
}
switch(_9){
case dk.PAGE_DOWN:
case dk.DOWN_ARROW:
case dk.PAGE_UP:
case dk.UP_ARROW:
if(!this._isShowingNow){
_a=true;
_b="_startSearchAll";
}else{
this._announceOption(_c);
}
dojo.stopEvent(_8);
break;
case dk.ENTER:
if(_c){
if(_c==pw.nextButton){
this._nextSearch(1);
dojo.stopEvent(_8);
break;
}else{
if(_c==pw.previousButton){
this._nextSearch(-1);
dojo.stopEvent(_8);
break;
}
}
}else{
this._setBlurValue();
this._setCaretPos(this.focusNode,this.focusNode.value.length);
}
_8.preventDefault();
case dk.TAB:
var _d=this.get("displayedValue");
if(pw&&(_d==pw._messages["previousMessage"]||_d==pw._messages["nextMessage"])){
break;
}
if(_c){
this._selectOption();
}
if(this._isShowingNow){
this._lastQuery=null;
this._hideResultList();
}
break;
case " ":
if(_c){
dojo.stopEvent(_8);
this._selectOption();
this._hideResultList();
}else{
_a=true;
}
break;
case dk.ESCAPE:
if(this._isShowingNow){
dojo.stopEvent(_8);
this._hideResultList();
}
break;
case dk.DELETE:
case dk.BACKSPACE:
this._prev_key_backspace=true;
_a=true;
break;
default:
_a=typeof _9=="string"||_9==229;
}
if(_a){
this.item=undefined;
this.searchTimer=setTimeout(dojo.hitch(this,_b),1);
}
},_autoCompleteText:function(_e){
var fn=this.focusNode;
dijit.selectInputText(fn,fn.value.length);
var _f=this.ignoreCase?"toLowerCase":"substr";
if(_e[_f](0).indexOf(this.focusNode.value[_f](0))==0){
var _10=this._getCaretPos(fn);
if((_10+1)>fn.value.length){
fn.value=_e;
dijit.selectInputText(fn,_10);
}
}else{
fn.value=_e;
dijit.selectInputText(fn);
}
},_openResultList:function(_11,_12){
this._fetchHandle=null;
if(this.disabled||this.readOnly||(_12.query[this.searchAttr]!=this._lastQuery)){
return;
}
this._popupWidget.clearResultList();
if(!_11.length&&!this._maxOptions){
this._hideResultList();
return;
}
_12._maxOptions=this._maxOptions;
var _13=this._popupWidget.createOptions(_11,_12,dojo.hitch(this,"_getMenuLabelFromItem"));
this._showResultList();
if(_12.direction){
if(1==_12.direction){
this._popupWidget.highlightFirstOption();
}else{
if(-1==_12.direction){
this._popupWidget.highlightLastOption();
}
}
this._announceOption(this._popupWidget.getHighlightedOption());
}else{
if(this.autoComplete&&!this._prev_key_backspace&&!/^[*]+$/.test(_12.query[this.searchAttr])){
this._announceOption(_13[1]);
}
}
},_showResultList:function(){
this._hideResultList();
this.displayMessage("");
dojo.style(this._popupWidget.domNode,{width:"",height:""});
var _14=this.open();
var _15=dojo.marginBox(this._popupWidget.domNode);
this._popupWidget.domNode.style.overflow=((_14.h==_15.h)&&(_14.w==_15.w))?"hidden":"auto";
var _16=_14.w;
if(_14.h<this._popupWidget.domNode.scrollHeight){
_16+=16;
}
dojo.marginBox(this._popupWidget.domNode,{h:_14.h,w:Math.max(_16,this.domNode.offsetWidth)});
if(_16<this.domNode.offsetWidth){
this._popupWidget.domNode.parentNode.style.left=dojo.position(this.domNode,true).x+"px";
}
dijit.setWaiState(this.comboNode,"expanded","true");
},_hideResultList:function(){
this._abortQuery();
if(this._isShowingNow){
dijit.popup.close(this._popupWidget);
this._isShowingNow=false;
dijit.setWaiState(this.comboNode,"expanded","false");
dijit.removeWaiState(this.focusNode,"activedescendant");
}
},_setBlurValue:function(){
var _17=this.get("displayedValue");
var pw=this._popupWidget;
if(pw&&(_17==pw._messages["previousMessage"]||_17==pw._messages["nextMessage"])){
this._setValueAttr(this._lastValueReported,true);
}else{
if(typeof this.item=="undefined"){
this.item=null;
this.set("displayedValue",_17);
}else{
if(this.value!=this._lastValueReported){
dijit.form._FormValueWidget.prototype._setValueAttr.call(this,this.value,true);
}
this._refreshState();
}
}
},_onBlur:function(){
this._hideResultList();
this.inherited(arguments);
},_setItemAttr:function(_18,_19,_1a){
if(!_1a){
_1a=this.labelFunc(_18,this.store);
}
this.value=this._getValueField()!=this.searchAttr?this.store.getIdentity(_18):_1a;
this.item=_18;
dijit.form.ComboBox.superclass._setValueAttr.call(this,this.value,_19,_1a);
},_announceOption:function(_1b){
if(!_1b){
return;
}
var _1c;
if(_1b==this._popupWidget.nextButton||_1b==this._popupWidget.previousButton){
_1c=_1b.innerHTML;
this.item=undefined;
this.value="";
}else{
_1c=this.labelFunc(_1b.item,this.store);
this.set("item",_1b.item,false,_1c);
}
this.focusNode.value=this.focusNode.value.substring(0,this._lastInput.length);
dijit.setWaiState(this.focusNode,"activedescendant",dojo.attr(_1b,"id"));
this._autoCompleteText(_1c);
},_selectOption:function(evt){
if(evt){
this._announceOption(evt.target);
}
this._hideResultList();
this._setCaretPos(this.focusNode,this.focusNode.value.length);
dijit.form._FormValueWidget.prototype._setValueAttr.call(this,this.value,true);
},_onArrowMouseDown:function(evt){
if(this.disabled||this.readOnly){
return;
}
dojo.stopEvent(evt);
this.focus();
if(this._isShowingNow){
this._hideResultList();
}else{
this._startSearchAll();
}
},_startSearchAll:function(){
this._startSearch("");
},_startSearchFromInput:function(){
this._startSearch(this.focusNode.value.replace(/([\\\*\?])/g,"\\$1"));
},_getQueryString:function(_1d){
return dojo.string.substitute(this.queryExpr,[_1d]);
},_startSearch:function(key){
if(!this._popupWidget){
var _1e=this.id+"_popup";
this._popupWidget=new dijit.form._ComboBoxMenu({onChange:dojo.hitch(this,this._selectOption),id:_1e,dir:this.dir});
dijit.removeWaiState(this.focusNode,"activedescendant");
dijit.setWaiState(this.textbox,"owns",_1e);
}
var _1f=dojo.clone(this.query);
this._lastInput=key;
this._lastQuery=_1f[this.searchAttr]=this._getQueryString(key);
this.searchTimer=setTimeout(dojo.hitch(this,function(_20,_21){
this.searchTimer=null;
var _22={queryOptions:{ignoreCase:this.ignoreCase,deep:true},query:_20,onBegin:dojo.hitch(this,"_setMaxOptions"),onComplete:dojo.hitch(this,"_openResultList"),onError:function(_23){
_21._fetchHandle=null;
console.error("dijit.form.ComboBox: "+_23);
dojo.hitch(_21,"_hideResultList")();
},start:0,count:this.pageSize};
dojo.mixin(_22,_21.fetchProperties);
this._fetchHandle=_21.store.fetch(_22);
var _24=function(_25,_26){
_25.start+=_25.count*_26;
_25.direction=_26;
this._fetchHandle=this.store.fetch(_25);
};
this._nextSearch=this._popupWidget.onPage=dojo.hitch(this,_24,this._fetchHandle);
},_1f,this),this.searchDelay);
},_setMaxOptions:function(_27,_28){
this._maxOptions=_27;
},_getValueField:function(){
return this.searchAttr;
},compositionend:function(evt){
this._onKeyPress({charOrCode:229});
},constructor:function(){
this.query={};
this.fetchProperties={};
},postMixInProperties:function(){
if(!this.store){
var _29=this.srcNodeRef;
this.store=new dijit.form._ComboBoxDataStore(_29);
if(!("value" in this.params)){
var _2a=this.store.fetchSelectedItem();
if(_2a){
var _2b=this._getValueField();
this.value=_2b!=this.searchAttr?this.store.getValue(_2a,_2b):this.labelFunc(_2a,this.store);
}
}
}
this.inherited(arguments);
},postCreate:function(){
if(!this.hasDownArrow){
this.downArrowNode.style.display="none";
}
var _2c=dojo.query("label[for=\""+this.id+"\"]");
if(_2c.length){
_2c[0].id=(this.id+"_label");
var cn=this.comboNode;
dijit.setWaiState(cn,"labelledby",_2c[0].id);
}
this.inherited(arguments);
},uninitialize:function(){
if(this._popupWidget&&!this._popupWidget._destroyed){
this._hideResultList();
this._popupWidget.destroy();
}
this.inherited(arguments);
},_getMenuLabelFromItem:function(_2d){
var _2e=this.labelAttr?this.store.getValue(_2d,this.labelAttr):this.labelFunc(_2d,this.store);
var _2f=this.labelType;
if(this.highlightMatch!="none"&&this.labelType=="text"&&this._lastInput){
_2e=this.doHighlight(_2e,this._escapeHtml(this._lastInput));
_2f="html";
}
return {html:_2f=="html",label:_2e};
},doHighlight:function(_30,_31){
var _32="i"+(this.highlightMatch=="all"?"g":"");
var _33=this._escapeHtml(_30);
_31=dojo.regexp.escapeString(_31);
var ret=_33.replace(new RegExp("(^|\\s)("+_31+")",_32),"$1<span class=\"dijitComboBoxHighlightMatch\">$2</span>");
return ret;
},_escapeHtml:function(str){
str=String(str).replace(/&/gm,"&amp;").replace(/</gm,"&lt;").replace(/>/gm,"&gt;").replace(/"/gm,"&quot;");
return str;
},open:function(){
this._isShowingNow=true;
return dijit.popup.open({popup:this._popupWidget,around:this.domNode,parent:this});
},reset:function(){
this.item=null;
this.inherited(arguments);
},labelFunc:function(_34,_35){
return _35.getValue(_34,this.searchAttr).toString();
}});
dojo.declare("dijit.form._ComboBoxMenu",[dijit._Widget,dijit._Templated,dijit._CssStateMixin],{templateString:"<ul class='dijitReset dijitMenu' dojoAttachEvent='onmousedown:_onMouseDown,onmouseup:_onMouseUp,onmouseover:_onMouseOver,onmouseout:_onMouseOut' tabIndex='-1' style='overflow: \"auto\"; overflow-x: \"hidden\";'>"+"<li class='dijitMenuItem dijitMenuPreviousButton' dojoAttachPoint='previousButton' waiRole='option'></li>"+"<li class='dijitMenuItem dijitMenuNextButton' dojoAttachPoint='nextButton' waiRole='option'></li>"+"</ul>",_messages:null,baseClass:"dijitComboBoxMenu",postMixInProperties:function(){
this._messages=dojo.i18n.getLocalization("dijit.form","ComboBox",this.lang);
this.inherited(arguments);
},_setValueAttr:function(_36){
this.value=_36;
this.onChange(_36);
},onChange:function(_37){
},onPage:function(_38){
},postCreate:function(){
this.previousButton.innerHTML=this._messages["previousMessage"];
this.nextButton.innerHTML=this._messages["nextMessage"];
this.inherited(arguments);
},onClose:function(){
this._blurOptionNode();
},_createOption:function(_39,_3a){
var _3b=_3a(_39);
var _3c=dojo.doc.createElement("li");
dijit.setWaiRole(_3c,"option");
if(_3b.html){
_3c.innerHTML=_3b.label;
}else{
_3c.appendChild(dojo.doc.createTextNode(_3b.label));
}
if(_3c.innerHTML==""){
_3c.innerHTML="&nbsp;";
}
_3c.item=_39;
return _3c;
},createOptions:function(_3d,_3e,_3f){
this.previousButton.style.display=(_3e.start==0)?"none":"";
dojo.attr(this.previousButton,"id",this.id+"_prev");
dojo.forEach(_3d,function(_40,i){
var _41=this._createOption(_40,_3f);
_41.className="dijitReset dijitMenuItem"+(this.isLeftToRight()?"":" dijitMenuItemRtl");
dojo.attr(_41,"id",this.id+i);
this.domNode.insertBefore(_41,this.nextButton);
},this);
var _42=false;
if(_3e._maxOptions&&_3e._maxOptions!=-1){
if((_3e.start+_3e.count)<_3e._maxOptions){
_42=true;
}else{
if((_3e.start+_3e.count)>_3e._maxOptions&&_3e.count==_3d.length){
_42=true;
}
}
}else{
if(_3e.count==_3d.length){
_42=true;
}
}
this.nextButton.style.display=_42?"":"none";
dojo.attr(this.nextButton,"id",this.id+"_next");
return this.domNode.childNodes;
},clearResultList:function(){
while(this.domNode.childNodes.length>2){
this.domNode.removeChild(this.domNode.childNodes[this.domNode.childNodes.length-2]);
}
},_onMouseDown:function(evt){
dojo.stopEvent(evt);
},_onMouseUp:function(evt){
if(evt.target===this.domNode||!this._highlighted_option){
return;
}else{
if(evt.target==this.previousButton){
this.onPage(-1);
}else{
if(evt.target==this.nextButton){
this.onPage(1);
}else{
var tgt=evt.target;
while(!tgt.item){
tgt=tgt.parentNode;
}
this._setValueAttr({target:tgt},true);
}
}
}
},_onMouseOver:function(evt){
if(evt.target===this.domNode){
return;
}
var tgt=evt.target;
if(!(tgt==this.previousButton||tgt==this.nextButton)){
while(!tgt.item){
tgt=tgt.parentNode;
}
}
this._focusOptionNode(tgt);
},_onMouseOut:function(evt){
if(evt.target===this.domNode){
return;
}
this._blurOptionNode();
},_focusOptionNode:function(_43){
if(this._highlighted_option!=_43){
this._blurOptionNode();
this._highlighted_option=_43;
dojo.addClass(this._highlighted_option,"dijitMenuItemSelected");
}
},_blurOptionNode:function(){
if(this._highlighted_option){
dojo.removeClass(this._highlighted_option,"dijitMenuItemSelected");
this._highlighted_option=null;
}
},_highlightNextOption:function(){
if(!this.getHighlightedOption()){
var fc=this.domNode.firstChild;
this._focusOptionNode(fc.style.display=="none"?fc.nextSibling:fc);
}else{
var ns=this._highlighted_option.nextSibling;
if(ns&&ns.style.display!="none"){
this._focusOptionNode(ns);
}else{
this.highlightFirstOption();
}
}
dojo.window.scrollIntoView(this._highlighted_option);
},highlightFirstOption:function(){
var _44=this.domNode.firstChild;
var _45=_44.nextSibling;
this._focusOptionNode(_45.style.display=="none"?_44:_45);
dojo.window.scrollIntoView(this._highlighted_option);
},highlightLastOption:function(){
this._focusOptionNode(this.domNode.lastChild.previousSibling);
dojo.window.scrollIntoView(this._highlighted_option);
},_highlightPrevOption:function(){
if(!this.getHighlightedOption()){
var lc=this.domNode.lastChild;
this._focusOptionNode(lc.style.display=="none"?lc.previousSibling:lc);
}else{
var ps=this._highlighted_option.previousSibling;
if(ps&&ps.style.display!="none"){
this._focusOptionNode(ps);
}else{
this.highlightLastOption();
}
}
dojo.window.scrollIntoView(this._highlighted_option);
},_page:function(up){
var _46=0;
var _47=this.domNode.scrollTop;
var _48=dojo.style(this.domNode,"height");
if(!this.getHighlightedOption()){
this._highlightNextOption();
}
while(_46<_48){
if(up){
if(!this.getHighlightedOption().previousSibling||this._highlighted_option.previousSibling.style.display=="none"){
break;
}
this._highlightPrevOption();
}else{
if(!this.getHighlightedOption().nextSibling||this._highlighted_option.nextSibling.style.display=="none"){
break;
}
this._highlightNextOption();
}
var _49=this.domNode.scrollTop;
_46+=(_49-_47)*(up?-1:1);
_47=_49;
}
},pageUp:function(){
this._page(true);
},pageDown:function(){
this._page(false);
},getHighlightedOption:function(){
var ho=this._highlighted_option;
return (ho&&ho.parentNode)?ho:null;
},handleKey:function(key){
switch(key){
case dojo.keys.DOWN_ARROW:
this._highlightNextOption();
break;
case dojo.keys.PAGE_DOWN:
this.pageDown();
break;
case dojo.keys.UP_ARROW:
this._highlightPrevOption();
break;
case dojo.keys.PAGE_UP:
this.pageUp();
break;
}
}});
dojo.declare("dijit.form.ComboBox",[dijit.form.ValidationTextBox,dijit.form.ComboBoxMixin],{_setValueAttr:function(_4a,_4b,_4c){
this.item=null;
if(!_4a){
_4a="";
}
dijit.form.ValidationTextBox.prototype._setValueAttr.call(this,_4a,_4b,_4c);
}});
dojo.declare("dijit.form._ComboBoxDataStore",null,{constructor:function(_4d){
this.root=_4d;
if(_4d.tagName!="SELECT"&&_4d.firstChild){
_4d=dojo.query("select",_4d);
if(_4d.length>0){
_4d=_4d[0];
}else{
this.root.innerHTML="<SELECT>"+this.root.innerHTML+"</SELECT>";
_4d=this.root.firstChild;
}
this.root=_4d;
}
dojo.query("> option",_4d).forEach(function(_4e){
_4e.innerHTML=dojo.trim(_4e.innerHTML);
});
},getValue:function(_4f,_50,_51){
return (_50=="value")?_4f.value:(_4f.innerText||_4f.textContent||"");
},isItemLoaded:function(_52){
return true;
},getFeatures:function(){
return {"dojo.data.api.Read":true,"dojo.data.api.Identity":true};
},_fetchItems:function(_53,_54,_55){
if(!_53.query){
_53.query={};
}
if(!_53.query.name){
_53.query.name="";
}
if(!_53.queryOptions){
_53.queryOptions={};
}
var _56=dojo.data.util.filter.patternToRegExp(_53.query.name,_53.queryOptions.ignoreCase),_57=dojo.query("> option",this.root).filter(function(_58){
return (_58.innerText||_58.textContent||"").match(_56);
});
if(_53.sort){
_57.sort(dojo.data.util.sorter.createSortFunction(_53.sort,this));
}
_54(_57,_53);
},close:function(_59){
return;
},getLabel:function(_5a){
return _5a.innerHTML;
},getIdentity:function(_5b){
return dojo.attr(_5b,"value");
},fetchItemByIdentity:function(_5c){
var _5d=dojo.query("> option[value='"+_5c.identity+"']",this.root)[0];
_5c.onItem(_5d);
},fetchSelectedItem:function(){
var _5e=this.root,si=_5e.selectedIndex;
return typeof si=="number"?dojo.query("> option:nth-child("+(si!=-1?si+1:1)+")",_5e)[0]:null;
}});
dojo.extend(dijit.form._ComboBoxDataStore,dojo.data.util.simpleFetch);
}
