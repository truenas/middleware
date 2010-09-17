/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojox.grid.DataGrid"]){
dojo._hasResource["dojox.grid.DataGrid"]=true;
dojo.provide("dojox.grid.DataGrid");
dojo.require("dojox.grid._Grid");
dojo.require("dojox.grid.DataSelection");
dojo.declare("dojox.grid.DataGrid",dojox.grid._Grid,{store:null,query:null,queryOptions:null,fetchText:"...",sortFields:null,updateDelay:1,items:null,_store_connects:null,_by_idty:null,_by_idx:null,_cache:null,_pages:null,_pending_requests:null,_bop:-1,_eop:-1,_requests:0,rowCount:0,_isLoaded:false,_isLoading:false,postCreate:function(){
this._pages=[];
this._store_connects=[];
this._by_idty={};
this._by_idx=[];
this._cache=[];
this._pending_requests={};
this._setStore(this.store);
this.inherited(arguments);
},createSelection:function(){
this.selection=new dojox.grid.DataSelection(this);
},get:function(_1,_2){
if(_2&&this.field=="_item"&&!this.fields){
return _2;
}else{
if(_2&&this.fields){
var _3=[];
var s=this.grid.store;
dojo.forEach(this.fields,function(f){
_3=_3.concat(s.getValues(_2,f));
});
return _3;
}else{
if(!_2&&typeof _1==="string"){
return this.inherited(arguments);
}
}
}
return (!_2?this.defaultValue:(!this.field?this.value:(this.field=="_item"?_2:this.grid.store.getValue(_2,this.field))));
},_checkUpdateStatus:function(){
if(this.updateDelay>0){
var _4=false;
if(this._endUpdateDelay){
clearTimeout(this._endUpdateDelay);
delete this._endUpdateDelay;
_4=true;
}
if(!this.updating){
this.beginUpdate();
_4=true;
}
if(_4){
var _5=this;
this._endUpdateDelay=setTimeout(function(){
delete _5._endUpdateDelay;
_5.endUpdate();
},this.updateDelay);
}
}
},_onSet:function(_6,_7,_8,_9){
this._checkUpdateStatus();
var _a=this.getItemIndex(_6);
if(_a>-1){
this.updateRow(_a);
}
},_createItem:function(_b,_c){
var _d=this._hasIdentity?this.store.getIdentity(_b):dojo.toJson(this.query)+":idx:"+_c+":sort:"+dojo.toJson(this.getSortProps());
var o=this._by_idty[_d]={idty:_d,item:_b};
return o;
},_addItem:function(_e,_f,_10){
this._by_idx[_f]=this._createItem(_e,_f);
if(!_10){
this.updateRow(_f);
}
},_onNew:function(_11,_12){
this._checkUpdateStatus();
var _13=this.get("rowCount");
this._addingItem=true;
this.updateRowCount(_13+1);
this._addingItem=false;
this._addItem(_11,_13);
this.showMessage();
},_onDelete:function(_14){
this._checkUpdateStatus();
var idx=this._getItemIndex(_14,true);
if(idx>=0){
this._pages=[];
this._bop=-1;
this._eop=-1;
var o=this._by_idx[idx];
this._by_idx.splice(idx,1);
delete this._by_idty[o.idty];
this.updateRowCount(this.get("rowCount")-1);
if(this.get("rowCount")===0){
this.showMessage(this.noDataMessage);
}
}
},_onRevert:function(){
this._refresh();
},setStore:function(_15,_16,_17){
this._setQuery(_16,_17);
this._setStore(_15);
this._refresh(true);
},setQuery:function(_18,_19){
this._setQuery(_18,_19);
this._refresh(true);
},setItems:function(_1a){
this.items=_1a;
this._setStore(this.store);
this._refresh(true);
},_setQuery:function(_1b,_1c){
this.query=_1b;
this.queryOptions=_1c||this.queryOptions;
},_setStore:function(_1d){
if(this.store&&this._store_connects){
dojo.forEach(this._store_connects,function(arr){
dojo.forEach(arr,dojo.disconnect);
});
}
this.store=_1d;
if(this.store){
var f=this.store.getFeatures();
var h=[];
this._canEdit=!!f["dojo.data.api.Write"]&&!!f["dojo.data.api.Identity"];
this._hasIdentity=!!f["dojo.data.api.Identity"];
if(!!f["dojo.data.api.Notification"]&&!this.items){
h.push(this.connect(this.store,"onSet","_onSet"));
h.push(this.connect(this.store,"onNew","_onNew"));
h.push(this.connect(this.store,"onDelete","_onDelete"));
}
if(this._canEdit){
h.push(this.connect(this.store,"revert","_onRevert"));
}
this._store_connects=h;
}
},_onFetchBegin:function(_1e,req){
if(!this.scroller){
return;
}
if(this.rowCount!=_1e){
if(req.isRender){
this.scroller.init(_1e,this.keepRows,this.rowsPerPage);
this.rowCount=_1e;
this._setAutoHeightAttr(this.autoHeight,true);
this._skipRowRenormalize=true;
this.prerender();
this._skipRowRenormalize=false;
}else{
this.updateRowCount(_1e);
}
}
if(!_1e){
this.views.render();
this._resize();
this.showMessage(this.noDataMessage);
this.focus.initFocusView();
}else{
this.showMessage();
}
},_onFetchComplete:function(_1f,req){
if(!this.scroller){
return;
}
if(_1f&&_1f.length>0){
dojo.forEach(_1f,function(_20,idx){
this._addItem(_20,req.start+idx,true);
},this);
if(this._autoHeight){
this._skipRowRenormalize=true;
}
this.updateRows(req.start,_1f.length);
if(this._autoHeight){
this._skipRowRenormalize=false;
}
if(req.isRender){
this.setScrollTop(0);
this.postrender();
}else{
if(this._lastScrollTop){
this.setScrollTop(this._lastScrollTop);
}
}
}
delete this._lastScrollTop;
if(!this._isLoaded){
this._isLoading=false;
this._isLoaded=true;
}
this._pending_requests[req.start]=false;
},_onFetchError:function(err,req){
console.log(err);
delete this._lastScrollTop;
if(!this._isLoaded){
this._isLoading=false;
this._isLoaded=true;
this.showMessage(this.errorMessage);
}
this._pending_requests[req.start]=false;
this.onFetchError(err,req);
},onFetchError:function(err,req){
},_fetch:function(_21,_22){
_21=_21||0;
if(this.store&&!this._pending_requests[_21]){
if(!this._isLoaded&&!this._isLoading){
this._isLoading=true;
this.showMessage(this.loadingMessage);
}
this._pending_requests[_21]=true;
try{
if(this.items){
var _23=this.items;
var _24=this.store;
this.rowsPerPage=_23.length;
var req={start:_21,count:this.rowsPerPage,isRender:_22};
this._onFetchBegin(_23.length,req);
var _25=0;
dojo.forEach(_23,function(i){
if(!_24.isItemLoaded(i)){
_25++;
}
});
if(_25===0){
this._onFetchComplete(_23,req);
}else{
var _26=function(_27){
_25--;
if(_25===0){
this._onFetchComplete(_23,req);
}
};
dojo.forEach(_23,function(i){
if(!_24.isItemLoaded(i)){
_24.loadItem({item:i,onItem:_26,scope:this});
}
},this);
}
}else{
this.store.fetch({start:_21,count:this.rowsPerPage,query:this.query,sort:this.getSortProps(),queryOptions:this.queryOptions,isRender:_22,onBegin:dojo.hitch(this,"_onFetchBegin"),onComplete:dojo.hitch(this,"_onFetchComplete"),onError:dojo.hitch(this,"_onFetchError")});
}
}
catch(e){
this._onFetchError(e,{start:_21,count:this.rowsPerPage});
}
}
},_clearData:function(){
this.updateRowCount(0);
this._by_idty={};
this._by_idx=[];
this._pages=[];
this._bop=this._eop=-1;
this._isLoaded=false;
this._isLoading=false;
},getItem:function(idx){
var _28=this._by_idx[idx];
if(!_28||(_28&&!_28.item)){
this._preparePage(idx);
return null;
}
return _28.item;
},getItemIndex:function(_29){
return this._getItemIndex(_29,false);
},_getItemIndex:function(_2a,_2b){
if(!_2b&&!this.store.isItem(_2a)){
return -1;
}
var _2c=this._hasIdentity?this.store.getIdentity(_2a):null;
for(var i=0,l=this._by_idx.length;i<l;i++){
var d=this._by_idx[i];
if(d&&((_2c&&d.idty==_2c)||(d.item===_2a))){
return i;
}
}
return -1;
},filter:function(_2d,_2e){
this.query=_2d;
if(_2e){
this._clearData();
}
this._fetch();
},_getItemAttr:function(idx,_2f){
var _30=this.getItem(idx);
return (!_30?this.fetchText:this.store.getValue(_30,_2f));
},_render:function(){
if(this.domNode.parentNode){
this.scroller.init(this.get("rowCount"),this.keepRows,this.rowsPerPage);
this.prerender();
this._fetch(0,true);
}
},_requestsPending:function(_31){
return this._pending_requests[_31];
},_rowToPage:function(_32){
return (this.rowsPerPage?Math.floor(_32/this.rowsPerPage):_32);
},_pageToRow:function(_33){
return (this.rowsPerPage?this.rowsPerPage*_33:_33);
},_preparePage:function(_34){
if((_34<this._bop||_34>=this._eop)&&!this._addingItem){
var _35=this._rowToPage(_34);
this._needPage(_35);
this._bop=_35*this.rowsPerPage;
this._eop=this._bop+(this.rowsPerPage||this.get("rowCount"));
}
},_needPage:function(_36){
if(!this._pages[_36]){
this._pages[_36]=true;
this._requestPage(_36);
}
},_requestPage:function(_37){
var row=this._pageToRow(_37);
var _38=Math.min(this.rowsPerPage,this.get("rowCount")-row);
if(_38>0){
this._requests++;
if(!this._requestsPending(row)){
setTimeout(dojo.hitch(this,"_fetch",row,false),1);
}
}
},getCellName:function(_39){
return _39.field;
},_refresh:function(_3a){
this._clearData();
this._fetch(0,_3a);
},sort:function(){
this._lastScrollTop=this.scrollTop;
this._refresh();
},canSort:function(){
return (!this._isLoading);
},getSortProps:function(){
var c=this.getCell(this.getSortIndex());
if(!c){
if(this.sortFields){
return this.sortFields;
}
return null;
}else{
var _3b=c["sortDesc"];
var si=!(this.sortInfo>0);
if(typeof _3b=="undefined"){
_3b=si;
}else{
_3b=si?!_3b:_3b;
}
return [{attribute:c.field,descending:_3b}];
}
},styleRowState:function(_3c){
if(this.store&&this.store.getState){
var _3d=this.store.getState(_3c.index),c="";
for(var i=0,ss=["inflight","error","inserting"],s;s=ss[i];i++){
if(_3d[s]){
c=" dojoxGridRow-"+s;
break;
}
}
_3c.customClasses+=c;
}
},onStyleRow:function(_3e){
this.styleRowState(_3e);
this.inherited(arguments);
},canEdit:function(_3f,_40){
return this._canEdit;
},_copyAttr:function(idx,_41){
var row={};
var _42={};
var src=this.getItem(idx);
return this.store.getValue(src,_41);
},doStartEdit:function(_43,_44){
if(!this._cache[_44]){
this._cache[_44]=this._copyAttr(_44,_43.field);
}
this.onStartEdit(_43,_44);
},doApplyCellEdit:function(_45,_46,_47){
this.store.fetchItemByIdentity({identity:this._by_idx[_46].idty,onItem:dojo.hitch(this,function(_48){
var _49=this.store.getValue(_48,_47);
if(typeof _49=="number"){
_45=isNaN(_45)?_45:parseFloat(_45);
}else{
if(typeof _49=="boolean"){
_45=_45=="true"?true:_45=="false"?false:_45;
}else{
if(_49 instanceof Date){
var _4a=new Date(_45);
_45=isNaN(_4a.getTime())?_45:_4a;
}
}
}
this.store.setValue(_48,_47,_45);
this.onApplyCellEdit(_45,_46,_47);
})});
},doCancelEdit:function(_4b){
var _4c=this._cache[_4b];
if(_4c){
this.updateRow(_4b);
delete this._cache[_4b];
}
this.onCancelEdit.apply(this,arguments);
},doApplyEdit:function(_4d,_4e){
var _4f=this._cache[_4d];
this.onApplyEdit(_4d);
},removeSelectedRows:function(){
if(this._canEdit){
this.edit.apply();
var fx=dojo.hitch(this,function(_50){
if(_50.length){
dojo.forEach(_50,this.store.deleteItem,this.store);
this.selection.clear();
}
});
if(this.allItemsSelected){
this.store.fetch({query:this.query,queryOptions:this.queryOptions,onComplete:fx});
}else{
fx(this.selection.getSelected());
}
}
}});
dojox.grid.DataGrid.cell_markupFactory=function(_51,_52,_53){
var _54=dojo.trim(dojo.attr(_52,"field")||"");
if(_54){
_53.field=_54;
}
_53.field=_53.field||_53.name;
var _55=dojo.trim(dojo.attr(_52,"fields")||"");
if(_55){
_53.fields=_55.split(",");
}
if(_51){
_51(_52,_53);
}
};
dojox.grid.DataGrid.markupFactory=function(_56,_57,_58,_59){
return dojox.grid._Grid.markupFactory(_56,_57,_58,dojo.partial(dojox.grid.DataGrid.cell_markupFactory,_59));
};
}
