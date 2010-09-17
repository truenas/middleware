/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.image.Lightbox"]){
dojo._hasResource["dojox.image.Lightbox"]=true;
dojo.provide("dojox.image.Lightbox");
dojo.experimental("dojox.image.Lightbox");
dojo.require("dojo.window");
dojo.require("dijit.Dialog");
dojo.require("dojox.fx._base");
dojo.declare("dojox.image.Lightbox",dijit._Widget,{group:"",title:"",href:"",duration:500,modal:false,_allowPassthru:false,_attachedDialog:null,startup:function(){
this.inherited(arguments);
var _1=dijit.byId("dojoxLightboxDialog");
if(_1){
this._attachedDialog=_1;
}else{
this._attachedDialog=new dojox.image.LightboxDialog({id:"dojoxLightboxDialog"});
this._attachedDialog.startup();
}
if(!this.store){
this._addSelf();
this.connect(this.domNode,"onclick","_handleClick");
}
},_addSelf:function(){
this._attachedDialog.addImage({href:this.href,title:this.title},this.group||null);
},_handleClick:function(e){
if(!this._allowPassthru){
e.preventDefault();
}else{
return;
}
this.show();
},show:function(){
this._attachedDialog.show(this);
},hide:function(){
this._attachedDialog.hide();
},disable:function(){
this._allowPassthru=true;
},enable:function(){
this._allowPassthru=false;
},onClick:function(){
},destroy:function(){
this._attachedDialog.removeImage(this);
this.inherited(arguments);
}});
dojo.declare("dojox.image.LightboxDialog",dijit.Dialog,{title:"",inGroup:null,imgUrl:dijit._Widget.prototype._blankGif,errorMessage:"Image not found.",adjust:true,modal:false,_groups:{XnoGroupX:[]},errorImg:dojo.moduleUrl("dojox.image","resources/images/warning.png"),templateString:dojo.cache("dojox.image","resources/Lightbox.html","<div class=\"dojoxLightbox\" dojoAttachPoint=\"containerNode\">\n\t<div style=\"position:relative\">\n\t\t<div dojoAttachPoint=\"imageContainer\" class=\"dojoxLightboxContainer\" dojoAttachEvent=\"onclick: _onImageClick\">\n\t\t\t<img dojoAttachPoint=\"imgNode\" src=\"${imgUrl}\" class=\"dojoxLightboxImage\" alt=\"${title}\">\n\t\t\t<div class=\"dojoxLightboxFooter\" dojoAttachPoint=\"titleNode\">\n\t\t\t\t<div class=\"dijitInline LightboxClose\" dojoAttachPoint=\"closeButtonNode\"></div>\n\t\t\t\t<div class=\"dijitInline LightboxNext\" dojoAttachPoint=\"nextButtonNode\"></div>\t\n\t\t\t\t<div class=\"dijitInline LightboxPrev\" dojoAttachPoint=\"prevButtonNode\"></div>\n\t\t\t\t<div class=\"dojoxLightboxText\" dojoAttachPoint=\"titleTextNode\"><span dojoAttachPoint=\"textNode\">${title}</span><span dojoAttachPoint=\"groupCount\" class=\"dojoxLightboxGroupText\"></span></div>\n\t\t\t</div>\n\t\t</div>\n\t</div>\n</div>\n"),startup:function(){
this.inherited(arguments);
this._animConnects=[];
this.connect(this.nextButtonNode,"onclick","_nextImage");
this.connect(this.prevButtonNode,"onclick","_prevImage");
this.connect(this.closeButtonNode,"onclick","hide");
this._makeAnims();
this._vp=dojo.window.getBox();
return this;
},show:function(_2){
var _3=this;
this._lastGroup=_2;
if(!_3.open){
_3.inherited(arguments);
_3._modalconnects.push(dojo.connect(dojo.global,"onscroll",this,"_position"),dojo.connect(dojo.global,"onresize",this,"_position"),dojo.connect(dojo.body(),"onkeypress",this,"_handleKey"));
if(!_2.modal){
_3._modalconnects.push(dojo.connect(dijit._underlay.domNode,"onclick",this,"onCancel"));
}
}
if(this._wasStyled){
var _4=dojo.create("img",null,_3.imgNode,"after");
dojo.destroy(_3.imgNode);
_3.imgNode=_4;
_3._makeAnims();
_3._wasStyled=false;
}
dojo.style(_3.imgNode,"opacity","0");
dojo.style(_3.titleNode,"opacity","0");
var _5=_2.href;
if((_2.group&&_2!=="XnoGroupX")||_3.inGroup){
if(!_3.inGroup){
_3.inGroup=_3._groups[(_2.group)];
dojo.forEach(_3.inGroup,function(g,i){
if(g.href==_2.href){
_3._index=i;
}
});
}
if(!_3._index){
_3._index=0;
var sr=_3.inGroup[_3._index];
_5=(sr&&sr.href)||_3.errorImg;
}
_3.groupCount.innerHTML=" ("+(_3._index+1)+" of "+Math.max(1,_3.inGroup.length)+")";
_3.prevButtonNode.style.visibility="visible";
_3.nextButtonNode.style.visibility="visible";
}else{
_3.groupCount.innerHTML="";
_3.prevButtonNode.style.visibility="hidden";
_3.nextButtonNode.style.visibility="hidden";
}
if(!_2.leaveTitle){
_3.textNode.innerHTML=_2.title;
}
_3._ready(_5);
},_ready:function(_6){
var _7=this;
_7._imgError=dojo.connect(_7.imgNode,"error",_7,function(){
dojo.disconnect(_7._imgError);
_7.imgNode.src=_7.errorImg;
_7.textNode.innerHTML=_7.errorMessage;
});
_7._imgConnect=dojo.connect(_7.imgNode,"load",_7,function(e){
_7.resizeTo({w:_7.imgNode.width,h:_7.imgNode.height,duration:_7.duration});
dojo.disconnect(_7._imgConnect);
if(_7._imgError){
dojo.disconnect(_7._imgError);
}
});
_7.imgNode.src=_6;
},_nextImage:function(){
if(!this.inGroup){
return;
}
if(this._index+1<this.inGroup.length){
this._index++;
}else{
this._index=0;
}
this._loadImage();
},_prevImage:function(){
if(this.inGroup){
if(this._index==0){
this._index=this.inGroup.length-1;
}else{
this._index--;
}
this._loadImage();
}
},_loadImage:function(){
this._loadingAnim.play(1);
},_prepNodes:function(){
this._imageReady=false;
if(this.inGroup&&this.inGroup[this._index]){
this.show({href:this.inGroup[this._index].href,title:this.inGroup[this._index].title});
}else{
this.show({title:this.errorMessage,href:this.errorImg});
}
},resizeTo:function(_8,_9){
var _a=dojo.boxModel=="border-box"?dojo._getBorderExtents(this.domNode).w:0,_b=_9||{h:30};
this._lastTitleSize=_b;
if(this.adjust&&(_8.h+_b.h+_a+80>this._vp.h||_8.w+_a+60>this._vp.w)){
this._lastSize=_8;
_8=this._scaleToFit(_8);
}
this._currentSize=_8;
var _c=dojox.fx.sizeTo({node:this.containerNode,duration:_8.duration||this.duration,width:_8.w+_a,height:_8.h+_b.h+_a});
this.connect(_c,"onEnd","_showImage");
_c.play(15);
},_scaleToFit:function(_d){
var ns={};
if(this._vp.h>this._vp.w){
ns.w=this._vp.w-80;
ns.h=ns.w*(_d.h/_d.w);
}else{
ns.h=this._vp.h-60-this._lastTitleSize.h;
ns.w=ns.h*(_d.w/_d.h);
}
this._wasStyled=true;
this._setImageSize(ns);
ns.duration=_d.duration;
return ns;
},_setImageSize:function(_e){
var s=this.imgNode;
s.height=_e.h;
s.width=_e.w;
},_size:function(){
},_position:function(e){
this._vp=dojo.window.getBox();
this.inherited(arguments);
if(e&&e.type=="resize"){
if(this._wasStyled){
this._setImageSize(this._lastSize);
this.resizeTo(this._lastSize);
}else{
if(this.imgNode.height+80>this._vp.h||this.imgNode.width+60>this._vp.h){
this.resizeTo({w:this.imgNode.width,h:this.imgNode.height});
}
}
}
},_showImage:function(){
this._showImageAnim.play(1);
},_showNav:function(){
var _f=dojo.marginBox(this.titleNode);
if(_f.h>this._lastTitleSize.h){
this.resizeTo(this._wasStyled?this._lastSize:this._currentSize,_f);
}else{
this._showNavAnim.play(1);
}
},hide:function(){
dojo.fadeOut({node:this.titleNode,duration:200,onEnd:dojo.hitch(this,function(){
this.imgNode.src=this._blankGif;
})}).play(5);
this.inherited(arguments);
this.inGroup=null;
this._index=null;
},addImage:function(_10,_11){
var g=_11;
if(!_10.href){
return;
}
if(g){
if(!this._groups[g]){
this._groups[g]=[];
}
this._groups[g].push(_10);
}else{
this._groups["XnoGroupX"].push(_10);
}
},removeImage:function(_12){
var g=_12.group||"XnoGroupX";
dojo.every(this._groups[g],function(_13,i,ar){
if(_13.href==_12.href){
ar.splice(i,1);
return false;
}
return true;
});
},removeGroup:function(_14){
if(this._groups[_14]){
this._groups[_14]=[];
}
},_handleKey:function(e){
if(!this.open){
return;
}
var dk=dojo.keys;
switch(e.charOrCode){
case dk.ESCAPE:
this.hide();
break;
case dk.DOWN_ARROW:
case dk.RIGHT_ARROW:
case 78:
this._nextImage();
break;
case dk.UP_ARROW:
case dk.LEFT_ARROW:
case 80:
this._prevImage();
break;
}
},_makeAnims:function(){
dojo.forEach(this._animConnects,dojo.disconnect);
this._animConnects=[];
this._showImageAnim=dojo.fadeIn({node:this.imgNode,duration:this.duration});
this._animConnects.push(dojo.connect(this._showImageAnim,"onEnd",this,"_showNav"));
this._loadingAnim=dojo.fx.combine([dojo.fadeOut({node:this.imgNode,duration:175}),dojo.fadeOut({node:this.titleNode,duration:175})]);
this._animConnects.push(dojo.connect(this._loadingAnim,"onEnd",this,"_prepNodes"));
this._showNavAnim=dojo.fadeIn({node:this.titleNode,duration:225});
},onClick:function(_15){
},_onImageClick:function(e){
if(e&&e.target==this.imgNode){
this.onClick(this._lastGroup);
if(this._lastGroup.declaredClass){
this._lastGroup.onClick(this._lastGroup);
}
}
}});
}
