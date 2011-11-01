define(["dojox/data/JsonRestStore", "dojo/_base/declare"], function(JsonRestStore, declare) {

    var MyStore = declare("freeadmin.tree.JsonRestStore", [dojox.data.JsonRestStore], {
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
    return MyStore;
});
