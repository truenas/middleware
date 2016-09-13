define([
  "dojo/_base/declare",
  "dojo/dom-construct",
  "dojo/dom-style",
  "dojo/json",
  "dojo/mouse",
  "dojo/on",
  "dojo/query",
  "dojo/request/iframe",
  "dojo/request/xhr",
  "dijit/_Widget",
  "dijit/_TemplatedMixin",
  "dijit/Dialog",
  "dijit/registry",
  "dijit/TooltipDialog",
  "dijit/form/Button",
  "dijit/form/CheckBox",
  "dijit/form/Form",
  "dijit/form/Select",
  "dijit/form/TextBox",
  "dijit/form/SimpleTextarea",
  "dijit/popup",
  "dojox/uuid/generateRandomUuid",
  "freeadmin/Progress",
  "dojo/text!freeadmin/templates/cloudreplication.html",
  ], function(
  declare,
  domConst,
  domStyle,
  json,
  mouse,
  on,
  query,
  iframe,
  xhr,
  _Widget,
  _Templated,
  Dialog,
  registry,
  TooltipDialog,
  Button,
  CheckBox,
  Form,
  Select,
  TextBox,
  SimpleTextarea,
  popup,
  generateRandomUuid,
  Progress,
  template) {

    var CloudReplication = declare("freeadmin.CloudReplication", [ _Widget, _Templated ], {
      errorMessage: "",
      initial: "",
      url: "",
      credentials: "",
      filesystems: "",
      templateString: template,
      postCreate: function() {

        var me = this, _form, credentials, filesystems;
        var submit, cancel;
        var initial = {};
        var creds = [{label: "-----", value: ""}];
        var fss = [{label: "-----", value: ""}];

        if(this.initial != '') {
          initial = json.parse(this.initial);
        }

        if(this.credentials != '') {
          credentials = json.parse(this.credentials);
        }

        if(this.filesystems != '') {
          filesystems = json.parse(this.filesystems);
        }

        for(var i=0;i<credentials.length;i++) {
          creds.push({label: credentials[i][1], value: credentials[i][0]});
        }

        for(var i=0;i<filesystems.length;i++) {
          fss.push({label: filesystems[i], value: filesystems[i]});
        }

        if(!gettext) {
          gettext = function(s) { return s; }
        }

        this._form = new Form({
          enctype: "multipart/form-data",
          method: "post"
        }, this.dapForm);
        this._form.startup();

        if(this.errorMessage != '') {
          this.dapErrorMessage.innerHTML = this.errorMessage;
        } else {
          domStyle.set(this.dapErrorMessageRow, "display", "none");
        }

        this.dapNameLabel.innerHTML = gettext('Name');

        new TextBox({
          name: "csrfmiddlewaretoken",
          value: CSRFToken,
          type: "hidden"
        }, this.dapCSRF);

        this._credential = new Select({
          name: "credential",
          options: creds,
          value: "",
        }, this.dapCredential);
        if(initial.credential) this._credential.set('value', initial.credential);

        this._filesystem = new Select({
          name: "filesystem",
          options: fss,
          value: "",
        }, this.dapFilesystem);
        if(initial.filesystem) this._filesystem.set('value', initial.filesystem);

        this._name = new TextBox({
          name: "name",
          value: initial.name
        }, this.dapName);

        this._submit = new Button({
          label: gettext("Submit")
        }, this.dapSubmit);

        on(this._submit, 'click', function() {
          me.submit();
        });

        this.inherited(arguments);

      },
      validate: function() {
        var map;
          map = {
            1: this._name,
            2: this._filesystem,
            3: this._credential,
          };

        for(var i in map) {
          var field = map[i];
          var value = field.get('value');
          if(value == '') {
            var tooltip = new TooltipDialog({
              content: gettext('This field is required.'),
              onMouseLeave: function() {
                popup.close(tooltip);
                tooltip.destroyRecursive();
              }
            });
            popup.open({
              popup: tooltip,
              around: field.domNode,
              orient: ["above", "after", "below-alt"]
            });
            field.focus();
            return false;
          }
        }
        return true;
      },
      submit: function() {

        var me = this;

        if(!this.validate()) return false;

        this._submit.set('disabled', true);

      }
    });
    return CloudReplication;
});
