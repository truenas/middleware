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
      name: "",
      value: "",
      errorMessage: "",
      initial: "",
      url: "",
      credentials: "",
      templateString: template,
      postCreate: function() {

        var me = this, credentials = [];
        var creds = [{label: "-----", value: ""}];

        if(this.initial != '') {
          this.initial = json.parse(this.initial);
        }

        if(this.credentials != '') {
          credentials = json.parse(this.credentials);
        }

        for(var i=0;i<credentials.length;i++) {
          creds.push({label: credentials[i][0], value: credentials[i][1]});
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
        if(this.initial.credential) this._credential.set('value', this.initial.credential);

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

        this.hideAll();

        this.inherited(arguments);

      },
      _hideLoading: function() {
        this._standby.hide();
        domStyle.set(this.dapProvider, "height", "inherit");
      },
      _showLoading: function() {
        this.hideAll();
        domStyle.set(this.dapProvider, "height", "100px");
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
            me._buckets = new Select({
              name: "bucket",
              options: options,
              value: ''
            }, me.dapAmazonBuckets);
            if(me.initial.bucket) me._buckets.set('value', me.initial.bucket);

            me._folder = new TextBox({
              name: "folder"
            }, me.dapAmazonFolder);
            if(me.initial.folder) me._folder.set('value', me.initial.folder);

            me._hideLoading();
          }
        );
      },
      _getValueAttr: function() {
        var value = {};
        if(this._credential) value['credential'] = this._credential.get('value');
        if(this._buckets) value['bucket'] = this._buckets.get('value');
        if(this._folder) value['folder'] = this._folder.get('value');
        return json.stringify(value);
      }
    });
    return CloudSync;
});
