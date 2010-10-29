/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.grid.enhanced.plugins.NestedSorting"]){
dojo._hasResource["dojox.grid.enhanced.plugins.NestedSorting"]=true;
dojo.provide("dojox.grid.enhanced.plugins.NestedSorting");
dojo.declare("dojox.grid.enhanced.plugins.NestedSorting",null,{sortAttrs:[],_unarySortCell:{},_minColWidth:63,_widthDelta:23,_minColWidthUpdated:false,_sortTipMap:{},_overResizeWidth:3,storeItemSelected:"storeItemSelectedAttr",exceptionalSelectedItems:[],_a11yText:{"dojoxGridDescending":"&#9662;","dojoxGridAscending":"&#9652;","dojoxGridAscendingTip":"&#1784;","dojoxGridDescendingTip":"&#1783;","dojoxGridUnsortedTip":"x"},constructor:function(_1){
_1.mixin(_1,this);
dojo.forEach(_1.views.views,function(_2){
dojo.connect(_2,"renderHeader",dojo.hitch(_2,_1._initSelectCols));
dojo.connect(_2.header,"domousemove",_2.grid,"_sychronizeResize");
});
this.initSort(_1);
_1.keepSortSelection&&dojo.connect(_1,"_onFetchComplete",_1,"updateNewRowSelection");
if(_1.indirectSelection&&_1.rowSelectCell.toggleAllSelection){
dojo.connect(_1.rowSelectCell,"toggleAllSelection",_1,"allSelectionToggled");
}
dojo.subscribe(_1.rowMovedTopic,_1,_1.clearSort);
dojo.subscribe(_1.rowSelectionChangedTopic,_1,_1._selectionChanged);
_1.focus.destroy();
_1.focus=new dojox.grid.enhanced.plugins._NestedSortingFocusManager(_1);
dojo.connect(_1.views,"render",_1,"initAriaInfo");
},initSort:function(_3){
_3.getSortProps=_3._getDsSortAttrs;
},setSortIndex:function(_4,_5,e){
if(!this.nestedSorting){
this.inherited(arguments);
}else{
this.keepSortSelection&&this.retainLastRowSelection();
this.inSorting=true;
this._toggleProgressTip(true,e);
this._updateSortAttrs(e,_5);
this.focus.addSortFocus(e);
if(this.canSort()){
this.sort();
this.edit.info={};
this.update();
}
this._toggleProgressTip(false,e);
this.inSorting=false;
}
},_updateSortAttrs:function(e,_6){
var _7=false;
var _8=!!e.unarySortChoice;
if(_8){
var _9=this.getCellSortInfo(e.cell);
var _a=(this.sortAttrs.length>0&&_9["sortPos"]!=1)?_9["unarySortAsc"]:this._getNewSortState(_9["unarySortAsc"]);
if(_a&&_a!=0){
this.sortAttrs=[{attr:e.cell.field,asc:_a,cell:e.cell,cellNode:e.cellNode}];
this._unarySortCell={cell:e.cell,node:e.cellNode};
}else{
this.sortAttrs=[];
this._unarySortCell=null;
}
}else{
this.setCellSortInfo(e,_6);
}
},getCellSortInfo:function(_b){
if(!_b){
return false;
}
var _c=null;
var _d=this.sortAttrs;
dojo.forEach(_d,function(_e,_f,_10){
if(_e&&_e["attr"]==_b.field&&_e["cell"]==_b){
_c={unarySortAsc:_10[0]?_10[0]["asc"]:undefined,nestedSortAsc:_e["asc"],sortPos:_f+1};
}
});
return _c?_c:{unarySortAsc:_d&&_d[0]?_d[0]["asc"]:undefined,nestedSortAsc:undefined,sortPos:-1};
},setCellSortInfo:function(e,_11){
var _12=e.cell;
var _13=false;
var _14=[];
var _15=this.sortAttrs;
dojo.forEach(_15,dojo.hitch(this,function(_16,_17){
if(_16&&_16["attr"]==_12.field){
var si=_11?_11:this._getNewSortState(_16["asc"]);
if(si==1||si==-1){
_16["asc"]=si;
}else{
if(si==0){
_14.push(_17);
}else{
throw new Exception("Illegal nested sorting status - "+si);
}
}
_13=true;
}
}));
var _18=0;
dojo.forEach(_14,function(_19){
_15.splice((_19-_18++),1);
});
if(!_13){
var si=_11?_11:1;
if(si!=0){
_15.push({attr:_12.field,asc:si,cell:e.cell,cellNode:e.cellNode});
}
}
if(_14.length>0){
this._unarySortCell={cell:_15[0]["cell"],node:_15[0]["cellNode"]};
}
},_getDsSortAttrs:function(){
var _1a=[];
var si=null;
dojo.forEach(this.sortAttrs,function(_1b){
if(_1b&&(_1b["asc"]==1||_1b["asc"]==-1)){
_1a.push({attribute:_1b["attr"],descending:(_1b["asc"]==-1)});
}
});
return _1a.length>0?_1a:null;
},_getNewSortState:function(si){
return si?(si==1?-1:(si==-1?0:1)):1;
},sortStateInt2Str:function(si){
if(!si){
return "Unsorted";
}
switch(si){
case 1:
return "Ascending";
case -1:
return "Descending";
default:
return "Unsorted";
}
},clearSort:function(){
dojo.query("[id*='Sort']",this.viewsHeaderNode).forEach(function(_1c){
dojo.addClass(_1c,"dojoxGridUnsorted");
});
this.sortAttrs=[];
this.focus.clearHeaderFocus();
},_getNestedSortHeaderContent:function(_1d){
var n=_1d.name||_1d.grid.getCellName(_1d);
if(_1d.grid.pluginMgr.isFixedCell(_1d)){
return ["<div class=\"dojoxGridCellContent\">",n,"</div>"].join("");
}
var _1e=_1d.grid.getCellSortInfo(_1d);
var _1f=_1d.grid.sortAttrs;
var _20=(_1f&&_1f.length>1&&_1e["sortPos"]>=1);
var _21=(_1f&&_1f.length==1&&_1e["sortPos"]==1);
var _22=_1d.grid;
var ret=["<div class=\"dojoxGridSortRoot\">","<div class=\"dojoxGridSortWrapper\">","<span id=\"selectSortSeparator"+_1d.index+"\" class=\"dojoxGridSortSeparatorOff\"></span>","<span class=\"dojoxGridNestedSortWrapper\" tabindex=\"-1\">","<span id=\""+_1d.view.id+"SortPos"+_1d.index+"\" class=\"dojoxGridSortPos "+(_20?"":"dojoxGridSortPosOff")+"\">"+(_20?_1e["sortPos"]:"")+"</span>","<span id=\"nestedSortCol"+_1d.index+"\" class=\"dojoxGridSort dojoxGridNestedSort "+(_20?("dojoxGrid"+_22.sortStateInt2Str(_1e["nestedSortAsc"])):"dojoxGridUnsorted")+"\">",_22._a11yText["dojoxGrid"+_22.sortStateInt2Str(_1e["nestedSortAsc"])]||".","</span>","</span>","<span id=\"SortSeparator"+_1d.index+"\" class=\"dojoxGridSortSeparatorOff\"></span>","<span class=\"dojoxGridUnarySortWrapper\" tabindex=\"-1\"><span id=\"unarySortCol"+_1d.index+"\" class=\"dojoxGridSort dojoxGridUnarySort "+(_21?("dojoxGrid"+_22.sortStateInt2Str(_1e["unarySortAsc"])):"dojoxGridUnsorted")+"\">",_22._a11yText["dojoxGrid"+_22.sortStateInt2Str(_1e["unarySortAsc"])]||".","</span></span>","</div>","<div tabindex=\"-1\" id=\"selectCol"+_1d.index+"\" class=\"dojoxGridHeaderCellSelectRegion\"><span id=\"caption"+_1d.index+"\">"+n+"<span></div>","</div>"];
return ret.join("");
},addHoverSortTip:function(e){
this._sortTipMap[e.cellIndex]=true;
var _23=this.getCellSortInfo(e.cell);
if(!_23){
return;
}
var _24=this._getCellElements(e.cellNode);
if(!_24){
return;
}
var _25=this.sortAttrs;
var _26=!_25||_25.length<1;
var _27=(_25&&_25.length==1&&_23["sortPos"]==1);
dojo.addClass(_24["selectSortSeparator"],"dojoxGridSortSeparatorOn");
if(_26||_27){
this._addHoverUnarySortTip(_24,_23,e);
}else{
this._addHoverNestedSortTip(_24,_23,e);
this.updateMinColWidth(_24["nestedSortPos"]);
}
var _28=_24["selectRegion"];
this._fixSelectRegion(_28);
if(!dijit.hasWaiRole(_28)){
dijit.setWaiState(_28,"label","Column "+(e.cellIndex+1)+" "+e.cell.field);
}
this._toggleHighlight(e.sourceView,e);
this.focus._updateFocusBorder();
},_addHoverUnarySortTip:function(_29,_2a,e){
dojo.addClass(_29["nestedSortWrapper"],"dojoxGridUnsorted");
var _2b=this.sortStateInt2Str(this._getNewSortState(_2a["unarySortAsc"]));
dijit.setWaiState(_29["unarySortWrapper"],"label","Column "+(e.cellIndex+1)+" "+e.cell.field+" - Choose "+_2b.toLowerCase()+" single sort");
var _2c="dojoxGrid"+_2b+"Tip";
dojo.addClass(_29["unarySortChoice"],_2c);
_29["unarySortChoice"].innerHTML=this._a11yText[_2c];
this._addTipInfo(_29["unarySortWrapper"],this._composeSortTip(_2b,"singleSort"));
},_addHoverNestedSortTip:function(_2d,_2e,e){
var _2f=_2d["nestedSortPos"];
var _30=_2d["unarySortWrapper"];
var _31=_2d["nestedSortWrapper"];
var _32=this.sortAttrs;
dojo.removeClass(_31,"dojoxGridUnsorted");
var _33=this.sortStateInt2Str(this._getNewSortState(_2e["nestedSortAsc"]));
dijit.setWaiState(_31,"label","Column "+(e.cellIndex+1)+" "+e.cell.field+" - Choose "+_33.toLowerCase()+" nested sort");
var _34="dojoxGrid"+_33+"Tip";
this._addA11yInfo(_2d["nestedSortChoice"],_34);
this._addTipInfo(_31,this._composeSortTip(_33,"nestedSort"));
_33=this.sortStateInt2Str(_2e["unarySortAsc"]);
dijit.setWaiState(_30,"label","Column "+(e.cellIndex+1)+" "+e.cell.field+" - Choose "+_33.toLowerCase()+" single sort");
_34="dojoxGrid"+_33+"Tip";
this._addA11yInfo(_2d["unarySortChoice"],_34);
this._addTipInfo(_30,this._composeSortTip(_33,"singleSort"));
dojo.addClass(_2d["sortSeparator"],"dojoxGridSortSeparatorOn");
dojo.removeClass(_2f,"dojoxGridSortPosOff");
if(_2e["sortPos"]<1){
_2f.innerHTML=(_32?_32.length:0)+1;
if(!this._unarySortInFocus()&&_32&&_32.length==1){
var _35=this._getUnaryNode();
_35.innerHTML="1";
dojo.removeClass(_35,"dojoxGridSortPosOff");
dojo.removeClass(_35.parentNode,"dojoxGridUnsorted");
this._fixSelectRegion(this._getCellElements(_35)["selectRegion"]);
}
}
},_unarySortInFocus:function(){
return this._unarySortCell.cell&&this.focus.headerCellInFocus(this._unarySortCell.cell.index);
},_composeSortTip:function(_36,_37){
_36=_36.toLowerCase();
if(_36=="unsorted"){
return this._nls[_36];
}else{
var tip=dojo.string.substitute(this._nls["sortingState"],[this._nls[_37],this._nls[_36]]);
return tip;
}
},_addTipInfo:function(_38,_39){
dojo.attr(_38,"title",_39);
dojo.query("span",_38).forEach(function(n){
dojo.attr(n,"title",_39);
});
},_addA11yInfo:function(_3a,_3b){
dojo.addClass(_3a,_3b);
_3a.innerHTML=this._a11yText[_3b];
},removeHoverSortTip:function(e){
if(!this._sortTipMap[e.cellIndex]){
return;
}
var _3c=this.getCellSortInfo(e.cell);
if(!_3c){
return;
}
var _3d=this._getCellElements(e.cellNode);
if(!_3d){
return;
}
var _3e=_3d.nestedSortChoice;
var _3f=_3d.unarySortChoice;
var _40=_3d.unarySortWrapper;
var _41=_3d.nestedSortWrapper;
this._toggleHighlight(e.sourceView,e,true);
function _42(_43){
dojo.forEach(_43,function(_44){
var _45=dojo.trim((" "+_44["className"]+" ").replace(/\sdojoxGrid\w+Tip\s/g," "));
if(_44["className"]!=_45){
_44["className"]=_45;
}
});
};
_42([_3e,_3f]);
_3f.innerHTML=this._a11yText["dojoxGrid"+this.sortStateInt2Str(_3c["unarySortAsc"])]||".";
_3e.innerHTML=this._a11yText["dojoxGrid"+this.sortStateInt2Str(_3c["nestedSortAsc"])]||".";
dojo.removeClass(_3d["selectSortSeparator"],"dojoxGridSortSeparatorOn");
dojo.removeClass(_3d["sortSeparator"],"dojoxGridSortSeparatorOn");
if(_3c["sortPos"]==1&&this.focus.isNavHeader()&&!this.focus.headerCellInFocus(e.cellIndex)){
dojo.removeClass(_3d["nestedSortWrapper"],"dojoxGridUnsorted");
}
var _46=this.sortAttrs;
if(!isNaN(_3c["sortPos"])&&_3c["sortPos"]<1){
_3d["nestedSortPos"].innerHTML="";
dojo.addClass(_41,"dojoxGridUnsorted");
if(!this.focus._focusBorderBox&&_46&&_46.length==1){
var _47=this._getUnaryNode();
_47.innerHTML="";
dojo.addClass(_47,"dojoxGridSortPosOff");
this._fixSelectRegion(this._getCellElements(_47)["selectRegion"]);
}
}
this._fixSelectRegion(_3d["selectRegion"]);
dijit.removeWaiState(_41,"label");
dijit.removeWaiState(_40,"label");
if(_3c["sortPos"]>=0){
var _48=(_46.length==1);
var _49=_48?_40:_41;
this._setSortRegionWaiState(_48,e.cellIndex,e.cell.field,_3c["sortPos"],_49);
}
this.focus._updateFocusBorder();
this._sortTipMap[e.cellIndex]=false;
},_getUnaryNode:function(){
for(var i=0;i<this.views.views.length;i++){
var n=dojo.byId(this.views.views[i].id+"SortPos"+this._unarySortCell.cell.index);
if(n){
return n;
}
}
},_fixSelectRegion:function(_4a){
var _4b=_4a.previousSibling;
var _4c=dojo.contentBox(_4a.parentNode);
var _4d=dojo.marginBox(_4a);
var _4e=dojo.marginBox(_4b);
if(dojo.isIE&&!dojo._isBodyLtr()){
var w=0;
dojo.forEach(_4b.childNodes,function(_4f){
w+=dojo.marginBox(_4f).w;
});
_4e.w=w;
_4e.l=(_4e.t=0);
dojo.marginBox(_4b,_4e);
}
if(_4d.w!=(_4c.w-_4e.w)){
_4d.w=_4c.w-_4e.w;
if(!dojo.isWebKit){
dojo.marginBox(_4a,_4d);
}else{
_4d.h=dojo.contentBox(_4c).h;
dojo.style(_4a,"width",(_4d.w-4)+"px");
}
}
},updateMinColWidth:function(_50){
if(this._minColWidthUpdated){
return;
}
var _51=_50.innerHTML;
_50.innerHTML=dojo.query(".dojoxGridSortWrapper",this.viewsHeaderNode).length;
var _52=_50.parentNode.parentNode;
this._minColWidth=dojo.marginBox(_52).w+this._widthDelta;
_50.innerHTML=_51;
this._minColWidthUpdated=true;
},getMinColWidth:function(){
return this._minColWidth;
},_initSelectCols:function(){
var _53=dojo.query(".dojoxGridHeaderCellSelectRegion",this.headerContentNode);
var _54=dojo.query(".dojoxGridUnarySortWrapper",this.headerContentNode);
var _55=dojo.query(".dojoxGridNestedSortWrapper",this.headerContentNode);
_53.concat(_54).concat(_55).forEach(function(_56){
dojo.connect(_56,"onmousemove",dojo.hitch(this.grid,this.grid._toggleHighlight,this));
dojo.connect(_56,"onmouseout",dojo.hitch(this.grid,this.grid._removeActiveState));
},this);
this.grid._fixHeaderCellStyle(_53,this);
if(dojo.isIE&&!dojo._isBodyLtr()){
this.grid._fixAllSelectRegion();
}
},_fixHeaderCellStyle:function(_57,_58){
dojo.forEach(_57,dojo.hitch(this,function(_59){
var _5a=dojo.marginBox(_59),_5b=this._getCellElements(_59),_5c=_5b.sortWrapper;
_5c.style.height=_5a.h+"px";
_5c.style.lineHeight=_5a.h+"px";
var _5d=_5b["selectSortSeparator"],_5e=_5b["sortSeparator"];
_5e.style.height=_5d.style.height=_5a.h*3/5+"px";
_5e.style.marginTop=_5d.style.marginTop=_5a.h*1/5+"px";
_58.header.overResizeWidth=this._overResizeWidth;
}));
},_fixAllSelectRegion:function(){
var _5f=dojo.query(".dojoxGridHeaderCellSelectRegion",this.viewsHeaderNode);
dojo.forEach(_5f,dojo.hitch(this,function(_60){
this._fixSelectRegion(_60);
}));
},_toggleHighlight:function(_61,e,_62){
if(!e.target||!e.type||!e.type.match(/mouse|contextmenu/)){
return;
}
var _63=this._getCellElements(e.target);
if(!_63){
return;
}
var _64=_63["selectRegion"];
var _65=_63["nestedSortWrapper"];
var _66=_63["unarySortWrapper"];
dojo.removeClass(_64,"dojoxGridSelectRegionHover");
dojo.removeClass(_65,"dojoxGridSortHover");
dojo.removeClass(_66,"dojoxGridSortHover");
if(!_62&&!_61.grid._inResize(_61)){
var _67=this._getSortEventInfo(e);
if(_67.selectChoice){
dojo.addClass(_64,"dojoxGridSelectRegionHover");
}else{
if(_67.nestedSortChoice){
dojo.addClass(_65,"dojoxGridSortHover");
}else{
if(_67.unarySortChoice){
dojo.addClass(_66,"dojoxGridSortHover");
}
}
}
}
},_removeActiveState:function(e){
if(!e.target||!e.type||!e.type.match(/mouse|contextmenu/)){
return;
}
var _68=this._getChoiceRegion(e.target,this._getSortEventInfo(e));
_68&&dojo.removeClass(_68,this.headerCellActiveClass);
},_toggleProgressTip:function(on,e){
var _69=[this.domNode,e?e.cellNode:null];
setTimeout(function(){
dojo.forEach(_69,function(_6a){
if(_6a){
if(on&&!dojo.hasClass(_6a,"dojoxGridSortInProgress")){
dojo.addClass(_6a,"dojoxGridSortInProgress");
}else{
if(!on&&dojo.hasClass(_6a,"dojoxGridSortInProgress")){
dojo.removeClass(_6a,"dojoxGridSortInProgress");
}
}
}
});
},0.1);
},_getSortEventInfo:function(e){
var _6b=function(_6c,css){
return dojo.hasClass(_6c,css)||(_6c.parentNode&&dojo.hasClass(_6c.parentNode,css));
};
return {selectChoice:_6b(e.target,"dojoxGridHeaderCellSelectRegion"),unarySortChoice:_6b(e.target,"dojoxGridUnarySortWrapper"),nestedSortChoice:_6b(e.target,"dojoxGridNestedSortWrapper")};
},ignoreEvent:function(e){
return !(e.nestedSortChoice||e.unarySortChoice||e.selectChoice);
},_sychronizeResize:function(e){
if(!e.cell||e.cell.isRowSelector||this.focus.headerCellInFocus(e.cellIndex)){
return;
}
if(!this._inResize(e.sourceView)){
this.addHoverSortTip(e);
}else{
var idx=e.cellIndex;
if(!this._sortTipMap[e.cellIndex]){
e.cellIndex=this._sortTipMap[idx+1]?(idx+1):(this._sortTipMap[idx-1]?(idx-1):idx);
e.cellNode=e.cellNode.parentNode.childNodes[e.cellIndex];
}
this.removeHoverSortTip(e);
}
},_getCellElements:function(_6d){
try{
while(_6d&&_6d.nodeName.toLowerCase()!="th"){
_6d=_6d.parentNode;
}
if(!_6d){
return null;
}
var ns=dojo.query(".dojoxGridSortRoot",_6d);
if(ns.length!=1){
return null;
}
var n=ns[0];
return {"selectSortSeparator":dojo.query("[id^='selectSortSeparator']",n)[0],"nestedSortPos":dojo.query(".dojoxGridSortPos",n)[0],"nestedSortChoice":dojo.query("[id^='nestedSortCol']",n)[0],"sortSeparator":dojo.query("[id^='SortSeparator']",n)[0],"unarySortChoice":dojo.query("[id^='unarySortCol']",n)[0],"selectRegion":dojo.query(".dojoxGridHeaderCellSelectRegion",n)[0],"sortWrapper":dojo.query(".dojoxGridSortWrapper",n)[0],"unarySortWrapper":dojo.query(".dojoxGridUnarySortWrapper",n)[0],"nestedSortWrapper":dojo.query(".dojoxGridNestedSortWrapper",n)[0],"sortRoot":n,"headCellNode":_6d};
}
catch(e){
console.debug("NestedSorting._getCellElemets() error:"+e);
}
return null;
},_getChoiceRegion:function(_6e,_6f){
var _70,_71=this._getCellElements(_6e);
if(!_71){
return;
}
_6f.unarySortChoice&&(_70=_71["unarySortWrapper"]);
_6f.nestedSortChoice&&(_70=_71["nestedSortWrapper"]);
_6f.selectChoice&&(_70=_71["selectRegion"]);
return _70;
},_inResize:function(_72){
return _72.header.moverDiv||dojo.hasClass(_72.headerNode,"dojoxGridColResize")||dojo.hasClass(_72.headerNode,"dojoxGridColNoResize");
},retainLastRowSelection:function(){
dojo.forEach(this._by_idx,function(o,idx){
if(!o||!o.item){
return;
}
var _73=!!this.selection.isSelected(idx);
o.item[this.storeItemSelected]=[_73];
if(this.indirectSelection&&this.rowSelectCell.toggleAllTrigerred&&_73!=this.toggleAllValue){
this.exceptionalSelectedItems.push(o.item);
}
},this);
this.selection.selected=[];
dojo.publish(this.sortRowSelectionChangedTopic,[this]);
},updateNewRowSelection:function(_74,req){
dojo.forEach(_74,function(_75,idx){
if(this.indirectSelection&&this.rowSelectCell.toggleAllTrigerred){
if(dojo.indexOf(this.exceptionalSelectedItems,_75)<0){
_75[this.storeItemSelected]=[this.toggleAllValue];
}
}
if(_75[this.storeItemSelected]&&_75[this.storeItemSelected][0]){
var _76=req.start+idx;
this.selection.selectedIndex=_76;
this.selection.selected[_76]=true;
this.updateRowStyles(_76);
}
},this);
dojo.publish(this.sortRowSelectionChangedTopic,[this]);
if(dojo.isMoz&&this._by_idx.length==0){
this.update();
}
},allSelectionToggled:function(_77){
this.exceptionalSelectedItems=[];
this.toggleAllValue=this.rowSelectCell.defaultValue;
},_selectionChanged:function(obj){
obj==this.select&&(this.toggleAllValue=false);
},getStoreSelectedValue:function(_78){
var _79=this._by_idx[_78];
return _79&&_79.item&&!!(_79.item[this.storeItemSelected]&&_79.item[this.storeItemSelected][0]);
},initAriaInfo:function(){
var _7a=this.sortAttrs;
dojo.forEach(_7a,dojo.hitch(this,function(_7b,_7c){
if(!_7b.cell||!_7b.cellNode){
return;
}
var _7d=_7b.cell.getHeaderNode();
var _7e=this._getCellElements(_7d);
if(!_7e){
return;
}
var _7f=_7e["selectRegion"];
dijit.setWaiState(_7f,"label","Column "+(_7b.cell.index+1)+" "+_7b.attr);
var _80=(_7a.length==1);
var _81=this.sortStateInt2Str(_7b.asc).toLowerCase();
var _82=_80?_7e["unarySortWrapper"]:_7e["nestedSortWrapper"];
dijit.setWaiState(_82,"sort",_81);
this._setSortRegionWaiState(_80,_7b.cell.index,_7b.attr,_7c+1,_82);
}));
},_setSortRegionWaiState:function(_83,_84,_85,_86,_87){
if(_86<0){
return;
}
var _88=_83?"single sort":"nested sort";
var _89="Column "+(_84+1)+" "+_85+" "+_88+" "+(!_83?(" sort position "+_86):"");
dijit.setWaiState(_87,"label",_89);
},_inPage:function(_8a){
return _8a<this._bop||_8a>=this._eop;
}});
dojo.declare("dojox.grid.enhanced.plugins._NestedSortingFocusManager",dojox.grid._FocusManager,{lastHeaderFocus:{cellNode:null,regionIdx:-1},currentHeaderFocusEvt:null,cssMarkers:["dojoxGridHeaderCellSelectRegion","dojoxGridNestedSortWrapper","dojoxGridUnarySortWrapper"],_focusBorderBox:null,_initColumnHeaders:function(){
var _8b=this._findHeaderCells();
dojo.forEach(_8b,dojo.hitch(this,function(_8c){
var _8d=dojo.query(".dojoxGridHeaderCellSelectRegion",_8c);
var _8e=dojo.query("[class*='SortWrapper']",_8c);
_8d=_8d.concat(_8e);
_8d.length==0&&(_8d=[_8c]);
dojo.forEach(_8d,dojo.hitch(this,function(_8f){
this._connects.push(dojo.connect(_8f,"onfocus",this,"doColHeaderFocus"));
this._connects.push(dojo.connect(_8f,"onblur",this,"doColHeaderBlur"));
}));
}));
},focusHeader:function(_90,_91,_92){
if(!this.isNavHeader()){
this.inherited(arguments);
}else{
var _93=this._findHeaderCells();
this._colHeadNode=_93[this._colHeadFocusIdx];
_91&&(this.lastHeaderFocus.cellNode=this._colHeadNode);
}
if(!this._colHeadNode){
return;
}
if(this.grid.indirectSelection&&this._colHeadFocusIdx==0){
this._colHeadNode=this._findHeaderCells()[++this._colHeadFocusIdx];
}
var _94=_92?0:(this.lastHeaderFocus.regionIdx>=0?this.lastHeaderFocus.regionIdx:(_90?2:0));
var _95=dojo.query("."+this.cssMarkers[_94],this._colHeadNode)[0]||this._colHeadNode;
this.grid.addHoverSortTip(this.currentHeaderFocusEvt=this._mockEvt(_95));
this.lastHeaderFocus.regionIdx=_94;
_95&&dojox.grid.util.fire(_95,"focus");
},focusSelectColEndingHeader:function(e){
if(!e||!e.cellNode){
return;
}
this._colHeadFocusIdx=e.cellIndex;
this.focusHeader(null,false,true);
},_delayedHeaderFocus:function(){
this.isNavHeader()&&this.focusHeader(null,true);
},_setActiveColHeader:function(_96,_97,_98){
dojo.attr(this.grid.domNode,"aria-activedescendant",_96.id);
this._colHeadNode=_96;
this._colHeadFocusIdx=_97;
},doColHeaderFocus:function(e){
this.lastHeaderFocus.cellNode=this._colHeadNode;
if(e.target==this._colHeadNode){
this._scrollHeader(this.getHeaderIndex());
}else{
var _99=this.getFocusView(e);
if(!_99){
return;
}
_99.header.baseDecorateEvent(e);
this._addFocusBorder(e.target);
this._colHeadFocusIdx=e.cellIndex;
this._colHeadNode=this._findHeaderCells()[this._colHeadFocusIdx];
this._colHeadNode&&this.getHeaderIndex()!=-1&&this._scrollHeader(this._colHeadFocusIdx);
}
this._focusifyCellNode(false);
this.grid.isDndSelectEnable&&this.grid.focus._blurRowBar();
this.grid.addHoverSortTip(this.currentHeaderFocusEvt=this._mockEvt(e.target));
if(dojo.isIE&&!dojo._isBodyLtr()){
this.grid._fixAllSelectRegion();
}
},doColHeaderBlur:function(e){
this.inherited(arguments);
this._removeFocusBorder();
if(!this.isNavCellRegion){
var _9a=this.getFocusView(e);
if(!_9a){
return;
}
_9a.header.baseDecorateEvent(e);
this.grid.removeHoverSortTip(e);
this.lastHeaderFocus.cellNode=this._colHeadNode;
}
},getFocusView:function(e){
var _9b;
dojo.forEach(this.grid.views.views,function(_9c){
if(!_9b){
var _9d=dojo.coords(_9c.domNode),_9e=dojo.coords(e.target);
var _9f=_9e.x>=_9d.x&&_9e.x<=(_9d.x+_9d.w);
_9f&&(_9b=_9c);
}
});
return (this.focusView=_9b);
},_mockEvt:function(_a0){
var _a1=this.grid.getCell(this._colHeadFocusIdx);
return {target:_a0,cellIndex:this._colHeadFocusIdx,cell:_a1,cellNode:this._colHeadNode,clientX:-1,sourceView:_a1.view};
},navHeader:function(e){
var _a2=e.ctrlKey?0:(e.keyCode==dojo.keys.LEFT_ARROW)?-1:1;
!dojo._isBodyLtr()&&(_a2*=-1);
this.focusView.header.baseDecorateEvent(e);
dojo.forEach(this.cssMarkers,dojo.hitch(this,function(css,_a3){
if(dojo.hasClass(e.target,css)){
var _a4=_a3+_a2,_a5,_a6;
do{
_a5=dojo.query("."+this.cssMarkers[_a4],e.cellNode)[0];
if(_a5&&dojo.style(_a5.lastChild||_a5.firstChild,"display")!="none"){
_a6=_a5;
break;
}
_a4+=_a2;
}while(_a4>=0&&_a4<this.cssMarkers.length);
if(_a6&&_a4>=0&&_a4<this.cssMarkers.length){
if(e.ctrlKey){
return;
}
dojo.isIE&&(this.grid._sortTipMap[e.cellIndex]=false);
this.navCellRegion(_a6,_a4);
return;
}
var _a7=_a4<0?-1:(_a4>=this.cssMarkers.length?1:0);
this.navHeaderNode(_a7);
}
}));
},navHeaderNode:function(_a8,_a9){
var _aa=this._colHeadFocusIdx+_a8;
var _ab=this._findHeaderCells();
while(_aa>=0&&_aa<_ab.length&&_ab[_aa].style.display=="none"){
_aa+=_a8;
}
if(this.grid.indirectSelection&&_aa==0){
return;
}
if(_a8!=0&&_aa>=0&&_aa<this.grid.layout.cells.length){
this.lastHeaderFocus.cellNode=this._colHeadNode;
this.lastHeaderFocus.regionIdx=-1;
this._colHeadFocusIdx=_aa;
this.focusHeader(_a8<0?true:false,false,_a9);
}
},navCellRegion:function(_ac,_ad){
this.isNavCellRegion=true;
dojox.grid.util.fire(_ac,"focus");
this.currentHeaderFocusEvt.target=_ac;
this.lastHeaderFocus.regionIdx=_ad;
var _ae=_ad==0?_ac:_ac.parentNode.nextSibling;
_ae&&this.grid._fixSelectRegion(_ae);
this.isNavCellRegion=false;
},headerCellInFocus:function(_af){
return (this._colHeadFocusIdx==_af)&&this._focusBorderBox;
},clearHeaderFocus:function(){
this._colHeadNode=this._colHeadFocusIdx=null;
this.lastHeaderFocus={cellNode:null,regionIdx:-1};
},addSortFocus:function(e){
var _b0=this.grid.getCellSortInfo(e.cell);
if(!_b0){
return;
}
var _b1=this.grid.sortAttrs;
var _b2=!_b1||_b1.length<1;
var _b3=(_b1&&_b1.length==1&&_b0["sortPos"]==1);
this._colHeadFocusIdx=e.cellIndex;
this._colHeadNode=e.cellNode;
this.currentHeaderFocusEvt={};
this.lastHeaderFocus.regionIdx=(_b2||_b3)?2:(e.nestedSortChoice?1:0);
},_addFocusBorder:function(_b4){
if(!_b4){
return;
}
this._removeFocusBorder();
this._focusBorderBox=dojo.create("div");
this._focusBorderBox.className="dojoxGridFocusBorderBox";
dojo.toggleClass(_b4,"dojoxGridSelectRegionFocus",true);
dojo.toggleClass(_b4,"dojoxGridSelectRegionHover",false);
var _b5=_b4.offsetHeight;
if(_b4.hasChildNodes()){
_b4.insertBefore(this._focusBorderBox,_b4.firstChild);
}else{
_b4.appendChild(this._focusBorderBox);
}
var _b6={"l":0,"t":0,"r":0,"b":0};
for(var i in _b6){
_b6[i]=dojo.create("div");
}
var pos={x:dojo.coords(_b4).x-dojo.coords(this._focusBorderBox).x,y:dojo.coords(_b4).y-dojo.coords(this._focusBorderBox).y,w:_b4.offsetWidth,h:_b5};
for(var i in _b6){
var n=_b6[i];
dojo.addClass(n,"dojoxGridFocusBorder");
dojo.style(n,"top",pos.y+"px");
dojo.style(n,"left",pos.x+"px");
this._focusBorderBox.appendChild(n);
}
var _b7=function(val){
return val>0?val:0;
};
dojo.style(_b6.r,"left",_b7(pos.x+pos.w-1)+"px");
dojo.style(_b6.b,"top",_b7(pos.y+pos.h-1)+"px");
dojo.style(_b6.l,"height",_b7(pos.h-1)+"px");
dojo.style(_b6.r,"height",_b7(pos.h-1)+"px");
dojo.style(_b6.t,"width",_b7(pos.w-1)+"px");
dojo.style(_b6.b,"width",_b7(pos.w-1)+"px");
},_updateFocusBorder:function(){
if(this._focusBorderBox==null){
return;
}
this._addFocusBorder(this._focusBorderBox.parentNode);
},_removeFocusBorder:function(){
if(this._focusBorderBox&&this._focusBorderBox.parentNode){
dojo.toggleClass(this._focusBorderBox.parentNode,"dojoxGridSelectRegionFocus",false);
this._focusBorderBox.parentNode.removeChild(this._focusBorderBox);
}
this._focusBorderBox=null;
}});
}
