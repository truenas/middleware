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
      target: null,
      targets: null,
      postCreate: function() {

        var me = this;

        this.dapFCName.innerHTML = this.name + " (#" + this.port + ")";

        me._mini = new RadioButton({
          name: "mode",
          value: "INITIATOR",
          checked: (me.mode == 'INITIATOR') ? true : false
        }, this.dapFCModeIni);

        me._mtgt = new RadioButton({
          name: "mode",
          value: "TARGET",
          checked: (me.mode == 'TARGET') ? true : false
        }, this.dapFCModeTgt);

        on(me._mini, 'change', lang.hitch(me, me.modeChange));

        var tgtoptions = [{label: '------', value: ''}];
        for(var i=0;i<me.targets.length;i++) {
          var tgt = me.targets[i];
          tgtoptions.push({label: tgt.iscsi_target_name, value: tgt.id})
        }

        me._target = new Select({
          name: "target",
          value: (me.target) ? me.target : '',
          options: tgtoptions
        }, this.dapFCTarget);

        on(me._target, 'change', function(val) {
          console.log(this.get('value'), val);
          xhr.post('/services/fiberchanneltotarget/', {
            headers: {
              "X-CSRFToken": CSRFToken
            },
            handleAs: "json",
            data: {
              fc_port: me.port,
              fc_target: val
            }
          }).then(function(data) {

          });

        });

        me.modeChange();

        this.inherited(arguments);

      },
      modeChange: function() {
        var me = this;
        if(me._mtgt.get('checked') == true) {
          domStyle.set(me._target.domNode, "display", "");
        } else {
          domStyle.set(me._target.domNode, "display", "none");
        }
      },
      submit: function() {
      }
    });

    var FCPorts = declare("freeadmin.FCPorts", [ _Widget, _Templated ], {
      templateString: '<table data-dojo-attach-point="dapTable"></table>',
      postCreate: function() {

        var me = this;
        var targets;

        xhr.get('/api/v1.0/services/iscsi/target/', {
          headers: {
            "X-Requested-From": "WebUI",
            "Content-Type": "application/json"
          },
          handleAs: "json",
          query: {"format": "json"},
          sync: true
        }).then(function(data) {
          targets = data;
        });

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
              mode: entry.mode,
              target: entry.target,
              targets: targets,
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
