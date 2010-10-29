/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit._editor.plugins.Print"]){
dojo._hasResource["dijit._editor.plugins.Print"]=true;
dojo.provide("dijit._editor.plugins.Print");
dojo.require("dijit._editor._Plugin");
dojo.require("dijit.form.Button");
dojo.require("dojo.i18n");
dojo.requireLocalization("dijit._editor","commands",null,"ROOT,ar,ca,cs,da,de,el,es,fi,fr,he,hu,it,ja,ko,nb,nl,pl,pt,pt-pt,ro,ru,sk,sl,sv,th,tr,zh,zh-tw");
dojo.declare("dijit._editor.plugins.Print",dijit._editor._Plugin,{_initButton:function(){
var _1=dojo.i18n.getLocalization("dijit._editor","commands"),_2=this.editor;
this.button=new dijit.form.Button({label:_1["print"],dir:_2.dir,lang:_2.lang,showLabel:false,iconClass:this.iconClassPrefix+" "+this.iconClassPrefix+"Print",tabIndex:"-1",onClick:dojo.hitch(this,"_print")});
},setEditor:function(_3){
this.editor=_3;
this._initButton();
this.editor.onLoadDeferred.addCallback(dojo.hitch(this,function(){
if(!this.editor.iframe.contentWindow["print"]){
this.button.set("disabled",true);
}
}));
},_print:function(){
var _4=this.editor.iframe;
if(_4.contentWindow["print"]){
if(!dojo.isOpera&&!dojo.isChrome){
dijit.focus(_4);
_4.contentWindow.print();
}else{
var _5=this.editor.document;
var _6=this.editor.get("value");
_6="<html><head><meta http-equiv='Content-Type' "+"content='text/html; charset='UTF-8'></head><body>"+_6+"</body></html>";
var _7=window.open("javascript: ''","","status=0,menubar=0,location=0,toolbar=0,"+"width=1,height=1,resizable=0,scrollbars=0");
_7.document.open();
_7.document.write(_6);
_7.document.close();
var _8=[];
var _9=_5.getElementsByTagName("style");
if(_9){
var i;
for(i=0;i<_9.length;i++){
var _a=_9[i].innerHTML;
var _b=_7.document.createElement("style");
_b.appendChild(_7.document.createTextNode(_a));
_7.document.getElementsByTagName("head")[0].appendChild(_b);
}
}
_7.print();
_7.close();
}
}
}});
dojo.subscribe(dijit._scopeName+".Editor.getPlugin",null,function(o){
if(o.plugin){
return;
}
var _c=o.args.name.toLowerCase();
if(_c==="print"){
o.plugin=new dijit._editor.plugins.Print({command:"print"});
}
});
}
