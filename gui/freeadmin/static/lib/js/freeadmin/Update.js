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

      var autochecked;
      if(me.initial.autoCheck !== undefined) {
        autochecked = me.initial.autoCheck;
      } else {
        autochecked = false;
      }

      me._autoCheck = new CheckBox({
        checked: autochecked
      }, me.dapAutoCheck);

      me.dapCurrentTrain.innerHTML = me.initial.currentTrain;

      me._checkUpdate = new Button({
        label: gettext("Check For Updates")
      }, me.dapCheckUpdateBtn);

      me._applyPending = new Button({
        label: gettext("Apply Pending Updates"),
        disabled: true
      }, me.dapApplyPendintBtn);

      var options = [];

      for(var i in me.initial.trains) {
        var name = me.initial.trains[i];
        var entry = {label: name, value: name};
        if(name == me.initial.currentTrain) entry['selected'] = true;
        options.push(entry);
      }

      me._applyPending = new Select({
        options: options
      }, me.dapSelectTrain);

      on(me._applyPending, "change", function(val) {
        me.update(val);
      });

      me._updatesGrid = new (declare([OnDemandGrid, Selection]))({
        selectionMode: "single",
        columns: {
          name: "Name"
        },
        className: "dgrid-wizardshare"
      }, me.dapUpdateGrid);

      me.update(me.initial.currentTrain);

      this.inherited(arguments);

    },
    update: function(train) {

      var me = this;
      xhr.get("/api/v1.0/system/update/check/?format=json", {
        handleAs: "json",
        headers: {
          'Content-Type': 'application/json'
        },
        query: {train: train}
      }).then(function(results) {
        var newstore = new Memory({data: results});
        me._updatesGrid.set('store', newstore);
        me._updatesGrid.refresh();
      }, function(err) {
        me._updatesGrid.set('store', null);
        me._updatesGrid.refresh();
      });

    }
  });
  return Update;
});
