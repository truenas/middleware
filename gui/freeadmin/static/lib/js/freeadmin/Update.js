define([
  "dojo/_base/declare",
  "dojo/_base/lang",
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
  "dijit/_base/manager",
  "dijit/_Widget",
  "dijit/_TemplatedMixin",
  "dijit/Dialog",
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
  lang,
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
  manager,
  _Widget,
  _Templated,
  Dialog,
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
    manualUrl: "",
    updateUrl: "",
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

      on(me._autoCheck, "change", function(val) {

        xhr.post(me.updateUrl, {
          handleAs: "json",
          headers: {"X-CSRFToken": CSRFToken},
          data: {autocheck: val}
        }).then(function(data) {
          if(data) {

          } else {

          }
        }, function(error) {

        });
      });

      me.dapCurrentTrain.innerHTML = me.initial.currentTrain;

      me._manualUpdate = new Button({
        label: gettext("Manual Update"),
        onClick: function() {
          editObject(gettext("Manual Update"), me.manualUrl, [me.domNode]);
        }
      }, me.dapManualUpdate);

      me._checkUpdate = new Button({
        label: gettext("Check For Updates")
      }, me.dapCheckUpdateBtn);

      on(me._checkUpdate, "click", function() {
        me.update(me._selectTrain.get("value"));
      });

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

      me._selectTrain = new Select({
        options: options,
      }, me.dapSelectTrain);
      me._selectTrain.set('oldvalue', me.initial.currentTrain);

      on(me._selectTrain, "change", function(val) {

        if(me._selectTrain.get('internalchange') === true) {
          me._selectTrain.set('internalchange', false);
          return;
        }

        var confirmDialog;

        var ok = new Button({
          label: gettext("Yes"),
          onClick: function() {
            confirmDialog.hide();
            me._selectTrain.set('oldvalue', val);
            me.update(val);
          }
        });

        var cancel = new Button({
          label: gettext("No"),
          onClick: function() {
            me._selectTrain.set('internalchange', true);
            me._selectTrain.set('value', me._selectTrain.get('oldvalue'));
            confirmDialog.hide();
          }
        });

        confirmDialog = new Dialog({
          title: gettext("Confirm"),
          style: "background-color: white;",
          content: "Are you sure you want to change trains?",
          onHide: function() {
            ok.destroy();
            cancel.destroy();
            setTimeout(lang.hitch(this, 'destroyRecursive'), manager.defaultDuration);
          }
        });

        confirmDialog.domNode.appendChild(ok.domNode);
        confirmDialog.domNode.appendChild(cancel.domNode);
        confirmDialog.show();

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

      me._applyPending.set('disabled', true);
      me._updatesGrid.set('store', null);
      me._updatesGrid.refresh();

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
        if(results.length > 0) {
          me._applyPending.set('disabled', false);
        } else {
          me._applyPending.set('disabled', true);
        }
      }, function(err) {
        me._updatesGrid.set('store', null);
        me._updatesGrid.refresh();
        me._applyPending.set('disabled', true);
      });

    }
  });
  return Update;
});
