/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.Tree"]){
dojo._hasResource["dijit.Tree"]=true;
dojo.provide("dijit.Tree");
dojo.require("dojo.fx");
dojo.require("dojo.DeferredList");
dojo.require("dijit._Widget");
dojo.require("dijit._Templated");
dojo.require("dijit._Container");
dojo.require("dijit._Contained");
dojo.require("dijit._CssStateMixin");
dojo.require("dojo.cookie");
dojo.declare("dijit._TreeNode",[dijit._Widget,dijit._Templated,dijit._Container,dijit._Contained,dijit._CssStateMixin],{item:null,isTreeNode:true,label:"",isExpandable:null,isExpanded:false,state:"UNCHECKED",templateString:dojo.cache("dijit","templates/TreeNode.html","<div class=\"dijitTreeNode\" waiRole=\"presentation\"\n\t><div dojoAttachPoint=\"rowNode\" class=\"dijitTreeRow\" waiRole=\"presentation\" dojoAttachEvent=\"onmouseenter:_onMouseEnter, onmouseleave:_onMouseLeave, onclick:_onClick, ondblclick:_onDblClick\"\n\t\t><img src=\"${_blankGif}\" alt=\"\" dojoAttachPoint=\"expandoNode\" class=\"dijitTreeExpando\" waiRole=\"presentation\"\n\t\t/><span dojoAttachPoint=\"expandoNodeText\" class=\"dijitExpandoText\" waiRole=\"presentation\"\n\t\t></span\n\t\t><span dojoAttachPoint=\"contentNode\"\n\t\t\tclass=\"dijitTreeContent\" waiRole=\"presentation\">\n\t\t\t<img src=\"${_blankGif}\" alt=\"\" dojoAttachPoint=\"iconNode\" class=\"dijitIcon dijitTreeIcon\" waiRole=\"presentation\"\n\t\t\t/><span dojoAttachPoint=\"labelNode\" class=\"dijitTreeLabel\" wairole=\"treeitem\" tabindex=\"-1\" waiState=\"selected-false\" dojoAttachEvent=\"onfocus:_onLabelFocus\"></span>\n\t\t</span\n\t></div>\n\t<div dojoAttachPoint=\"containerNode\" class=\"dijitTreeContainer\" waiRole=\"presentation\" style=\"display: none;\"></div>\n</div>\n"),baseClass:"dijitTreeNode",cssStateNodes:{rowNode:"dijitTreeRow",labelNode:"dijitTreeLabel"},attributeMap:dojo.delegate(dijit._Widget.prototype.attributeMap,{label:{node:"labelNode",type:"innerText"},tooltip:{node:"rowNode",type:"attribute",attribute:"title"}}),postCreate:function(){
this.inherited(arguments);
this._setExpando();
this._updateItemClasses(this.item);
if(this.isExpandable){
dijit.setWaiState(this.labelNode,"expanded",this.isExpanded);
}
},_setIndentAttr:function(_1){
this.indent=_1;
var _2=(Math.max(_1,0)*this.tree._nodePixelIndent)+"px";
dojo.style(this.domNode,"backgroundPosition",_2+" 0px");
dojo.style(this.rowNode,this.isLeftToRight()?"paddingLeft":"paddingRight",_2);
dojo.forEach(this.getChildren(),function(_3){
_3.set("indent",_1+1);
});
},markProcessing:function(){
this.state="LOADING";
this._setExpando(true);
},unmarkProcessing:function(){
this._setExpando(false);
},_updateItemClasses:function(_4){
var _5=this.tree,_6=_5.model;
if(_5._v10Compat&&_4===_6.root){
_4=null;
}
this._applyClassAndStyle(_4,"icon","Icon");
this._applyClassAndStyle(_4,"label","Label");
this._applyClassAndStyle(_4,"row","Row");
},_applyClassAndStyle:function(_7,_8,_9){
var _a="_"+_8+"Class";
var _b=_8+"Node";
if(this[_a]){
dojo.removeClass(this[_b],this[_a]);
}
this[_a]=this.tree["get"+_9+"Class"](_7,this.isExpanded);
if(this[_a]){
dojo.addClass(this[_b],this[_a]);
}
dojo.style(this[_b],this.tree["get"+_9+"Style"](_7,this.isExpanded)||{});
},_updateLayout:function(){
var _c=this.getParent();
if(!_c||_c.rowNode.style.display=="none"){
dojo.addClass(this.domNode,"dijitTreeIsRoot");
}else{
dojo.toggleClass(this.domNode,"dijitTreeIsLast",!this.getNextSibling());
}
},_setExpando:function(_d){
var _e=["dijitTreeExpandoLoading","dijitTreeExpandoOpened","dijitTreeExpandoClosed","dijitTreeExpandoLeaf"],_f=["*","-","+","*"],idx=_d?0:(this.isExpandable?(this.isExpanded?1:2):3);
dojo.removeClass(this.expandoNode,_e);
dojo.addClass(this.expandoNode,_e[idx]);
this.expandoNodeText.innerHTML=_f[idx];
},expand:function(){
if(this._expandDeferred){
return this._expandDeferred;
}
this._wipeOut&&this._wipeOut.stop();
this.isExpanded=true;
dijit.setWaiState(this.labelNode,"expanded","true");
dijit.setWaiRole(this.containerNode,"group");
dojo.addClass(this.contentNode,"dijitTreeContentExpanded");
this._setExpando();
this._updateItemClasses(this.item);
if(this==this.tree.rootNode){
dijit.setWaiState(this.tree.domNode,"expanded","true");
}
var def,_10=dojo.fx.wipeIn({node:this.containerNode,duration:dijit.defaultDuration,onEnd:function(){
def.callback(true);
}});
def=(this._expandDeferred=new dojo.Deferred(function(){
_10.stop();
}));
_10.play();
return def;
},collapse:function(){
if(!this.isExpanded){
return;
}
if(this._expandDeferred){
this._expandDeferred.cancel();
delete this._expandDeferred;
}
this.isExpanded=false;
dijit.setWaiState(this.labelNode,"expanded","false");
if(this==this.tree.rootNode){
dijit.setWaiState(this.tree.domNode,"expanded","false");
}
dojo.removeClass(this.contentNode,"dijitTreeContentExpanded");
this._setExpando();
this._updateItemClasses(this.item);
if(!this._wipeOut){
this._wipeOut=dojo.fx.wipeOut({node:this.containerNode,duration:dijit.defaultDuration});
}
this._wipeOut.play();
},indent:0,setChildItems:function(_11){
var _12=this.tree,_13=_12.model,_14=[];
dojo.forEach(this.getChildren(),function(_15){
dijit._Container.prototype.removeChild.call(this,_15);
},this);
this.state="LOADED";
if(_11&&_11.length>0){
this.isExpandable=true;
dojo.forEach(_11,function(_16){
var id=_13.getIdentity(_16),_17=_12._itemNodesMap[id],_18;
if(_17){
for(var i=0;i<_17.length;i++){
if(_17[i]&&!_17[i].getParent()){
_18=_17[i];
_18.set("indent",this.indent+1);
break;
}
}
}
if(!_18){
_18=this.tree._createTreeNode({item:_16,tree:_12,isExpandable:_13.mayHaveChildren(_16),label:_12.getLabel(_16),tooltip:_12.getTooltip(_16),dir:_12.dir,lang:_12.lang,indent:this.indent+1});
if(_17){
_17.push(_18);
}else{
_12._itemNodesMap[id]=[_18];
}
}
this.addChild(_18);
if(this.tree.autoExpand||this.tree._state(_16)){
_14.push(_12._expandNode(_18));
}
},this);
dojo.forEach(this.getChildren(),function(_19,idx){
_19._updateLayout();
});
}else{
this.isExpandable=false;
}
if(this._setExpando){
this._setExpando(false);
}
this._updateItemClasses(this.item);
if(this==_12.rootNode){
var fc=this.tree.showRoot?this:this.getChildren()[0];
if(fc){
fc.setFocusable(true);
_12.lastFocused=fc;
}else{
_12.domNode.setAttribute("tabIndex","0");
}
}
return new dojo.DeferredList(_14);
},removeChild:function(_1a){
this.inherited(arguments);
var _1b=this.getChildren();
if(_1b.length==0){
this.isExpandable=false;
this.collapse();
}
dojo.forEach(_1b,function(_1c){
_1c._updateLayout();
});
},makeExpandable:function(){
this.isExpandable=true;
this._setExpando(false);
},_onLabelFocus:function(evt){
this.tree._onNodeFocus(this);
},setSelected:function(_1d){
dijit.setWaiState(this.labelNode,"selected",_1d);
dojo.toggleClass(this.rowNode,"dijitTreeRowSelected",_1d);
},setFocusable:function(_1e){
this.labelNode.setAttribute("tabIndex",_1e?"0":"-1");
},_onClick:function(evt){
this.tree._onClick(this,evt);
},_onDblClick:function(evt){
this.tree._onDblClick(this,evt);
},_onMouseEnter:function(evt){
this.tree._onNodeMouseEnter(this,evt);
},_onMouseLeave:function(evt){
this.tree._onNodeMouseLeave(this,evt);
}});
dojo.declare("dijit.Tree",[dijit._Widget,dijit._Templated],{store:null,model:null,query:null,label:"",showRoot:true,childrenAttr:["children"],path:[],selectedItem:null,openOnClick:false,openOnDblClick:false,templateString:dojo.cache("dijit","templates/Tree.html","<div class=\"dijitTree dijitTreeContainer\" waiRole=\"tree\"\n\tdojoAttachEvent=\"onkeypress:_onKeyPress\">\n\t<div class=\"dijitInline dijitTreeIndent\" style=\"position: absolute; top: -9999px\" dojoAttachPoint=\"indentDetector\"></div>\n</div>\n"),persist:true,autoExpand:false,dndController:null,dndParams:["onDndDrop","itemCreator","onDndCancel","checkAcceptance","checkItemAcceptance","dragThreshold","betweenThreshold"],onDndDrop:null,itemCreator:null,onDndCancel:null,checkAcceptance:null,checkItemAcceptance:null,dragThreshold:5,betweenThreshold:0,_nodePixelIndent:19,_publish:function(_1f,_20){
dojo.publish(this.id,[dojo.mixin({tree:this,event:_1f},_20||{})]);
},postMixInProperties:function(){
this.tree=this;
if(this.autoExpand){
this.persist=false;
}
this._itemNodesMap={};
if(!this.cookieName){
this.cookieName=this.id+"SaveStateCookie";
}
this._loadDeferred=new dojo.Deferred();
this.inherited(arguments);
},postCreate:function(){
this._initState();
if(!this.model){
this._store2model();
}
this.connect(this.model,"onChange","_onItemChange");
this.connect(this.model,"onChildrenChange","_onItemChildrenChange");
this.connect(this.model,"onDelete","_onItemDelete");
this._load();
this.inherited(arguments);
if(this.dndController){
if(dojo.isString(this.dndController)){
this.dndController=dojo.getObject(this.dndController);
}
var _21={};
for(var i=0;i<this.dndParams.length;i++){
if(this[this.dndParams[i]]){
_21[this.dndParams[i]]=this[this.dndParams[i]];
}
}
this.dndController=new this.dndController(this,_21);
}
},_store2model:function(){
this._v10Compat=true;
dojo.deprecated("Tree: from version 2.0, should specify a model object rather than a store/query");
var _22={id:this.id+"_ForestStoreModel",store:this.store,query:this.query,childrenAttrs:this.childrenAttr};
if(this.params.mayHaveChildren){
_22.mayHaveChildren=dojo.hitch(this,"mayHaveChildren");
}
if(this.params.getItemChildren){
_22.getChildren=dojo.hitch(this,function(_23,_24,_25){
this.getItemChildren((this._v10Compat&&_23===this.model.root)?null:_23,_24,_25);
});
}
this.model=new dijit.tree.ForestStoreModel(_22);
this.showRoot=Boolean(this.label);
},onLoad:function(){
},_load:function(){
this.model.getRoot(dojo.hitch(this,function(_26){
var rn=(this.rootNode=this.tree._createTreeNode({item:_26,tree:this,isExpandable:true,label:this.label||this.getLabel(_26),indent:this.showRoot?0:-1}));
if(!this.showRoot){
rn.rowNode.style.display="none";
}
this.domNode.appendChild(rn.domNode);
var _27=this.model.getIdentity(_26);
if(this._itemNodesMap[_27]){
this._itemNodesMap[_27].push(rn);
}else{
this._itemNodesMap[_27]=[rn];
}
rn._updateLayout();
this._expandNode(rn).addCallback(dojo.hitch(this,function(){
this._loadDeferred.callback(true);
this.onLoad();
}));
}),function(err){
console.error(this,": error loading root: ",err);
});
},getNodesByItem:function(_28){
if(!_28){
return [];
}
var _29=dojo.isString(_28)?_28:this.model.getIdentity(_28);
return [].concat(this._itemNodesMap[_29]);
},_setSelectedItemAttr:function(_2a){
var _2b=this.get("selectedItem");
var _2c=(!_2a||dojo.isString(_2a))?_2a:this.model.getIdentity(_2a);
if(_2c==_2b?this.model.getIdentity(_2b):null){
return;
}
var _2d=this._itemNodesMap[_2c];
this._selectNode((_2d&&_2d[0])||null);
},_getSelectedItemAttr:function(){
return this.selectedNode&&this.selectedNode.item;
},_setPathAttr:function(_2e){
var d=new dojo.Deferred();
this._selectNode(null);
if(!_2e||!_2e.length){
d.resolve(true);
return d;
}
this._loadDeferred.addCallback(dojo.hitch(this,function(){
if(!this.rootNode){
d.reject(new Error("!this.rootNode"));
return;
}
if(_2e[0]!==this.rootNode.item&&(dojo.isString(_2e[0])&&_2e[0]!=this.model.getIdentity(this.rootNode.item))){
d.reject(new Error(this.id+":path[0] doesn't match this.rootNode.item.  Maybe you are using the wrong tree."));
return;
}
_2e.shift();
var _2f=this.rootNode;
function _30(){
var _31=_2e.shift(),_32=dojo.isString(_31)?_31:this.model.getIdentity(_31);
dojo.some(this._itemNodesMap[_32],function(n){
if(n.getParent()==_2f){
_2f=n;
return true;
}
return false;
});
if(_2e.length){
this._expandNode(_2f).addCallback(dojo.hitch(this,_30));
}else{
this._selectNode(_2f);
d.resolve(true);
}
};
this._expandNode(_2f).addCallback(dojo.hitch(this,_30));
}));
return d;
},_getPathAttr:function(){
if(!this.selectedNode){
return;
}
var res=[];
var _33=this.selectedNode;
while(_33&&_33!==this.rootNode){
res.unshift(_33.item);
_33=_33.getParent();
}
res.unshift(this.rootNode.item);
return res;
},mayHaveChildren:function(_34){
},getItemChildren:function(_35,_36){
},getLabel:function(_37){
return this.model.getLabel(_37);
},getIconClass:function(_38,_39){
return (!_38||this.model.mayHaveChildren(_38))?(_39?"dijitFolderOpened":"dijitFolderClosed"):"dijitLeaf";
},getLabelClass:function(_3a,_3b){
},getRowClass:function(_3c,_3d){
},getIconStyle:function(_3e,_3f){
},getLabelStyle:function(_40,_41){
},getRowStyle:function(_42,_43){
},getTooltip:function(_44){
return "";
},_onKeyPress:function(e){
if(e.altKey){
return;
}
var dk=dojo.keys;
var _45=dijit.getEnclosingWidget(e.target);
if(!_45){
return;
}
var key=e.charOrCode;
if(typeof key=="string"){
if(!e.altKey&&!e.ctrlKey&&!e.shiftKey&&!e.metaKey){
this._onLetterKeyNav({node:_45,key:key.toLowerCase()});
dojo.stopEvent(e);
}
}else{
if(this._curSearch){
clearTimeout(this._curSearch.timer);
delete this._curSearch;
}
var map=this._keyHandlerMap;
if(!map){
map={};
map[dk.ENTER]="_onEnterKey";
map[this.isLeftToRight()?dk.LEFT_ARROW:dk.RIGHT_ARROW]="_onLeftArrow";
map[this.isLeftToRight()?dk.RIGHT_ARROW:dk.LEFT_ARROW]="_onRightArrow";
map[dk.UP_ARROW]="_onUpArrow";
map[dk.DOWN_ARROW]="_onDownArrow";
map[dk.HOME]="_onHomeKey";
map[dk.END]="_onEndKey";
this._keyHandlerMap=map;
}
if(this._keyHandlerMap[key]){
this[this._keyHandlerMap[key]]({node:_45,item:_45.item,evt:e});
dojo.stopEvent(e);
}
}
},_onEnterKey:function(_46,evt){
this._publish("execute",{item:_46.item,node:_46.node});
this._selectNode(_46.node);
this.onClick(_46.item,_46.node,evt);
},_onDownArrow:function(_47){
var _48=this._getNextNode(_47.node);
if(_48&&_48.isTreeNode){
this.focusNode(_48);
}
},_onUpArrow:function(_49){
var _4a=_49.node;
var _4b=_4a.getPreviousSibling();
if(_4b){
_4a=_4b;
while(_4a.isExpandable&&_4a.isExpanded&&_4a.hasChildren()){
var _4c=_4a.getChildren();
_4a=_4c[_4c.length-1];
}
}else{
var _4d=_4a.getParent();
if(!(!this.showRoot&&_4d===this.rootNode)){
_4a=_4d;
}
}
if(_4a&&_4a.isTreeNode){
this.focusNode(_4a);
}
},_onRightArrow:function(_4e){
var _4f=_4e.node;
if(_4f.isExpandable&&!_4f.isExpanded){
this._expandNode(_4f);
}else{
if(_4f.hasChildren()){
_4f=_4f.getChildren()[0];
if(_4f&&_4f.isTreeNode){
this.focusNode(_4f);
}
}
}
},_onLeftArrow:function(_50){
var _51=_50.node;
if(_51.isExpandable&&_51.isExpanded){
this._collapseNode(_51);
}else{
var _52=_51.getParent();
if(_52&&_52.isTreeNode&&!(!this.showRoot&&_52===this.rootNode)){
this.focusNode(_52);
}
}
},_onHomeKey:function(){
var _53=this._getRootOrFirstNode();
if(_53){
this.focusNode(_53);
}
},_onEndKey:function(_54){
var _55=this.rootNode;
while(_55.isExpanded){
var c=_55.getChildren();
_55=c[c.length-1];
}
if(_55&&_55.isTreeNode){
this.focusNode(_55);
}
},multiCharSearchDuration:250,_onLetterKeyNav:function(_56){
var cs=this._curSearch;
if(cs){
cs.pattern=cs.pattern+_56.key;
clearTimeout(cs.timer);
}else{
cs=this._curSearch={pattern:_56.key,startNode:_56.node};
}
var _57=this;
cs.timer=setTimeout(function(){
delete _57._curSearch;
},this.multiCharSearchDuration);
var _58=cs.startNode;
do{
_58=this._getNextNode(_58);
if(!_58){
_58=this._getRootOrFirstNode();
}
}while(_58!==cs.startNode&&(_58.label.toLowerCase().substr(0,cs.pattern.length)!=cs.pattern));
if(_58&&_58.isTreeNode){
if(_58!==cs.startNode){
this.focusNode(_58);
}
}
},_onClick:function(_59,e){
var _5a=e.target,_5b=(_5a==_59.expandoNode||_5a==_59.expandoNodeText);
if((this.openOnClick&&_59.isExpandable)||_5b){
if(_59.isExpandable){
this._onExpandoClick({node:_59});
}
}else{
this._publish("execute",{item:_59.item,node:_59,evt:e});
this.onClick(_59.item,_59,e);
this.focusNode(_59);
}
if(!_5b){
this._selectNode(_59);
}
dojo.stopEvent(e);
},_onDblClick:function(_5c,e){
var _5d=e.target,_5e=(_5d==_5c.expandoNode||_5d==_5c.expandoNodeText);
if((this.openOnDblClick&&_5c.isExpandable)||_5e){
if(_5c.isExpandable){
this._onExpandoClick({node:_5c});
}
}else{
this._publish("execute",{item:_5c.item,node:_5c,evt:e});
this.onDblClick(_5c.item,_5c,e);
this.focusNode(_5c);
}
if(!_5e){
this._selectNode(_5c);
}
dojo.stopEvent(e);
},_onExpandoClick:function(_5f){
var _60=_5f.node;
this.focusNode(_60);
if(_60.isExpanded){
this._collapseNode(_60);
}else{
this._expandNode(_60);
}
},onClick:function(_61,_62,evt){
},onDblClick:function(_63,_64,evt){
},onOpen:function(_65,_66){
},onClose:function(_67,_68){
},_getNextNode:function(_69){
if(_69.isExpandable&&_69.isExpanded&&_69.hasChildren()){
return _69.getChildren()[0];
}else{
while(_69&&_69.isTreeNode){
var _6a=_69.getNextSibling();
if(_6a){
return _6a;
}
_69=_69.getParent();
}
return null;
}
},_getRootOrFirstNode:function(){
return this.showRoot?this.rootNode:this.rootNode.getChildren()[0];
},_collapseNode:function(_6b){
if(_6b._expandNodeDeferred){
delete _6b._expandNodeDeferred;
}
if(_6b.isExpandable){
if(_6b.state=="LOADING"){
return;
}
_6b.collapse();
this.onClose(_6b.item,_6b);
if(_6b.item){
this._state(_6b.item,false);
this._saveState();
}
}
},_expandNode:function(_6c,_6d){
if(_6c._expandNodeDeferred&&!_6d){
return _6c._expandNodeDeferred;
}
var _6e=this.model,_6f=_6c.item,_70=this;
switch(_6c.state){
case "UNCHECKED":
_6c.markProcessing();
var def=(_6c._expandNodeDeferred=new dojo.Deferred());
_6e.getChildren(_6f,function(_71){
_6c.unmarkProcessing();
var _72=_6c.setChildItems(_71);
var ed=_70._expandNode(_6c,true);
_72.addCallback(function(){
ed.addCallback(function(){
def.callback();
});
});
},function(err){
console.error(_70,": error loading root children: ",err);
});
break;
default:
def=(_6c._expandNodeDeferred=_6c.expand());
this.onOpen(_6c.item,_6c);
if(_6f){
this._state(_6f,true);
this._saveState();
}
}
return def;
},focusNode:function(_73){
dijit.focus(_73.labelNode);
},_selectNode:function(_74){
if(this.selectedNode&&!this.selectedNode._destroyed){
this.selectedNode.setSelected(false);
}
if(_74){
_74.setSelected(true);
}
this.selectedNode=_74;
},_onNodeFocus:function(_75){
if(_75&&_75!=this.lastFocused){
if(this.lastFocused&&!this.lastFocused._destroyed){
this.lastFocused.setFocusable(false);
}
_75.setFocusable(true);
this.lastFocused=_75;
}
},_onNodeMouseEnter:function(_76){
},_onNodeMouseLeave:function(_77){
},_onItemChange:function(_78){
var _79=this.model,_7a=_79.getIdentity(_78),_7b=this._itemNodesMap[_7a];
if(_7b){
var _7c=this.getLabel(_78),_7d=this.getTooltip(_78);
dojo.forEach(_7b,function(_7e){
_7e.set({item:_78,label:_7c,tooltip:_7d});
_7e._updateItemClasses(_78);
});
}
},_onItemChildrenChange:function(_7f,_80){
var _81=this.model,_82=_81.getIdentity(_7f),_83=this._itemNodesMap[_82];
if(_83){
dojo.forEach(_83,function(_84){
_84.setChildItems(_80);
});
}
},_onItemDelete:function(_85){
var _86=this.model,_87=_86.getIdentity(_85),_88=this._itemNodesMap[_87];
if(_88){
dojo.forEach(_88,function(_89){
var _8a=_89.getParent();
if(_8a){
_8a.removeChild(_89);
}
_89.destroyRecursive();
});
delete this._itemNodesMap[_87];
}
},_initState:function(){
if(this.persist){
var _8b=dojo.cookie(this.cookieName);
this._openedItemIds={};
if(_8b){
dojo.forEach(_8b.split(","),function(_8c){
this._openedItemIds[_8c]=true;
},this);
}
}
},_state:function(_8d,_8e){
if(!this.persist){
return false;
}
var id=this.model.getIdentity(_8d);
if(arguments.length===1){
return this._openedItemIds[id];
}
if(_8e){
this._openedItemIds[id]=true;
}else{
delete this._openedItemIds[id];
}
},_saveState:function(){
if(!this.persist){
return;
}
var ary=[];
for(var id in this._openedItemIds){
ary.push(id);
}
dojo.cookie(this.cookieName,ary.join(","),{expires:365});
},destroy:function(){
if(this._curSearch){
clearTimeout(this._curSearch.timer);
delete this._curSearch;
}
if(this.rootNode){
this.rootNode.destroyRecursive();
}
if(this.dndController&&!dojo.isString(this.dndController)){
this.dndController.destroy();
}
this.rootNode=null;
this.inherited(arguments);
},destroyRecursive:function(){
this.destroy();
},resize:function(_8f){
if(_8f){
dojo.marginBox(this.domNode,_8f);
dojo.style(this.domNode,"overflow","auto");
}
this._nodePixelIndent=dojo.marginBox(this.tree.indentDetector).w;
if(this.tree.rootNode){
this.tree.rootNode.set("indent",this.showRoot?0:-1);
}
},_createTreeNode:function(_90){
return new dijit._TreeNode(_90);
}});
dojo.require("dijit.tree.TreeStoreModel");
dojo.require("dijit.tree.ForestStoreModel");
}
