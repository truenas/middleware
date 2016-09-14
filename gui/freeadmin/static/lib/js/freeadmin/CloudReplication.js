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
  "dojox/widget/Standby",
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
  Standby,
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

        on(this._credential, 'change', function(value) {
          me.hideAll();
          if(value != '') {
            me._showLoading();
            Middleware.call(
              'datastore.query', ['system.cloudcredentials', [['id', '=', value]], {get: true} ],
              function(result) {
                if(result.provider == 'AMAZON') me.showAmazon(result);
              }
            );
          }
        });

        this._filesystem = new Select({
          name: "filesystem",
          options: fss,
          value: "",
        }, this.dapFilesystem);
        if(initial.filesystem) this._filesystem.set('value', initial.filesystem);

        this._enabled = new CheckBox({
          name: "enabled",
          value: true
        }, me.dapEnabled);

        this._name = new TextBox({
          name: "name",
          value: initial.name
        }, this.dapName);

        this._submit = new Button({
          label: gettext('OK')
        }, this.dapSubmit);

        on(this._submit, 'click', function() {
          me.submit();
        });

        this._cancel = new Button({
          label: gettext('Cancel')
        }, this.dapCancel);

        on(this._cancel, 'click', function() {
          cancelDialog(this);
        });

        this._standby = new Standby({
          target: me.dapProvider,
        });
        document.body.appendChild(this._standby.domNode);
        this._standby.startup();

        this.inherited(arguments);

      },
      _hideLoading: function() {
        this._standby.hide();
      },
      _showLoading: function() {
        this.hideAll();
        this._standby.show();
      },
      hideAll: function() {
        domStyle.set(this.dapAmazon, "display", "none");
      },
      showAmazon: function(credential) {
        var me = this;
        Middleware.call(
          'backup.s3.get_buckets', [credential.id],
          function(result) {
            var options = [{label: "-----", value: ""}];
            for(var i=0;i<result.length;i++) {
              options.push({label: result[i].name, value: result[i].name});
            }
            domStyle.set(me.dapAmazon, "display", "table-row");
            var buckets = new Select({
              name: "bucket",
              options: options,
              value: ''
            }, me.dapAmazonBuckets);

            var folder = new TextBox({
              name: "folder"
            }, me.dapAmazonFolder);

            me._hideLoading();
          }
        );
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
      submit: function(e) {

        var me = this;
        doSubmit({
           form: me._form,
           event: e,
           url: me.url,
        });

      }
    });
    return CloudReplication;
});
