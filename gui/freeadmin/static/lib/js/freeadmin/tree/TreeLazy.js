define(["dijit/Tree","dojo/_base/declare"], function(Tree, declare) {

    var TreeLazy = declare("freeadmin.tree.TreeLazy", [Tree], {
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
    return TreeLazy;
});
