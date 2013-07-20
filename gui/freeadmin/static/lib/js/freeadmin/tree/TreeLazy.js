define(["dijit/Tree","dojo/_base/declare"], function(Tree, declare) {

    var TreeLazy = declare("freeadmin.tree.TreeLazy", [Tree], {
        _collapseNode: function(node, recursive){
            if(node._collapseNodeDeferred && !recursive){
                 return node._collapseNodeDeferred;    // dojo.Deferred
            }
            /*
             * Force the node to be checked again if collapsed
             */
            node.state = "NotLoaded";
            node._loadDeferred = null;
            return this.inherited(arguments);
        },
        reload: function () {

            this.model.store.close();
            path = this.get('path');

            if (this.rootNode) {
                this.rootNode.destroyRecursive();
            }

            this.rootNode.state = "NotLoaded";

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
    return TreeLazy;
});
