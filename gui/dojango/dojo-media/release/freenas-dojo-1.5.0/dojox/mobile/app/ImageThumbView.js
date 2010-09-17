/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.mobile.app.ImageThumbView"]){
dojo._hasResource["dojox.mobile.app.ImageThumbView"]=true;
dojo.provide("dojox.mobile.app.ImageThumbView");
dojo.experimental("dojox.mobile.app.ImageThumbView");
dojo.require("dijit._Widget");
dojo.require("dojo.string");
dojo.declare("dojox.mobile.app.ImageThumbView",dijit._Widget,{items:null,urlParam:"url",itemTemplate:"<div class=\"mblThumbInner\">"+"<div class=\"mblThumbOverlay\"></div>"+"<div class=\"mblThumbMask\">"+"<div class=\"mblThumbSrc\" style=\"background-image:url(${url})\"></div>"+"</div>"+"</div>",minPadding:5,maxPerRow:3,baseClass:"mblImageThumbView",selectedIndex:-1,cache:null,postCreate:function(){
this.inherited(arguments);
var _1=this;
var _2="mblThumbHover";
this.addThumb=dojo.hitch(this,this.addThumb);
this.handleImgLoad=dojo.hitch(this,this.handleImgLoad);
this._onLoadImages={};
this.cache=[];
this.visibleImages=[];
this.connect(this.domNode,"onclick",function(_3){
var _4=_1._getItemNodeFromEvent(_3);
if(_4){
_1.onSelect(_4._item,_4._index,_1.items);
dojo.query(".selected",this.domNode).removeClass("selected");
dojo.addClass(_4,"selected");
}
});
this.resize();
this.render();
},onSelect:function(_5,_6,_7){
},_setItemsAttr:function(_8){
this.items=_8||[];
this.render();
},_getItemNode:function(_9){
while(_9&&!dojo.hasClass(_9,"mblThumb")&&_9!=this.domNode){
_9=_9.parentNode;
}
return (_9==this.domNode)?null:_9;
},_getItemNodeFromEvent:function(_a){
if(_a.touches&&_a.touches.length>0){
_a=_a.touches[0];
}
return this._getItemNode(_a.target);
},resize:function(){
this._thumbSize=null;
this._size=dojo.marginBox(this.domNode);
this.render();
},render:function(){
var i;
var _b;
var _c;
var _d;
while(this.visibleImages.length>0){
_d=this.visibleImages.pop();
this.cache.push(_d);
dojo.addClass(_d,"hidden");
_d._cached=true;
}
if(!this.items||this.items.length==0){
return;
}
for(i=0;i<this.items.length;i++){
_c=this.items[i];
_b=(dojo.isString(_c)?_c:_c[this.urlParam]);
this.addThumb(_c,_b,i);
}
if(!this._thumbSize){
return;
}
var _e=0;
var _f=-1;
var _10=this._thumbSize.w+(this.padding*2);
var _11=this._thumbSize.h+(this.padding*2);
var _12=this.thumbNodes=dojo.query(".mblThumb",this.domNode);
var pos=0;
for(i=0;i<_12.length;i++){
if(_12[i]._cached){
continue;
}
if(pos%this.maxPerRow==0){
_f++;
}
_e=pos%this.maxPerRow;
this.place(_12[i],(_e*_10)+this.padding,(_f*_11)+this.padding);
if(!_12[i]._loading){
dojo.removeClass(_12[i],"hidden");
}
if(pos==this.selectedIndex){
dojo[pos==this.selectedIndex?"addClass":"removeClass"](_12[i],"selected");
}
pos++;
}
var _13=Math.ceil(pos/this.maxPerRow);
if(this._numRows!=_13){
this._numRows=_13;
dojo.style(this.domNode,"height",(_13*(this._thumbSize.h+this.padding*2))+"px");
}
},addThumb:function(_14,url,_15){
var _16;
if(this.cache.length>0){
_16=this.cache.pop();
}else{
_16=dojo.create("div",{"class":"mblThumb hidden",innerHTML:dojo.string.substitute(this.itemTemplate,{url:url},null,this)},this.domNode);
}
dojo.addClass(_16,"hidden");
var _17=dojo.create("img",{});
_17._thumbDiv=_16;
_17._conn=dojo.connect(_17,"onload",this.handleImgLoad);
_17._url=url;
_16._loading=true;
this._onLoadImages[url]=_17;
_17.src=url;
this.visibleImages.push(_16);
_16._index=_15;
_16._item=_14;
_16._url=url;
_16._cached=false;
if(!this._thumbSize){
this._thumbSize=dojo.marginBox(_16);
this.calcPadding();
}
},handleImgLoad:function(_18){
var img=_18.target;
dojo.disconnect(img._conn);
dojo.removeClass(img._thumbDiv,"hidden");
img._thumbDiv._loading=false;
dojo.query(".mblThumbSrc",img._thumbDiv).style("backgroundImage","url("+img._url+")");
delete this._onLoadImages[img._url];
},calcPadding:function(){
var _19=this._size.w;
var _1a=this._thumbSize.w;
var _1b=_1a+this.minPadding;
this.maxPerRow=Math.floor(_19/_1b);
this.padding=(_19-(_1a*this.maxPerRow))/(this.maxPerRow*2);
},place:function(_1c,x,y){
dojo.style(_1c,{"-webkit-transform":"translate("+x+"px,"+y+"px)"});
}});
}
