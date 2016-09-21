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
  "dojo/text!freeadmin/templates/cloudsync.html",
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

    var CloudSync = declare("freeadmin.CloudSync", [ _Widget, _Templated ], {
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

        for(var i=0;i<credentials.length;i++) {
          creds.push({label: credentials[i][1], value: credentials[i][0]});
        }

        if(!gettext) {
          gettext = function(s) { return s; }
        }

        if(this.errorMessage != '') {
          this.dapErrorMessage.innerHTML = this.errorMessage;
        } else {
          domStyle.set(this.dapErrorMessageRow, "display", "none");
        }

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

      }
    });
    return CloudSync;
});
