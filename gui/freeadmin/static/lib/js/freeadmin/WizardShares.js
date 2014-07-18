define([
  "dojo/_base/declare",
  "dojo/data/ObjectStore",
  "dojo/dom",
  "dojo/dom-attr",
  "dojo/dom-construct",
  "dojo/dom-style",
  "dojo/json",
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
  "dijit/form/ValidationTextBox",
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
  dom,
  domAttr,
  domConstruct,
  domStyle,
  json,
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
  ValidationTextBox,
  TabContainer,
  ContentPane,
  OnDemandGrid,
  Selection,
  timing,
  sprintf,
  template) {

  var WizardShares = declare("freeadmin.WizardShares", [ _Widget, _Templated ], {
    templateString : template,
    initial: "[]",
    postCreate: function() {
      var me = this;

      me.dapShareNameLabel.innerHTML = gettext("Share name") + ":";

      me._shareName = new ValidationTextBox({
        name: "sharename",
        required: true,
        pattern: "[a-zA-Z0-9_\\-\\.]+",
        invalidMessage: gettext('This field may only contain alphanumeric and the following characters: "_", "-", ".".')
      }, me.dapShareName);

      me._shareCIFS = new RadioButton({checked: true}, me.dapShareCIFS);
      me._shareAFP = new RadioButton({}, me.dapShareAFP);
      me._shareNFS = new RadioButton({}, me.dapShareNFS);

      me._shareAFP_TM = new CheckBox({}, me.dapShareAFP_TM);
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
          data: json.parse(me.initial)
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
        me._shareDelete.set("disabled", false);
        me._shareUpdate.set("disabled", false);

        for(var id in me._sharesList.selection) {
          if(me._sharesList.selection[id])
            me.select(id);
        }
      });

      me.dump();

      this.inherited(arguments);

    },
    add: function() {
      var me = this;
      var purpose;

      if(!me.isValid()) return;

      if(me._shareCIFS.get("value")) purpose = "cifs";
      else if(me._shareAFP.get("value")) purpose = "afp";
      else if(me._shareNFS.get("value")) purpose = "nfs";
      me._store.put({
        name: me._shareName.get("value"),
        purpose: purpose,
        allowguest: me._shareGuest.get("value"),
        timemachine: me._shareAFP_TM.get("value")
      });
      me._sharesList.refresh();
      me.dump();
    },
    remove: function(id) {
      var me = this;
      me._store.remove(id);
      me._sharesList.refresh();
      if(Object.keys(me._sharesList.selection).length == 0) {
        me._shareDelete.set("disabled", true);
        me._shareUpdate.set("disabled", true);
      }
      me.dump();
    },
    select: function(id) {
      var me = this;
      var data = me._store.get(id);
      me._shareName.set("value", data.name);
      me._shareGuest.set("value", data.allowguest);
      me._shareAFP_TM.set("value", data.timemachine);
      switch(data.purpose) {
        case "cifs":
          me._shareCIFS.set("value", true);
          me._shareAFP.set("value", false);
          me._shareNFS.set("value", false);
          break;
        case "afp":
          me._shareCIFS.set("value", false);
          me._shareAFP.set("value", true);
          me._shareNFS.set("value", false);
          break;
        case "nfs":
          me._shareCIFS.set("value", false);
          me._shareAFP.set("value", false);
          me._shareNFS.set("value", true);
          break;
      }
    },
    isValid: function() {
      var me = this;
      var valid = true;
      if(!me._shareName.isValid()) {
        me._shareName.focus();
        valid = false;
      }
      return valid;
    },
    dump: function() {
      var me = this;
      var dumpNode = dom.byId(me.id + "_dump");

      var total = 0;
      if(dumpNode) {
        domConstruct.empty(dumpNode);
      } else {
        dumpNode = domConstruct.create("div", {id: me.id + "_dump"}, me.domNode.parentNode);
      }

      me._store.query({}).forEach(function(obj, idx) {

        new TextBox({
          name: "shares-" + idx + "-share_name",
        type: "hidden",
          value: obj.name
        }).placeAt(dumpNode);

        new TextBox({
          name: "shares-" + idx + "-share_purpose",
        type: "hidden",
          value: obj.purpose
        }).placeAt(dumpNode);

        new TextBox({
          name: "shares-" + idx + "-share_allowguest",
        type: "hidden",
          value: obj.allowguest
        }).placeAt(dumpNode);

        new TextBox({
          name: "shares-" + idx + "-share_timemachine",
        type: "hidden",
          value: obj.timemachine
        }).placeAt(dumpNode);

        total++;

      });

      new TextBox({
        name: "shares-TOTAL_FORMS",
        type: "hidden",
        value: total
      }).placeAt(dumpNode);

      new TextBox({
        name: "shares-INITIAL_FORMS",
        type: "hidden",
        value: "0"
      }).placeAt(dumpNode);

    }
  });
  return WizardShares;
});
