/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.grid.enhanced.dnd._DndMovingManager"]){
dojo._hasResource["dojox.grid.enhanced.dnd._DndMovingManager"]=true;
dojo.provide("dojox.grid.enhanced.dnd._DndMovingManager");
dojo.require("dojox.grid.enhanced.dnd._DndSelectingManager");
dojo.require("dojox.grid.enhanced.dnd._DndMover");
dojo.require("dojo.dnd.move");
dojo.declare("dojox.grid.enhanced.dnd._DndMovingManager",dojox.grid.enhanced.dnd._DndSelectingManager,{exceptRowsTo:-1,exceptColumnsTo:-1,coverDIVs:[],movers:[],constructor:function(_1){
if(this.grid.indirectSelection){
this.exceptColumnsTo=this.grid.pluginMgr.getFixedCellNumber()-1;
}
this.coverDIVs=this.movers=[];
dojo.subscribe("CTRL_KEY_DOWN",dojo.hitch(this,function(_2,_3){
if(_2==this.grid&&_2!=this){
this.keyboardMove(_3);
}
}));
dojo.forEach(this.grid.views.views,function(_4){
dojo.connect(_4.scrollboxNode,"onscroll",dojo.hitch(this,function(){
this.clearDrugDivs();
}));
},this);
},getGridWidth:function(){
return dojo.contentBox(this.grid.domNode).w-this.grid.views.views[0].getWidth().replace("px","");
},isColSelected:function(_5){
return this.selectedColumns[_5]&&_5>this.exceptColumnsTo;
},getHScrollBarHeight:function(){
this.scrollbarHeight=0;
dojo.forEach(this.grid.views.views,function(_6,_7){
if(_6.scrollboxNode){
var _8=_6.scrollboxNode.offsetHeight-_6.scrollboxNode.clientHeight;
this.scrollbarHeight=_8>this.scrollbarHeight?_8:this.scrollbarHeight;
}
},this);
return this.scrollbarHeight;
},getExceptionalColOffsetWidth:function(){
if(!this.grid.indirectSelection||!this.grid.rowSelectCell){
return 0;
}
var _9=(normalizedOffsetWidth=0),_a=this.grid.rowSelectCell.view.scrollboxNode;
dojo.forEach(this.getHeaderNodes(),function(_b,_c){
if(_c<=this.exceptColumnsTo){
var _d=dojo.coords(_b);
_9+=_d.w;
}
},this);
normalizedOffsetWidth=_9-_a.scrollLeft*(dojo._isBodyLtr()?1:(dojo.isMoz?-1:1));
return normalizedOffsetWidth>0?normalizedOffsetWidth:0;
},getGridCoords:function(_e){
if(!this.gridCoords||_e){
this.gridCoords=new Object();
if(!this.headerHeight){
this.headerHeight=dojo.coords(this.getHeaderNodes()[0]).h;
}
var _f=dojo.coords(this.grid.views.views[0].domNode);
var _10=dojo.coords(this.grid.domNode);
var _11=dojo.contentBox(this.grid.domNode);
this.gridCoords.h=_11.h-this.headerHeight-this.getHScrollBarHeight();
this.gridCoords.t=_10.y;
this.gridCoords.l=dojo._isBodyLtr()?(_10.x+_f.w):_10.x;
this.gridCoords.w=_11.w-_f.w;
}
return this.gridCoords;
},createAvatar:function(_12,_13,_14,top,_15){
this.gridCoords=null;
var _16=this.getGridCoords();
var _17=dojo.doc.createElement("DIV");
_17.className="dojoxGridSelectedDIV";
_17.id="grid_dnd_cover_div_"+_14+"_"+top;
_17.style.width=_12+"px";
var _18=dojo._docScroll();
var _19=top<_16.t+this.headerHeight?_16.t+this.headerHeight-top:0;
var _1a=_16.t+_16.h+this.headerHeight;
var _1b=0;
if(top<_16.t+this.headerHeight){
_1b=(_16.t+this.headerHeight);
}else{
if(top>_1a){
_1b=10000;
}else{
_1b=top;
}
}
_17.style.top=_1b+_18.y+"px";
_17.style.left=(_14+_18.x)+"px";
var _1c=_1b+_13-_19;
if(_1c>_1a+(_15?this.scrollbarHeight:0)){
_1c=_1a;
}
_17.style.height=((_1c-_1b)>=0?(_1c-_1b):0)+"px";
dojo.doc.body.appendChild(_17);
_17.connections=[];
_17.connections.push(dojo.connect(_17,"onmouseout",this,function(){
this.clearDrugDivs();
}));
_17.connections.push(dojo.connect(_17,"onclick",this,"avataDivClick"));
_17.connections.push(dojo.connect(_17,"keydown",this,function(e){
this.handleESC(e,this);
}));
this.coverDIVs.push(_17);
return _17;
},handleESC:function(e,_1d){
var dk=dojo.keys;
switch(e.keyCode){
case dk.ESCAPE:
try{
this.cancelDND();
}
catch(e){
console.debug(e);
}
break;
}
},cancelDND:function(){
this.cleanAll();
this.clearDrugDivs();
if(this.mover){
this.mover.destroy();
}
this.cleanAll();
},createCoverMover:function(_1e,_1f,_20,top,_21){
var _22=this.getGridCoords(),_23=(_21=="col"?true:false);
var _24={box:{l:(_21=="row"?_20:_22.l)+dojo._docScroll().x,t:(_21=="col"?top:_22.t+this.headerHeight)+dojo._docScroll().y,w:_21=="row"?1:_22.w,h:_21=="col"?1:_22.h},within:true,movingType:_21,mover:dojox.grid.enhanced.dnd._DndMover};
return new dojox.grid.enhanced.dnd._DndBoxConstrainedMoveable(this.createAvatar(_1e,_1f,_20,top,_23),_24);
},getBorderDiv:function(){
var _25=dojo.byId("borderDIV"+this.grid.id);
if(_25==null){
_25=dojo.doc.createElement("DIV");
_25.id="borderDIV"+this.grid.id;
_25.className="dojoxGridBorderDIV";
dojo.doc.body.appendChild(_25);
}
return _25;
},setBorderDiv:function(_26,_27,_28,top){
var _29=this.getBorderDiv();
dojo.style(_29,{"height":_27+"px","top":top+"px","width":_26+"px","left":_28+"px"});
return _29;
},removeOtherMovers:function(id){
if(!this.coverDIVs.hasRemovedOtherMovers){
var _2a;
dojo.forEach(this.coverDIVs,function(div){
if(div.id!=id){
dojo.doc.body.removeChild(div);
}else{
_2a=div;
}
},this);
this.coverDIVs=[_2a];
this.coverDIVs.hasRemovedOtherMovers=true;
}
},addColMovers:function(){
var _2b=-1;
dojo.forEach(this.selectedColumns,function(col,_2c){
if(this.isColSelected(_2c)){
if(_2b==-1){
_2b=_2c;
}
if(this.selectedColumns[_2c+1]==null){
this.addColMover(_2b,_2c);
_2b=-1;
}
}
},this);
},addColMover:function(_2d,_2e){
if(this.lock){
return;
}
var _2f=(rightPosition=0);
var top=null,_30=null;
if(dojo._isBodyLtr()){
dojo.forEach(this.getHeaderNodes(),function(_31,_32){
var _33=dojo.coords(_31);
if(_32==_2d){
_2f=_33.x;
top=_33.y+_33.h;
_30=_33.h;
}
if(_32==_2e){
rightPosition=_33.x+_33.w;
}
});
}else{
dojo.forEach(this.getHeaderNodes(),function(_34,_35){
var _36=dojo.coords(_34);
if(_35==_2d){
rightPosition=_36.x+_36.w;
_30=_36.h;
}
if(_35==_2e){
_2f=_36.x;
top=_36.y+_36.h;
}
});
}
var _37=this.normalizeColMoverCoords(_2f,rightPosition,_2d,_2e);
var _38=_37.h,_39=_37.w;
_2f=_37.l,rightPosition=_37.r;
var _3a=this.createCoverMover(_39,_38,_2f,top,"col");
this.movers.push(_3a);
var _3b=this.setBorderDiv(3,_38,-1000,top+dojo._docScroll().y);
dojo.attr(_3b,"colH",_37.colH);
dojo.connect(_3a,"onMoveStart",dojo.hitch(this,function(_3c,_3d){
this.mover=_3c;
this.removeOtherMovers(_3c.node.id);
}));
dojo.connect(_3a,"onMove",dojo.hitch(this,function(_3e,_3f,_40){
if(_3e.node==null||_3e.node.parentNode==null){
return;
}
this.isMoving=true;
this.moveColBorder(_3e,_40,_3b);
}));
dojo.connect(_3a,"onMoveStop",dojo.hitch(this,function(_41){
if(this.drugDestIndex==null||this.isContinuousSelection(this.selectedColumns)&&(this.drugDestIndex==_2d||this.drugDestIndex==_2e||this.drugDestIndex==(_2e+1)&&this.drugBefore)){
this.movingIgnored=true;
if(this.isMoving){
this.isMoving=false;
this.clearDrugDivs();
}
return;
}
this.isMoving=false;
this.mover=null;
this.startMoveCols();
this.drugDestIndex=null;
}));
},normalizeColMoverCoords:function(_42,_43,_44,_45){
var _46=_43-_42,_47=this.grid.views.views,_48=this.grid.pluginMgr;
var _49={"w":_46,"h":0,"l":_42,"r":_43,"colH":0};
var _4a=this.getGridWidth()-_47[_47.length-1].getScrollbarWidth();
var rtl=!dojo._isBodyLtr();
var _4b=_48.getViewByCellIdx(!rtl?_44:_45);
var _4c=_48.getViewByCellIdx(!rtl?_45:_44);
var _4d=(_4b==_4c);
if(!_4b||!_4c){
return _49;
}
var _4e=dojo.coords(_4b.scrollboxNode).x+(rtl&&dojo.isIE?_4b.getScrollbarWidth():0);
var _4f=dojo.coords(_4c.scrollboxNode);
var _50=_4f.x+_4f.w-((!rtl||!dojo.isIE)?_4c.getScrollbarWidth():0);
if(_49.l<_4e){
_49.w=_49.r-_4e;
_49.l=_4e;
}
if(_49.r>_50){
_49.w=_50-_49.l;
}
var i,_51=this.grid.views.views[0],_52=dojo.coords(_51.contentNode).h;
var _53=_4c,_54=_4f.h;
_49.colH=_52;
_54=!_4d?_54:(_54-(_53.scrollboxNode.offsetHeight-_53.scrollboxNode.clientHeight));
_49.h=_52<_54?_52:_54;
return _49;
},moveColBorder:function(_55,_56,_57){
var _58=dojo._docScroll(),rtl=!dojo._isBodyLtr();
_56.x-=_58.x;
var _59=this.grid.views.views,_5a=this.getGridCoords();
var _5b=_59[!rtl?1:_59.length-1].scrollboxNode;
var _5c=_59[!rtl?_59.length-1:1].scrollboxNode;
var _5d=(!rtl||!dojo.isIE)?_5a.l:(_5a.l+_5b.offsetWidth-_5b.clientWidth);
var _5e=(!rtl||dojo.isMoz)?(_5a.l+_5a.w-(_5c.offsetWidth-_5c.clientWidth)):(_5a.l+_5a.w);
dojo.forEach(this.getHeaderNodes(),dojo.hitch(this,function(_5f,_60){
if(_60>this.exceptColumnsTo){
var x,_61=dojo.coords(_5f);
if(_56.x>=_61.x&&_56.x<=_61.x+_61.w){
if(!this.selectedColumns[_60]||!this.selectedColumns[_60-1]){
x=_61.x+_58.x+(rtl?_61.w:0);
if(_56.x<_5d||_56.x>_5e||x<_5d||x>_5e){
return;
}
dojo.style(_57,"left",x+"px");
this.drugDestIndex=_60;
this.drugBefore=true;
!dojo.isIE&&this.normalizeColBorderHeight(_57,_60);
}
}else{
if(this.getHeaderNodes()[_60+1]==null&&(!rtl?(_56.x>_61.x+_61.w):(_56.x<_61.x))){
x=_56.x<_5d?_5d:(_56.x>_5e?_5e:(_61.x+_58.x+(rtl?0:_61.w)));
dojo.style(_57,"left",x+"px");
this.drugDestIndex=_60;
this.drugBefore=false;
!dojo.isIE&&this.normalizeColBorderHeight(_57,_60);
}
}
}
}));
},normalizeColBorderHeight:function(_62,_63){
var _64=this.grid.pluginMgr.getViewByCellIdx(_63);
if(!_64){
return;
}
var _65=_64.scrollboxNode,_66=dojo.attr(_62,"colH");
var _67=dojo.coords(_65).h-(_65.offsetHeight-_65.clientHeight);
_67=_66>0&&_66<_67?_66:_67;
dojo.style(_62,"height",_67+"px");
},avataDivClick:function(e){
if(this.movingIgnored){
this.movingIgnored=false;
return;
}
this.cleanAll();
this.clearDrugDivs();
},startMoveCols:function(){
this.changeCursorState("wait");
this.srcIndexdelta=0;
deltaColAmount=0;
dojo.forEach(this.selectedColumns,dojo.hitch(this,function(col,_68){
if(this.isColSelected(_68)){
if(this.drugDestIndex>_68){
_68-=deltaColAmount;
}
deltaColAmount+=1;
var _69=this.grid.layout.cells[_68].view.idx;
var _6a=this.grid.layout.cells[this.drugDestIndex].view.idx;
if(_68!=this.drugDestIndex){
this.grid.layout.moveColumn(_69,_6a,_68,this.drugDestIndex,this.drugBefore);
}
if(this.drugDestIndex<=_68&&this.drugDestIndex+1<this.grid.layout.cells.length){
this.drugDestIndex+=1;
}
}
}));
var _6b=this.drugDestIndex+(this.drugBefore?0:1);
this.clearDrugDivs();
this.cleanAll();
this.resetCellIdx();
this.drugSelectionStart.colIndex=_6b-deltaColAmount;
this.drugSelectColumn(this.drugSelectionStart.colIndex+deltaColAmount-1);
},changeCursorState:function(_6c){
dojo.forEach(this.coverDIVs,function(div){
div.style.cursor="wait";
});
},addRowMovers:function(){
var _6d=-1;
dojo.forEach(this.grid.selection.selected,function(row,_6e){
var _6f=this.grid.views.views[0];
if(row&&_6f.rowNodes[_6e]){
if(_6d==-1){
_6d=_6e;
}
if(this.grid.selection.selected[_6e+1]==null||!_6f.rowNodes[_6e+1]){
this.addRowMover(_6d,_6e);
_6d=-1;
}
}
},this);
},addRowMover:function(_70,to){
var _71=0,_72=this.grid.views.views;
dojo.forEach(_72,function(_73,_74){
_71+=_73.getScrollbarWidth();
});
var _75=_72[_72.length-1].getScrollbarWidth();
var _76=!dojo._isBodyLtr()?(dojo.isIE?_71-_75:_71):0;
var _77=this.getGridWidth()-_75;
var _78=this.grid.views.views[0];
var _79=_78.rowNodes[_70],_7a=_78.rowNodes[to];
if(!_79||!_7a){
return;
}
var _7b=dojo.coords(_79),_7c=dojo.coords(_7a);
var _7d=this.getExceptionalColOffsetWidth();
var _7e=this.createCoverMover(_77-_7d,(_7c.y-_7b.y+_7c.h),dojo._isBodyLtr()?(_7b.x+_7b.w+_7d):(_7b.x-_77-_76),_7b.y,"row");
var _7f=this.setBorderDiv(_77,3,(dojo._isBodyLtr()?(_7c.x+_7c.w):(_7c.x-_77-_76))+dojo._docScroll().x,-100);
var _80=dojo.connect(_7e,"onMoveStart",dojo.hitch(this,function(_81,_82){
this.mover=_81;
this.removeOtherMovers(_81.node.id);
}));
var _83=dojo.connect(_7e,"onMove",dojo.hitch(this,function(_84,_85,_86){
if(_84.node==null||_84.node.parentNode==null){
return;
}
this.isMoving=true;
this.moveRowBorder(_84,_85,_7f,_86);
}));
var _87=dojo.connect(_7e,"onMoveStop",dojo.hitch(this,function(_88){
if(this.avaOnRowIndex==null||this.isContinuousSelection(this.grid.selection.selected)&&(this.avaOnRowIndex==_70||this.avaOnRowIndex==(to+1))){
this.movingIgnored=true;
if(this.isMoving){
this.isMoving=false;
this.clearDrugDivs();
}
return;
}
this.isMoving=false;
this.mover=null;
this.grid.select.outRangeY=false;
this.grid.select.moveOutTop=false;
this.grid.scroller.findScrollTop(this.grid.scroller.page*this.grid.scroller.rowsPerPage);
this.startMoveRows();
this.avaOnRowIndex=null;
delete _7e;
}));
},moveRowBorder:function(_89,_8a,_8b,_8c){
var _8d=this.getGridCoords(true),_8e=dojo._docScroll();
var _8f=_8d.t+this.headerHeight+_8d.h;
_8a.t-=_8e.y,_8c.y-=_8e.y;
if(_8c.y>=_8f){
this.grid.select.outRangeY=true;
this.autoMoveToNextRow();
}else{
if(_8c.y<=_8d.t+this.headerHeight){
this.grid.select.moveOutTop=true;
this.autoMoveToPreRow();
}else{
this.grid.select.outRangeY=this.grid.select.moveOutTop=false;
var _90=this.grid.views.views[0],_91=_90.rowNodes;
var _92=dojo.coords(_90.contentNode).h;
var _93=0,_94=-1;
for(i in _91){
i=parseInt(i);
++_93;
if(i>_94){
_94=i;
}
}
var _95=dojo.coords(_91[_94]);
if(_92<_8d.h&&_8c.y>(_95.y+_95.h)){
this.avaOnRowIndex=_93;
dojo.style(_8b,{"top":_95.y+_95.h+_8e.y+"px"});
return;
}
var _96,_97,_98;
for(var _99 in _91){
_99=parseInt(_99);
if(isNaN(_99)){
continue;
}
_97=_91[_99];
if(!_97){
continue;
}
_96=dojo.coords(_97),_98=(_96.y<=_8f);
if(_98&&_8c.y>_96.y&&_8c.y<_96.y+_96.h){
if(!this.grid.selection.selected[_99]||!this.grid.selection.selected[_99-1]){
this.avaOnRowIndex=_99;
dojo.style(_8b,{"top":_96.y+_8e.y+"px"});
}
}
}
}
}
},autoMoveToPreRow:function(){
if(this.grid.select.moveOutTop){
if(this.grid.scroller.firstVisibleRow>0){
this.grid.scrollToRow(this.grid.scroller.firstVisibleRow-1);
this.autoMoveBorderDivPre();
setTimeout(dojo.hitch(this,"autoMoveToPreRow"),this.autoScrollRate);
}
}
},autoMoveBorderDivPre:function(){
var _9a=dojo._docScroll(),_9b=this.getGridCoords();
var _9c=_9b.t+this.headerHeight+_9a.y;
var _9d,_9e=this.getBorderDiv();
if(this.avaOnRowIndex-1<=0){
this.avaOnRowIndex=0;
_9d=_9c;
}else{
this.avaOnRowIndex--;
_9d=dojo.coords(this.grid.views.views[0].rowNodes[this.avaOnRowIndex]).y+_9a.y;
}
_9e.style.top=(_9d<_9c?_9c:_9d)+"px";
},autoMoveToNextRow:function(){
if(this.grid.select.outRangeY){
if(this.avaOnRowIndex+1<=this.grid.scroller.rowCount){
this.grid.scrollToRow(this.grid.scroller.firstVisibleRow+1);
this.autoMoveBorderDiv();
setTimeout(dojo.hitch(this,"autoMoveToNextRow"),this.autoScrollRate);
}
}
},autoMoveBorderDiv:function(){
var _9f=dojo._docScroll(),_a0=this.getGridCoords();
var _a1=_a0.t+this.headerHeight+_a0.h+_9f.y;
var _a2,_a3=this.getBorderDiv();
if(this.avaOnRowIndex+1>=this.grid.scroller.rowCount){
this.avaOnRowIndex=this.grid.scroller.rowCount;
_a2=_a1;
}else{
this.avaOnRowIndex++;
_a2=dojo.coords(this.grid.views.views[0].rowNodes[this.avaOnRowIndex]).y+_9f.y;
}
_a3.style.top=(_a2>_a1?_a1:_a2)+"px";
},startMoveRows:function(){
var _a4=Math.min(this.avaOnRowIndex,this.getFirstSelected());
var end=Math.max(this.avaOnRowIndex-1,this.getLastSelected());
this.moveRows(_a4,end,this.getPageInfo());
},moveRows:function(_a5,end,_a6){
var i,_a7=false,_a8=(selectedRowsAboveBorderDIV=0),_a9=[];
var _aa=this.grid.scroller,_ab=_aa.rowsPerPage;
var _ac=_a6.topPage*_ab,_ad=(_a6.bottomPage+1)*_ab-1;
var _ae=dojo.hitch(this,function(_af,to){
for(i=_af;i<to;i++){
if(!this.grid.selection.selected[i]||!this.grid._by_idx[i]){
_a9.push(this.grid._by_idx[i]);
}
}
});
_ae(_a5,this.avaOnRowIndex);
for(i=_a5;i<=end;i++){
if(this.grid.selection.selected[i]&&this.grid._by_idx[i]){
_a9.push(this.grid._by_idx[i]);
_a8++;
if(this.avaOnRowIndex>i){
selectedRowsAboveBorderDIV++;
}
}
}
_ae(this.avaOnRowIndex,end+1);
for(i=_a5,j=0;i<=end;i++){
this.grid._by_idx[i]=_a9[j++];
if(i>=_ac&&i<=_ad){
this.grid.updateRow(i);
_a7=true;
}
}
this.avaOnRowIndex+=_a8-selectedRowsAboveBorderDIV;
try{
this.clearDrugDivs();
this.cleanAll();
this.drugSelectionStart.rowIndex=this.avaOnRowIndex-_a8;
this.drugSelectRow(this.drugSelectionStart.rowIndex+_a8-1);
if(_a7){
var _b0=_aa.stack;
dojo.forEach(_a6.invalidPages,function(_b1){
_aa.destroyPage(_b1);
i=dojo.indexOf(_b0,_b1);
if(i>=0){
_b0.splice(i,1);
}
});
}
this.publishRowMove();
}
catch(e){
console.debug(e);
}
},clearDrugDivs:function(){
if(!this.isMoving){
var _b2=this.getBorderDiv();
_b2.style.top=-100+"px";
_b2.style.height="0px";
_b2.style.left=-100+"px";
dojo.forEach(this.coverDIVs,function(div){
dojo.forEach(div.connections,function(_b3){
dojo.disconnect(_b3);
});
dojo.doc.body.removeChild(div);
delete div;
},this);
this.coverDIVs=[];
}
},setDrugCoverDivs:function(_b4,_b5){
if(!this.isMoving){
if(this.isColSelected(_b4)){
this.addColMovers();
}else{
if(this.grid.selection.selected[_b5]){
this.addRowMovers();
}else{
this.clearDrugDivs();
}
}
}
},getPageInfo:function(){
var _b6=this.grid.scroller,_b7=(bottomPage=_b6.page);
var _b8=_b6.firstVisibleRow,_b9=_b6.lastVisibleRow;
var _ba=_b6.rowsPerPage,_bb=_b6.pageNodes[0];
var _bc,_bd,_be=[],_bf;
dojo.forEach(_bb,function(_c0,_c1){
if(!_c0){
return;
}
_bf=false;
_bc=_c1*_ba;
_bd=(_c1+1)*_ba-1;
if(_b8>=_bc&&_b8<=_bd){
_b7=_c1;
_bf=true;
}
if(_b9>=_bc&&_b9<=_bd){
bottomPage=_c1;
_bf=true;
}
if(!_bf&&(_bc>_b9||_bd<_b8)){
_be.push(_c1);
}
});
return {topPage:_b7,bottomPage:bottomPage,invalidPages:_be};
},resetCellIdx:function(){
var _c2=0;
var _c3=-1;
dojo.forEach(this.grid.views.views,function(_c4,_c5){
if(_c5==0){
return;
}
if(_c4.structure.cells&&_c4.structure.cells[0]){
dojo.forEach(_c4.structure.cells[0],function(_c6,_c7){
var _c8=_c6.markup[2].split(" ");
var idx=_c2+_c7;
_c8[1]="idx=\""+idx+"\"";
_c6.markup[2]=_c8.join(" ");
});
}
for(i in _c4.rowNodes){
if(!_c4.rowNodes[i]){
return;
}
dojo.forEach(_c4.rowNodes[i].firstChild.rows[0].cells,function(_c9,_ca){
if(_c9&&_c9.attributes){
if(_ca+_c2>_c3){
_c3=_ca+_c2;
}
var idx=document.createAttribute("idx");
idx.value=_ca+_c2;
_c9.attributes.setNamedItem(idx);
}
});
}
_c2=_c3+1;
});
},publishRowMove:function(){
dojo.publish(this.grid.rowMovedTopic,[this]);
},keyboardMove:function(_cb){
var _cc=this.selectedColumns.length>0;
var _cd=dojo.hitch(this.grid.selection,dojox.grid.Selection.prototype["getFirstSelected"])()>=0;
var i,_ce,dk=dojo.keys,_cf=_cb.keyCode;
if(!dojo._isBodyLtr()){
_cf=(_cb.keyCode==dk.LEFT_ARROW)?dk.RIGHT_ARROW:(_cb.keyCode==dk.RIGHT_ARROW?dk.LEFT_ARROW:_cf);
}
switch(_cf){
case dk.LEFT_ARROW:
if(!_cc){
return;
}
_ce=this.getHeaderNodes().length;
for(i=0;i<_ce;i++){
if(this.isColSelected(i)){
this.drugDestIndex=i-1;
this.drugBefore=true;
break;
}
}
var _d0=this.grid.indirectSelection?1:0;
(this.drugDestIndex>=_d0)?this.startMoveCols():(this.drugDestIndex=_d0);
break;
case dk.RIGHT_ARROW:
if(!_cc){
return;
}
_ce=this.getHeaderNodes().length;
this.drugBefore=true;
for(i=0;i<_ce;i++){
if(this.isColSelected(i)&&!this.isColSelected(i+1)){
this.drugDestIndex=i+2;
if(this.drugDestIndex==_ce){
this.drugDestIndex--;
this.drugBefore=false;
}
break;
}
}
if(this.drugDestIndex<_ce){
this.startMoveCols();
}
break;
case dk.UP_ARROW:
if(!_cd){
return;
}
this.avaOnRowIndex=dojo.hitch(this.grid.selection,dojox.grid.Selection.prototype["getFirstSelected"])()-1;
if(this.avaOnRowIndex>-1){
this.startMoveRows();
}
break;
case dk.DOWN_ARROW:
if(!_cd){
return;
}
for(i=0;i<this.grid.rowCount;i++){
if(this.grid.selection.selected[i]&&!this.grid.selection.selected[i+1]){
this.avaOnRowIndex=i+2;
break;
}
}
if(this.avaOnRowIndex<=this.grid.rowCount){
this.startMoveRows();
}
}
}});
}
