define([
  "dojo/_base/declare",
  "dojo/dom-style",
  "dojo/json",
  "dojo/mouse",
  "dojo/on",
  "dojo/query",
  "dijit/_Widget",
  "dijit/_TemplatedMixin",
  "dijit/registry",
  "dijit/TooltipDialog",
  "dijit/form/Button",
  "dijit/form/CheckBox",
  "dijit/form/Form",
  "dijit/form/Select",
  "dijit/form/TextBox",
  "dijit/form/SimpleTextarea",
  "dijit/popup",
  "dojo/text!freeadmin/templates/supportticket.html",
  "dojo/text!freeadmin/templates/supportticket_attachment.html"
  ], function(
  declare,
  domStyle,
  json,
  mouse,
  on,
  query,
  _Widget,
  _Templated,
  registry,
  TooltipDialog,
  Button,
  CheckBox,
  Form,
  Select,
  TextBox,
  SimpleTextarea,
  popup,
  template,
  templateAttachment) {

    var TYPE_OPTIONS = [
      {label: "Bug", value: "bug"},
      {label: "Feature", value: "feature"}
    ];

    var CATEGORY_OPTIONS = [
      {label: "AFP", value: "AFP"},
      {label: "API", value: "API"},
      {label: "Alerts", value: "Alerts"},
      {label: "CIFS", value: "CIFS"}
    ];

    var SupportTicket = declare("freeadmin.SupportTicket", [ _Widget, _Templated ], {
      errorMessage: "",
      initial: "",
      progressUrl: "",
      url: "",
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

        this.dapUsernameLabel.innerHTML = gettext('Username');
        this.dapRegisterLabel.innerHTML = gettext('If you do not have an account, please') + ' <a href="https://bugs.freenas.org/account/register" target="_blank">' + gettext('register') + '</a>.';
        this.dapDebugLabel.innerHTML = gettext('Attach Debug Info');

        new TextBox({
          name: "csrfmiddlewaretoken",
          value: CSRFToken,
          type: "hidden"
        }, this.dapCSRF);

        this._username = new TextBox({
          name: "username",
          value: initial.username
        }, this.dapUsername);

        this._password = new TextBox({
          name: "password",
          type: "password",
          value: initial.password
        }, this.dapPassword);

        this._type = new Select({
          name: "type",
          options: TYPE_OPTIONS
        }, this.dapType);
        if(initial.type) this._type.set('value', initial.type);

        this._category = new Select({
          name: "category",
          options: CATEGORY_OPTIONS
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
          checked: initial.debug
        }, this.dapDebug);

        submit = new Button({
          label: gettext("Submit")
        }, this.dapSubmit);

        cancel = new Button({
          label: gettext("Cancel")
        }, this.dapCancel);

        on(submit, 'click', function() {
          me.submit();
        });

        on(cancel, 'click', function() {
          cancelDialog(this);
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
        var map = {
          1: this._username,
          2: this._password,
          3: this._subject,
          4: this._desc
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

        var steps = [];
        var fileUpload = false;

        query("input[type=file]", this._form.domNode).forEach(function(item, idx) {
          if(item.value) fileUpload = true;
        });

        if(this._debug.get('value') == 'on') {
          steps.push({
            label: gettext("Generating debug info")
          });
        }

        if(fileUpload) {
          steps.push({
            label: gettext("Uploading attachments")
          });
        }

        steps.push({
          label: gettext("Submitting ticket")
        });

        var progressbar = {
          poolUrl: this.progressUrl,
          steps: steps,
          fileUpload: fileUpload
        };

        if(!this.validate()) return false;
        doSubmit({
          url: this.url,
          form: this._form,
          progressbar: progressbar
        });
      }
    });
    return SupportTicket;
});
