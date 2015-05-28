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
  "dojo/request/xhr",
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
  "dijit/form/RadioButton",
  "dijit/form/Select",
  "dijit/form/TextBox",
  "dijit/layout/TabContainer",
  "dijit/layout/ContentPane",
  "dijit/popup",
  "dojox/layout/ResizeHandle",
  "dojox/string/sprintf",
  "dojox/widget/Toaster",
  "dojo/text!freeadmin/templates/fcport.html",
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
  xhr,
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
  RadioButton,
  Select,
  TextBox,
  TabContainer,
  ContentPane,
  popup,
  ResizeHandle,
  sprintf,
  Toaster,
  template) {

    var FCPort = declare("freeadmin.FCPort", [ _Widget, _Templated ], {
      templateString: template,
      name: null,
      port: null,
      mode: null,
      postCreate: function() {

        var me = this;

        this.dapFCName.innerHTML = this.name + " (#" + this.port + ")";

        new RadioButton({
          name: "mode",
          value: "initiator",
          checked: (me.mode == 'INITIATOR') ? true : false
        }, this.dapFCModeIni);

        new RadioButton({
          name: "mode",
          value: "target",
          checked: (me.mode == 'TARGET') ? true : false
        }, this.dapFCModeTgt);

        this.inherited(arguments);

      },
      submit: function() {
      }
    });

    var FCPorts = declare("freeadmin.FCPorts", [ _Widget, _Templated ], {
      templateString: '<table data-dojo-attach-point="dapTable"></table>',
      postCreate: function() {

        var me = this;

        xhr.get('/api/v1.0/sharing/fcports/', {
          headers: {
            "X-Requested-From": "WebUI",
            "Content-Type": "application/json"
          },
          handleAs: "json",
          query: {"format": "json"}
        }).then(function(data) {

          for(var i=0;i<data.length;i++) {
            var entry = data[i];
            var fcport = FCPort({
              name: entry.name,
              port: entry.port,
              mode: entry.mode
            })
            me.dapTable.appendChild(fcport.domNode);
          }

        });

        this.inherited(arguments);

      },
      submit: function() {
      }
    });

    return FCPorts;
});
