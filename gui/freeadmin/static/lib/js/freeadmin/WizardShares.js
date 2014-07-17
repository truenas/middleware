define([
  "dojo/_base/declare",
  "dojo/data/ObjectStore",
  "dojo/dom-attr",
  "dojo/dom-style",
  "dojo/on",
  "dojo/request/xhr",
  "dojo/store/Memory",
  "dijit/_Widget",
  "dijit/_TemplatedMixin",
  "dijit/form/CheckBox",
  "dijit/form/TextBox",
  "dijit/form/Button",
  "dijit/form/RadioButton",
  "dijit/form/MultiSelect",
  "dijit/layout/TabContainer",
  "dijit/layout/ContentPane",
  "dgrid/OnDemandGrid",
  "dgrid/Selection",
  "dojox/timing",
  "dojox/string/sprintf",
  "dojo/text!freeadmin/templates/wizardshares.html"
  ], function(
  declare,
  ObjectStore,
  domAttr,
  domStyle,
  on,
  xhr,
  Memory,
  _Widget,
  _Templated,
  CheckBox,
  TextBox,
  Button,
  RadioButton,
  MultiSelect,
  TabContainer,
  ContentPane,
  OnDemandGrid,
  Selection,
  timing,
  sprintf,
  template) {

  var WizardShares = declare("freeadmin.WizardShares", [ _Widget, _Templated ], {
    templateString : template,
    postCreate: function() {
      var me = this;

      me.dapShareNameLabel.innerHTML = gettext("Share name") + ":";

      me._shareName = new TextBox({
        name: "sharename"
      }, me.dapShareName);

      me._shareCIFS = new RadioButton({}, me.dapShareCIFS);
      me._shareAFP = new RadioButton({}, me.dapShareAFP);
      me._shareNFS = new RadioButton({}, me.dapShareNFS);

      me._shareGuest = new CheckBox({}, me.dapShareGuest);

      me._shareAdd = new Button({
        label: gettext("Add")
      }, me.dapShareAdd);
      on(me._shareAdd, "click", function() {
        me.add();
      });

      me._shareDelete = new Button({
        label: gettext("Delete"),
        disabled: true
      }, me.dapShareDelete);
      on(me._shareDelete, "click", function() {
        for(var id in me._sharesList.selection) {
          if(me._sharesList.selection[id]) {
            var row = me._sharesList.row(id);
            me.remove(row.id);
          }
        }
      });

      me._shareUpdate = new Button({
        label: gettext("Update"),
        disabled: true
      }, me.dapShareUpdate);
      on(me._shareUpdate, "click", function() {
        me.add();
      });

      me._store = new Memory({
          idProperty: "name",
          data: []
      });

      me._sharesList = new (declare([OnDemandGrid, Selection]))({
        store: me._store,
        selectionMode: "single",
        columns: {
          name: "Name"
        },
        className: "dgrid-wizardshare"
      }, me.dapSharesList);

      me._sharesList.on("dgrid-select", function(event) {
        me._shareDelete.set('disabled', false);
        me._shareUpdate.set('disabled', false);

        for(var id in me._sharesList.selection) {
          if(me._sharesList.selection[id])
            me.select(id);
        }
      });

      this.inherited(arguments);

    },
    add: function() {
      var me = this;
      var purpose;
      if(me._shareCIFS.get('value')) purpose = 'cifs';
      else if(me._shareAFP.get('value')) purpose = 'afp';
      else if(me._shareNFS.get('value')) purpose = 'nfs';
      me._store.put({
        name: me._shareName.get("value"),
        purpose: purpose,
        allowguest: me._shareGuest.get('value')
      });
      me._sharesList.refresh();
    },
    remove: function(id) {
      var me = this;
      me._store.remove(id);
      me._sharesList.refresh();
      if(Object.keys(me._sharesList.selection).length == 0) {
        me._shareDelete.set('disabled', true);
        me._shareUpdate.set('disabled', true);
      }
    },
    select: function(id) {
      var me = this;
      var data = me._store.get(id);
      me._shareName.set('value', data.name);
      me._shareGuest.set('value', data.allowguest);
      switch(data.purpose) {
        case 'cifs':
          me._shareCIFS.set('value', true);
          me._shareAFP.set('value', false);
          me._shareNFS.set('value', false);
          break;
        case 'afp':
          me._shareCIFS.set('value', false);
          me._shareAFP.set('value', true);
          me._shareNFS.set('value', false);
          break;
        case 'nfs':
          me._shareCIFS.set('value', false);
          me._shareAFP.set('value', false);
          me._shareNFS.set('value', true);
          break;
      }
    }
  });
  return WizardShares;
});
