define([
  "dojo/_base/declare",
  "dojo/_base/lang",
  "dojo/data/ObjectStore",
  "dojo/on",
  "dojo/request/xhr",
  "dojo/store/JsonRest",
  "dojo/store/Memory",
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
  ObjectStore,
  on,
  xhr,
  JsonRest,
  Memory,
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
    verifyUrl: "",
    updateUrl: "",
    updateServer: "",
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

      me.dapUpdateServer.innerHTML = me.updateServer;
      me.dapUpdateTrainInfoLink.setAttribute('href', me.updateServer+"/trains.txt");
      me.dapUpdateTrainInfoLink.innerHTML = gettext('Train Descriptions');

      me.dapCurrentTrain.innerHTML = gettext('Loading');
      me.dapAutoCheckText.innerHTML = gettext('Automatically check for updates');
      me.dapCurrentTrainText.innerHTML = gettext('Current Train');
      me.dapUpdateServerText.innerHTML = gettext('Update Server');
      me.dapUpdateGridText.innerHTML = gettext('Pending Updates');

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

      me._verifyInstall = new Button({
        label: gettext("Verify Install"),
        onClick: function() {
          editObject(gettext("Verify Install"), me.verifyUrl, [me.domNode]);
        }
      }, me.dapVerifyInstallBtn);

      me._selectTrain = new Select({
        disabled: true
      }, me.dapSelectTrain);

      xhr.get(me.initial.trainUrl, {
        headers: {
          "X-Requested-From": "WebUI",
          "Content-Type": "application/json"
        },
        handleAs: "json",
        query: {"format": "json"}
      }).then(function(data) {
        console.log("data", data);
        me.dapCurrentTrain.innerHTML = data.selected_train.name;
        me.dapCurrentTrainDesc.innerHTML = data.selected_train.descr;

        var options = [];
        for(var i in data.trains) {
          var name = data.trains[i];
          var entry = {id: name, label: name, value: name};
          if(name == data.selected_train.name) entry['selected'] = true;
          console.log(options);
          options.push(entry);
        }

        var store = new Memory({data: options});
        var objstore = new ObjectStore({ objectStore: store });
        me._selectTrain.set('store', objstore);
        me._selectTrain.set('oldvalue', data.selected_train.name);
        me._selectTrain.set('internalchange', true);
        me._selectTrain.set('value', data.selected_train.name);
        me._selectTrain.set('disabled', false);

        me._updatesGrid.set('store', me._store);
        me._updatesGrid.set('query', "?train=" + data.selected_train.name);
      });

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
