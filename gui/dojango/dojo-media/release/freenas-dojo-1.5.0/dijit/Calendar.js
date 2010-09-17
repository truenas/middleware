/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.Calendar"]){
dojo._hasResource["dijit.Calendar"]=true;
dojo.provide("dijit.Calendar");
dojo.require("dojo.cldr.supplemental");
dojo.require("dojo.date");
dojo.require("dojo.date.locale");
dojo.require("dijit._Widget");
dojo.require("dijit._Templated");
dojo.require("dijit._CssStateMixin");
dojo.declare("dijit.Calendar",[dijit._Widget,dijit._Templated,dijit._CssStateMixin],{templateString:dojo.cache("dijit","templates/Calendar.html","<table cellspacing=\"0\" cellpadding=\"0\" class=\"dijitCalendarContainer\" role=\"grid\" dojoAttachEvent=\"onkeypress: _onKeyPress\">\n\t<thead>\n\t\t<tr class=\"dijitReset dijitCalendarMonthContainer\" valign=\"top\">\n\t\t\t<th class='dijitReset dijitCalendarArrow' dojoAttachPoint=\"decrementMonth\">\n\t\t\t\t<img src=\"${_blankGif}\" alt=\"\" class=\"dijitCalendarIncrementControl dijitCalendarDecrease\" waiRole=\"presentation\"/>\n\t\t\t\t<span dojoAttachPoint=\"decreaseArrowNode\" class=\"dijitA11ySideArrow\">-</span>\n\t\t\t</th>\n\t\t\t<th class='dijitReset' colspan=\"5\">\n\t\t\t\t<div class=\"dijitVisible\">\n\t\t\t\t\t<div class=\"dijitPopup dijitMenu dijitMenuPassive dijitHidden\" dojoAttachPoint=\"monthDropDown\" dojoAttachEvent=\"onmouseup: _onMonthSelect, onmouseover: _onMenuHover, onmouseout: _onMenuHover\">\n\t\t\t\t\t\t<div class=\"dijitCalendarMonthLabelTemplate dijitCalendarMonthLabel\"></div>\n\t\t\t\t\t</div>\n\t\t\t\t</div>\n\t\t\t\t<div dojoAttachPoint=\"monthLabelSpacer\" class=\"dijitSpacer\"></div>\n\t\t\t\t<div dojoAttachPoint=\"monthLabelNode\" class=\"dijitCalendarMonthLabel dijitInline dijitVisible\" dojoAttachEvent=\"onmousedown: _onMonthToggle\"></div>\n\t\t\t</th>\n\t\t\t<th class='dijitReset dijitCalendarArrow' dojoAttachPoint=\"incrementMonth\">\n\t\t\t\t<img src=\"${_blankGif}\" alt=\"\" class=\"dijitCalendarIncrementControl dijitCalendarIncrease\" waiRole=\"presentation\"/>\n\t\t\t\t<span dojoAttachPoint=\"increaseArrowNode\" class=\"dijitA11ySideArrow\">+</span>\n\t\t\t</th>\n\t\t</tr>\n\t\t<tr>\n\t\t\t<th class=\"dijitReset dijitCalendarDayLabelTemplate\" role=\"columnheader\"><span class=\"dijitCalendarDayLabel\"></span></th>\n\t\t</tr>\n\t</thead>\n\t<tbody dojoAttachEvent=\"onclick: _onDayClick, onmouseover: _onDayMouseOver, onmouseout: _onDayMouseOut, onmousedown: _onDayMouseDown, onmouseup: _onDayMouseUp\" class=\"dijitReset dijitCalendarBodyContainer\">\n\t\t<tr class=\"dijitReset dijitCalendarWeekTemplate\" role=\"row\">\n\t\t\t<td class=\"dijitReset dijitCalendarDateTemplate\" role=\"gridcell\"><span class=\"dijitCalendarDateLabel\"></span></td>\n\t\t</tr>\n\t</tbody>\n\t<tfoot class=\"dijitReset dijitCalendarYearContainer\">\n\t\t<tr>\n\t\t\t<td class='dijitReset' valign=\"top\" colspan=\"7\">\n\t\t\t\t<h3 class=\"dijitCalendarYearLabel\">\n\t\t\t\t\t<span dojoAttachPoint=\"previousYearLabelNode\" class=\"dijitInline dijitCalendarPreviousYear\"></span>\n\t\t\t\t\t<span dojoAttachPoint=\"currentYearLabelNode\" class=\"dijitInline dijitCalendarSelectedYear\"></span>\n\t\t\t\t\t<span dojoAttachPoint=\"nextYearLabelNode\" class=\"dijitInline dijitCalendarNextYear\"></span>\n\t\t\t\t</h3>\n\t\t\t</td>\n\t\t</tr>\n\t</tfoot>\n</table>\n"),value:new Date(),datePackage:"dojo.date",dayWidth:"narrow",tabIndex:"0",baseClass:"dijitCalendar",cssStateNodes:{"decrementMonth":"dijitCalendarArrow","incrementMonth":"dijitCalendarArrow","previousYearLabelNode":"dijitCalendarPreviousYear","nextYearLabelNode":"dijitCalendarNextYear"},attributeMap:dojo.delegate(dijit._Widget.prototype.attributeMap,{tabIndex:"domNode"}),setValue:function(_1){
dojo.deprecated("dijit.Calendar:setValue() is deprecated.  Use set('value', ...) instead.","","2.0");
this.set("value",_1);
},_getValueAttr:function(){
var _2=new this.dateClassObj(this.value);
_2.setHours(0,0,0,0);
if(_2.getDate()<this.value.getDate()){
_2=this.dateFuncObj.add(_2,"hour",1);
}
return _2;
},_setValueAttr:function(_3){
if(!this.value||this.dateFuncObj.compare(_3,this.value)){
_3=new this.dateClassObj(_3);
_3.setHours(1);
this.displayMonth=new this.dateClassObj(_3);
if(!this.isDisabledDate(_3,this.lang)){
this.value=_3;
this.onChange(this.get("value"));
}
dojo.attr(this.domNode,"aria-label",this.dateLocaleModule.format(_3,{selector:"date",formatLength:"full"}));
this._populateGrid();
}
},_setText:function(_4,_5){
while(_4.firstChild){
_4.removeChild(_4.firstChild);
}
_4.appendChild(dojo.doc.createTextNode(_5));
},_populateGrid:function(){
var _6=this.displayMonth;
_6.setDate(1);
var _7=_6.getDay(),_8=this.dateFuncObj.getDaysInMonth(_6),_9=this.dateFuncObj.getDaysInMonth(this.dateFuncObj.add(_6,"month",-1)),_a=new this.dateClassObj(),_b=dojo.cldr.supplemental.getFirstDayOfWeek(this.lang);
if(_b>_7){
_b-=7;
}
dojo.query(".dijitCalendarDateTemplate",this.domNode).forEach(function(_c,i){
i+=_b;
var _d=new this.dateClassObj(_6),_e,_f="dijitCalendar",adj=0;
if(i<_7){
_e=_9-_7+i+1;
adj=-1;
_f+="Previous";
}else{
if(i>=(_7+_8)){
_e=i-_7-_8+1;
adj=1;
_f+="Next";
}else{
_e=i-_7+1;
_f+="Current";
}
}
if(adj){
_d=this.dateFuncObj.add(_d,"month",adj);
}
_d.setDate(_e);
if(!this.dateFuncObj.compare(_d,_a,"date")){
_f="dijitCalendarCurrentDate "+_f;
}
if(this._isSelectedDate(_d,this.lang)){
_f="dijitCalendarSelectedDate "+_f;
}
if(this.isDisabledDate(_d,this.lang)){
_f="dijitCalendarDisabledDate "+_f;
}
var _10=this.getClassForDate(_d,this.lang);
if(_10){
_f=_10+" "+_f;
}
_c.className=_f+"Month dijitCalendarDateTemplate";
_c.dijitDateValue=_d.valueOf();
var _11=dojo.query(".dijitCalendarDateLabel",_c)[0],_12=_d.getDateLocalized?_d.getDateLocalized(this.lang):_d.getDate();
this._setText(_11,_12);
},this);
var _13=this.dateLocaleModule.getNames("months","wide","standAlone",this.lang,_6);
this._setText(this.monthLabelNode,_13[_6.getMonth()]);
dojo.query(".dijitCalendarMonthLabelTemplate",this.domNode).forEach(function(_14,i){
dojo.toggleClass(_14,"dijitHidden",!(i in _13));
this._setText(_14,_13[i]);
},this);
var y=_6.getFullYear()-1;
var d=new this.dateClassObj();
dojo.forEach(["previous","current","next"],function(_15){
d.setFullYear(y++);
this._setText(this[_15+"YearLabelNode"],this.dateLocaleModule.format(d,{selector:"year",locale:this.lang}));
},this);
var _16=this;
var _17=function(_18,_19,adj){
_16._connects.push(dijit.typematic.addMouseListener(_16[_18],_16,function(_1a){
if(_1a>=0){
_16._adjustDisplay(_19,adj);
}
},0.8,500));
};
_17("incrementMonth","month",1);
_17("decrementMonth","month",-1);
_17("nextYearLabelNode","year",1);
_17("previousYearLabelNode","year",-1);
},goToToday:function(){
this.set("value",new this.dateClassObj());
},constructor:function(_1b){
var _1c=(_1b.datePackage&&(_1b.datePackage!="dojo.date"))?_1b.datePackage+".Date":"Date";
this.dateClassObj=dojo.getObject(_1c,false);
this.datePackage=_1b.datePackage||this.datePackage;
this.dateFuncObj=dojo.getObject(this.datePackage,false);
this.dateLocaleModule=dojo.getObject(this.datePackage+".locale",false);
},postMixInProperties:function(){
if(isNaN(this.value)){
delete this.value;
}
this.inherited(arguments);
},postCreate:function(){
this.inherited(arguments);
dojo.setSelectable(this.domNode,false);
var _1d=dojo.hitch(this,function(_1e,n){
var _1f=dojo.query(_1e,this.domNode)[0];
for(var i=0;i<n;i++){
_1f.parentNode.appendChild(_1f.cloneNode(true));
}
});
_1d(".dijitCalendarDayLabelTemplate",6);
_1d(".dijitCalendarDateTemplate",6);
_1d(".dijitCalendarWeekTemplate",5);
var _20=this.dateLocaleModule.getNames("days",this.dayWidth,"standAlone",this.lang);
var _21=dojo.cldr.supplemental.getFirstDayOfWeek(this.lang);
dojo.query(".dijitCalendarDayLabel",this.domNode).forEach(function(_22,i){
this._setText(_22,_20[(i+_21)%7]);
},this);
var _23=new this.dateClassObj(this.value);
var _24=this.dateLocaleModule.getNames("months","wide","standAlone",this.lang,_23);
_1d(".dijitCalendarMonthLabelTemplate",_24.length-1);
dojo.query(".dijitCalendarMonthLabelTemplate",this.domNode).forEach(function(_25,i){
dojo.attr(_25,"month",i);
if(i in _24){
this._setText(_25,_24[i]);
}
dojo.place(_25.cloneNode(true),this.monthLabelSpacer);
},this);
this.value=null;
this.set("value",_23);
},_onMenuHover:function(e){
dojo.stopEvent(e);
dojo.toggleClass(e.target,"dijitMenuItemHover");
},_adjustDisplay:function(_26,_27){
this.displayMonth=this.dateFuncObj.add(this.displayMonth,_26,_27);
this._populateGrid();
},_onMonthToggle:function(evt){
dojo.stopEvent(evt);
if(evt.type=="mousedown"){
var _28=dojo.position(this.monthLabelNode);
var dim={width:_28.w+"px",top:-this.displayMonth.getMonth()*_28.h+"px"};
if((dojo.isIE&&dojo.isQuirks)||dojo.isIE<7){
dim.left=-_28.w/2+"px";
}
dojo.style(this.monthDropDown,dim);
this._popupHandler=this.connect(document,"onmouseup","_onMonthToggle");
}else{
this.disconnect(this._popupHandler);
delete this._popupHandler;
}
dojo.toggleClass(this.monthDropDown,"dijitHidden");
dojo.toggleClass(this.monthLabelNode,"dijitVisible");
},_onMonthSelect:function(evt){
this._onMonthToggle(evt);
this.displayMonth.setMonth(dojo.attr(evt.target,"month"));
this._populateGrid();
},_onDayClick:function(evt){
dojo.stopEvent(evt);
for(var _29=evt.target;_29&&!_29.dijitDateValue;_29=_29.parentNode){
}
if(_29&&!dojo.hasClass(_29,"dijitCalendarDisabledDate")){
this.set("value",_29.dijitDateValue);
this.onValueSelected(this.get("value"));
}
},_onDayMouseOver:function(evt){
var _2a=dojo.hasClass(evt.target,"dijitCalendarDateLabel")?evt.target.parentNode:evt.target;
if(_2a&&(_2a.dijitDateValue||_2a==this.previousYearLabelNode||_2a==this.nextYearLabelNode)){
dojo.addClass(_2a,"dijitCalendarHoveredDate");
this._currentNode=_2a;
}
},_onDayMouseOut:function(evt){
if(!this._currentNode){
return;
}
if(evt.relatedTarget&&evt.relatedTarget.parentNode==this._currentNode){
return;
}
dojo.removeClass(this._currentNode,"dijitCalendarHoveredDate");
if(dojo.hasClass(this._currentNode,"dijitCalendarActiveDate")){
dojo.removeClass(this._currentNode,"dijitCalendarActiveDate");
}
this._currentNode=null;
},_onDayMouseDown:function(evt){
var _2b=evt.target.parentNode;
if(_2b&&_2b.dijitDateValue){
dojo.addClass(_2b,"dijitCalendarActiveDate");
this._currentNode=_2b;
}
},_onDayMouseUp:function(evt){
var _2c=evt.target.parentNode;
if(_2c&&_2c.dijitDateValue){
dojo.removeClass(_2c,"dijitCalendarActiveDate");
}
},_onKeyPress:function(evt){
var dk=dojo.keys,_2d=-1,_2e,_2f=this.value;
switch(evt.keyCode){
case dk.RIGHT_ARROW:
_2d=1;
case dk.LEFT_ARROW:
_2e="day";
if(!this.isLeftToRight()){
_2d*=-1;
}
break;
case dk.DOWN_ARROW:
_2d=1;
case dk.UP_ARROW:
_2e="week";
break;
case dk.PAGE_DOWN:
_2d=1;
case dk.PAGE_UP:
_2e=evt.ctrlKey?"year":"month";
break;
case dk.END:
_2f=this.dateFuncObj.add(_2f,"month",1);
_2e="day";
case dk.HOME:
_2f=new Date(_2f).setDate(1);
break;
case dk.ENTER:
this.onValueSelected(this.get("value"));
break;
case dk.ESCAPE:
default:
return;
}
dojo.stopEvent(evt);
if(_2e){
_2f=this.dateFuncObj.add(_2f,_2e,_2d);
}
this.set("value",_2f);
},onValueSelected:function(_30){
},onChange:function(_31){
},_isSelectedDate:function(_32,_33){
return !this.dateFuncObj.compare(_32,this.value,"date");
},isDisabledDate:function(_34,_35){
},getClassForDate:function(_36,_37){
}});
}
