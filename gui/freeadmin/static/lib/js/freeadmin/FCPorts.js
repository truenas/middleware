define([
  "dojo/_base/declare",
  "dojo/_base/lang",
  "dojo/dom-style",
  "dojo/json",
  "dojo/on",
  "dojo/request/xhr",
  "dijit/_Widget",
  "dijit/_TemplatedMixin",
  "dijit/TooltipDialog",
  "dijit/registry",
  "dijit/form/Button",
  "dijit/form/Form",
  "dijit/form/RadioButton",
  "dijit/form/Select",
  "dijit/popup",
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
  TooltipDialog,
  registry,
  Button,
  Form,
  RadioButton,
  Select,
  popup,
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
          name: "mode-" + me.name,
          value: "INITIATOR",
          checked: (me.mode == 'INITIATOR') ? true : false
        }, this.dapFCModeIni);

        me._mtgt = new RadioButton({
          name: "mode-" + me.name,
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

        on(me._target, 'change', lang.hitch(this, me.modeChange));
        me.modeChange();

        this.inherited(arguments);

      },
      modeChange: function() {
        var me = this;
        if(me._mtgt.get('checked') == true) {
          domStyle.set(me._target.domNode, "display", "");
          me.target = me._target.get('value');
        } else {
          domStyle.set(me._target.domNode, "display", "none");
          me.target = null;
        }
      },
      isValid: function() {
        var me = this;
        var valid = true;
        if(me._mtgt.get('checked') === true) {
          if(me._target.get('value') == '') {
            valid = false;
            var td = new TooltipDialog({
              content: "This field is required.",
              onMouseLeave: function() {
                popup.close(td);
                td.destroyRecursive();
              }
            });
            popup.open({
              popup: td,
              around: me._target.domNode,
              orient: ["above", "after", "below-alt"]
            });
          }
        }
        return valid;
      }
    });

    var FCPorts = declare("freeadmin.FCPorts", [ _Widget, _Templated ], {
      templateString: '<div data-dojo-attach-point="dapFCPorts"><table data-dojo-attach-point="dapTable" style="padding-left: 0px;"></table><div data-dojo-attach-point="dapSubmit"></div></div>',
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
      isValid: function() {
        var me = this;
        var valid = true;
        for(var i=0;i<me.ports.length;i++) {
          valid = valid & me.ports[i].isValid();

        }
        return valid;
      },
      submit: function() {

        if(!this.isValid()) return;

        var me = this;
        if(me._form) me._form.destroyRecursive();
        me._form = new Form({});
        me.domNode.appendChild(me._form.domNode);

        for(var i=0;i<me.ports.length;i++) {
          var fcport = me.ports[i];
          var port = new _Widget();
          me._form.domNode.appendChild(port.domNode);
          port.set('name', 'fcport-' + i + '-port');
          port.set('value', fcport.name);

          var target = new _Widget();
          me._form.domNode.appendChild(target.domNode);
          target.set('name', 'fcport-' + i + '-target');
          target.set('value', fcport.target || '');

        }

        me._submit.set('disabled', true);

        doSubmit({
          url: '/services/fiberchanneltotarget/',
          form: me._form,
          onComplete: function(data) {
            me._submit.set('disabled', false);
          }
        });

      }
    });

    return FCPorts;
});
