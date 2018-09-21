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
  "dojox/html/entities",
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
  entities,
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
      buckets: {},
      bucketTitle: {},
      taskSchemas: {},
      templateString: template,
      _buckets: null,
      _bucketsInput: null,
      _hadBuckets: false,
      _folder: null,
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
          this.buckets[credentials[i][1]] = credentials[i][2];
          this.bucketTitle[credentials[i][1]] = credentials[i][3];
          this.taskSchemas[credentials[i][1]] = credentials[i][4];
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
          if(value != '') {
            if (me.buckets[value]) {
              me._showLoading();
              Middleware.call(
                'cloudsync.list_buckets', [value],
                function(result) {
                  me._hideLoading();
                  me.setupProviderAttributes(value, result);
                },
                function(error) {
                  me._hideLoading();
                  me.setupProviderAttributes(value, null, error);
                }
              )
            } else {
              me.setupProviderAttributes(value);
            }
          } else {
            this.hideAll();
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
      },
      setupProviderAttributes: function(credentialId, buckets, bucketsError) {
        if (this.buckets[credentialId]) {
          if (buckets !== null)
          {
            this._hadBuckets = true;
            var options = [{label: "-----", value: ""}];
            for(var i=0;i<buckets.length;i++) {
              options.push({label: buckets[i].Name, value: buckets[i].Name});
            }
            domStyle.set(this.dapBucket, "display", "block");
            domStyle.set(this.dapBucketInput, "display", "none");
            if (this._buckets == null) {
              this._buckets = new Select({
                name: "bucket",
                options: options,
                value: ''
              }, this.dapBuckets);
            }
            this._buckets.set('options', options);
            if(this.initial.bucket) this._buckets.set('value', this.initial.bucket);
          } else {
            this._hadBuckets = false;
            domStyle.set(this.dapBucket, "display", "none");
            domStyle.set(this.dapBucketInput, "display", "block");
            if (this._bucketsInput == null) {
              this._bucketsInput = new TextBox({
                name: "bucket",
              }, this.dapBucketsInput);
            }
            this.dapBucketInputError.innerHTML = "Error " + bucketsError.error + "<pre style='white-space: pre-wrap;'>" + entities.encode(bucketsError.reason) + "</pre>Please enter " + this.bucketTitle[credentialId].toLowerCase() + " name manually:";
            if(this.initial.bucket) this._bucketsInput.set('value', this.initial.bucket);
          }
          this.dapBucketLabel.innerHTML = this.bucketTitle[credentialId];
          this.dapBucketInputLabel.innerHTML = this.bucketTitle[credentialId];
        } else {
          domStyle.set(this.dapBucket, "display", "none");
          domStyle.set(this.dapBucketInput, "display", "none");
        }

        if (this._folder == null) {
          this._folder = new TextBox({
            name: "folder"
          }, this.dapFolder);
        }
        if(this.initial.folder) this._folder.set('value', this.initial.folder);

        var html = "";
        for (var i = 0; i < this.taskSchemas[credentialId].length; i++)
        {
            var property = this.taskSchemas[credentialId][i];

            var id = "id_attributes_" + property.property;
            if (property.schema.type.indexOf("boolean") != -1)
            {
                html += '<div style="margin-bottom: 5px;"><label><input type="checkbox" id="' + id + '" value="1"> ' + property.schema.title + '</label></div>';
            }
            else
            {
                var input = "<input type='text' id='" + id + "'>";
                if (property.schema.enum)
                {
                    input = "<select id='" + id + "'>";
                    for (var i = 0; i < property.schema.enum.length; i++)
                    {
                        input += '<option>' + property.schema.enum[i] + '</option>';
                    }
                    input += '</select>';
                }

                html += '<div style="margin-bottom: 5px;"><div>' + property.schema.title + '</div><div>' + input + '</div></div>';
            }
        }
        this.dapEtc.innerHTML = html;
        for (var i = 0; i < this.taskSchemas[credentialId].length; i++)
        {
            var property = this.taskSchemas[credentialId][i];

            var id = "id_attributes_" + property.property;

            if (this.initial[property.property] !== undefined)
            {
                if (property.schema.type.indexOf("boolean") != -1)
                {
                    document.getElementById(id).checked = this.initial[property.property];
                }
                else
                {
                    document.getElementById(id).value = this.initial[property.property];
                }
            }
        }
      },
      _getValueAttr: function() {
        var value = {};
        if(this._credential) value['credential'] = this._credential.get('value');
        if(value.credential) {
          if (this.buckets[value.credential]) {
            if (this._hadBuckets) {
              if(this._buckets) value['bucket'] = this._buckets.get('value');
            } else {
              if(this._bucketsInput) value['bucket'] = this._bucketsInput.get('value');
            }
          }
          for (var i = 0; i < this.taskSchemas[value.credential].length; i++)
          {
            var property = this.taskSchemas[value.credential][i];
            var id = "id_attributes_" + property.property;
            if (document.getElementById(id)) {
              if (property.schema.type.indexOf("boolean") != -1) {
                value[property.property] = document.getElementById(id).checked;
              } else {
                value[property.property] = document.getElementById(id).value;
              }
              if (value[property.property] === "null") {
                value[property.property] = null;
              }
            }
          }
        }
        if(this._folder) value['folder'] = this._folder.get('value');
        return json.stringify(value);
      }
    });
    return CloudSync;
});
