dojo.provide("freeadmin.tree.TreeLazy");
dojo.provide("freeadmin.tree.ForestStoreModel");
dojo.provide("freeadmin.tree.JsonRestStore");

dojo.require("dijit.Tree");
dojo.require("dijit.tree.ForestStoreModel");
dojo.require("dojox.data.JsonRestStore");

dojo.declare("freeadmin.tree.TreeLazy", dijit.Tree, {

    _collapseNode: function( node, recursive){
        if(node._collapseNodeDeferred && !recursive){
             return node._collapseNodeDeferred;    // dojo.Deferred
        }
        /*
         * Force the node to be checked again if collapsed
         */
        node.state="UNCHECKED";
        return this.inherited(arguments);
    }
});

dojo.declare("freeadmin.tree.ForestStoreModel", dijit.tree.ForestStoreModel, {
    getChildren: function(parentItem, callback, onError){
        if(parentItem === this.root){
            if(this.root.children){
                // already loaded, just return
                callback(this.root.children);
            }else{
                this.store.fetch({
                    query: this.query,
                    queryOptions: {cache:false},
                    onComplete: dojo.hitch(this, function(items){
                        this.root.children = items;
                        callback(items);
                    }),
                    onError: onError
                });
            }
        }else{

            /*
             * This is the piece were we overwrite over the super class
             * We do this to overwrite the deferred item load,
             * {re}loading the node everytime
             */
            var store = this.store;
            store.loadItem({
                item: parentItem,
                onItem: function(parItem){
                    callback(parItem.children);
                },
                onError: onError
            });
        }
    },
});

dojo.declare("freeadmin.tree.JsonRestStore", dojox.data.JsonRestStore, {
    loadItem: function(args) {
        var item;
        var oldload = args.item._loadObject;
        if(args.item._loadObject){
            args.item._loadObject(function(result){
                item = result; // in synchronous mode this can allow loadItem to return the value
                // delete item._loadObject;
                // The magic happens here!! We always keep _loadObject to relaod the node
                item._loadObject = oldload;
                var func = result instanceof Error ? args.onError : args.onItem;
                if(func){
                    func.call(args.scope, result);
                }
            });
        }else if(args.onItem){
            args.onItem.call(args.scope, args.item);
        }
        return item;
    },
});
