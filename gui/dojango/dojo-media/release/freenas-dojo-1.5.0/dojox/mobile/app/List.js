/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.mobile.app.List"]){
dojo._hasResource["dojox.mobile.app.List"]=true;
dojo.provide("dojox.mobile.app.List");
dojo.experimental("dojox.mobile.app.List");
dojo.require("dojo.string");
dojo.require("dijit._Widget");
(function(){
var _1={};
dojo.declare("dojox.mobile.app.List",dijit._Widget,{items:null,itemTemplate:"",emptyTemplate:"",labelDelete:"Delete",labelCancel:"Cancel",controller:null,autoDelete:true,enableDelete:true,_templateLoadCount:0,_mouseDownPos:null,constructor:function(){
this._checkLoadComplete=dojo.hitch(this,this._checkLoadComplete);
this._replaceToken=dojo.hitch(this,this._replaceToken);
this._postDeleteAnim=dojo.hitch(this,this._postDeleteAnim);
},postCreate:function(){
var _2=this;
if(this.emptyTemplate){
this._templateLoadCount++;
}
if(this.itemTemplate){
this._templateLoadCount++;
}
dojo.addClass(this.domNode,"list");
var _3;
this.connect(this.domNode,"onmousedown",function(_4){
var _5=_4;
if(_4.targetTouches&&_4.targetTouches.length>0){
_5=_4.targetTouches[0];
}
var _6=_2._getRowNode(_4.target);
if(_6){
_2._setDataInfo(_6,_4);
_2._selectRow(_6);
_2._mouseDownPos={x:_5.pageX,y:_5.pageY};
_2._dragThreshold=null;
}else{
console.log("didnt get a node");
}
});
this.connect(this.domNode,"onmouseup",function(_7){
if(_7.targetTouches&&_7.targetTouches.length>0){
_7=_7.targetTouches[0];
}
var _8=_2._getRowNode(_7.target);
if(_8){
_2._setDataInfo(_8,_7);
if(_2._selectedRow){
_2.onSelect(_8._data,_8._idx,_8);
}
this._deselectRow();
}
});
if(this.enableDelete){
this.connect(this.domNode,"mousemove",function(_9){
dojo.stopEvent(_9);
if(!_2._selectedRow){
return;
}
var _a=_2._getRowNode(_9.target);
if(_2.enableDelete&&_a&&!_2._deleting){
_2.handleDrag(_9);
}
});
}
this.connect(this.domNode,"onclick",function(_b){
if(_b.touches&&_b.touches.length>0){
_b=_b.touches[0];
}
var _c=_2._getRowNode(_b.target,true);
if(_c){
_2._setDataInfo(_c,_b);
}
});
this.connect(this.domNode,"mouseout",function(_d){
if(_d.touches&&_d.touches.length>0){
_d=_d.touches[0];
}
if(_d.target==_2._selectedRow){
_2._deselectRow();
}
});
if(!this.itemTemplate){
throw Error("An item template must be provided to "+this.declaredClass);
}
this._loadTemplate(this.itemTemplate,"itemTemplate",this._checkLoadComplete);
if(this.emptyTemplate){
this._loadTemplate(this.emptyTemplate,"emptyTemplate",this._checkLoadComplete);
}
},handleDrag:function(_e){
var _f=_e;
if(_e.targetTouches&&_e.targetTouches.length>0){
_f=_e.targetTouches[0];
}
var _10=_f.pageX-this._mouseDownPos.x;
var _11=Math.abs(_10);
if(_11>10&&!this._dragThreshold){
this._dragThreshold=dojo.marginBox(this._selectedRow).w*0.6;
if(!this.autoDelete){
this.createDeleteButtons(this._selectedRow);
}
}
this._selectedRow.style.left=(_11>10?_10:0)+"px";
if(this._dragThreshold&&this._dragThreshold<_11){
this.preDelete(_10);
}
},handleDragCancel:function(){
if(this._deleting){
return;
}
dojo.removeClass(this._selectedRow,"hold");
this._selectedRow.style.left=0;
this._mouseDownPos=null;
this._dragThreshold=null;
this._deleteBtns&&dojo.style(this._deleteBtns,"display","none");
},preDelete:function(_12){
var _13=this;
this._deleting=true;
dojo.animateProperty({node:this._selectedRow,duration:400,properties:{left:{end:_12+((_12>0?1:-1)*this._dragThreshold*0.8)}},onEnd:dojo.hitch(this,function(){
if(this.autoDelete){
this.deleteRow(this._selectedRow);
}
})}).play();
},deleteRow:function(row){
dojo.style(row,{visibility:"hidden",minHeight:"0px"});
dojo.removeClass(row,"hold");
this._deleteAnimConn=this.connect(row,"webkitAnimationEnd",this._postDeleteAnim);
dojo.addClass(row,"collapsed");
},_postDeleteAnim:function(_14){
if(this._deleteAnimConn){
this.disconnect(this._deleteAnimConn);
this._deleteAnimConn=null;
}
var row=this._selectedRow;
var _15=row.nextSibling;
row.parentNode.removeChild(row);
this.onDelete(row._data,row._idx,this.items);
while(_15){
if(_15._idx){
_15._idx--;
}
_15=_15.nextSibling;
}
dojo.destroy(row);
dojo.query("> *:not(.buttons)",this.domNode).forEach(this.applyClass);
this._deleting=false;
this._deselectRow();
},createDeleteButtons:function(_16){
var mb=dojo.marginBox(_16);
var pos=dojo._abs(_16,true);
if(!this._deleteBtns){
this._deleteBtns=dojo.create("div",{"class":"buttons"},this.domNode);
this.buttons=[];
this.buttons.push(new dojox.mobile.Button({btnClass:"mblRedButton",label:this.labelDelete}));
this.buttons.push(new dojox.mobile.Button({btnClass:"mblBlueButton",label:this.labelCancel}));
dojo.place(this.buttons[0].domNode,this._deleteBtns);
dojo.place(this.buttons[1].domNode,this._deleteBtns);
dojo.addClass(this.buttons[0].domNode,"deleteBtn");
dojo.addClass(this.buttons[1].domNode,"cancelBtn");
this._handleButtonClick=dojo.hitch(this._handleButtonClick);
this.connect(this._deleteBtns,"onclick",this._handleButtonClick);
}
dojo.removeClass(this._deleteBtns,"fade out fast");
dojo.style(this._deleteBtns,{display:"",width:mb.w+"px",height:mb.h+"px",top:(_16.offsetTop)+"px",left:"0px"});
},onDelete:function(_17,_18,_19){
_19.splice(_18,1);
if(_19.length<1){
this.render();
}
},cancelDelete:function(){
this._deleting=false;
this.handleDragCancel();
},_handleButtonClick:function(_1a){
if(_1a.touches&&_1a.touches.length>0){
_1a=_1a.touches[0];
}
var _1b=_1a.target;
if(dojo.hasClass(_1b,"deleteBtn")){
this.deleteRow(this._selectedRow);
}else{
if(dojo.hasClass(_1b,"cancelBtn")){
this.cancelDelete();
}else{
return;
}
}
dojo.addClass(this._deleteBtns,"fade out");
},applyClass:function(_1c,idx,_1d){
dojo.removeClass(_1c,"first last");
if(idx==0){
dojo.addClass(_1c,"first");
}
if(idx==_1d.length-1){
dojo.addClass(_1c,"last");
}
},_setDataInfo:function(_1e,_1f){
_1f.item=_1e._data;
_1f.index=_1e._idx;
},onSelect:function(_20,_21,_22){
},_selectRow:function(row){
if(this._deleting&&this._selectedRow&&row!=this._selectedRow){
this.cancelDelete();
}
if(!dojo.hasClass(row,"row")){
return;
}
dojo.addClass(row,"hold");
this._selectedRow=row;
},_deselectRow:function(){
if(!this._selectedRow||this._deleting){
return;
}
this.handleDragCancel();
dojo.removeClass(this._selectedRow,"hold");
this._selectedRow=null;
},_getRowNode:function(_23,_24){
while(_23&&!_23._data&&_23!=this.domNode){
if(!_24&&dojo.hasClass(_23,"noclick")){
return null;
}
_23=_23.parentNode;
}
return _23;
},render:function(){
dojo.query("> *:not(.buttons)",this.domNode).forEach(dojo.destroy);
var _25=[];
var row,i;
dojo.addClass(this.domNode,"list");
for(i=0;i<this.items.length;i++){
row=dojo._toDom(dojo.string.substitute(this.itemTemplate,this.items[i],this._replaceToken,this));
_25.push(row);
}
for(i=0;i<this.items.length;i++){
_25[i]._data=this.items[i];
_25[i]._idx=i;
this.domNode.appendChild(_25[i]);
}
if(this.items.length<1&&this.emptyTemplate){
dojo.place(dojo._toDom(this.emptyTemplate),this.domNode,"first");
}
if(dojo.hasClass(this.domNode.parentNode,"mblRoundRect")){
dojo.addClass(this.domNode.parentNode,"mblRoundRectList");
}
var _26=dojo.query("> div:not(.buttons)",this.domNode);
_26.addClass("row");
if(_26.length>0){
dojo.addClass(_26[0],"first");
dojo.addClass(_26[_26.length-1],"last");
}
},_replaceToken:function(_27,key){
if(key.charAt(0)=="!"){
_27=dojo.getObject(key.substr(1),false,_this);
}
if(typeof _27=="undefined"){
return "";
}
if(_27==null){
return "";
}
return key.charAt(0)=="!"?_27:_27.toString().replace(/"/g,"&quot;");
},_checkLoadComplete:function(){
this._templateLoadCount--;
if(this._templateLoadCount<1&&this.get("items")){
this.render();
}
},_loadTemplate:function(url,_28,_29){
if(!url){
_29();
return;
}
if(_1[url]){
this.set(_28,_1[url]);
_29();
}else{
var _2a=this;
dojo.xhrGet({url:url,sync:false,handleAs:"text",load:function(_2b){
_1[url]=dojo.trim(_2b);
_2a.set(_28,_1[url]);
_29();
}});
}
},_setItemsAttr:function(_2c){
this.items=_2c||[];
if(this._templateLoadCount<1&&_2c){
this.render();
}
},destroy:function(){
if(this.buttons){
dojo.forEach(this.buttons,function(_2d){
_2d.destroy();
});
this.buttons=null;
}
this.inherited(arguments);
}});
})();
}
