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

    var PER_NODE_WIDTH = 48;
    var PER_NODE_HEIGHT = 26;

    var Disk = declare("freeadmin.Disk", [ _Widget, _Templated ], {
      templateString: '<div class="disk" style="width: 38px; height: 16px; text-align: center; float: left; background-color: #eee; border: 1px solid #ddd; margin: 2px; padding: 2px;">${name}</div>',
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
              break;
            }
          }
        } else {
          this.remove();
        }
      }
    });

    var Vdev = declare("freeadmin.Vdev", [ _Widget, _Templated ], {
      templateString: '<tr><td data-dojo-attach-point="dapVdevType" style="width: 110px;"></td><td><div class="vdev" data-dojo-attach-point="dapResMain" style="width: 5px; position: relative;"><div data-dojo-attach-point="dapRes" style="position: absolute;"></div></div></td><td data-dojo-attach-point="dapNumCol"></td><td data-dojo-attach-point="dapDelete">Delete</td></tr>',
      widgetsInTemplate: true,
      numDisks: 0,
      type: "",
      disks: [],
      initialDisks: [],
      can_delete: false,
      vdev: null,
      manager: null,
      getChildren: function() {
        // This needs investigating
        // For some reason chidlren are not retrieved automatically
        return [this.vdevtype, this.vdisks];
      },
      postCreate: function() {
        var me = this;
        this.disks = [];

        this.vdevtype = new Select({
          options: [
            { label: "RaidZ", value: "raidz" },
            { label: "RaidZ2", value: "raidz2" },
            { label: "RaidZ3", value: "raidz3" },
            { label: "Mirror", value: "mirror" },
            { label: "Stripe", value: "stripe" },
            { label: "Log (ZIL)", value: "log" },
            { label: "Cache (L2ARC)", value: "cache" }
          ],
        }).placeAt(this.dapVdevType);
        if(this.type) {
          this.vdevtype.set('value', this.type);
        }
        this.vdevtype.startup();

        this.vdisks = new _Widget();
        this.dapResMain.appendChild(this.vdisks.domNode);

        this.resize = new ResizeHandle({
            targetContainer: this.dapResMain,
            resizeAxis: "xy",
            activeResize: false,
            _extraRows: 0,
            animateSizing: false, // Animated cause problem to get the size in onResize
            _checkConstraints: function(newW, newH){
              var availDisks = me.disks.length + me.manager.getAvailDisksNum();

              var numRows = (newH / PER_NODE_HEIGHT);
              var floorR = Math.floor(numRows);
              if(numRows - floorR >= 0.5) {
                floorR += 1;
              }
              if(floorR < 1) floorR = 1;
              newH = floorR * PER_NODE_HEIGHT;

              var numNodes = newW / PER_NODE_WIDTH;
              var floor = Math.floor(numNodes);
              if(numNodes - floor >= 0.5) {
                floor += 1;
              }
              if(floor < 0) floor = 0;
              newW = floor * PER_NODE_WIDTH;

              var disks = me.manager._disksForVdev(me, floor, floorR);

              if(floor * floorR > availDisks || disks === null) {
                 newH = this.lastH;
                 newW = this.lastW;
              } else {
                if(this.lastH != newH || this.lastW != newW) {
                  me.manager._disksCheck(me, false, floor, floorR);
                  this.lastH = newH;
                  this.lastW = newW;
                  this._disks = disks;
                }
              }

              return { w: newW, h: newH };
            },
            minHeight: 30,
            minWidth: 30,
            intermediateChanges: true,
            getSlots: function() {
              var width = domStyle.get(this.domNode.parentNode, "width");
              return Math.floor(width / PER_NODE_WIDTH);
            },
            onResize: function(e) {
              if(this._disks !== null) {

                for(var i=0,len=me.disks.length;i<len;i++) {
                  var disk = me.disks[0];
                  var index = this._disks[0].indexOf(disk);
                  if(index == -1) {
                    disk.remove();
                  }
                }
                for(var i in this._disks[0]) {
                  var disk = this._disks[0][i];
                  var index = me.disks.indexOf(disk);
                  if(index == -1) {
                    disk.addToRow(me);
                  }
                }

                for(var i=1;i<this._disks.length;i++) {
                  var vdev = me.manager.addVdev({
                    can_delete: true,
                    initialDisks: this._disks[i],
                    type: me.vdevtype.get("value")
                  });
                }
                this._disks = null;
              }
              domStyle.set(this.targetDomNode, "height", PER_NODE_HEIGHT + "px");
              me.manager._disksCheck(me);

              lang.hitch(me.manager, me.manager.drawAvailDisks)();
            }
        }, this.dapRes);
        domStyle.set(this.dapResMain, "height", PER_NODE_HEIGHT + "px");
        this.resize.startup();

        if(this.can_delete === true) {

          var me = this;
          on(this.dapDelete, "click", function() {
            while(true) {
              if(me.disks.length == 0) break;
              var disk = me.disks[0].remove();
            }
            me.destroy();
          });

        } else {
          domConst.destroy(this.dapDelete);
        }

        on(this.vdevtype, "change", function() {
          if(this._stopEvent !== true) {
            me.manager._disksCheck(me, true);
          } else {
            this._stopEvent = false;
          }
        });
        this.manager._disksCheck(this);

        if(this.numDisks !== undefined) {
          for(var i=0;i<this.numDisks;i++) {
            var disk = this.manager.popAvailDisk();
            if(disk) {
              disk.addToRow(this);
            }
          }
        }

        if(this.initialDisks.length > 0) {
          for(var i in this.initialDisks) {
            this.initialDisks[i].addToRow(this);
          }
        }

        domStyle.set(this.resize.domNode.parentNode, "width", this.disks.length * PER_NODE_WIDTH + "px");

      }
    });

    var VolumeManager = declare("freeadmin.VolumeManager", [ _Widget, _Templated ], {
      templateString: template,
      disks: "{}",
      url: "",
      url_progress: "",
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
          domStyle.set(tr, "height", (PER_NODE_HEIGHT + 2) + "px");
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
      getAvailDisksNum: function() {
        var num = 0;
        for(var size in this._avail_disks) {
          num += this._avail_disks[size].length;
        }
        return num;
      },
      popAvailDisk: function() {
        var disk = null;
        for(var size in this._avail_disks) {
          for(var idx in this._avail_disks[size]) {
            disk = this._avail_disks[size][idx];
            break;
          }
          if(disk !== null) break;
        }
        return disk;
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
          lang.hitch(me, me.addVdev)({can_delete: true});
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

        this.addVdev({can_delete: false});

        //this._supportingWidgets.push(slider);

        this.inherited(arguments);

      },
      addVdev: function(attrs) {

        var vdev;
        attrs['manager'] = this;
        vdev = new Vdev(attrs);
        domConst.place(vdev.domNode, this.dapLayoutTable);

        this._layout.push(vdev);
        return vdev;

      },
      _disksForVdev: function(vdev, slots, rows) {

        var disksrows = [];
        // Clone all_disks from _avail_disks
        var all_disks = {};
        for(var size in this._avail_disks) {
          all_disks[size] = [];
          for(var i in this._avail_disks[size]) {
            all_disks[size].push(this._avail_disks[size][i]);
          }
        }
        // Add disks from current vdev to all_disks
        if(vdev.disks.length > 0) {
          for(var i in vdev.disks) {
            var disk = vdev.disks[i];
            all_disks[disk.size].push(disk);
          }
        }

        for(var i=0;i<rows;i++) {

          var disks = [];
          for(var size in all_disks) {
            var bysize = all_disks[size];
            if(bysize.length >= slots) {
              disks = bysize.slice(0, slots);
              bysize.splice(0, slots);
              break;
            }
          }
          if(disks.length > 0) {
            disksrows.push(disks);
          } else {
            disksrows = null;
            break;
          }

        }

        return disksrows;

      },
      _optimalCheck: {
          'mirror': function(num) {
            return num == 2;
          },
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
      },
      _disksCheck: function(vdev, manual, cols, rows) {

        var found = false, has_check = false, numdisks;
        if(cols !== undefined) {
          numdisks = cols;
        } else {
          numdisks = vdev.disks.length;
        }

        if(manual !== true) {
          for(var key in this._optimalCheck) {
            if(this._optimalCheck[key](numdisks)) {
              vdev.vdevtype._stopEvent = true;
              vdev.vdevtype.set('value', key);
              found = true;
              has_check = true;
              break;
            }
          }
          if(found == false) {
            var vdevtype = vdev.vdevtype.get("value");
            has_check = this._optimalCheck[vdevtype] !== undefined;
          }
        } else {
          var vdevtype = vdev.vdevtype.get("value");
          var optimalf = this._optimalCheck[vdevtype];
          if(optimalf !== undefined) {
            found = optimalf(numdisks);
            has_check = true;
          }
        }

        if(rows !== undefined && rows > 1) {
          rows = rows +'x ';
        } else {
          rows = '';
        }
        if(has_check) {
          if(found) {
            vdev.dapNumCol.innerHTML = rows + numdisks + ' disks; optimal';
          } else {
            vdev.dapNumCol.innerHTML = rows + numdisks + ' disks; non-optimal';
          }
        } else {
          vdev.dapNumCol.innerHTML = rows + numdisks + ' disks';
        }
      },
      submit: function() {
        /*
         * Set all field names for layout before submit
         * It is easier than keep track of the fields on-the-fly
         */
        for(var i=0;i<this._layout.length;i++) {
          var vdev = this._layout[i];
          vdev.vdevtype.set('name', 'layout-' + i + '-vdevtype');
          vdev.vdisks.set('name', 'layout-' + i + '-disks');
          var disks = [];
          for(var key in vdev.disks) {
            disks.push(vdev.disks[key].get("name"));
          }
          vdev.vdisks.set('value', disks);
          domAttr.set(vdev.vdisks.domNode.parentNode, "data-dojo-name", 'layout-' + i + '-disks');
        }
        this._total_vdevs.set('value', this._layout.length);
        doSubmit({
          url: this.url,
          form: this._form,
          progressbar: this.url_progress
        });
      }
    });
    return VolumeManager;
});
