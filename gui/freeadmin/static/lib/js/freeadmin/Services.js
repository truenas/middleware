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
  "dijit/form/CheckBox",
  "dijit/form/Form",
  "dojox/widget/Standby",
  "dojo/text!freeadmin/templates/service_entry.html",
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
  CheckBox,
  Form,
  Standby,
  template) {

    var URL_MAP = {
      'iscsitarget': function() { Menu.openISCSI(); }
    };

    var NAME_MAP = {
      'afp': gettext('AFP'),
      'domaincontroller': gettext('Domain Controller'),
      'dynamicdns': gettext('Dynamic DNS'),
      'ftp': gettext('FTP'),
      'iscsitarget': gettext('iSCSI'),
      'lldp': gettext('LLDP'),
      'nfs': gettext('NFS'),
      'rsync': gettext('Rsync'),
      'smartd': gettext('S.M.A.R.T.'),
      'snmp': gettext('SNMP'),
      'ssh': gettext('SSH'),
      'cifs': gettext('SMB'),
      'tftp': gettext('TFTP'),
      'ups': gettext('UPS'),
      'webdav': gettext('WebDAV'),
    }

    var Service = declare("freeadmin.Service", [ _Widget, _Templated ], {
      templateString: template,
      serviceList: null,
      name: null,
      state: null,
      enable: null,
      postCreate: function() {

        var me = this;

        if(NAME_MAP[me.name]) {
          me.dapName.innerHTML = NAME_MAP[me.name];
        } else {
          me.dapName.innerHTML = me.name;
        }

        me.startstop = new Button({}, me.dapStartStop);

        me.onboot = new CheckBox({
          checked: me.enable
        }, me.dapOnBoot);

        on(me.startstop, "click", function() {
          me.startLoading();
          if(me.state == 'RUNNING') {
            Middleware.call('service.stop', [me.name], function(result) {
              if(!result) {
                me.state = 'STOPPED';
                me.sync();
              }
              me.stopLoading();
            });
          } else {
            Middleware.call('service.start', [me.name], function(result) {
              if(result) {
                me.state = 'RUNNING';
                me.sync();
              }
              me.stopLoading();
            });
          }
        });

        domStyle.set(me.dapSettings, "cursor", "pointer");
        on(me.dapSettings, "click", function() {
          var map = URL_MAP[me.name];
          if(map) {
            map();
            return;
          }
          var url = me.serviceList.urls[me.name];
          if(url)
            editObject('Settings', url);
        });
        me.sync();

        this.inherited(arguments);

      },
      startLoading: function() {
        var me = this;
        me.startstop.set('disabled', true);
        me.onboot.set('disabled', true);
      },
      stopLoading: function() {
        var me = this;
        me.startstop.set('disabled', false);
        me.onboot.set('disabled', false);
      },
      sync: function() {
        var me = this;
        if(me.state == 'RUNNING') {
          me.dapLight.src = '/static/images/ui/misc/green_light.png';
        } else {
          me.dapLight.src = '/static/images/ui/misc/red_light.png';
        }
        me.startstop.set('label', (me.state == 'RUNNING') ? gettext('Stop Now') : gettext('Start Now'));
      }
    });

    var ServiceList = declare("freeadmin.ServiceList", [ _Widget, _Templated ], {
      templateString: '<div data-dojo-attach-point="dapServiceList"><table data-dojo-attach-point="dapTable" style="padding-left: 0px;"></table></div>',
      urls: null,
      postCreate: function() {

        var me = this;

        me.urls = json.parse(me.urls);

        Middleware.call('service.query', [[], {"order_by": ["service"]}], function(result) {
          for(var i=0;i<result.length;i++) {
            var item = result[i];
            var service = Service({
              serviceList: me,
              name: item.service,
              state: item.state,
              enable: item.enable
            })
            me.dapTable.appendChild(service.domNode);
          }
        });

        this.inherited(arguments);

      }
    });

    return ServiceList;
});
