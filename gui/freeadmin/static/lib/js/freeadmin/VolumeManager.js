define([
  "dojo/_base/array",
  "dojo/_base/connect",
  "dojo/_base/declare",
  "dojo/_base/lang",
  "dojo/dom-attr",
  "dojo/dom-class",
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
  "dojox/widget/Toaster",
  "dojo/text!freeadmin/templates/volumemanager.html"
  ], function(
  array,
  connect,
  declare,
  lang,
  domAttr,
  domClass,
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
  Toaster,
  template) {

    var PER_NODE_WIDTH = 49;
    var PER_NODE_HEIGHT = 26;
    var HEADER_HEIGHT = 14;
    var EMPTY_WIDTH = 6;
    var EMPTY_NODE = 19;

    var Disk = declare("freeadmin.Disk", [ _Widget, _Templated ], {
      //templateString: '<div class="disk" style="width: 38px; height: 16px; text-align: center; float: left; background-color: #eee; border: 1px solid #ddd; margin: 2px; padding: 2px;">${name}</div>',
      templateString: '<div class="disk" style="margin: 2px; padding: 2px; width: 40px;">${name}</div>',
      name: "",
      serial: "",
      size: "",
      vdev: null,
      manager: null,
      disksAvail: null,
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
      addToRow: function(vdev, row, col) {
        try {
          vdev.validate(this);

          if(query("tr", vdev.dapTable).length - 1 < row + 1) {
            var tr = domConst.create("tr", null, vdev.dapTable.childNodes[0]);
            for(var i=0;i<16;i++) {
              domConst.create("td", null, tr);
            }
          }
          var cell = query("tr:nth-child("+(row+2)+") td:nth-child("+(col+2)+")", vdev.dapTable)[0];
          var index = this.disksAvail.disks.indexOf(this);
          this.disksAvail.disks.splice(index, 1);
          cell.appendChild(this.domNode);
          vdev.disks.push(this);
          this.disksAvail.update();
          this.set('vdev', vdev);
          this.manager._disksCheck(vdev);
          vdev.colorActive();
        } catch(e) {
          var me = this;
          connect.publish("volumeManager", {
            message: e.message,
            type: "fatal",
            duration: 500
          });

        }
      },
      remove: function() {
        this.disksAvail.disks.push(this);
        this.domNode.parentNode.removeChild(this.domNode);
        this.vdev.disks.splice(this.vdev.disks.indexOf(this), 1);
        this.disksAvail.update();
        this.manager._disksCheck(this.vdev);
        this.vdev.colorActive();
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

    var DisksAvail = declare("freeadmin.DisksAvail", [ _Widget, _Templated ], {
      templateString: '<div><span data-dojo-attach-point="dapSize"></span> (<span data-dojo-attach-point="dapNum"></span> drives)</div>',
      disks: [],
      size: "",
      postCreate: function() {
        for(var i in this.disks) {
          this.disks[i].disksAvail = this;
        }
        this.update();
      },
      update: function() {
        this.dapSize.innerHTML = this.size;
        this.dapNum.innerHTML = this.disks.length;
      }
    });

    var Vdev = declare("freeadmin.Vdev", [ _Widget, _Templated ], {
      templateString: '<tr><td data-dojo-attach-point="dapVdevType" style="width: 110px;"><br /><span data-dojo-attach-point="dapNumCol"></span><br /><span data-dojo-attach-point="dapDelete">Delete</span></td><td><div style="position: relative"><div class="vdev" data-dojo-attach-point="dapResMain" style="width: 5px; position: absolute;"><div data-dojo-attach-point="dapRes" style="position: absolute;"></div></div><table border="0" cellspacing="0" cellpadding="0" class="groupDisksTable" data-dojo-attach-point="dapTable"><tr><th class="first"></th><th>1</th><th>2</th><th>3</th><th>4</th><th>5</th><th>6</th><th>7</th><th>8</th><th>9</th><th>10</th><th>11</th><th>12</th><th>13</th><th>14</th><th>15</th></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr></table></div></td></tr>',
      widgetsInTemplate: true,
      numDisks: 0,
      type: "",
      disks: [],
      initialDisks: [],
      can_delete: false,
      vdev: null,
      rows: 1,
      manager: null,
      validate: function(disk) {
        var valid = true;
        for(var key in this.disks) {
          var each = this.disks[key];
          if(each.size != disk.size) {
            valid = false;
            break;
          }
        }
        if(valid === false) {
          throw new Object({message: "Disk size mismatch"});
        }
      },
      colorActive: function() {

        var cols = this.disks.length / this.rows;
        query("tr", this.dapTable).forEach(function(item, idx) {
          if(idx == 0) return;
          query("td", item).forEach(function(item, idx) {
            if(idx > cols) {
              domClass.remove(item, "active");
            } else {
              domClass.add(item, "active");
            }
          });
        });
        query("th", this.dapTable).forEach(function(item, idx) {
            if(idx > cols) {
              domClass.remove(item, "active");
            } else {
              domClass.add(item, "active");
            }
        });

      },
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
        }).placeAt(this.dapVdevType, 0);
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
            lastH: 0,
            lastW: 0,
            animateSizing: false, // Animated cause problem to get the size in onResize
            intermediateChanges: true,
            minHeight: 43,
            minWidth: 5,
            _disks: null,
            _checkConstraints: function(newW, newH){
              var availDisks = me.disks.length + me.manager.getAvailDisksNum();
              newH -= HEADER_HEIGHT;
              newW -= EMPTY_WIDTH;

              var numRows = (newH / PER_NODE_HEIGHT);
              var floorR = Math.floor(numRows);
              if(numRows - floorR >= 0.5) {
                floorR += 1;
              }
              if(floorR < 1) floorR = 1; // At least 1 row
              newH = (floorR * PER_NODE_HEIGHT) + HEADER_HEIGHT;

              var numNodes, floor;
              var currentW = PER_NODE_WIDTH * me.disks.length;
              if(newW > currentW) {
                numNodes = (newW - currentW) / EMPTY_NODE;

                floor = Math.floor(numNodes);
                if(numNodes - floor >= 0.5) {
                  floor += 1;
                }
                if(floor < 0) floor = 0; // Non-negative disks
                newW = EMPTY_WIDTH + currentW + floor * EMPTY_NODE;
                floor += currentW / PER_NODE_WIDTH;
              } else {
                numNodes = newW / PER_NODE_WIDTH;
                floor = Math.floor(numNodes);
                if(numNodes - floor >= 0.5) {
                  floor += 1;
                }
                if(floor < 0) floor = 0; // Non-negative disks
                newW = (floor * PER_NODE_WIDTH) + EMPTY_WIDTH;

              }

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
              me.rows = floorR; // dirty hack to set number of rows in group

              return { w: newW, h: newH };
            },
            getSlots: function() {
              var width = domStyle.get(this.domNode.parentNode, "width");
              return Math.floor(width / PER_NODE_WIDTH);
            },
            onResize: function(e) {
              if(this._disks !== null) {

                /*
                 * We need to take care manipulating me.disks
                 * because disk.remove() will interact over the same
                 * structure
                 */
                while(me.disks.length > 0) {
                  me.disks[0].remove();
                }

                for(var i=0;i<this._disks.length;i++) {
                  for(var j=0;j<this._disks[i].length;j++) {
                    var disk = this._disks[i][j];
                    var index = me.disks.indexOf(disk);
                    console.log (i, j);
                    if(index == -1) {
                      disk.addToRow(me, i, j);
                    }
                  }
                }

                var extraRows = query("tr", me.dapTable).length - this._disks.length - 1;
                for(var i=0;i<extraRows;i++) {
                  query("tr:nth-child("+(this._disks.length+2)+")", me.dapTable).forEach(domConst.destroy);
                }

                this._disks = null;
              }
              // Set the new correct width after releasing mouse
              domStyle.set(this.targetDomNode, "width", (EMPTY_WIDTH + (me.disks.length / me.rows) * PER_NODE_WIDTH) + "px");

              me.manager._disksCheck(me);
            }
        }, this.dapRes);
        domStyle.set(this.dapResMain, "height", (HEADER_HEIGHT + PER_NODE_HEIGHT) + "px");
        this.resize.startup();

        if(this.can_delete === true) {

          on(this.dapDelete, "click", function() {
            while(true) {
              if(me.disks.length == 0) break;
              me.disks[0].remove();
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
        for(var i in this._avail_disks) {
          var dAvail = this._avail_disks[i];
          this.dapDisksTable.appendChild(dAvail.domNode);
        }
      },
      getAvailDisksNum: function() {
        var num = 0;
        for(var i in this._avail_disks) {
          num += this._avail_disks[i].disks.length;
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

        this._avail_disks = [];
        for(var size in this.disks) {
          var disks = this.disks[size];
          var avail_disks = [];
          for(var key in disks) {
            avail_disks.push(new Disk({
              manager: this,
              name: disks[key]['dev'],
              size: size,
              serial: disks[key]['serial']
            }));
          }
          var dAvail = new DisksAvail({
            disks: avail_disks,
            size: size,
          });
          this._avail_disks.push(dAvail);
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

        new Toaster({
          messageTopic: "volumeManager",
          separator: "<hr/>",
          positionDirection: "br-left",
          duration: "0"
        }, this.dapToaster);

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

        var disksrows = null;
        var total = slots * rows;
        // Clone all_disks from _avail_disks
        var all_disks = {};
        for(var i in this._avail_disks) {
          var dAvail = this._avail_disks[i];
          all_disks[dAvail.size] = [];
          for(var j in dAvail.disks) {
            all_disks[dAvail.size].push(dAvail.disks[j]);
          }
        }

        // Add disks from current vdev to all_disks
        if(vdev.disks.length > 0) {
          for(var i in vdev.disks) {
            var disk = vdev.disks[i];
            all_disks[disk.size].push(disk);
          }
        }

        // Find disks for the same size for a row
        for(var size in all_disks) {
          var bysize = all_disks[size];
          if(bysize.length >= total) {
            disksrows = [];
            for(var i=0;i<rows;i++) {
              disksrows.push(bysize.slice(0, slots));
              bysize.splice(0, slots);
            }
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
              // .set will trigger onChange, ignore it once
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
            vdev.dapNumCol.innerHTML = rows + numdisks + ' disks<br />optimal';
          } else {
            vdev.dapNumCol.innerHTML = rows + numdisks + ' disks<br />non-optimal';
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
