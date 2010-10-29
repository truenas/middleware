/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.form.RangeSlider"]){
dojo._hasResource["dojox.form.RangeSlider"]=true;
dojo.provide("dojox.form.RangeSlider");
dojo.require("dijit.form.HorizontalSlider");
dojo.require("dijit.form.VerticalSlider");
dojo.require("dojox.fx");
(function(){
var _1=function(a,b){
return b-a;
},_2=function(a,b){
return a-b;
};
dojo.declare("dojox.form._RangeSliderMixin",null,{value:[0,100],postMixInProperties:function(){
this.inherited(arguments);
this.value=dojo.map(this.value,function(i){
return parseInt(i,10);
});
},postCreate:function(){
this.inherited(arguments);
this.value.sort(this._isReversed()?_1:_2);
var _3=this;
var _4=function(){
dijit.form._SliderMoverMax.apply(this,arguments);
this.widget=_3;
};
dojo.extend(_4,dijit.form._SliderMoverMax.prototype);
this._movableMax=new dojo.dnd.Moveable(this.sliderHandleMax,{mover:_4});
dijit.setWaiState(this.focusNodeMax,"valuemin",this.minimum);
dijit.setWaiState(this.focusNodeMax,"valuemax",this.maximum);
var _5=function(){
dijit.form._SliderBarMover.apply(this,arguments);
this.widget=_3;
};
dojo.extend(_5,dijit.form._SliderBarMover.prototype);
this._movableBar=new dojo.dnd.Moveable(this.progressBar,{mover:_5});
},destroy:function(){
this.inherited(arguments);
this._movableMax.destroy();
this._movableBar.destroy();
},_onKeyPress:function(e){
if(this.disabled||this.readOnly||e.altKey||e.ctrlKey){
return;
}
var _6=e.currentTarget,_7=false,_8=false,k=dojo.keys;
if(_6==this.sliderHandle){
_7=true;
}else{
if(_6==this.progressBar){
_8=_7=true;
}else{
if(_6==this.sliderHandleMax){
_8=true;
}
}
}
switch(e.keyCode){
case k.HOME:
this._setValueAttr(this.minimum,true,_8);
break;
case k.END:
this._setValueAttr(this.maximum,true,_8);
break;
case ((this._descending||this.isLeftToRight())?k.RIGHT_ARROW:k.LEFT_ARROW):
case (this._descending===false?k.DOWN_ARROW:k.UP_ARROW):
case (this._descending===false?k.PAGE_DOWN:k.PAGE_UP):
if(_7&&_8){
this._bumpValue([{"change":e.keyCode==k.PAGE_UP?this.pageIncrement:1,"useMaxValue":true},{"change":e.keyCode==k.PAGE_UP?this.pageIncrement:1,"useMaxValue":false}]);
}else{
if(_7){
this._bumpValue(e.keyCode==k.PAGE_UP?this.pageIncrement:1,true);
}else{
if(_8){
this._bumpValue(e.keyCode==k.PAGE_UP?this.pageIncrement:1);
}
}
}
break;
case ((this._descending||this.isLeftToRight())?k.LEFT_ARROW:k.RIGHT_ARROW):
case (this._descending===false?k.UP_ARROW:k.DOWN_ARROW):
case (this._descending===false?k.PAGE_UP:k.PAGE_DOWN):
if(_7&&_8){
this._bumpValue([{change:e.keyCode==k.PAGE_DOWN?-this.pageIncrement:-1,useMaxValue:false},{change:e.keyCode==k.PAGE_DOWN?-this.pageIncrement:-1,useMaxValue:true}]);
}else{
if(_7){
this._bumpValue(e.keyCode==k.PAGE_DOWN?-this.pageIncrement:-1);
}else{
if(_8){
this._bumpValue(e.keyCode==k.PAGE_DOWN?-this.pageIncrement:-1,true);
}
}
}
break;
default:
dijit.form._FormValueWidget.prototype._onKeyPress.apply(this,arguments);
this.inherited(arguments);
return;
}
dojo.stopEvent(e);
},_onHandleClickMax:function(e){
if(this.disabled||this.readOnly){
return;
}
if(!dojo.isIE){
dijit.focus(this.sliderHandleMax);
}
dojo.stopEvent(e);
},_onClkIncBumper:function(){
this._setValueAttr(this._descending===false?this.minimum:this.maximum,true,true);
},_bumpValue:function(_9,_a){
var _b=dojo.isArray(_9)?[this._getBumpValue(_9[0].change,_9[0].useMaxValue),this._getBumpValue(_9[1].change,_9[1].useMaxValue)]:this._getBumpValue(_9,_a);
this._setValueAttr(_b,true,!dojo.isArray(_9)&&((_9>0&&!_a)||(_a&&_9<0)));
},_getBumpValue:function(_c,_d){
var s=dojo.getComputedStyle(this.sliderBarContainer),c=dojo._getContentBox(this.sliderBarContainer,s),_e=this.discreteValues,_f=!_d?this.value[0]:this.value[1];
if(_e<=1||_e==Infinity){
_e=c[this._pixelCount];
}
_e--;
if((this._isReversed()&&_c<0)||(_c>0&&!this._isReversed())){
_f=!_d?this.value[1]:this.value[0];
}
var _10=(_f-this.minimum)*_e/(this.maximum-this.minimum)+_c;
if(_10<0){
_10=0;
}
if(_10>_e){
_10=_e;
}
return _10*(this.maximum-this.minimum)/_e+this.minimum;
},_onBarClick:function(e){
if(this.disabled||this.readOnly){
return;
}
if(!dojo.isIE){
dijit.focus(this.progressBar);
}
dojo.stopEvent(e);
},_onRemainingBarClick:function(e){
if(this.disabled||this.readOnly){
return;
}
if(!dojo.isIE){
dijit.focus(this.progressBar);
}
var _11=dojo.coords(this.sliderBarContainer,true),bar=dojo.coords(this.progressBar,true),_12=e[this._mousePixelCoord]-_11[this._startingPixelCoord],_13=bar[this._startingPixelCount],_14=_13+bar[this._pixelCount],_15=this._isReversed()?_12<=_13:_12>=_14,p=this._isReversed()?_11[this._pixelCount]-_12:_12;
this._setPixelValue(p,_11[this._pixelCount],true,_15);
dojo.stopEvent(e);
},_setPixelValue:function(_16,_17,_18,_19){
if(this.disabled||this.readOnly){
return;
}
var _1a=this._getValueByPixelValue(_16,_17);
this._setValueAttr(_1a,_18,_19);
},_getValueByPixelValue:function(_1b,_1c){
_1b=_1b<0?0:_1c<_1b?_1c:_1b;
var _1d=this.discreteValues;
if(_1d<=1||_1d==Infinity){
_1d=_1c;
}
_1d--;
var _1e=_1c/_1d;
var _1f=Math.round(_1b/_1e);
return (this.maximum-this.minimum)*_1f/_1d+this.minimum;
},_setValueAttr:function(_20,_21,_22){
var _23=this.value;
if(!dojo.isArray(_20)){
if(_22){
if(this._isReversed()){
_23[0]=_20;
}else{
_23[1]=_20;
}
}else{
if(this._isReversed()){
_23[1]=_20;
}else{
_23[0]=_20;
}
}
}else{
_23=_20;
}
this._lastValueReported="";
this.valueNode.value=this.value=_20=_23;
dijit.setWaiState(this.focusNode,"valuenow",_23[0]);
dijit.setWaiState(this.focusNodeMax,"valuenow",_23[1]);
this.value.sort(this._isReversed()?_1:_2);
dijit.form._FormValueWidget.prototype._setValueAttr.apply(this,arguments);
this._printSliderBar(_21,_22);
},_printSliderBar:function(_24,_25){
var _26=(this.value[0]-this.minimum)/(this.maximum-this.minimum);
var _27=(this.value[1]-this.minimum)/(this.maximum-this.minimum);
var _28=_26;
if(_26>_27){
_26=_27;
_27=_28;
}
var _29=this._isReversed()?((1-_26)*100):(_26*100);
var _2a=this._isReversed()?((1-_27)*100):(_27*100);
var _2b=this._isReversed()?((1-_27)*100):(_26*100);
if(_24&&this.slideDuration>0&&this.progressBar.style[this._progressPixelSize]){
var _2c=_25?_27:_26;
var _2d=this;
var _2e={};
var _2f=parseFloat(this.progressBar.style[this._handleOffsetCoord]);
var _30=this.slideDuration/10;
if(_30===0){
return;
}
if(_30<0){
_30=0-_30;
}
var _31={};
var _32={};
var _33={};
_31[this._handleOffsetCoord]={start:this.sliderHandle.style[this._handleOffsetCoord],end:_29,units:"%"};
_32[this._handleOffsetCoord]={start:this.sliderHandleMax.style[this._handleOffsetCoord],end:_2a,units:"%"};
_33[this._handleOffsetCoord]={start:this.progressBar.style[this._handleOffsetCoord],end:_2b,units:"%"};
_33[this._progressPixelSize]={start:this.progressBar.style[this._progressPixelSize],end:(_27-_26)*100,units:"%"};
var _34=dojo.animateProperty({node:this.sliderHandle,duration:_30,properties:_31});
var _35=dojo.animateProperty({node:this.sliderHandleMax,duration:_30,properties:_32});
var _36=dojo.animateProperty({node:this.progressBar,duration:_30,properties:_33});
var _37=dojo.fx.combine([_34,_35,_36]);
_37.play();
}else{
this.sliderHandle.style[this._handleOffsetCoord]=_29+"%";
this.sliderHandleMax.style[this._handleOffsetCoord]=_2a+"%";
this.progressBar.style[this._handleOffsetCoord]=_2b+"%";
this.progressBar.style[this._progressPixelSize]=((_27-_26)*100)+"%";
}
}});
dojo.declare("dijit.form._SliderMoverMax",dijit.form._SliderMover,{onMouseMove:function(e){
var _38=this.widget;
var _39=_38._abspos;
if(!_39){
_39=_38._abspos=dojo.coords(_38.sliderBarContainer,true);
_38._setPixelValue_=dojo.hitch(_38,"_setPixelValue");
_38._isReversed_=_38._isReversed();
}
var _3a=e[_38._mousePixelCoord]-_39[_38._startingPixelCoord];
_38._setPixelValue_(_38._isReversed_?(_39[_38._pixelCount]-_3a):_3a,_39[_38._pixelCount],false,true);
},destroy:function(e){
dojo.dnd.Mover.prototype.destroy.apply(this,arguments);
var _3b=this.widget;
_3b._abspos=null;
_3b._setValueAttr(_3b.value,true);
}});
dojo.declare("dijit.form._SliderBarMover",dojo.dnd.Mover,{onMouseMove:function(e){
var _3c=this.widget;
if(_3c.disabled||_3c.readOnly){
return;
}
var _3d=_3c._abspos;
var bar=_3c._bar;
var _3e=_3c._mouseOffset;
if(!_3d){
_3d=_3c._abspos=dojo.coords(_3c.sliderBarContainer,true);
_3c._setPixelValue_=dojo.hitch(_3c,"_setPixelValue");
_3c._getValueByPixelValue_=dojo.hitch(_3c,"_getValueByPixelValue");
_3c._isReversed_=_3c._isReversed();
}
if(!bar){
bar=_3c._bar=dojo.coords(_3c.progressBar,true);
}
if(!_3e){
_3e=_3c._mouseOffset=e[_3c._mousePixelCoord]-_3d[_3c._startingPixelCoord]-bar[_3c._startingPixelCount];
}
var _3f=e[_3c._mousePixelCoord]-_3d[_3c._startingPixelCoord]-_3e,_40=_3f+bar[_3c._pixelCount];
pixelValues=[_3f,_40];
pixelValues.sort(_2);
if(pixelValues[0]<=0){
pixelValues[0]=0;
pixelValues[1]=bar[_3c._pixelCount];
}
if(pixelValues[1]>=_3d[_3c._pixelCount]){
pixelValues[1]=_3d[_3c._pixelCount];
pixelValues[0]=_3d[_3c._pixelCount]-bar[_3c._pixelCount];
}
var _41=[_3c._getValueByPixelValue(_3c._isReversed_?(_3d[_3c._pixelCount]-pixelValues[0]):pixelValues[0],_3d[_3c._pixelCount]),_3c._getValueByPixelValue(_3c._isReversed_?(_3d[_3c._pixelCount]-pixelValues[1]):pixelValues[1],_3d[_3c._pixelCount])];
_3c._setValueAttr(_41,false,false);
},destroy:function(){
dojo.dnd.Mover.prototype.destroy.apply(this,arguments);
var _42=this.widget;
_42._abspos=null;
_42._bar=null;
_42._mouseOffset=null;
_42._setValueAttr(_42.value,true);
}});
dojo.declare("dojox.form.HorizontalRangeSlider",[dijit.form.HorizontalSlider,dojox.form._RangeSliderMixin],{templateString:dojo.cache("dojox.form","resources/HorizontalRangeSlider.html","<table class=\"dijit dijitReset dijitSlider dijitSliderH dojoxRangeSlider\" cellspacing=\"0\" cellpadding=\"0\" border=\"0\" rules=\"none\" dojoAttachEvent=\"onkeypress:_onKeyPress,onkeyup:_onKeyUp\"\n\t><tr class=\"dijitReset\"\n\t\t><td class=\"dijitReset\" colspan=\"2\"></td\n\t\t><td dojoAttachPoint=\"topDecoration\" class=\"dijitReset dijitSliderDecoration dijitSliderDecorationT dijitSliderDecorationH\"></td\n\t\t><td class=\"dijitReset\" colspan=\"2\"></td\n\t></tr\n\t><tr class=\"dijitReset\"\n\t\t><td class=\"dijitReset dijitSliderButtonContainer dijitSliderButtonContainerH\"\n\t\t\t><div class=\"dijitSliderDecrementIconH\" tabIndex=\"-1\" style=\"display:none\" dojoAttachPoint=\"decrementButton\"><span class=\"dijitSliderButtonInner\">-</span></div\n\t\t></td\n\t\t><td class=\"dijitReset\"\n\t\t\t><div class=\"dijitSliderBar dijitSliderBumper dijitSliderBumperH dijitSliderLeftBumper\" dojoAttachEvent=\"onmousedown:_onClkDecBumper\"></div\n\t\t></td\n\t\t><td class=\"dijitReset\"\n\t\t\t><input dojoAttachPoint=\"valueNode\" type=\"hidden\" ${!nameAttrSetting}\n\t\t\t/><div waiRole=\"presentation\" class=\"dojoxRangeSliderBarContainer\" dojoAttachPoint=\"sliderBarContainer\"\n\t\t\t\t><div dojoAttachPoint=\"sliderHandle\" tabIndex=\"${tabIndex}\" class=\"dijitSliderMoveable dijitSliderMoveableH\" dojoAttachEvent=\"onmousedown:_onHandleClick\" waiRole=\"slider\" valuemin=\"${minimum}\" valuemax=\"${maximum}\"\n\t\t\t\t\t><div class=\"dijitSliderImageHandle dijitSliderImageHandleH\"></div\n\t\t\t\t></div\n\t\t\t\t><div waiRole=\"presentation\" dojoAttachPoint=\"progressBar,focusNode\" class=\"dijitSliderBar dijitSliderBarH dijitSliderProgressBar dijitSliderProgressBarH\" dojoAttachEvent=\"onmousedown:_onBarClick\"></div\n\t\t\t\t><div dojoAttachPoint=\"sliderHandleMax,focusNodeMax\" tabIndex=\"${tabIndex}\" class=\"dijitSliderMoveable dijitSliderMoveableH\" dojoAttachEvent=\"onmousedown:_onHandleClickMax\" waiRole=\"sliderMax\" valuemin=\"${minimum}\" valuemax=\"${maximum}\"\n\t\t\t\t\t><div class=\"dijitSliderImageHandle dijitSliderImageHandleH\"></div\n\t\t\t\t></div\n\t\t\t\t><div waiRole=\"presentation\" dojoAttachPoint=\"remainingBar\" class=\"dijitSliderBar dijitSliderBarH dijitSliderRemainingBar dijitSliderRemainingBarH\" dojoAttachEvent=\"onmousedown:_onRemainingBarClick\"></div\n\t\t\t></div\n\t\t></td\n\t\t><td class=\"dijitReset\"\n\t\t\t><div class=\"dijitSliderBar dijitSliderBumper dijitSliderBumperH dijitSliderRightBumper\" dojoAttachEvent=\"onmousedown:_onClkIncBumper\"></div\n\t\t></td\n\t\t><td class=\"dijitReset dijitSliderButtonContainer dijitSliderButtonContainerH\"\n\t\t\t><div class=\"dijitSliderIncrementIconH\" tabIndex=\"-1\" style=\"display:none\" dojoAttachPoint=\"incrementButton\"><span class=\"dijitSliderButtonInner\">+</span></div\n\t\t></td\n\t></tr\n\t><tr class=\"dijitReset\"\n\t\t><td class=\"dijitReset\" colspan=\"2\"></td\n\t\t><td dojoAttachPoint=\"containerNode,bottomDecoration\" class=\"dijitReset dijitSliderDecoration dijitSliderDecorationB dijitSliderDecorationH\"></td\n\t\t><td class=\"dijitReset\" colspan=\"2\"></td\n\t></tr\n></table>\n")});
dojo.declare("dojox.form.VerticalRangeSlider",[dijit.form.VerticalSlider,dojox.form._RangeSliderMixin],{templateString:dojo.cache("dojox.form","resources/VerticalRangeSlider.html","<table class=\"dijitReset dijitSlider dijitSliderV dojoxRangeSlider\" cellspacing=\"0\" cellpadding=\"0\" border=\"0\" rules=\"none\"\n\t><tr class=\"dijitReset\"\n\t\t><td class=\"dijitReset\"></td\n\t\t><td class=\"dijitReset dijitSliderButtonContainer dijitSliderButtonContainerV\"\n\t\t\t><div class=\"dijitSliderIncrementIconV\" tabIndex=\"-1\" style=\"display:none\" dojoAttachPoint=\"decrementButton\" dojoAttachEvent=\"onclick: increment\"><span class=\"dijitSliderButtonInner\">+</span></div\n\t\t></td\n\t\t><td class=\"dijitReset\"></td\n\t></tr\n\t><tr class=\"dijitReset\"\n\t\t><td class=\"dijitReset\"></td\n\t\t><td class=\"dijitReset\"\n\t\t\t><center><div class=\"dijitSliderBar dijitSliderBumper dijitSliderBumperV dijitSliderTopBumper\" dojoAttachEvent=\"onclick:_onClkIncBumper\"></div></center\n\t\t></td\n\t\t><td class=\"dijitReset\"></td\n\t></tr\n\t><tr class=\"dijitReset\"\n\t\t><td dojoAttachPoint=\"leftDecoration\" class=\"dijitReset dijitSliderDecoration dijitSliderDecorationL dijitSliderDecorationV\" style=\"text-align:center;height:100%;\"></td\n\t\t><td class=\"dijitReset\" style=\"height:100%;\"\n\t\t\t><input dojoAttachPoint=\"valueNode\" type=\"hidden\" ${!nameAttrSetting}\n\t\t\t/><center waiRole=\"presentation\" style=\"position:relative;height:100%;\" dojoAttachPoint=\"sliderBarContainer\"\n\t\t\t\t><div waiRole=\"presentation\" dojoAttachPoint=\"remainingBar\" class=\"dijitSliderBar dijitSliderBarV dijitSliderRemainingBar dijitSliderRemainingBarV\" dojoAttachEvent=\"onmousedown:_onRemainingBarClick\"\n\t\t\t\t\t><div dojoAttachPoint=\"sliderHandle\" tabIndex=\"${tabIndex}\" class=\"dijitSliderMoveable dijitSliderMoveableV\" dojoAttachEvent=\"onkeypress:_onKeyPress,onmousedown:_onHandleClick\" style=\"vertical-align:top;\" waiRole=\"slider\" valuemin=\"${minimum}\" valuemax=\"${maximum}\"\n\t\t\t\t\t\t><div class=\"dijitSliderImageHandle dijitSliderImageHandleV\"></div\n\t\t\t\t\t></div\n\t\t\t\t\t><div waiRole=\"presentation\" dojoAttachPoint=\"progressBar,focusNode\" tabIndex=\"${tabIndex}\" class=\"dijitSliderBar dijitSliderBarV dijitSliderProgressBar dijitSliderProgressBarV\" dojoAttachEvent=\"onkeypress:_onKeyPress,onmousedown:_onBarClick\"\n\t\t\t\t\t></div\n\t\t\t\t\t><div dojoAttachPoint=\"sliderHandleMax,focusNodeMax\" tabIndex=\"${tabIndex}\" class=\"dijitSliderMoveable dijitSliderMoveableV\" dojoAttachEvent=\"onkeypress:_onKeyPress,onmousedown:_onHandleClickMax\" style=\"vertical-align:top;\" waiRole=\"slider\" valuemin=\"${minimum}\" valuemax=\"${maximum}\"\n\t\t\t\t\t\t><div class=\"dijitSliderImageHandle dijitSliderImageHandleV\"></div\n\t\t\t\t\t></div\n\t\t\t\t></div\n\t\t\t></center\n\t\t></td\n\t\t><td dojoAttachPoint=\"containerNode,rightDecoration\" class=\"dijitReset dijitSliderDecoration dijitSliderDecorationR dijitSliderDecorationV\" style=\"text-align:center;height:100%;\"></td\n\t></tr\n\t><tr class=\"dijitReset\"\n\t\t><td class=\"dijitReset\"></td\n\t\t><td class=\"dijitReset\"\n\t\t\t><center><div class=\"dijitSliderBar dijitSliderBumper dijitSliderBumperV dijitSliderBottomBumper\" dojoAttachEvent=\"onclick:_onClkDecBumper\"></div></center\n\t\t></td\n\t\t><td class=\"dijitReset\"></td\n\t></tr\n\t><tr class=\"dijitReset\"\n\t\t><td class=\"dijitReset\"></td\n\t\t><td class=\"dijitReset dijitSliderButtonContainer dijitSliderButtonContainerV\"\n\t\t\t><div class=\"dijitSliderDecrementIconV\" tabIndex=\"-1\" style=\"display:none\" dojoAttachPoint=\"incrementButton\" dojoAttachEvent=\"onclick: decrement\"><span class=\"dijitSliderButtonInner\">-</span></div\n\t\t></td\n\t\t><td class=\"dijitReset\"></td\n\t></tr\n></table>\n")});
})();
}
