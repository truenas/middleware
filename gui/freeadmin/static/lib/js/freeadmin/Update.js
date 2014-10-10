define([
  "dojo/_base/declare",
  "dojo/data/ItemFileReadStore",
  "dojo/data/ObjectStore",
  "dojo/dom",
  "dojo/dom-attr",
  "dojo/dom-construct",
  "dojo/dom-style",
  "dojo/json",
  "dojo/on",
  "dojo/query",
  "dojo/request/xhr",
  "dojo/store/Memory",
  "dijit/_Widget",
  "dijit/_TemplatedMixin",
  "dijit/form/CheckBox",
  "dijit/form/ComboBox",
  "dijit/form/TextBox",
  "dijit/form/Button",
  "dijit/form/RadioButton",
  "dijit/form/Select",
  "dijit/form/ValidationTextBox",
  "dijit/layout/TabContainer",
  "dijit/layout/ContentPane",
  "dgrid/OnDemandGrid",
  "dgrid/Selection",
  "dojox/timing",
  "dojox/string/sprintf",
  "dojo/text!freeadmin/templates/update.html",
  "freeadmin/form/UnixPerm"
  ], function(
  declare,
  ItemFileReadStore,
  ObjectStore,
  dom,
  domAttr,
  domConstruct,
  domStyle,
  json,
  on,
  query,
  xhr,
  Memory,
  _Widget,
  _Templated,
  CheckBox,
  ComboBox,
  TextBox,
  Button,
  RadioButton,
  Select,
  ValidationTextBox,
  TabContainer,
  ContentPane,
  OnDemandGrid,
  Selection,
  timing,
  sprintf,
  template,
  UnixPerm) {

  var Update = declare("freeadmin.Update", [ _Widget, _Templated ], {
    templateString : template,
    initial: {},
    postCreate: function() {
      var me = this;

      me._autoCheck = new CheckBox({

      }, me.dapAutoCheck);

      me._checkUpdate = new Button({
        label: gettext("Check For Updates")
      }, me.dapCheckUpdateBtn);

      me._applyPending = new Button({
        label: gettext("Apply Pending Updates"),
        disabled: true
      }, me.dapApplyPendintBtn);

      me._applyPending = new Select({
      }, me.dapSelectTrain);

      me._store = new Memory({
          idProperty: "name",
          data: []
      });

      me._updatesGrid = new (declare([OnDemandGrid, Selection]))({
        store: me._store,
        selectionMode: "single",
        columns: {
          name: "Name"
        },
        className: "dgrid-wizardshare"
      }, me.dapUpdateGrid);

      this.inherited(arguments);

    }
  });
  return Update;
});
