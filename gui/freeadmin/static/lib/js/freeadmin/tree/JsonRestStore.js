define(["dojox/data/JsonRestStore", "dojo/_base/declare"], function(JsonRestStore, declare) {

    var MyStore = declare("freeadmin.tree.JsonRestStore", [JsonRestStore], {
        loadItem: function(args) {
            if(args.item.id.indexOf("?") >= 0) {
                args.item.__id = args.item.__id + '&preventCache=' + new Date().getTime();
            } else {
                args.item.__id = args.item.__id + '?preventCache=' + new Date().getTime();
            }
            //args.item.__id = args.item.__id + '&test=11';
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
        }
    });
    return MyStore;
});
