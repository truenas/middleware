/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit._base.popup"]){
dojo._hasResource["dijit._base.popup"]=true;
dojo.provide("dijit._base.popup");
dojo.require("dijit._base.focus");
dojo.require("dijit._base.place");
dojo.require("dijit._base.window");
dijit.popup={_stack:[],_beginZIndex:1000,_idGen:1,moveOffScreen:function(_1){
var _2=_1.parentNode;
if(!_2||!dojo.hasClass(_2,"dijitPopup")){
_2=dojo.create("div",{"class":"dijitPopup",style:{visibility:"hidden",top:"-9999px"}},dojo.body());
dijit.setWaiRole(_2,"presentation");
_2.appendChild(_1);
}
var s=_1.style;
s.display="";
s.visibility="";
s.position="";
s.top="0px";
dojo.style(_2,{visibility:"hidden",top:"-9999px"});
},getTopPopup:function(){
var _3=this._stack;
for(var pi=_3.length-1;pi>0&&_3[pi].parent===_3[pi-1].widget;pi--){
}
return _3[pi];
},open:function(_4){
var _5=this._stack,_6=_4.popup,_7=_4.orient||((_4.parent?_4.parent.isLeftToRight():dojo._isBodyLtr())?{"BL":"TL","BR":"TR","TL":"BL","TR":"BR"}:{"BR":"TR","BL":"TL","TR":"BR","TL":"BL"}),_8=_4.around,id=(_4.around&&_4.around.id)?(_4.around.id+"_dropdown"):("popup_"+this._idGen++);
var _9=_6.domNode.parentNode;
if(!_9||!dojo.hasClass(_9,"dijitPopup")){
this.moveOffScreen(_6.domNode);
_9=_6.domNode.parentNode;
}
dojo.attr(_9,{id:id,style:{zIndex:this._beginZIndex+_5.length},"class":"dijitPopup "+(_6.baseClass||_6["class"]||"").split(" ")[0]+"Popup",dijitPopupParent:_4.parent?_4.parent.id:""});
if(dojo.isIE||dojo.isMoz){
var _a=_9.childNodes[1];
if(!_a){
_a=new dijit.BackgroundIframe(_9);
}
}
var _b=_8?dijit.placeOnScreenAroundElement(_9,_8,_7,_6.orient?dojo.hitch(_6,"orient"):null):dijit.placeOnScreen(_9,_4,_7=="R"?["TR","BR","TL","BL"]:["TL","BL","TR","BR"],_4.padding);
_9.style.visibility="visible";
_6.domNode.style.visibility="visible";
var _c=[];
_c.push(dojo.connect(_9,"onkeypress",this,function(_d){
if(_d.charOrCode==dojo.keys.ESCAPE&&_4.onCancel){
dojo.stopEvent(_d);
_4.onCancel();
}else{
if(_d.charOrCode===dojo.keys.TAB){
dojo.stopEvent(_d);
var _e=this.getTopPopup();
if(_e&&_e.onCancel){
_e.onCancel();
}
}
}
}));
if(_6.onCancel){
_c.push(dojo.connect(_6,"onCancel",_4.onCancel));
}
_c.push(dojo.connect(_6,_6.onExecute?"onExecute":"onChange",this,function(){
var _f=this.getTopPopup();
if(_f&&_f.onExecute){
_f.onExecute();
}
}));
_5.push({wrapper:_9,iframe:_a,widget:_6,parent:_4.parent,onExecute:_4.onExecute,onCancel:_4.onCancel,onClose:_4.onClose,handlers:_c});
if(_6.onOpen){
_6.onOpen(_b);
}
return _b;
},close:function(_10){
var _11=this._stack;
while(dojo.some(_11,function(_12){
return _12.widget==_10;
})){
var top=_11.pop(),_13=top.wrapper,_14=top.iframe,_15=top.widget,_16=top.onClose;
if(_15.onClose){
_15.onClose();
}
dojo.forEach(top.handlers,dojo.disconnect);
if(_15&&_15.domNode){
this.moveOffScreen(_15.domNode);
}else{
dojo.destroy(_13);
}
if(_16){
_16();
}
}
}};
dijit._frames=new function(){
var _17=[];
this.pop=function(){
var _18;
if(_17.length){
_18=_17.pop();
_18.style.display="";
}else{
if(dojo.isIE){
var _19=dojo.config["dojoBlankHtmlUrl"]||(dojo.moduleUrl("dojo","resources/blank.html")+"")||"javascript:\"\"";
var _1a="<iframe src='"+_19+"'"+" style='position: absolute; left: 0px; top: 0px;"+"z-index: -1; filter:Alpha(Opacity=\"0\");'>";
_18=dojo.doc.createElement(_1a);
}else{
_18=dojo.create("iframe");
_18.src="javascript:\"\"";
_18.className="dijitBackgroundIframe";
dojo.style(_18,"opacity",0.1);
}
_18.tabIndex=-1;
dijit.setWaiRole(_18,"presentation");
}
return _18;
};
this.push=function(_1b){
_1b.style.display="none";
_17.push(_1b);
};
}();
dijit.BackgroundIframe=function(_1c){
if(!_1c.id){
throw new Error("no id");
}
if(dojo.isIE||dojo.isMoz){
var _1d=dijit._frames.pop();
_1c.appendChild(_1d);
if(dojo.isIE<7){
this.resize(_1c);
this._conn=dojo.connect(_1c,"onresize",this,function(){
this.resize(_1c);
});
}else{
dojo.style(_1d,{width:"100%",height:"100%"});
}
this.iframe=_1d;
}
};
dojo.extend(dijit.BackgroundIframe,{resize:function(_1e){
if(this.iframe&&dojo.isIE<7){
dojo.style(this.iframe,{width:_1e.offsetWidth+"px",height:_1e.offsetHeight+"px"});
}
},destroy:function(){
if(this._conn){
dojo.disconnect(this._conn);
this._conn=null;
}
if(this.iframe){
dijit._frames.push(this.iframe);
delete this.iframe;
}
}});
}
