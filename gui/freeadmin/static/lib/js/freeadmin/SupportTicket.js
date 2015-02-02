define([
  "dojo/_base/array",
  "dojo/_base/connect",
  "dojo/_base/declare",
  "dojo/_base/lang",
  "dojo/dom-class",
  "dojo/dom-construct",
  "dojo/dom-style",
  "dojo/json",
  "dojo/mouse",
  "dojo/on",
  "dojo/query",
  "dojo/store/Memory",
  "dojo/store/Observable",
  "dijit/_Widget",
  "dijit/_TemplatedMixin",
  "dijit/registry",
  "dijit/Tooltip",
  "dijit/TooltipDialog",
  "dijit/form/Button",
  "dijit/form/CheckBox",
  "dijit/form/FilteringSelect",
  "dijit/form/Form",
  "dijit/form/Select",
  "dijit/form/TextBox",
  "dijit/form/SimpleTextarea",
  "dijit/layout/TabContainer",
  "dijit/layout/ContentPane",
  "dijit/popup",
  "dojox/layout/ResizeHandle",
  "dojox/string/sprintf",
  "dojox/widget/Toaster",
  "dojo/text!freeadmin/templates/supportticket.html",
  "dojo/text!freeadmin/templates/supportticket_attachment.html"
  ], function(
  array,
  connect,
  declare,
  lang,
  domClass,
  domConst,
  domStyle,
  json,
  mouse,
  on,
  query,
  Memory,
  Observable,
  _Widget,
  _Templated,
  registry,
  Tooltip,
  TooltipDialog,
  Button,
  CheckBox,
  FilteringSelect,
  Form,
  Select,
  TextBox,
  SimpleTextarea,
  TabContainer,
  ContentPane,
  popup,
  ResizeHandle,
  sprintf,
  Toaster,
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
      url: "",
      templateString: template,
      postCreate: function() {

        var me = this, _form;
        var submit, cancel;
        var attachment_add;

        if(!gettext) {
          gettext = function(s) { return s; }
        }

        this._form = new Form({
          enctype: "multipart/form-data",
          method: "post"
        }, this.dapForm);
        this._form.startup();

        this.dapUsernameLabel.innerHTML = gettext('Username');
        this.dapRegisterLabel.innerHTML = gettext('If you do not have an account, please') + ' <a href="https://bugs.freenas.org/account/register" target="_blank">' + gettext('register') + '</a>.';

        new TextBox({
          name: "csrfmiddlewaretoken",
          value: CSRFToken,
          type: "hidden"
        }, this.dapCSRF);

        this._username = new TextBox({
          name: "username"
        }, this.dapUsername);

        this._password = new TextBox({
          name: "password",
          type: "password"
        }, this.dapPassword);

        this._type = new Select({
          name: "type",
          options: TYPE_OPTIONS
        }, this.dapType);

        this._category = new Select({
          name: "category",
          options: CATEGORY_OPTIONS
        }, this.dapCategory);

        this._subject = new TextBox({
          name: "subject"
        }, this.dapSubject);

        this._desc = new SimpleTextarea({
          name: "desc",
          style: "width: 450px; height:160px;"
        }, this.dapDesc);

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
        if(!this.validate()) return false;
        doSubmit({
          url: this.url,
          form: this._form,
          //progressbar: this.url_progress
        });
      }
    });
    return SupportTicket;
});
