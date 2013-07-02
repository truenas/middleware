define([
    "dijit/Tree",
    "dijit/registry",
    "dojo/_base/declare",
    "dojo/_base/array",
    "dojo/_base/Deferred",
    "dojo/_base/lang"
    ], function(Tree, registry, declare, array, Deferred, lang) {

    var MyTree = declare("freeadmin.tree.Tree", [Tree], {
        _createTreeNode: function(/*Object*/ args){
          /*
           * This is an override to set a custom ID for the tree node
           */
          //return new TreeNode(args);
          if(args.item.gname) {
            var myId = "treeNode_" + args.item.gname;
            while(registry.byId(myId)) {
              console.warn("The id already exists:", myId);
              myId = myId + "_";
            }
            args['id'] = myId;
          }
          return this.inherited(arguments);

        },
        _expandNode: function( node, recursive){
            if(node._expandNodeDeferred && !recursive){
                return node._expandNodeDeferred;    // dojo.Deferred
            }

            //item = node.item;
            //alert("doing ya");
            //if (item._loadObject && !node._loadObjectFunction) {
            //    node._loadObjectFunction = item._loadObject;
            //}

            return this.inherited(arguments);

        },
        reload: function () {

            this.model.store.close();
            path = this.get('path');

            if (this.rootNode) {
                this.rootNode.destroyRecursive();
            }

            this.rootNode.state = "UNCHECKED";

            storeTarget = this.model.store.target;
            for (var idx in dojox.rpc.Rest._index) {
                if (idx.match("^" + storeTarget)) {
                    delete dojox.rpc.Rest._index[idx];
                }
            }

            this.model.constructor(this.model);

            this.postMixInProperties();
            this._load();
            if(path && path.length > 0) {
                this.set('path', path).then(
                        lang.hitch(this, function() {
                            this.focusNode(this.get('selectedNode'));
                        }
                ));
            }
            this.onLoad();

        }
    });
    return MyTree;

});
