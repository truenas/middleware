define([
  "dojo/_base/array",
  "dojo/_base/declare",
  "dojo/_base/lang",
  "dojo/dom-attr",
  "dojo/dom-construct",
  "dojo/dom-style",
  "dojo/json",
  "dojo/on",
  "dojo/query",
  "dojo/topic",
  "dijit/_Widget",
  "dijit/_TemplatedMixin",
  "dijit/registry",
  "dijit/Tooltip",
  "dijit/form/Button",
  "dijit/form/CheckBox",
  "dijit/form/Form",
  "dijit/form/Select",
  "dijit/form/TextBox",
  "dijit/form/ToggleButton",
  "dijit/layout/TabContainer",
  "dijit/layout/ContentPane",
  "dojox/layout/ResizeHandle",
  "dojo/text!freeadmin/templates/volumemanager.html"
  ], function(
  array,
  declare,
  lang,
  domAttr,
  domConst,
  domStyle,
  json,
  on,
  query,
  topic,
  _Widget,
  _Templated,
  registry,
  Tooltip,
  Button,
  CheckBox,
  Form,
  Select,
  TextBox,
  ToggleButton,
  TabContainer,
  ContentPane,
  ResizeHandle,
  template) {

    var Disk = declare("freeadmin.Disk", [ _Widget, _Templated ], {
      templateString: '<div class="disk" style="width: 38px; text-align: center; float: left; background-color: #eee; border: 1px solid #ddd; margin: 2px; padding: 2px;">${name}</div>',
      name: "",
      serial: "",
      size: "",
      vdev: null,
      manager: null,
      postCreate: function() {
        var me = this;
        new Tooltip({
          showDelay: 200,
          connectId: [me.domNode],
          label: "Size: " + me.size
          //label: "Size: " + me.size + "<br />Serial: " + me.serial
        });
        on(this.domNode, "click", function() {
          lang.hitch(me, me.onClick)();
        });
      },
      addToRow: function(row) {
        var index = this.manager._avail_disks[this.size].indexOf(this);
        this.manager._avail_disks[this.size].splice(index, 1);
        this.domNode.parentNode.removeChild(this.domNode);
        row.resize.domNode.parentNode.appendChild(this.domNode);
        row.disks.push(this);
        lang.hitch(this.manager, this.manager.drawAvailDisks)();
        this.set('vdev', row);
        this.manager._disksCheck(row);
      },
      remove: function() {
        this.manager._avail_disks[this.get("size")].push(this);
        this.domNode.parentNode.removeChild(this.domNode);
        this.vdev.disks.splice(this.vdev.disks.indexOf(this), 1);
        lang.hitch(this.manager, this.manager.drawAvailDisks)();
        this.manager._disksCheck(this.vdev);
        this.set('vdev', null);
      },
      onClick: function() {
        if(this.vdev === null) {
          for(var key in this.manager._layout) {
            var row = this.manager._layout[key];
            var slots = lang.hitch(row.resize, row.resize.getSlots)();
            if(slots > row.disks.length) {
              this.addToRow(row);
            }
          }
        } else {
          this.remove();
        }
      }
    });

    var VolumeManager = declare("freeadmin.VolumeManager", [ _Widget, _Templated ], {
      templateString: template,
      disks: "{}",
      url: "",
      dedup_warning: "",
      extend: "",
      add_label: 'Add Volume<br/ ><span style="color: red;">Existing data will be cleared</span>',
      extend_label: "Extend Volume",
      _layout: [],
      _total_vdevs: null,
      _initial_vdevs: null,
      _form: null,
      _avail_disks: [],
      drawAvailDisks: function() {

        domConst.empty(this.dapDisksTable);
        for(var size in this._avail_disks) {
          var tr = domConst.create("tr", null, this.dapDisksTable);
          domConst.create("th", {innerHTML: size}, tr);
          var td = domConst.create("td", null, tr);
          var disks = this._avail_disks[size];
          if(disks.length == 0) {
            td.innerHTML = "(all disks in use)";
          }
          for(var key in disks) {
            var disk = disks[key];
            td.appendChild(disk.domNode);
          }
        }
      },
      postCreate: function() {

        var me = this, volume_name, volume_add, okbtn, enc, encini;

        this._layout = [];

        this.disks = json.parse(this.disks);
        this.extend = json.parse(this.extend);

        if(!gettext) {
          gettext = function(s) { return s; }
        }

        this._form = new Form({}, this.dapForm);
        this._form.startup();

        new TextBox({
          name: "__all__",
          type: "hidden"
        }, this.dapAll);

        new TextBox({
          name: "layout-__all__",
          type: "hidden"
        }, this.dapLayoutAll);

        volume_name = new TextBox({
          name: "volume_name",
          onKeyUp: function() {
            if(this.get('value') == '') {
              volume_add.set('disabled', false);
            } else {
              volume_add.set('disabled', true);
            }
          }
        }, this.dapName);

        volume_add = new Select({
          name: "volume_add",
          options: this.extend,
          value: "",
          onChange: function(val) {
            if(val != '') {
              volume_name.set('disabled', true);
              enc.set('disabled', true);
              encini.set('disabled', true);
              okbtn.set('label', me.extend_label);
            } else {
              volume_name.set('disabled', false);
              enc.set('disabled', false);
              encini.set('disabled', false);
              okbtn.set('label', me.add_label);
            }
          }
        }, this.dapExtend);

        new Select({
            name: "dedup",
            options: [
                { label: "On", value: "on" },
                { label: "Off", value: "off" },
            ],
            value: "off"
        }, this.dapDedup);

        enc = new CheckBox({
            name: "encryption"
        }, this.dapDiskEnc);

        encini = new CheckBox({
            name: "encryption_inirand",
            disabled: true
        }, this.dapDiskEncIni);

        on(enc, "click", function() {
            if(this.get("value") == "on") {
                encini.set('disabled', false);
            } else {
                encini.set('disabled', true);
            }
        });

        this._avail_disks = {};
        for(var size in this.disks) {
          var disks = this.disks[size];
          this._avail_disks[size] = [];
          for(var key in disks) {
            this._avail_disks[size].push(new Disk({
              manager: this,
              name: disks[key]['dev'],
              size: size,
              serial: disks[key]['serial']
            }));
          }
        }

        lang.hitch(this, this.drawAvailDisks)();

        /*
         * Add extra row for the layout
         */
        var add_extra = new Button({
          label: "Add Extra Row"
        }, this.dapLayoutAdd);
        on(add_extra, "click", function(evt) {
          lang.hitch(me, me.addVdev)(true);
        });

        okbtn = new Button({
          label: this.add_label,
          onClick: function() {
            lang.hitch(me, me.submit)();
          }
        }, this.dapAdd);

        new Button({
          label: "Cancel",
          onClick: function() {
            cancelDialog(this);
          }
        }, this.dapCancel);


        /*
        topic.subscribe("/dojo/resize/start", function(inst) {
            console.log("here", inst);
        });
        topic.subscribe("/dojo/resize/stop", function(inst) {
            console.log("here", inst);
        });
        */

        this._total_vdevs = new _Widget({
            name: "layout-TOTAL_FORMS",
            value: 0
        });
        this._initial_vdevs = new _Widget({
            name: "layout-INITIAL_FORMS",
            value: 0
        });
        this._form.domNode.appendChild(this._total_vdevs.domNode);
        this._form.domNode.appendChild(this._initial_vdevs.domNode);

        this.addVdev(false);

        //this._supportingWidgets.push(slider);

        this.inherited(arguments);

      },
      addVdev: function(removable) {

        var me = this;
        var disks = [];
        var vdevt = new Select({
          options: [
            { label: "RaidZ", value: "raidz" },
            { label: "RaidZ2", value: "raidz2" },
            { label: "RaidZ3", value: "raidz3" },
            { label: "Mirror", value: "mirror" },
            { label: "Stripe", value: "stripe" },
            { label: "Log (ZIL)", value: "log" },
            { label: "Cache (L2ARC)", value: "cache" }
          ],
        });

        var tr = domConst.create("tr");

        var td = domConst.create("td", null, tr);
        domConst.place(vdevt.domNode, td);

        var td = domConst.create("td", null, tr);
        var div = domConst.create("div", null, td);
        var div2 = domConst.create("div");
        div.appendChild(div2);

        var vdevdisks = new _Widget();
        div.appendChild(vdevdisks.domNode);

        var resize = new ResizeHandle({
            targetContainer: div,
            resizeAxis: "x",
            activeResize: true,
            minHeight: 30,
            maxHeight: 30,
            minWidth: 30,
            intermediateChanges: true,
            getSlots: function() {
                var width = domStyle.get(this.domNode.parentNode, "width");
                return Math.floor(width / 48);
            },
            onResize: function(e) {
              var resize = this, drawer;
              var numdisks = this.getSlots();
              drawer = null;
              for(var key in me._avail_disks) {
                if(me._avail_disks[key].length > 0) {
                  drawer = me._avail_disks[key];
                  break;
                }
              }
              if(numdisks > this.entry.disks.length && drawer) {
                // add new disk to resizer
                var newdisk = drawer[0].addToRow(this.entry);
              } else if(numdisks < this.entry.disks.length) {
                query(".disk:last-child", this.domNode.parentNode).forEach(function(node) {
                    var disk = registry.getEnclosingWidget(node);
                    disk.remove();
                });

              }
              me._disksCheck(resize.entry);

              lang.hitch(me, me.drawAvailDisks)();
            }
        }, div2);
        domStyle.set(div, "height", "30px");
        domStyle.set(div, "width", "30px");
        domStyle.set(div, "position", "relative");
        domStyle.set(div2, "position", "absolute");
        resize.startup();

        var numcol = domConst.create("td", null, tr);

        if(removable) {

          var me = this;
          var td = domConst.create("td", {innerHTML: "Delete"}, tr);
          on(td, "click", function() {
            while(true) {
                if(this.entry.disks.length == 0) break;
                var disk = this.entry.disks[0].remove();
            }
            domConst.destroy(tr);
          });

        }

        domConst.place(tr, this.dapLayoutTable);

        var entry = {
          vdev: vdevt,
          tr: tr,
          disks: disks,
          resize: resize,
          vdisks: vdevdisks,
          numcol: numcol
        };
        resize.entry = entry;
        td.entry = entry;

        on(vdevt, "change", function() {
            me._disksCheck(entry, disks.length);
        });
        this._disksCheck(entry, disks.length);

        this._layout.push(entry);

      },
      _disksCheck: function(entry) {
        var check = {
          'raidz': function(num) {
              if(num < 3) return false;
              return (Math.log(num - 1) / Math.LN2) % 1 == 0;
          },
          'raidz2': function(num) {
              if(num < 4) return false;
              return (Math.log(num - 2) / Math.LN2) % 1 == 0;
          },
          'raidz3': function(num) {
              if(num < 5) return false;
              return (Math.log(num - 3) / Math.LN2) % 1 == 0;
          }
        };
        var vdevtype = entry.vdev.get("value");
        var optimalf = check[vdevtype];
        var numdisks = entry.disks.length;
        if(optimalf !== undefined) {
          if(optimalf(numdisks)) {
            entry.numcol.innerHTML = numdisks + ' disks; optimal';
          } else {
            entry.numcol.innerHTML = numdisks + ' disks; non-optimal';
          }
        } else {
          entry.numcol.innerHTML = numdisks + ' disks';
        }
      },
      submit: function() {
        /*
         * Set all field names for layout before submit
         * It is easier than keep track of the fields on-the-fly
         */
        for(var i=0;i<this._layout.length;i++) {
            var entry = this._layout[i];
            entry.vdev.set('name', 'layout-' + i + '-vdevtype');
            entry.vdisks.set('name', 'layout-' + i + '-disks');
            var disks = [];
            for(var key in entry.disks) {
                disks.push(entry.disks[key].get("name"));
            }
            entry.vdisks.set('value', disks);
            domAttr.set(entry.vdisks.domNode.parentNode, "data-dojo-name", 'layout-' + i + '-disks');
        }
        this._total_vdevs.set('value', this._layout.length);
        doSubmit({
            url: this.url,
            form: this._form
        });
      }
    });
    return VolumeManager;
});
