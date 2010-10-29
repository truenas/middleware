/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.tree.TreeStoreModel"]){
dojo._hasResource["dijit.tree.TreeStoreModel"]=true;
dojo.provide("dijit.tree.TreeStoreModel");
dojo.declare("dijit.tree.TreeStoreModel",null,{store:null,childrenAttrs:["children"],newItemIdAttr:"id",labelAttr:"",root:null,query:null,deferItemLoadingUntilExpand:false,constructor:function(_1){
dojo.mixin(this,_1);
this.connects=[];
var _2=this.store;
if(!_2.getFeatures()["dojo.data.api.Identity"]){
throw new Error("dijit.Tree: store must support dojo.data.Identity");
}
if(_2.getFeatures()["dojo.data.api.Notification"]){
this.connects=this.connects.concat([dojo.connect(_2,"onNew",this,"onNewItem"),dojo.connect(_2,"onDelete",this,"onDeleteItem"),dojo.connect(_2,"onSet",this,"onSetItem")]);
}
},destroy:function(){
dojo.forEach(this.connects,dojo.disconnect);
},getRoot:function(_3,_4){
if(this.root){
_3(this.root);
}else{
this.store.fetch({query:this.query,onComplete:dojo.hitch(this,function(_5){
if(_5.length!=1){
throw new Error(this.declaredClass+": query "+dojo.toJson(this.query)+" returned "+_5.length+" items, but must return exactly one item");
}
this.root=_5[0];
_3(this.root);
}),onError:_4});
}
},mayHaveChildren:function(_6){
return dojo.some(this.childrenAttrs,function(_7){
return this.store.hasAttribute(_6,_7);
},this);
},getChildren:function(_8,_9,_a){
var _b=this.store;
if(!_b.isItemLoaded(_8)){
var _c=dojo.hitch(this,arguments.callee);
_b.loadItem({item:_8,onItem:function(_d){
_c(_d,_9,_a);
},onError:_a});
return;
}
var _e=[];
for(var i=0;i<this.childrenAttrs.length;i++){
var _f=_b.getValues(_8,this.childrenAttrs[i]);
_e=_e.concat(_f);
}
var _10=0;
if(!this.deferItemLoadingUntilExpand){
dojo.forEach(_e,function(_11){
if(!_b.isItemLoaded(_11)){
_10++;
}
});
}
if(_10==0){
_9(_e);
}else{
dojo.forEach(_e,function(_12,idx){
if(!_b.isItemLoaded(_12)){
_b.loadItem({item:_12,onItem:function(_13){
_e[idx]=_13;
if(--_10==0){
_9(_e);
}
},onError:_a});
}
});
}
},isItem:function(_14){
return this.store.isItem(_14);
},fetchItemByIdentity:function(_15){
this.store.fetchItemByIdentity(_15);
},getIdentity:function(_16){
return this.store.getIdentity(_16);
},getLabel:function(_17){
if(this.labelAttr){
return this.store.getValue(_17,this.labelAttr);
}else{
return this.store.getLabel(_17);
}
},newItem:function(_18,_19,_1a){
var _1b={parent:_19,attribute:this.childrenAttrs[0],insertIndex:_1a};
if(this.newItemIdAttr&&_18[this.newItemIdAttr]){
this.fetchItemByIdentity({identity:_18[this.newItemIdAttr],scope:this,onItem:function(_1c){
if(_1c){
this.pasteItem(_1c,null,_19,true,_1a);
}else{
this.store.newItem(_18,_1b);
}
}});
}else{
this.store.newItem(_18,_1b);
}
},pasteItem:function(_1d,_1e,_1f,_20,_21){
var _22=this.store,_23=this.childrenAttrs[0];
if(_1e){
dojo.forEach(this.childrenAttrs,function(_24){
if(_22.containsValue(_1e,_24,_1d)){
if(!_20){
var _25=dojo.filter(_22.getValues(_1e,_24),function(x){
return x!=_1d;
});
_22.setValues(_1e,_24,_25);
}
_23=_24;
}
});
}
if(_1f){
if(typeof _21=="number"){
var _26=_22.getValues(_1f,_23).slice();
_26.splice(_21,0,_1d);
_22.setValues(_1f,_23,_26);
}else{
_22.setValues(_1f,_23,_22.getValues(_1f,_23).concat(_1d));
}
}
},onChange:function(_27){
},onChildrenChange:function(_28,_29){
},onDelete:function(_2a,_2b){
},onNewItem:function(_2c,_2d){
if(!_2d){
return;
}
this.getChildren(_2d.item,dojo.hitch(this,function(_2e){
this.onChildrenChange(_2d.item,_2e);
}));
},onDeleteItem:function(_2f){
this.onDelete(_2f);
},onSetItem:function(_30,_31,_32,_33){
if(dojo.indexOf(this.childrenAttrs,_31)!=-1){
this.getChildren(_30,dojo.hitch(this,function(_34){
this.onChildrenChange(_30,_34);
}));
}else{
this.onChange(_30);
}
}});
}
