/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.mobile.app.compat"]){
dojo._hasResource["dojox.mobile.app.compat"]=true;
dojo.provide("dojox.mobile.app.compat");
dojo.require("dojox.mobile.compat");
dojo.extend(dojox.mobile.app.AlertDialog,{_doTransition:function(_1){
console.log("in _doTransition and this = ",this);
var h=dojo.marginBox(this.domNode.firstChild).h;
var _2=this.controller.getWindowSize().h;
var _3=_2-h;
var _4=_2;
var _5=dojo.fx.slideTo({node:this.domNode,duration:400,top:{start:_1<0?_3:_4,end:_1<0?_4:_3}});
var _6=dojo[_1<0?"fadeOut":"fadeIn"]({node:this.mask,duration:400});
var _7=dojo.fx.combine([_5,_6]);
var _8=this;
dojo.connect(_7,"onEnd",this,function(){
if(_1<0){
_8.domNode.style.display="none";
dojo.destroy(_8.domNode);
dojo.destroy(_8.mask);
}
});
_7.play();
}});
dojo.extend(dojox.mobile.app.List,{deleteRow:function(){
console.log("deleteRow in compat mode",_9);
var _9=this._selectedRow;
dojo.style(_9,{visibility:"hidden",minHeight:"0px"});
dojo.removeClass(_9,"hold");
var _a=dojo.contentBox(_9).h;
dojo.animateProperty({node:_9,duration:800,properties:{height:{start:_a,end:1},paddingTop:{end:0},paddingBottom:{end:0}},onEnd:this._postDeleteAnim}).play();
}});
if(dojox.mobile.app.ImageView&&!dojo.create("canvas").getContext){
dojo.extend(dojox.mobile.app.ImageView,{buildRendering:function(){
this.domNode.innerHTML="ImageView widget is not supported on this browser."+"Please try again with a modern browser, e.g. "+"Safari, Chrome or Firefox";
this.canvas={};
},postCreate:function(){
}});
}
if(dojox.mobile.app.ImageThumbView){
dojo.extend(dojox.mobile.app.ImageThumbView,{place:function(_b,x,y){
dojo.style(_b,{top:y+"px",left:x+"px",visibility:"visible"});
}});
}
}
