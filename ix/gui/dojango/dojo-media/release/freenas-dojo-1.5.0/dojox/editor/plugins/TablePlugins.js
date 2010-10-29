/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.editor.plugins.TablePlugins"]){
dojo._hasResource["dojox.editor.plugins.TablePlugins"]=true;
dojo.provide("dojox.editor.plugins.TablePlugins");
dojo.require("dijit._editor._Plugin");
dojo.require("dijit._editor.selection");
dojo.require("dijit.Menu");
dojo.require("dojo.i18n");
dojo.requireLocalization("dojox.editor.plugins","TableDialog",null,"ROOT,ar,ca,cs,da,de,el,es,fi,fr,he,hu,it,ja,ko,nb,nl,pl,pt,pt-pt,ro,ru,sk,sl,sv,th,tr,zh,zh-tw");
dojo.experimental("dojox.editor.plugins.TablePlugins");
dojo.declare("dojox.editor.plugins._TableHandler",dijit._editor._Plugin,{tablesConnected:false,currentlyAvailable:false,alwaysAvailable:false,availableCurrentlySet:false,initialized:false,tableData:null,shiftKeyDown:false,editorDomNode:null,undoEnabled:true,refCount:0,doMixins:function(){
dojo.mixin(this.editor,{getAncestorElement:function(_1){
return dojo.withGlobal(this.window,"getAncestorElement",dijit._editor.selection,[_1]);
},hasAncestorElement:function(_2){
return dojo.withGlobal(this.window,"hasAncestorElement",dijit._editor.selection,[_2]);
},selectElement:function(_3){
dojo.withGlobal(this.window,"selectElement",dijit._editor.selection,[_3]);
},byId:function(id){
return dojo.withGlobal(this.window,"byId",dojo,[id]);
},query:function(_4,_5,_6){
var ar=dojo.withGlobal(this.window,"query",dojo,[_4,_5]);
return (_6)?ar[0]:ar;
}});
},initialize:function(_7){
this.refCount++;
_7.customUndo=true;
if(this.initialized){
return;
}
this.initialized=true;
this.editor=_7;
this.editor._tablePluginHandler=this;
_7.onLoadDeferred.addCallback(dojo.hitch(this,function(){
this.editorDomNode=this.editor.editNode||this.editor.iframe.document.body.firstChild;
this._myListeners=[];
this._myListeners.push(dojo.connect(this.editorDomNode,"mouseup",this.editor,"onClick"));
this._myListeners.push(dojo.connect(this.editor,"onDisplayChanged",this,"checkAvailable"));
this._myListeners.push(dojo.connect(this.editor,"onBlur",this,"checkAvailable"));
this.doMixins();
this.connectDraggable();
}));
},getTableInfo:function(_8){
if(_8){
this._tempStoreTableData(false);
}
if(this.tableData){
return this.tableData;
}
var tr,_9,td,_a,_b,_c,_d,_e;
td=this.editor.getAncestorElement("td");
if(td){
tr=td.parentNode;
}
_b=this.editor.getAncestorElement("table");
_a=dojo.query("td",_b);
_a.forEach(function(d,i){
if(td==d){
_d=i;
}
});
_9=dojo.query("tr",_b);
_9.forEach(function(r,i){
if(tr==r){
_e=i;
}
});
_c=_a.length/_9.length;
var o={tbl:_b,td:td,tr:tr,trs:_9,tds:_a,rows:_9.length,cols:_c,tdIndex:_d,trIndex:_e,colIndex:_d%_c};
this.tableData=o;
this._tempStoreTableData(500);
return this.tableData;
},connectDraggable:function(){
if(!dojo.isIE){
return;
}
this.editorDomNode.ondragstart=dojo.hitch(this,"onDragStart");
this.editorDomNode.ondragend=dojo.hitch(this,"onDragEnd");
},onDragStart:function(){
var e=window.event;
if(!e.srcElement.id){
e.srcElement.id="tbl_"+(new Date().getTime());
}
},onDragEnd:function(){
var e=window.event;
var _f=e.srcElement;
var id=_f.id;
var win=this.editor.window;
if(_f.tagName.toLowerCase()=="table"){
setTimeout(function(){
var _10=dojo.withGlobal(win,"byId",dojo,[id]);
dojo.removeAttr(_10,"align");
},100);
}
},checkAvailable:function(){
if(this.availableCurrentlySet){
return this.currentlyAvailable;
}
if(!this.editor){
return false;
}
if(this.alwaysAvailable){
return true;
}
this.currentlyAvailable=this.editor._focused?this.editor.hasAncestorElement("table"):false;
if(this.currentlyAvailable){
this.connectTableKeys();
}else{
this.disconnectTableKeys();
}
this._tempAvailability(500);
dojo.publish(this.editor.id+"_tablePlugins",[this.currentlyAvailable]);
return this.currentlyAvailable;
},_prepareTable:function(tbl){
var tds=this.editor.query("td",tbl);
console.log("prep:",tds,tbl);
if(!tds[0].id){
tds.forEach(function(td,i){
if(!td.id){
td.id="tdid"+i+this.getTimeStamp();
}
},this);
}
return tds;
},getTimeStamp:function(){
return Math.floor(new Date().getTime()*1e-8);
},_tempStoreTableData:function(_11){
if(_11===true){
}else{
if(_11===false){
this.tableData=null;
}else{
if(_11===undefined){
console.warn("_tempStoreTableData must be passed an argument");
}else{
setTimeout(dojo.hitch(this,function(){
this.tableData=null;
}),_11);
}
}
}
},_tempAvailability:function(_12){
if(_12===true){
this.availableCurrentlySet=true;
}else{
if(_12===false){
this.availableCurrentlySet=false;
}else{
if(_12===undefined){
console.warn("_tempAvailability must be passed an argument");
}else{
this.availableCurrentlySet=true;
setTimeout(dojo.hitch(this,function(){
this.availableCurrentlySet=false;
}),_12);
}
}
}
},connectTableKeys:function(){
if(this.tablesConnected){
return;
}
this.tablesConnected=true;
var _13=(this.editor.iframe)?this.editor.document:this.editor.editNode;
this.cnKeyDn=dojo.connect(_13,"onkeydown",this,"onKeyDown");
this.cnKeyUp=dojo.connect(_13,"onkeyup",this,"onKeyUp");
this._myListeners.push(dojo.connect(_13,"onkeypress",this,"onKeyUp"));
},disconnectTableKeys:function(){
dojo.disconnect(this.cnKeyDn);
dojo.disconnect(this.cnKeyUp);
this.tablesConnected=false;
},onKeyDown:function(evt){
var key=evt.keyCode;
if(key==16){
this.shiftKeyDown=true;
}
if(key==9){
var o=this.getTableInfo();
o.tdIndex=(this.shiftKeyDown)?o.tdIndex-1:tabTo=o.tdIndex+1;
if(o.tdIndex>=0&&o.tdIndex<o.tds.length){
this.editor.selectElement(o.tds[o.tdIndex]);
this.currentlyAvailable=true;
this._tempAvailability(true);
this._tempStoreTableData(true);
this.stopEvent=true;
}else{
this.stopEvent=false;
this.onDisplayChanged();
}
if(this.stopEvent){
dojo.stopEvent(evt);
}
}
},onKeyUp:function(evt){
var key=evt.keyCode;
if(key==16){
this.shiftKeyDown=false;
}
if(key==37||key==38||key==39||key==40){
this.onDisplayChanged();
}
if(key==9&&this.stopEvent){
dojo.stopEvent(evt);
}
},onDisplayChanged:function(){
this.currentlyAvailable=false;
this._tempStoreTableData(false);
this._tempAvailability(false);
this.checkAvailable();
},uninitialize:function(_14){
if(this.editor==_14){
this.refCount--;
if(!this.refCount&&this.initialized){
if(this.tablesConnected){
this.disconnectTableKeys();
}
this.initialized=false;
dojo.forEach(this._myListeners,function(l){
dojo.disconnect(l);
});
delete this._myListeners;
delete this.editor._tablePluginHandler;
delete this.editor;
}
this.inherited(arguments);
}
}});
dojo.declare("dojox.editor.plugins.TablePlugins",dijit._editor._Plugin,{iconClassPrefix:"editorIcon",useDefaultCommand:false,buttonClass:dijit.form.Button,commandName:"",label:"",alwaysAvailable:false,undoEnabled:true,onDisplayChanged:function(_15){
if(!this.alwaysAvailable){
this.available=_15;
this.button.set("disabled",!this.available);
}
},setEditor:function(_16){
this.editor=_16;
this.editor.customUndo=true;
this.inherited(arguments);
this._availableTopic=dojo.subscribe(this.editor.id+"_tablePlugins",this,"onDisplayChanged");
this.onEditorLoaded();
},onEditorLoaded:function(){
if(!this.editor._tablePluginHandler){
var _17=new dojox.editor.plugins._TableHandler();
_17.initialize(this.editor);
}else{
this.editor._tablePluginHandler.initialize(this.editor);
}
},selectTable:function(){
var o=this.getTableInfo();
if(o&&o.tbl){
dojo.withGlobal(this.editor.window,"selectElement",dijit._editor.selection,[o.tbl]);
}
},_initButton:function(){
this.command=this.commandName;
this.label=this.editor.commands[this.command]=this._makeTitle(this.command);
this.inherited(arguments);
delete this.command;
this.connect(this.button,"onClick","modTable");
this.onDisplayChanged(false);
},modTable:function(cmd,_18){
this.begEdit();
var o=this.getTableInfo();
var sw=(dojo.isString(cmd))?cmd:this.commandName;
var r,c,i;
var _19=false;
if(dojo.isIE){
this.editor.focus();
}
switch(sw){
case "insertTableRowBefore":
r=o.tbl.insertRow(o.trIndex);
for(i=0;i<o.cols;i++){
c=r.insertCell(-1);
c.innerHTML="&nbsp;";
}
break;
case "insertTableRowAfter":
r=o.tbl.insertRow(o.trIndex+1);
for(i=0;i<o.cols;i++){
c=r.insertCell(-1);
c.innerHTML="&nbsp;";
}
break;
case "insertTableColumnBefore":
o.trs.forEach(function(r){
c=r.insertCell(o.colIndex);
c.innerHTML="&nbsp;";
});
_19=true;
break;
case "insertTableColumnAfter":
o.trs.forEach(function(r){
c=r.insertCell(o.colIndex+1);
c.innerHTML="&nbsp;";
});
_19=true;
break;
case "deleteTableRow":
o.tbl.deleteRow(o.trIndex);
console.log("TableInfo:",this.getTableInfo());
break;
case "deleteTableColumn":
o.trs.forEach(function(tr){
tr.deleteCell(o.colIndex);
});
_19=true;
break;
case "modifyTable":
break;
case "insertTable":
break;
}
if(_19){
this.makeColumnsEven();
}
this.endEdit();
},begEdit:function(){
if(this.editor._tablePluginHandler.undoEnabled){
if(this.editor.customUndo){
this.editor.beginEditing();
}else{
this.valBeforeUndo=this.editor.getValue();
}
}
},endEdit:function(){
if(this.editor._tablePluginHandler.undoEnabled){
if(this.editor.customUndo){
this.editor.endEditing();
}else{
var _1a=this.editor.getValue();
this.editor.setValue(this.valBeforeUndo);
this.editor.replaceValue(_1a);
}
this.editor.onDisplayChanged();
}
},makeColumnsEven:function(){
setTimeout(dojo.hitch(this,function(){
var o=this.getTableInfo(true);
var w=Math.floor(100/o.cols);
o.tds.forEach(function(d){
dojo.attr(d,"width",w+"%");
});
}),10);
},getTableInfo:function(_1b){
return this.editor._tablePluginHandler.getTableInfo(_1b);
},_makeTitle:function(str){
var ns=[];
dojo.forEach(str,function(c,i){
if(c.charCodeAt(0)<91&&i>0&&ns[i-1].charCodeAt(0)!=32){
ns.push(" ");
}
if(i===0){
c=c.toUpperCase();
}
ns.push(c);
});
return ns.join("");
},getSelectedCells:function(){
var _1c=[];
var tbl=this.getTableInfo().tbl;
this.editor._tablePluginHandler._prepareTable(tbl);
var e=this.editor;
var _1d=dojo.withGlobal(e.window,"getSelectedHtml",dijit._editor.selection,[null]);
var str=_1d.match(/id="*\w*"*/g);
dojo.forEach(str,function(a){
var id=a.substring(3,a.length);
if(id.charAt(0)=="\""&&id.charAt(id.length-1)=="\""){
id=id.substring(1,id.length-1);
}
var _1e=e.byId(id);
if(_1e&&_1e.tagName.toLowerCase()=="td"){
_1c.push(_1e);
}
},this);
if(!_1c.length){
var sel=dijit.range.getSelection(e.window);
if(sel.rangeCount){
var r=sel.getRangeAt(0);
var _1f=r.startContainer;
while(_1f&&_1f!=e.editNode&&_1f!=e.document){
if(_1f.nodeType===1){
var tg=_1f.tagName?_1f.tagName.toLowerCase():"";
if(tg==="td"){
return [_1f];
}
}
_1f=_1f.parentNode;
}
}
}
return _1c;
},destroy:function(){
this.inherited(arguments);
dojo.unsubscribe(this._availableTopic);
this.editor._tablePluginHandler.uninitialize(this.editor);
}});
dojo.declare("dojox.editor.plugins.TableContextMenu",dojox.editor.plugins.TablePlugins,{constructor:function(){
this.connect(this,"setEditor",function(_20){
_20.onLoadDeferred.addCallback(dojo.hitch(this,function(){
this._createContextMenu();
}));
this.button.domNode.style.display="none";
});
},_initButton:function(){
this.inherited(arguments);
if(this.commandName=="tableContextMenu"){
this.button.domNode.display="none";
}
},_createContextMenu:function(){
var _21=new dijit.Menu({targetNodeIds:[this.editor.iframe]});
var _22=dojo.i18n.getLocalization("dojox.editor.plugins","TableDialog",this.lang);
_21.addChild(new dijit.MenuItem({label:_22.selectTableLabel,onClick:dojo.hitch(this,"selectTable")}));
_21.addChild(new dijit.MenuSeparator());
_21.addChild(new dijit.MenuItem({label:_22.insertTableRowBeforeLabel,onClick:dojo.hitch(this,"modTable","insertTableRowBefore")}));
_21.addChild(new dijit.MenuItem({label:_22.insertTableRowAfterLabel,onClick:dojo.hitch(this,"modTable","insertTableRowAfter")}));
_21.addChild(new dijit.MenuItem({label:_22.insertTableColumnBeforeLabel,onClick:dojo.hitch(this,"modTable","insertTableColumnBefore")}));
_21.addChild(new dijit.MenuItem({label:_22.insertTableColumnAfterLabel,onClick:dojo.hitch(this,"modTable","insertTableColumnAfter")}));
_21.addChild(new dijit.MenuSeparator());
_21.addChild(new dijit.MenuItem({label:_22.deleteTableRowLabel,onClick:dojo.hitch(this,"modTable","deleteTableRow")}));
_21.addChild(new dijit.MenuItem({label:_22.deleteTableColumnLabel,onClick:dojo.hitch(this,"modTable","deleteTableColumn")}));
this.menu=_21;
}});
dojo.declare("dojox.editor.plugins.InsertTable",dojox.editor.plugins.TablePlugins,{alwaysAvailable:true,modTable:function(){
var w=new dojox.editor.plugins.EditorTableDialog({});
w.show();
var c=dojo.connect(w,"onBuildTable",this,function(obj){
dojo.disconnect(c);
var res=this.editor.execCommand("inserthtml",obj.htmlText);
});
}});
dojo.declare("dojox.editor.plugins.ModifyTable",dojox.editor.plugins.TablePlugins,{modTable:function(){
if(!this.editor._tablePluginHandler.checkAvailable()){
return;
}
var o=this.getTableInfo();
var w=new dojox.editor.plugins.EditorModifyTableDialog({table:o.tbl});
w.show();
this.connect(w,"onSetTable",function(_23){
var o=this.getTableInfo();
dojo.attr(o.td,"bgcolor",_23);
});
}});
dojo.declare("dojox.editor.plugins.ColorTableCell",dojox.editor.plugins.TablePlugins,{constructor:function(){
this.buttonClass=dijit.form.DropDownButton;
this.dropDown=new dijit.ColorPalette();
this.connect(this.dropDown,"onChange",function(_24){
this.modTable(null,_24);
});
},_initButton:function(){
this.command=this.commandName;
this.label=this.editor.commands[this.command]=this._makeTitle(this.command);
this.inherited(arguments);
delete this.command;
this.onDisplayChanged(false);
},modTable:function(cmd,_25){
this.begEdit();
var o=this.getTableInfo();
var tds=this.getSelectedCells(o.tbl);
dojo.forEach(tds,function(td){
dojo.style(td,"backgroundColor",_25);
});
this.endEdit();
}});
dojo.provide("dojox.editor.plugins.EditorTableDialog");
dojo.require("dijit.Dialog");
dojo.require("dijit.form.TextBox");
dojo.require("dijit.form.FilteringSelect");
dojo.require("dijit.form.Button");
dojo.declare("dojox.editor.plugins.EditorTableDialog",[dijit.Dialog],{baseClass:"EditorTableDialog",widgetsInTemplate:true,templateString:dojo.cache("dojox.editor.plugins","resources/insertTable.html","<div class=\"dijitDialog\" tabindex=\"-1\" waiRole=\"dialog\" waiState=\"labelledby-${id}_title\">\n\t<div dojoAttachPoint=\"titleBar\" class=\"dijitDialogTitleBar\">\n\t<span dojoAttachPoint=\"titleNode\" class=\"dijitDialogTitle\" id=\"${id}_title\">${insertTableTitle}</span>\n\t<span dojoAttachPoint=\"closeButtonNode\" class=\"dijitDialogCloseIcon\" dojoAttachEvent=\"onclick: onCancel\" title=\"${buttonCancel}\">\n\t\t<span dojoAttachPoint=\"closeText\" class=\"closeText\" title=\"${buttonCancel}\">x</span>\n\t</span>\n\t</div>\n    <div dojoAttachPoint=\"containerNode\" class=\"dijitDialogPaneContent\">\n        <table class=\"etdTable\"><tr>\n            <td class=\"left\">\n                <span dojoAttachPoint=\"selectRow\" dojoType=\"dijit.form.TextBox\" value=\"2\"></span>\n                <label>${rows}</label>\n            </td><td class=\"right\">\n                <span dojoAttachPoint=\"selectCol\" dojoType=\"dijit.form.TextBox\" value=\"2\"></span>\n                <label>${columns}</label>\n            </td></tr><tr><td>\n                <span dojoAttachPoint=\"selectWidth\" dojoType=\"dijit.form.TextBox\" value=\"100\"></span>\n                <label>${tableWidth}</label>\n            </td><td>\n                <select dojoAttachPoint=\"selectWidthType\" hasDownArrow=\"true\" dojoType=\"dijit.form.FilteringSelect\">\n                  <option value=\"percent\">${percent}</option>\n                  <option value=\"pixels\">${pixels}</option>\n                </select></td></tr>\n          <tr><td>\n                <span dojoAttachPoint=\"selectBorder\" dojoType=\"dijit.form.TextBox\" value=\"1\"></span>\n                <label>${borderThickness}</label></td>\n            <td>\n                ${pixels}\n            </td></tr><tr><td>\n                <span dojoAttachPoint=\"selectPad\" dojoType=\"dijit.form.TextBox\" value=\"0\"></span>\n                <label>${cellPadding}</label></td>\n            <td class=\"cellpad\"></td></tr><tr><td>\n                <span dojoAttachPoint=\"selectSpace\" dojoType=\"dijit.form.TextBox\" value=\"0\"></span>\n                <label>${cellSpacing}</label>\n            </td><td class=\"cellspace\"></td></tr></table>\n        <div class=\"dialogButtonContainer\">\n            <div dojoType=\"dijit.form.Button\" dojoAttachEvent=\"onClick: onInsert\">${buttonInsert}</div>\n            <div dojoType=\"dijit.form.Button\" dojoAttachEvent=\"onClick: onCancel\">${buttonCancel}</div>\n        </div>\n\t</div>\n</div>\n"),postMixInProperties:function(){
var _26=dojo.i18n.getLocalization("dojox.editor.plugins","TableDialog",this.lang);
dojo.mixin(this,_26);
this.inherited(arguments);
},postCreate:function(){
dojo.addClass(this.domNode,this.baseClass);
this.inherited(arguments);
},onInsert:function(){
console.log("insert");
var _27=this.selectRow.get("value")||1,_28=this.selectCol.get("value")||1,_29=this.selectWidth.get("value"),_2a=this.selectWidthType.get("value"),_2b=this.selectBorder.get("value"),pad=this.selectPad.get("value"),_2c=this.selectSpace.get("value"),_2d="tbl_"+(new Date().getTime()),t="<table id=\""+_2d+"\"width=\""+_29+((_2a=="percent")?"%":"")+"\" border=\""+_2b+"\" cellspacing=\""+_2c+"\" cellpadding=\""+pad+"\">\n";
for(var r=0;r<_27;r++){
t+="\t<tr>\n";
for(var c=0;c<_28;c++){
t+="\t\t<td width=\""+(Math.floor(100/_28))+"%\">&nbsp;</td>\n";
}
t+="\t</tr>\n";
}
t+="</table>";
this.onBuildTable({htmlText:t,id:_2d});
var cl=dojo.connect(this,"onHide",function(){
dojo.disconnect(cl);
var _2e=this;
setTimeout(function(){
_2e.destroyRecursive();
},10);
});
this.hide();
},onCancel:function(){
var c=dojo.connect(this,"onHide",function(){
dojo.disconnect(c);
var _2f=this;
setTimeout(function(){
_2f.destroyRecursive();
},10);
});
},onBuildTable:function(_30){
}});
dojo.provide("dojox.editor.plugins.EditorModifyTableDialog");
dojo.require("dijit.ColorPalette");
dojo.declare("dojox.editor.plugins.EditorModifyTableDialog",[dijit.Dialog],{baseClass:"EditorTableDialog",widgetsInTemplate:true,table:null,tableAtts:{},templateString:dojo.cache("dojox.editor.plugins","resources/modifyTable.html","<div class=\"dijitDialog\" tabindex=\"-1\" waiRole=\"dialog\" waiState=\"labelledby-${id}_title\">\n\t<div dojoAttachPoint=\"titleBar\" class=\"dijitDialogTitleBar\">\n\t<span dojoAttachPoint=\"titleNode\" class=\"dijitDialogTitle\" id=\"${id}_title\">${modifyTableTitle}</span>\n\t<span dojoAttachPoint=\"closeButtonNode\" class=\"dijitDialogCloseIcon\" dojoAttachEvent=\"onclick: onCancel\" title=\"${buttonCancel}\">\n\t\t<span dojoAttachPoint=\"closeText\" class=\"closeText\" title=\"${buttonCancel}\">x</span>\n\t</span>\n\t</div>\n    <div dojoAttachPoint=\"containerNode\" class=\"dijitDialogPaneContent\">\n        <table class=\"etdTable\">\n          <tr><td class=\"left\">\n                <span class=\"colorSwatchBtn\" dojoAttachPoint=\"backgroundCol\"></span>\n                <label>${backgroundColor}</label>\n            </td><td class=\"right\">\n                <span class=\"colorSwatchBtn\" dojoAttachPoint=\"borderCol\"></span>\n                <label>${borderColor}</label>\n            </td></tr><tr><td>\n                <span dojoAttachPoint=\"selectBorder\" dojoType=\"dijit.form.TextBox\" value=\"1\"></span>\n                <label>${borderThickness}</label>\n            </td><td>\n            ${pixels}\n            </td></tr><tr><td>\n                <select class=\"floatDijit\" dojoAttachPoint=\"selectAlign\" dojoType=\"dijit.form.FilteringSelect\">\n                  <option value=\"default\">${default}</option>\n                  <option value=\"left\">${left}</option>\n                  <option value=\"center\">${center}</option>\n                  <option value=\"right\">${right}</option>\n                </select>\n                <label>${align}</label>\n            </td><td></td></tr><tr><td>\n                <span dojoAttachPoint=\"selectWidth\" dojoType=\"dijit.form.TextBox\" value=\"100\"></span>\n                <label>${tableWidth}</label>\n            </td><td>\n                <select dojoAttachPoint=\"selectWidthType\" hasDownArrow=\"true\" dojoType=\"dijit.form.FilteringSelect\">\n                  <option value=\"percent\">${percent}</option>\n                  <option value=\"pixels\">${pixels}</option>\n                </select>\n                </td></tr><tr><td>\n                <span dojoAttachPoint=\"selectPad\" dojoType=\"dijit.form.TextBox\" value=\"0\"></span>\n                <label>${cellPadding}</label></td>\n            <td class=\"cellpad\"></td></tr><tr><td>\n                <span dojoAttachPoint=\"selectSpace\" dojoType=\"dijit.form.TextBox\" value=\"0\"></span>\n                <label>${cellSpacing}</label>\n            </td><td class=\"cellspace\"></td></tr>\n        </table>\n        <div class=\"dialogButtonContainer\">\n            <div dojoType=\"dijit.form.Button\" dojoAttachEvent=\"onClick: onSet\">${buttonSet}</div>\n            <div dojoType=\"dijit.form.Button\" dojoAttachEvent=\"onClick: onCancel\">${buttonCancel}</div>\n        </div>\n\t</div>\n</div>\n"),postMixInProperties:function(){
var _31=dojo.i18n.getLocalization("dojox.editor.plugins","TableDialog",this.lang);
dojo.mixin(this,_31);
this.inherited(arguments);
},postCreate:function(){
dojo.addClass(this.domNode,this.baseClass);
this.inherited(arguments);
this._cleanupWidgets=[];
var w1=new dijit.ColorPalette({});
this.connect(w1,"onChange",function(_32){
dijit.popup.close(w1);
this.setBrdColor(_32);
});
this.connect(w1,"onBlur",function(){
dijit.popup.close(w1);
});
this.connect(this.borderCol,"click",function(){
dijit.popup.open({popup:w1,around:this.borderCol});
w1.focus();
});
var w2=new dijit.ColorPalette({});
this.connect(w2,"onChange",function(_33){
dijit.popup.close(w2);
this.setBkColor(_33);
});
this.connect(w2,"onBlur",function(){
dijit.popup.close(w2);
});
this.connect(this.backgroundCol,"click",function(){
dijit.popup.open({popup:w2,around:this.backgroundCol});
w2.focus();
});
this._cleanupWidgets.push(w1);
this._cleanupWidgets.push(w2);
this.setBrdColor(dojo.attr(this.table,"bordercolor"));
this.setBkColor(dojo.attr(this.table,"bgcolor"));
var w=dojo.attr(this.table,"width");
if(!w){
w=this.table.style.width;
}
var p="pixels";
if(dojo.isString(w)&&w.indexOf("%")>-1){
p="percent";
w=w.replace(/%/,"");
}
if(w){
this.selectWidth.set("value",w);
this.selectWidthType.set("value",p);
}else{
this.selectWidth.set("value","");
this.selectWidthType.set("value","percent");
}
this.selectBorder.set("value",dojo.attr(this.table,"border"));
this.selectPad.set("value",dojo.attr(this.table,"cellPadding"));
this.selectSpace.set("value",dojo.attr(this.table,"cellSpacing"));
this.selectAlign.set("value",dojo.attr(this.table,"align"));
},setBrdColor:function(_34){
this.brdColor=_34;
dojo.style(this.borderCol,"backgroundColor",_34);
},setBkColor:function(_35){
this.bkColor=_35;
dojo.style(this.backgroundCol,"backgroundColor",_35);
},onSet:function(){
dojo.attr(this.table,"borderColor",this.brdColor);
dojo.attr(this.table,"bgColor",this.bkColor);
if(this.selectWidth.get("value")){
dojo.style(this.table,"width","");
dojo.attr(this.table,"width",(this.selectWidth.get("value")+((this.selectWidthType.get("value")=="pixels")?"":"%")));
}
dojo.attr(this.table,"border",this.selectBorder.get("value"));
dojo.attr(this.table,"cellPadding",this.selectPad.get("value"));
dojo.attr(this.table,"cellSpacing",this.selectSpace.get("value"));
dojo.attr(this.table,"align",this.selectAlign.get("value"));
var c=dojo.connect(this,"onHide",function(){
dojo.disconnect(c);
var _36=this;
setTimeout(function(){
_36.destroyRecursive();
},10);
});
this.hide();
},onCancel:function(){
var c=dojo.connect(this,"onHide",function(){
dojo.disconnect(c);
var _37=this;
setTimeout(function(){
_37.destroyRecursive();
},10);
});
},onSetTable:function(_38){
},destroy:function(){
this.inherited(arguments);
dojo.forEach(this._cleanupWidgets,function(w){
if(w&&w.destroy){
w.destroy();
}
});
delete this._cleanupWidgets;
}});
dojo.subscribe(dijit._scopeName+".Editor.getPlugin",null,function(o){
if(o.plugin){
return;
}
if(o.args&&o.args.command){
var cmd=o.args.command.charAt(0).toLowerCase()+o.args.command.substring(1,o.args.command.length);
switch(cmd){
case "insertTableRowBefore":
case "insertTableRowAfter":
case "insertTableColumnBefore":
case "insertTableColumnAfter":
case "deleteTableRow":
case "deleteTableColumn":
o.plugin=new dojox.editor.plugins.TablePlugins({commandName:cmd});
break;
case "colorTableCell":
o.plugin=new dojox.editor.plugins.ColorTableCell({commandName:cmd});
break;
case "modifyTable":
o.plugin=new dojox.editor.plugins.ModifyTable({commandName:cmd});
break;
case "insertTable":
o.plugin=new dojox.editor.plugins.InsertTable({commandName:cmd});
break;
case "tableContextMenu":
o.plugin=new dojox.editor.plugins.TableContextMenu({commandName:cmd});
break;
}
}
});
}
