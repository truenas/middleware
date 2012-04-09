define([
    "dojo/_base/declare",
    "dojo/cache",
    "dijit/_Widget",
    "dijit/_TemplatedMixin",
    "dijit/form/TextBox",
    "dijit/form/Button",
    "dijit/layout/TabContainer",
    "dijit/layout/ContentPane",
    "dojox/string/sprintf",
    ], function(declare, cache, _Widget, _Templated, TextBox, Button, TabContainer, ContentPane) {

    var PathSelector = declare("freeadmin.form.PathSelector", [ _Widget, _Templated ], {
        templateString : cache("freeadmin", "templates/pathselector.html"),
        name : "",
        value: "",
        root: "/",
        dirsonly: true,
        textfield: null,
        _getValueAttr: function() {
            if(this.textfield) {
                return this.textfield.get('value');
            }
            return this.value;
        },
        postCreate : function() {

            var path = this;
            var target;
            if(this.dirsonly) {
                target = '/system/lsdir/';
            } else {
                target = '/system/lsfiles/';
            }

            var store = new freeadmin.tree.JsonRestStore({
                target: target,
                labelAttribute: 'name',
                allowNoTrailingSlash: true,
            });

            var model = new freeadmin.tree.ForestStoreModel({
                store: store,
                query: {root: this.root},
                rootId: 'items',
                rootLabel: this.root,
                childrenAttrs: ['children'],
                deferItemLoadingUntilExpand: true,
            });

            var tree = new freeadmin.tree.TreeLazy({
                model: model,
                persist: false,
                style: "height: 250px;",
                onClick: function(obj, node, ev) {
                    if(node.item.path) {
                        path.textfield.set('value', node.item.path);
                    } else {
                        path.textfield.set('value', node.get('label'));
                    }
                }
            }, this.treeNode);

            this.textfield = new TextBox({
                value: path.value,
                name: path.name,
            }, this.pathField);

            var browse = new Button({
                label: 'Browse',
                onClick: function() {
                    var dialog = getDialog(path);
                    if(this.get('label') == 'Close') {
                        dojo.style(path.treeContainer, 'display', 'none');
                        this.set('label', 'Browse');
                    } else {
                        dojo.style(path.treeContainer, 'display', 'block');
                        this.set('label', 'Close');
                    }
                    if(dialog) {
                        dialog.layout();
                    }
                },
            }, this.pathButton);

        }
    });
    return PathSelector;
});
