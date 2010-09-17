/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.lang.aspect.tracer"]){
dojo._hasResource["dojox.lang.aspect.tracer"]=true;
dojo.provide("dojox.lang.aspect.tracer");
(function(){
var _1=dojox.lang.aspect;
var _2=function(_3){
this.method=_3?"group":"log";
if(_3){
this.after=this._after;
}
};
dojo.extend(_2,{before:function(){
var _4=_1.getContext(),_5=_4.joinPoint,_6=Array.prototype.join.call(arguments,", ");
console[this.method](_4.instance,"=>",_5.targetName+"("+_6+")");
},afterReturning:function(_7){
var _8=_1.getContext().joinPoint;
if(typeof _7!="undefined"){
console.log(_8.targetName+"() returns:",_7);
}else{
console.log(_8.targetName+"() returns");
}
},afterThrowing:function(_9){
console.log(_1.getContext().joinPoint.targetName+"() throws:",_9);
},_after:function(_a){
console.groupEnd();
}});
_1.tracer=function(_b){
return new _2(_b);
};
})();
}
