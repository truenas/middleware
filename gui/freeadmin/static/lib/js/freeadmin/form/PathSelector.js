define([
    "dojo/_base/declare",
    "dojo/dom-style",
    "dijit/_Widget",
    "dijit/_TemplatedMixin",
    "dijit/form/TextBox",
    "dijit/form/Button",
    "dijit/layout/TabContainer",
    "dijit/layout/ContentPane",
    "dojo/text!freeadmin/templates/pathselector.html",
    "freeadmin/tree/JsonRestStore",
    "freeadmin/tree/ForestStoreModel",
    "freeadmin/tree/TreeLazy"
    ], function(declare, domStyle, _Widget, _Templated, TextBox, Button, TabContainer, ContentPane, template, JsonRestStore, ForestStoreModel, TreeLazy) {

    var PathSelector = declare("freeadmin.form.PathSelector", [ _Widget, _Templated ], {
        templateString : template,
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
        postCreate: function() {

            var path = this;
            if(!gettext) {
                gettext = function(s) { return s; }
            }
            var target;

            if (document.getElementById('dirsonly') !== null)
                this.dirsonly = document.getElementById('dirsonly').value;

            if(this.dirsonly == true) {
                target = '/system/lsdir/';
            } else {
                target = '/system/lsfiles/';
            }

            var store = new JsonRestStore({
                target: target,
                labelAttribute: 'name',
                allowNoTrailingSlash: true
            });

            var model = new ForestStoreModel({
                store: store,
                query: {root: this.root},
                rootId: 'items',
                rootLabel: this.root,
                childrenAttrs: ['children'],
                deferItemLoadingUntilExpand: true
            });

            this.tree = new TreeLazy({
                model: model,
                persist: false,
                style: "height: 250px;",
                onClick: function(obj, node, ev) {
                    if(node.item.path) {
                        path.textfield.set('value', node.item.path);
                    } else if(node.item.root) {
                        path.textfield.set('value', '/');
                    } else {
                        path.textfield.set('value', node.get('label'));
                    }
                }
            }, this.treeNode);

            this.textfield = new TextBox({
                id: path.name + "_textBox",
                value: path.value,
                name: path.name,
            }, this.pathField);

            browse = new Button({
                id: path.name + "_openClose",
                label: gettext('Browse'),
                onClick: function() {
                    var dialog = getDialog(path);
                    if(this.get('label') == gettext('Close')) {
                        domStyle.set(path.treeContainer, 'display', 'none');
                        this.set('label', gettext('Browse'));
                    } else {
                        domStyle.set(path.treeContainer, 'display', 'block');
                        this.set('label', gettext('Close'));
                    }
                    if(dialog) {
                        //dialog.layout();
                        dialog._size();
                        dialog._position();
                    }
                },
            }, this.pathButton);

            this._supportingWidgets.push(browse);
            this._supportingWidgets.push(this.textfield);
            this._supportingWidgets.push(this.tree);
            this._supportingWidgets.push(model);
            this._supportingWidgets.push(store);

            this.inherited(arguments);

        }
    });
    return PathSelector;
});
