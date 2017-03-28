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
  "dstore/Memory",
  "dijit/_Widget",
  "dijit/_TemplatedMixin",
  "dijit/form/CheckBox",
  "dijit/form/ComboBox",
  "dijit/form/TextBox",
  "dijit/form/Button",
  "dijit/form/RadioButton",
  "dijit/form/MultiSelect",
  "dijit/form/ValidationTextBox",
  "dijit/layout/TabContainer",
  "dijit/layout/ContentPane",
  "dijit/Tooltip",
  "dgrid/OnDemandGrid",
  "dgrid/Selection",
  "dojox/timing",
  "dojox/string/sprintf",
  "dojo/text!freeadmin/templates/wizardshares.html",
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
  MultiSelect,
  ValidationTextBox,
  TabContainer,
  ContentPane,
  Tooltip,
  OnDemandGrid,
  Selection,
  timing,
  sprintf,
  template,
  UnixPerm) {

  var WizardShares = declare("freeadmin.WizardShares", [ _Widget, _Templated ], {
    templateString : template,
    initial: "[]",
    errors: "[]",
    postCreate: function() {
      var me = this;

      var errors = json.parse(me.errors)
      for(var i=0;i<errors.length;i++) {
        var form = errors[i];
        if(form && form.share_name) {
          me.dapSharesErrors.appendChild(domConstruct.toDom('<p><span style="color: red;">' + form.share_name[0] + '</span></p>'));
        }
      }

      me.dapShareNameLabel.innerHTML = gettext("Share name") + ":";

      me._shareName = new ValidationTextBox({
        name: "sharename",
        required: true,
        pattern: "[a-zA-Z0-9_\\-\\.]+",
        invalidMessage: gettext('This field may only contain alphanumeric and the following characters: "_", "-", ".".')
      }, me.dapShareName);

      on(me._shareName, "keyup", function(evt) {
        var value = this.get('value');
        var result = me._store.getSync(value);
        if(result) {
          var row = me._sharesList.row(value);
          me._sharesList.select(row);
        } else {
          me._sharesList.clearSelection();
          me._shareAdd.set('disabled', false);
          me._shareDelete.set('disabled', true);
          me._shareUpdate.set('disabled', true);
        }
      })

      me._shareCIFS = new RadioButton({checked: true}, me.dapShareCIFS);
      me._shareAFP = new RadioButton({}, me.dapShareAFP);
      me._shareNFS = new RadioButton({}, me.dapShareNFS);
      me._shareiSCSI = new RadioButton({}, me.dapShareiSCSI);

      on(me._shareCIFS, "change", function() {
        if(this.get('value')) {
          me._shareGuest.set('disabled', false);
        } else {
          me._shareGuest.set('disabled', true);
        }
      });

      on(me._shareAFP, "change", function() {
        if(this.get('value')) {
          me._shareAFP_TM.set('disabled', false);
        } else {
          me._shareAFP_TM.set('disabled', true);
        }
      });

      on(me._shareiSCSI, "change", function() {
        if(this.get('value')) {
          me._shareiSCSI_size.set('disabled', false);
          me._shareOwnership.set('disabled', true);
        } else {
          me._shareiSCSI_size.set('disabled', true);
          me._shareOwnership.set('disabled', false);
        }
      });

      me._shareAFP_TM = new CheckBox({disabled: true}, me.dapShareAFP_TM);
      me._shareGuest = new CheckBox({}, me.dapShareGuest);
      me._shareiSCSI_size = new ValidationTextBox({
        style: "width: 50px;",
        disabled: true,
        required: true,
        pattern: "^[0-9]+(\\.[0-9]+)?[BKMGT]$",
        invalidMessage: gettext('Specify the size using B, K, M, G, T prefixes.')
      }, me.dapShareiSCSI_size);

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
        collection: me._store,
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

      me._shareOwnership = new Button({label: gettext("Ownership")}, me.dapShareOwnership);
      on(me._shareOwnership, "click", function() {
        me.ownershipSave();
        domStyle.set(me.dapOwnership, "display", "");
        domStyle.set(me.dapMain, "display", "none");
        query(me.domNode).parents("table").query("tr.formButtons").forEach(function(item) {
          domStyle.set(item, "display", "none");
        });
      });

      me._storeUsers = new ItemFileReadStore({
        url: "/account/bsduser/json/?wizard=1",
        clearOnClose: true
      });
      me._storeUsers.fetch();

      me._storeGroups = new ItemFileReadStore({
        url: "/account/bsdgroup/json/?wizard=1",
        clearOnClose: true
      });
      me._storeGroups.fetch();

      me._ownershipUser = new ComboBox({
        required: true,
        store: me._storeUsers,
        searchAttr: 'name',
        autoComplete: false,
        intermediateChanges: true,
        value: 'root',
        invalidMessage: gettext('This user does not exist.'),
        validator: function(value, constraints) {
          var found;
          value = value.replace("\\", "\\\\");
          me._storeUsers.fetch({query: {name: value}, onComplete: function(results) {
            if(results.length > 0) {
              me._ownershipUserCreate.set('disabled', true);
              me._ownershipUserCreate.set('value', false);
              found = true;
            } else {
              me._ownershipUserCreate.set('disabled', false);
              found = false;
            }
          }});
          if(!found && !me._ownershipUserCreate.get("value")) {
            return false;
          }
          return true;
        }
      }, me.dapOwnershipUser);
      on(me._ownershipUser, "click", function() {
        me._storeUsers.url = me._storeUsers.url.split('?')[0];
        me._storeUsers.close();
        me._storeUsers.fetch();
      })
      on(me._ownershipUser, "change", function() {
        var t = me._ownershipUser.get('displayedValue');
        me._storeUsers.url = me._storeUsers.url.split('?')[0] + '?wizard=1&q='+t;
        me._storeUsers.close();
        me._storeUsers.fetch();
      });


      me._ownershipUserPw = new ValidationTextBox({
        type: "password"
      }, me.dapOwnershipUserPw);

      me._ownershipUserPw2 = new ValidationTextBox({
        type: "password",
        invalidMessage: gettext("Passwords do not match."),
        validator: function() {
          var pw1 = me._ownershipUserPw.get("value");
          var pw2 = me._ownershipUserPw2.get("value");
          if((pw1 || pw2) && pw1 != pw2) {
            return false;
          }
          return true;
        }
      }, me.dapOwnershipUserPw2);

      me._ownershipUserCreate = new CheckBox({disabled: true}, me.dapOwnershipUserCreate);
      on(me._ownershipUserCreate, "change", function(value) {
        me._ownershipUser.validate();
        if(value) {
          domStyle.set(me.dapOwnershipUserPwRow, "display", "");
          domStyle.set(me.dapOwnershipUserPw2Row, "display", "");
        } else {
          domStyle.set(me.dapOwnershipUserPwRow, "display", "none");
          domStyle.set(me.dapOwnershipUserPw2Row, "display", "none");
        }
      });
      new Tooltip({
        connectId: ["ownershipUserCreateHelp"],
       label: "To create a new user, type in the username and then check this box"
      });

      me._ownershipGroup = new ComboBox({
        required: true,
        store: me._storeGroups,
        searchAttr: 'name',
        autoComplete: false,
        intermediateChanges: true,
        value: 'wheel',
        invalidMessage: gettext('This group does not exist.'),
        validator: function(value, constraints) {
          var found;
          value = value.replace("\\", "\\\\");
          me._storeGroups.fetch({query: {name: value}, onComplete: function(results) {
            if(results.length > 0) {
              found = true;
              me._ownershipGroupCreate.set('disabled', true);
              me._ownershipGroupCreate.set('value', false);
            } else {
              me._ownershipGroupCreate.set('disabled', false);
              found = false;
            }
          }});
          if(!found && !me._ownershipGroupCreate.get("value")) {
            return false;
          }
          return true;
        }
      }, me.dapOwnershipGroup);
      on(me._ownershipGroup, "click", function() {
        me._storeGroups.url = me._storeGroups.url.split('?')[0];
        me._storeGroups.close();
        me._storeGroups.fetch();
      });
      on(me._ownershipGroup, "change", function() {
        var t = me._ownershipGroup.get('displayedValue');
        me._storeGroups.url = me._storeGroups.url.split('?')[0] + '?wizard=1&q='+t;
        me._storeGroups.close();
        me._storeGroups.fetch();
      });

      me._ownershipGroupCreate = new CheckBox({disabled: true}, me.dapOwnershipGroupCreate);
      on(me._ownershipGroupCreate, "change", function(value) {
        me._ownershipGroup.validate();
      });
      new Tooltip({
        connectId: ["ownershipGroupCreateHelp"],
       label: "To create a new group, type in the group name and then check this box"
      }); 

      me._ownershipMode = new UnixPerm({value: "755"}, me.dapOwnershipMode);

      me._ownershipReturn = new Button({label: gettext("Return")}, me.dapOwnershipReturn);
      me._ownershipCancel = new Button({label: gettext("Cancel")}, me.dapOwnershipCancel);

      var ownershipToShare = function() {
        domStyle.set(me.dapOwnership, "display", "none");
        domStyle.set(me.dapMain, "display", "");
        query(me.domNode).parents("table").query("tr.formButtons").forEach(function(item) {
          domStyle.set(item, "display", "");
        });
      };

      on(me._ownershipCancel, "click", function() {
        me.ownershipRestore();
        ownershipToShare();
      });
      on(me._ownershipReturn, "click", function() {

        var valid = true;
        if(!me._ownershipUser.get('disabled') && !me._ownershipUser.isValid()) {
          me._ownershipUser.focus();
          valid = false;
        }
        if(!me._ownershipGroup.get('disabled') && !me._ownershipGroup.isValid()) {
          me._ownershipGroup.focus();
          valid = false;
        }
        if(!me._ownershipUserPw2.isValid()) {
          me._ownershipUserPw2.focus();
          valid = false;
        }
        if(!valid) return;

        // Update the values in store if the item has already been saved
        var result = me._store.getSync(me._shareName.get("value"));
        if(result) {
          result.user = me._ownershipUser.get("value");
          result.group = me._ownershipGroup.get("value");
          result.usercreate = me._ownershipUserCreate.get("value");
          result.groupcreate = me._ownershipGroupCreate.get("value");
          result.mode = me._ownershipMode.get("value");
          me._store.putSync(result);
        }
        me.dump();
        ownershipToShare();
      });

      me.dump();

      this.inherited(arguments);

    },
    ownershipRestore: function() {
      var me = this;
      me._ownershipUser.set('value', me._ownershipSaved['user']);
      me._ownershipGroup.set('value', me._ownershipSaved['group']);
      me._ownershipUserCreate.set('value', me._ownershipSaved['usercreate']);
      me._ownershipUserPw.set('value', me._ownershipSaved['userpw']);
      me._ownershipUserPw2.set('value', me._ownershipSaved['userpw']);
      me._ownershipGroupCreate.set('value', me._ownershipSaved['groupcreate']);
      me._ownershipMode.set('value', me._ownershipSaved['mode']);
    },
    ownershipSave: function() {
      var me = this;
      me._ownershipSaved = {};
      me._ownershipSaved['user'] = me._ownershipUser.get('value');
      me._ownershipSaved['group'] = me._ownershipGroup.get('value');
      me._ownershipSaved['usercreate'] = me._ownershipUserCreate.get('value');
      me._ownershipSaved['userpw'] = me._ownershipUserPw.get('value');
      me._ownershipSaved['groupcreate'] = me._ownershipGroupCreate.get('value');
      me._ownershipSaved['mode'] = me._ownershipMode.get('value');
    },
    add: function() {
      var me = this;
      var purpose;

      if(!me.isValid()) return;

      if(me._shareCIFS.get("value")) purpose = "cifs";
      else if(me._shareAFP.get("value")) purpose = "afp";
      else if(me._shareNFS.get("value")) purpose = "nfs";
      else if(me._shareiSCSI.get("value")) purpose = "iscsitarget";
      me._store.putSync({
        name: me._shareName.get("value"),
        purpose: purpose,
        allowguest: me._shareGuest.get("value"),
        timemachine: me._shareAFP_TM.get("value"),
        iscsisize: me._shareiSCSI_size.get("value"),
        user: me._ownershipUser.get("value"),
        group: me._ownershipGroup.get("value"),
        usercreate: me._ownershipUserCreate.get("value"),
        userpw: me._ownershipUserPw.get("value"),
        groupcreate: me._ownershipGroupCreate.get("value"),
        mode: me._ownershipMode.get("value")
      });
      me._sharesList.refresh();
      me.dump();
      me.select(me._shareName.get("value"));
      me._sharesList.clearSelection();
      var row = me._sharesList.row(me._shareName.get("value"));
      me._sharesList.select(row);
    },
    remove: function(id) {
      var me = this;
      me._store.removeSync(id);
      me._sharesList.refresh();
      if(Object.keys(me._sharesList.selection).length == 0) {
        me._shareDelete.set("disabled", true);
        me._shareUpdate.set("disabled", true);
      }
      me.dump();
    },
    select: function(id) {
      var me = this;
      var data = me._store.getSync(id);
      me._shareName.set("value", data.name);
      me._shareGuest.set("value", data.allowguest);
      me._shareAFP_TM.set("value", data.timemachine);
      me._shareiSCSI_size.set("value", data.iscsisize);
      me._ownershipUser.set("value", data.user);
      me._ownershipGroup.set("value", data.group);
      me._ownershipUserCreate.set("value", data.usercreate);
      me._ownershipGroupCreate.set("value", data.groupcreate);
      if(data.usercreate) {
        me._ownershipUserCreate.set("disabled", false);
      } else {
        me._ownershipUserCreate.set("disabled", true);
      }
      if(data.userpw) {
        me._ownershipUserPw.set("value", data.userpw);
        me._ownershipUserPw2.set("value", data.userpw);
      } else {
        me._ownershipUserPw.set("value", "");
        me._ownershipUserPw2.set("value", "");
      }
      if(data.groupcreate) {
        me._ownershipGroupCreate.set("disabled", false);
      } else {
        me._ownershipGroupCreate.set("disabled", true);
      }
      me._ownershipMode.set("value", data.mode);
      switch(data.purpose) {
        case "cifs":
          me._shareCIFS.set("value", true);
          me._shareAFP.set("value", false);
          me._shareNFS.set("value", false);
          me._shareiSCSI.set("value", false);
          break;
        case "afp":
          me._shareCIFS.set("value", false);
          me._shareAFP.set("value", true);
          me._shareNFS.set("value", false);
          me._shareiSCSI.set("value", false);
          break;
        case "nfs":
          me._shareCIFS.set("value", false);
          me._shareAFP.set("value", false);
          me._shareNFS.set("value", true);
          me._shareiSCSI.set("value", false);
          break;
        case "iscsitarget":
          me._shareCIFS.set("value", false);
          me._shareAFP.set("value", false);
          me._shareNFS.set("value", false);
          me._shareiSCSI.set("value", true);
          break;
      }
      me._shareAdd.set('disabled', true);
      me._shareUpdate.set('disabled', false);
    },
    isValid: function() {
      var me = this;
      var valid = true;
      if(!me._shareName.isValid()) {
        me._shareName.focus();
        valid = false;
      }
      var iscsiselect = me._shareiSCSI.get('value');
      if(iscsiselect && !me._shareiSCSI_size.isValid()) {
        me._shareiSCSI_size.focus();
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

      me._store.forEach(function(obj, idx) {

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

        if(obj.allowguest) {
          new TextBox({
            name: "shares-" + idx + "-share_allowguest",
            type: "hidden",
            value: obj.allowguest
          }).placeAt(dumpNode);
        }

        if(obj.timemachine) {
          new TextBox({
            name: "shares-" + idx + "-share_timemachine",
            type: "hidden",
            value: obj.timemachine
          }).placeAt(dumpNode);
        }

        if(obj.iscsisize) {
          new TextBox({
            name: "shares-" + idx + "-share_iscsisize",
            type: "hidden",
            value: obj.iscsisize
          }).placeAt(dumpNode);
        }

        if(obj.user) {
          new TextBox({
            name: "shares-" + idx + "-share_user",
            type: "hidden",
            value: obj.user
          }).placeAt(dumpNode);
        }

        if(obj.group) {
          new TextBox({
            name: "shares-" + idx + "-share_group",
            type: "hidden",
            value: obj.group
          }).placeAt(dumpNode);
        }

        if(obj.usercreate) {
          new TextBox({
            name: "shares-" + idx + "-share_usercreate",
            type: "hidden",
            value: obj.usercreate
          }).placeAt(dumpNode);
          if(obj.userpw) {
            new TextBox({
              name: "shares-" + idx + "-share_userpw",
              type: "hidden",
              value: obj.userpw
            }).placeAt(dumpNode);
          }
        }

        if(obj.groupcreate) {
          new TextBox({
            name: "shares-" + idx + "-share_groupcreate",
            type: "hidden",
            value: obj.groupcreate
          }).placeAt(dumpNode);
        }

        if(obj.mode) {
          new TextBox({
            name: "shares-" + idx + "-share_mode",
            type: "hidden",
            value: obj.mode
          }).placeAt(dumpNode);
        }

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
