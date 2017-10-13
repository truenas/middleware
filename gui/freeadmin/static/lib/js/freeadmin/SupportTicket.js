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
  "dojo/text!freeadmin/templates/supportticket.html",
  "dojo/text!freeadmin/templates/supportticket_attachment.html"
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
  template,
  templateAttachment) {

    var TYPE_OPTIONS = [
      {label: "Bug", value: "bug"},
      {label: "Feature", value: "feature"}
    ];

    var TN_CATEGORY_OPTIONS = [
      {label: "Bug", value: "Bug"},
      {label: "Hardware", value: "Hardware"},
      {label: "Installation/Setup", value: "Installation/Setup"},
      {label: "Performance", value: "Performance"}
    ];

    var TN_ENV_OPTIONS = [
      {label: "Production", value: "Production"},
      {label: "Staging", value: "Staging"},
      {label: "Test", value: "Test"},
      {label: "Prototyping", value: "Prototyping"},
      {label: "Initial Deployment/Setup", value: "Initial Deployment/Setup"}
    ];

    var TN_CRIT_OPTIONS = [
      {label: "Inquiry", value: "Inquiry"},
      {label: "Loss of Functionality", value: "Loss of Functionality"},
      {label: "Total Down", value: "Total Down"}
    ];

    var SupportTicket = declare("freeadmin.SupportTicket", [ _Widget, _Templated ], {
      errorMessage: "",
      initial: "",
      categoriesUrl: "",
      progressUrl: "",
      url: "",
      softwareName: "",
      templateString: template,
      postCreate: function() {

        var me = this, _form;
        var submit, cancel;
        var attachment_add;
        var initial = {};

        if(this.initial != '') {
          initial = json.parse(this.initial);
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

        this.dapRegisterLabel.innerHTML = gettext('If you do not have an account, please') + ' <a href="https://bugs.freenas.org/account/register" target="_blank">' + gettext('register') + '</a>.';
        this.dapUsernameLabel.innerHTML = gettext('Username');
        this.dapPasswordLabel.innerHTML = gettext('Password');
        this.dapNameLabel.innerHTML = gettext('Name');
        this.dapEmailLabel.innerHTML = gettext('E-mail');
        this.dapPhoneLabel.innerHTML = gettext('Phone');
        this.dapTypeLabel.innerHTML = gettext('Type');
        this.dapCategoryLabel.innerHTML = gettext('Category');
        this.dapEnvLabel.innerHTML = gettext('Environment');
        this.dapCritLabel.innerHTML = gettext('Criticality');
        this.dapDebugLabel.innerHTML = gettext('Attach Debug Info');
        this.dapSubjectLabel.innerHTML = gettext('Subject');
        this.dapDescLabel.innerHTML = gettext('Description');
        this.dapAttachmentsLabel.innerHTML = gettext('Attachments');

        new TextBox({
          name: "csrfmiddlewaretoken",
          value: CSRFToken,
          type: "hidden"
        }, this.dapCSRF);

        if(this.softwareName == 'truenas') {
          domStyle.set(this.dapRegisterRow, "display", "none");
          domStyle.set(this.dapUsernameRow, "display", "none");
          domStyle.set(this.dapPasswordRow, "display", "none");
          domStyle.set(this.dapTypeRow, "display", "none");

          this._name = new TextBox({
            name: "name",
            value: initial.name || ''
          }, this.dapName);

          this._email = new TextBox({
            name: "email",
            value: initial.email || ''
          }, this.dapEmail);

          this._phone = new TextBox({
            name: "phone",
            value: initial.phone || ''
          }, this.dapPhone);

          this._env = new Select({
            name: "environment",
            options: TN_ENV_OPTIONS
          }, this.dapEnv);
          if(initial.environment) this._env.set('value', initial.environment);

          this._crit = new Select({
            name: "criticality",
            options: TN_CRIT_OPTIONS
          }, this.dapCrit);
          if(initial.criticality) this._crit.set('value', initial.criticality);

        } else {
          domStyle.set(this.dapCritRow, "display", "none");
          domStyle.set(this.dapEmailRow, "display", "none");
          domStyle.set(this.dapEnvRow, "display", "none");
          domStyle.set(this.dapNameRow, "display", "none");
          domStyle.set(this.dapPhoneRow, "display", "none");
          this._username = new TextBox({
            name: "username",
            value: initial.username
          }, this.dapUsername);

          on(this._username, 'change', function() {
            if(!me._username.get('value') || !me._password.get('value')) {
              return;
            }
            me.fetchCategories({
              user: me._username.get('value'),
              password: me._password.get('value')
            });
          });

          this._password = new TextBox({
            name: "password",
            type: "password",
            value: initial.password
          }, this.dapPassword);

          on(this._password, 'change', function() {
            if(!me._username.get('value') || !me._password.get('value')) {
              return;
            }
            me.fetchCategories({
              user: me._username.get('value'),
              password: me._password.get('value')
            });
          });

          this._type = new Select({
            name: "type",
            options: TYPE_OPTIONS
          }, this.dapType);
          if(initial.type) this._type.set('value', initial.type);

        }

        this._category = new Select({
          name: "category",
          options: (this.softwareName == 'truenas') ? TN_CATEGORY_OPTIONS : []
        }, this.dapCategory);
        if(initial.category) this._category.set('value', initial.category);

        this._subject = new TextBox({
          name: "subject",
          value: initial.subject
        }, this.dapSubject);

        this._desc = new SimpleTextarea({
          name: "desc",
          style: "width: 450px; height:160px;",
          value: initial.desc
        }, this.dapDesc);

        this._debug = new CheckBox({
          name: "debug",
          checked: (initial.debug !== undefined) ? initial.debug : true
        }, this.dapDebug);

        this._submit = new Button({
          label: gettext("Submit")
        }, this.dapSubmit);

        on(this._submit, 'click', function() {
          me.submit();
        });

        attachment_add = new Button({
          label: "+"
        }, this.dapAttachmentAdd);

        on(attachment_add, 'click', function() {
          me.AddAttachment();
        });

        this.AddAttachment();

        this.inherited(arguments);

      },
      fetchCategories: function(query) {
        var me = this;

        me.dapErrorMessage.innerHTML = '';
        domStyle.set(me.dapErrorMessageRow, "display", "block");
        domConst.empty(me.dapErrorMessage);
        var loading = domConst.toDom('<div class="dijitInline dijitIconLoading"></div> <span style="color: black;">Validating credentials...</span>');
        me.dapErrorMessage.appendChild(loading);


        xhr.post(me.categoriesUrl, {
          handleAs: 'json',
          data: query || '',
          headers: {"X-CSRFToken": CSRFToken}
        }).then(function(data) {
          if(data.error) {
            domConst.empty(me.dapErrorMessage);
            me.dapErrorMessage.innerHTML = data.message;
            domStyle.set(me.dapErrorMessageRow, "display", "block");
          } else {
            me.dapErrorMessage.innerHTML = '';
            domConst.empty(me.dapErrorMessage);
            domStyle.set(me.dapErrorMessageRow, "display", "none");
          }
          var cats = [];
          for(var i in data.categories) {
            cats.push({label: i, value: data.categories[i]});
          }
          me._category.removeOption(me._category.getOptions());
          me._category.addOption(cats);
        });
      },
      AddAttachment: function() {

        var attach = declare([ _Widget, _Templated ], {
          templateString: templateAttachment,
          postCreate: function() {
            var me = this;

            var _delete = new Button({
              label: "X"
            }, this.dapDelete);

            on(_delete, 'click', function() {
              me.destroyRecursive();
            });

            this.inherited(arguments);
          }
        });
        var widget = new attach({});
        this.dapAttachments.appendChild(widget.domNode);

      },
      validate: function() {
        var map;
        if(this.softwareName == 'truenas') {
          map = {
            1: this._subject,
            2: this._desc,
            3: this._name,
            4: this._email,
            2: this._category,
            5: this._phone
          };
        } else {
          map = {
            1: this._username,
            2: this._password,
            2: this._category,
            3: this._subject,
            4: this._desc
          };
        }

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
      clear: function() {
        this._subject.set('value', '');
        this._desc.set('value', '');
        domConst.empty(this.dapAttachments);
        this.AddAttachment();
      },
      submit: function() {

        var me = this;
        var steps = [];
        var fileUpload = false;

        query("input[type=file]", this._form.domNode).forEach(function(item, idx) {
          if(item.value) fileUpload = true;
        });

        if(fileUpload) {
          steps.push({
            label: gettext("Uploading attachments to host")
          });
        }

        steps.push({
          label: gettext("Submitting ticket")
        });

        var uuid = generateRandomUuid();

        var progressbar = new Progress({
          poolUrl: this.progressUrl,
          steps: steps,
          fileUpload: fileUpload,
          uuid: uuid
        });

        if(!this.validate()) return false;

        this._submit.set('disabled', true);

        var submitting = new Dialog({});
        submitting.containerNode.appendChild(progressbar.domNode);

        iframe.post(this.url + '?X-Progress-ID=' + uuid, {
          form: this._form.id,
          handleAs: 'json',
          headers: {"X-CSRFToken": CSRFToken}
        }).then(function(data) {

          if(data.error) {
            me.dapErrorMessage.innerHTML = data.message;
            domStyle.set(me.dapErrorMessageRow, "display", "block");
            submitting.destroyRecursive();
          } else {
            me.dapErrorMessage.innerHTML = '';
            domStyle.set(me.dapErrorMessageRow, "display", "none");
            progressbar.destroyRecursive();
            var dom = domConst.toDom('<p>Your ticket has been successfully submitted!</p><p>URL: <a href="' + data.message + '" target="_blank">' + data.message + '</a>')
            submitting.containerNode.appendChild(dom);

            me.clear();
          }

          me._submit.set('disabled', false);

        }, function(evt, response) {
           console.log("error", evt, response);
        });

        progressbar.update(uuid);

        submitting.show();

      }
    });
    return SupportTicket;
});
