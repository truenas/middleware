define([
  "dojo/_base/declare",
  "dojo/_base/lang",
  "dojo/dom-style",
  "dojo/json",
  "dojo/on",
  "dojo/request/xhr",
  "dijit/_Widget",
  "dijit/_TemplatedMixin",
  "dijit/registry",
  "dijit/form/Button",
  "dijit/form/Form",
  "dijit/form/RadioButton",
  "dijit/form/Select",
  "dojo/text!freeadmin/templates/fcport.html",
  ], function(
  declare,
  lang,
  domStyle,
  json,
  on,
  xhr,
  _Widget,
  _Templated,
  registry,
  Button,
  Form,
  RadioButton,
  Select,
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

        on(me._target, 'change', me.modeChange);
        me.modeChange();

        this.inherited(arguments);

      },
      modeChange: function() {
        var me = this;
        if(me._mtgt.get('checked') == true) {
          domStyle.set(me._target.domNode, "display", "");
        } else {
          domStyle.set(me._target.domNode, "display", "none");
          me.target = null;

        }
      }
    });

    var FCPorts = declare("freeadmin.FCPorts", [ _Widget, _Templated ], {
      templateString: '<div data-dojo-attach-point="dapFCPorts"><table data-dojo-attach-point="dapTable"></table><div data-dojo-attach-point="dapSubmit"></div></div>',
      ports: null,
      postCreate: function() {

        var me = this;
        var targets;

        me.ports = [];

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
            me.ports.push(fcport);
            me.dapTable.appendChild(fcport.domNode);
          }

        });

        me._submit = new Button({
          label: "Save"
        }, this.dapSubmit);

        on(me._submit, 'click', lang.hitch(this, me.submit));

        this.inherited(arguments);

      },
      submit: function() {

        var me = this;
        var form = new Form({});

        for(var i=0;i<me.ports.length;i++) {
          var fcport = me.ports[i];
          var port = new _Widget();
          form.domNode.appendChild(port.domNode);
          port.set('name', 'fcport-' + i + '-port');
          port.set('value', fcport.name);

          var target = new _Widget();
          form.domNode.appendChild(target.domNode);
          port.set('name', 'fcport-' + i + '-target');
          port.set('value', fcport.target);

        }

        doSubmit({
          url: '/services/fiberchanneltotarget/',
          form: form
        });

      }
    });

    return FCPorts;
});
