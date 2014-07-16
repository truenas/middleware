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
  "dijit/form/TextBox",
  "dijit/form/Button",
  "dijit/form/RadioButton",
  "dijit/form/Select",
  "dijit/layout/TabContainer",
  "dijit/layout/ContentPane",
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
  TextBox,
  Button,
  RadioButton,
  Select,
  TabContainer,
  ContentPane,
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

      me._shareSMB = new RadioButton({}, me.dapShareSMB);
      me._shareAFP = new RadioButton({}, me.dapShareAFP);
      me._shareNFS = new RadioButton({}, me.dapShareNFS);

      me._shareAdd = new Button({
        label: gettext("Add")
      }, me.dapShareAdd);
      on(me._shareAdd, "click", function() {
        console.log("click add");
        me.add();
      });

      me._shareDelete = new Button({
        label: gettext("Delete")
      }, me.dapShareDelete);
      me._shareDelete = new Button({
        label: gettext("Update")
      }, me.dapShareUpdate);

      me._memory = new Memory({
          idProperty: "name",
          data: []
      });

      me._store = new ObjectStore({objectStore: me._memory});

      me._sharesList = new Select({
        store: me._store,
        style: "width: 350px;"
      }, me.dapSharesList);

      this.inherited(arguments);

    },
    add: function() {
      var me = this;
      me._memory.put({
        name: me._shareName.get("value"),
        label: me._shareName.get("value")
      });
      me._sharesList.setStore(me._store);
    }
  });
  return WizardShares;
});
