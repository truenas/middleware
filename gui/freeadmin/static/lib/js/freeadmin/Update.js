define([
  "dojo/_base/declare",
  "dojo/_base/lang",
  "dojo/on",
  "dojo/request/xhr",
  "dojo/store/JsonRest",
  "dojo/store/Observable",
  "dijit/_base/manager",
  "dijit/_Widget",
  "dijit/_TemplatedMixin",
  "dijit/Dialog",
  "dijit/form/CheckBox",
  "dijit/form/Button",
  "dijit/form/Select",
  "dgrid/OnDemandGrid",
  "dgrid/Selection",
  "dojox/timing",
  "dojox/string/sprintf",
  "dojo/text!freeadmin/templates/update.html",
  ], function(
  declare,
  lang,
  on,
  xhr,
  JsonRest,
  Observable,
  manager,
  _Widget,
  _Templated,
  Dialog,
  CheckBox,
  Button,
  Select,
  OnDemandGrid,
  Selection,
  timing,
  sprintf,
  template) {

  var Update = declare("freeadmin.Update", [ _Widget, _Templated ], {
    templateString : template,
    applyUrl: "",
    checkUrl: "",
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
        label: gettext("Check Now"),
        onClick: function() {
          editObject(gettext("Check Now"), me.checkUrl, [me.domNode]);
        }
      }, me.dapCheckUpdateBtn);

      me._applyPending = new Button({
        label: gettext("Apply Pending Updates"),
        disabled: true,
        onClick: function() {
          editObject(gettext("Apply Pending Updates"), me.applyUrl, [me.domNode]);
        }
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

            xhr.post(me.updateUrl, {
              handleAs: "json",
              headers: {"X-CSRFToken": CSRFToken},
              data: {train: val}
            }).then(function(data) {
              if(data) {

              } else {

              }
            }, function(error) {

            });
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

      me._store = new Observable(new JsonRest({
        target: "/api/v1.0/system/update/check/"
      }));

      me._updatesGrid = new (declare([OnDemandGrid, Selection]))({
        selectionMode: "single",
        store: me._store,
        query: "?train=" + me.initial.currentTrain,
        columns: {
          name: "Name"
        },
        loadingMessage: gettext("Loading..."),
        noDataMessage: gettext("No pending updates have been found."),
        className: "dgrid-update"
      }, me.dapUpdateGrid);

      on(me._updatesGrid, "dgrid-refresh-complete", function(e) {
        e.results.then(function(data) {
          if(data.length > 0) {
            me._applyPending.set('disabled', false);
          } else {
            me._applyPending.set('disabled', true);
          }
        });
      });

      this.inherited(arguments);

    },
    update: function(train) {

      var me = this;
      me._applyPending.set('disabled', true);
      me._updatesGrid.set("query", "?train=" + train);

    }
  });
  return Update;
});
