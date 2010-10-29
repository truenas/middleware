/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.mobile.app._base"]){
dojo._hasResource["dojox.mobile.app._base"]=true;
dojo.provide("dojox.mobile.app._base");
dojo.experimental("dojox.mobile.app._base");
dojo.require("dijit._base");
dojo.require("dijit._Widget");
dojo.require("dojox.mobile");
dojo.require("dojox.mobile.parser");
dojo.require("dojox.mobile.app._event");
dojo.require("dojox.mobile.app._Widget");
dojo.require("dojox.mobile.app.StageController");
dojo.require("dojox.mobile.app.SceneController");
dojo.require("dojox.mobile.app.SceneAssistant");
dojo.require("dojox.mobile.app.AlertDialog");
dojo.require("dojox.mobile.app.List");
dojo.require("dojox.mobile.app.ListSelector");
dojo.require("dojox.mobile.app.TextBox");
dojo.require("dojox.mobile.app.ImageView");
dojo.require("dojox.mobile.app.ImageThumbView");
(function(){
var _1;
var _2;
var _3=["dojox.mobile","dojox.mobile.parser"];
var _4={};
var _5;
var _6;
var _7=[];
function _8(_9,_a){
var _b;
var _c;
do{
_b=_9.pop();
if(_b.source){
_c=_b.source;
}else{
if(_b.module){
_c=dojo.baseUrl+dojo._getModuleSymbols(_b.module).join("/")+".js";
}else{
alert("Error: invalid JavaScript resource "+dojo.toJson(_b));
return;
}
}
}while(_9.length>0&&_4[_c]);
if(_9.length<1&&_4[_c]){
console.log("All resources already loaded");
_a();
return;
}
console.log("loading url "+_c);
dojo.xhrGet({url:_c,sync:false}).addCallbacks(function(_d){
dojo["eval"](_d);
if(_9.length>0){
_8(_9,_a);
}else{
_a();
}
},function(){
alert("Failed to load resource "+_c);
});
};
var _e=function(){
_1=new dojox.mobile.app.StageController(_6);
var _f={id:"com.test.app",version:"1.0.0",initialScene:"main"};
if(window["appInfo"]){
dojo.mixin(_f,window["appInfo"]);
}
_2=dojox.mobile.app.info=_f;
if(_2.title){
var _10=dojo.query("head title")[0]||dojo.create("title",{},dojo.query("head")[0]);
document.title=_2.title;
}
_1.pushScene(_2.initialScene);
};
dojo.mixin(dojox.mobile.app,{init:function(_11){
_6=_11||dojo.body();
dojo.subscribe("/dojox/mobile/app/goback",function(){
_1.popScene();
});
dojo.subscribe("/dojox/mobile/app/alert",function(_12){
dojox.mobile.app.getActiveSceneController().showAlertDialog(_12);
});
dojo.xhrGet({url:"view-resources.json",load:function(_13){
var _14=[];
if(_13){
_7=_13=dojo.fromJson(_13);
console.log("Got scene resources",_7);
for(var i=0;i<_13.length;i++){
if(!_13[i].scene){
_14.push(_13[i]);
}
}
}
if(_14.length>0){
console.log("Loading initial resources");
_8(_14,_e);
}else{
console.log("No initial resources");
_e();
}
},error:_e});
},getActiveSceneController:function(){
return _1.getActiveSceneController();
},getStageController:function(){
return _1;
},loadResources:function(_15,_16){
_8(_15,_16);
},loadResourcesForScene:function(_17,_18){
var _19=[];
for(var i=0;i<_7.length;i++){
if(_7[i].scene==_17){
_19.push(_7[i]);
}
}
if(_19.length>0){
console.log("Loading "+_19.length+" resources for"+_17);
_8(_19,_18);
}else{
_18();
}
},resolveTemplate:function(_1a){
return "app/views/"+_1a+"/"+_1a+"-scene.html";
},resolveAssistant:function(_1b){
return "app/assistants/"+_1b+"-assistant.js";
}});
})();
}
