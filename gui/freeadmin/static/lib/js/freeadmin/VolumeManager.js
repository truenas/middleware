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
  "dojo/mouse",
  "dojo/on",
  "dojo/query",
  "dojo/store/Memory",
  "dojo/store/Observable",
  "dojo/topic",
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
  "dijit/form/ToggleButton",
  "dijit/layout/TabContainer",
  "dijit/layout/ContentPane",
  "dijit/popup",
  "dojox/layout/ResizeHandle",
  "dojox/string/sprintf",
  "dojox/widget/Toaster",
  "dojo/text!freeadmin/templates/volumemanager.html",
  "dojo/text!freeadmin/templates/volumemanager_diskgroup.html"
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
  mouse,
  on,
  query,
  Memory,
  Observable,
  topic,
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
  ToggleButton,
  TabContainer,
  ContentPane,
  popup,
  ResizeHandle,
  sprintf,
  Toaster,
  template,
  diskGroupTemplate) {

    var PER_NODE_WIDTH = 49;
    var PER_NODE_HEIGHT = 27;
    var HEADER_HEIGHT = 14;
    var EMPTY_WIDTH = 6;
    var EMPTY_NODE = 19;

    var SI_MAP = [
      ['PB', 1000000000000000],
      ['TB', 1000000000000],
      ['GB', 1000000000],
      ['MB', 1000000],
      ['kB', 1000],
      ['B', 1],
    ];

    var IEC_MAP = [
      ['PiB', 1125899906842624],
      ['TiB', 1099511627776],
      ['GiB', 1073741824],
      ['MiB', 1048576],
      ['KiB', 1024],
      ['B', 1],
    ];

    //TODO: move to another lib
    var humanizeSize = function(bytes, mode) {
      if(!mode) mode = "IEC";
      var MAP;
      if(mode == "IEC")
        MAP = IEC_MAP;
      else
        MAP = SI_MAP;
      for(var i=0;i<MAP.length;i++) {
        if(bytes > MAP[i][1]) {
          return sprintf("%.2f %s", bytes / MAP[i][1], MAP[i][0]);
        }
      }
      return bytes + ' B';
    }

    var Disk = declare("freeadmin.Disk", [ _Widget, _Templated ], {
      //templateString: '<div class="disk" style="width: 38px; height: 16px; text-align: center; float: left; background-color: #eee; border: 1px solid #ddd; margin: 2px; padding: 2px;">${name}</div>',
      templateString: '<div class="disk" style="margin: 2px; padding: 2px; width: 40px;">${name}</div>',
      name: "",
      serial: "",
      size: "",
      sizeBytes: 0,
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
            var tbody = query("tbody", vdev.dapTable)[0];
            var tr = domConst.create("tr", null, tbody);
            for(var i=0;i<16;i++) {
              domConst.create("td", null, tr);
            }
            vdev._addFormVdev(row);
          }
          var cell = query("tr:nth-child("+(row+2)+") td:nth-child("+(col+2)+")", vdev.dapTable)[0];
          var index = this.disksAvail.disks.indexOf(this);
          this.disksAvail.disks.splice(index, 1);
          cell.appendChild(this.domNode);
          vdev.disks.push(this);
          this.disksAvail.update();
          this.set('vdev', vdev);
          vdev._disksCheck();
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
        this.vdev._disksCheck();
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
      templateString: '<div data-dojo-attach-point="dapRow"><div data-dojo-attach-point="dapAdd"></div><span data-dojo-attach-point="dapIndex"></span> - <span data-dojo-attach-point="dapSize"></span> (<span data-dojo-attach-point="dapNum"></span>)</div>',
      disks: [],
      size: "",
      sizeBytes: 0,
      index: 0,
      manager: null,
      availDisks: null,
      _showNode: null,
      _tpDialog: null,
      postCreate: function() {
        var me = this;
        for(var i in this.disks) {
          this.disks[i].disksAvail = this;
        }
        this.dapAdd = new Button({
          label: "+"
        }, this.dapAdd);
        this.dapIndex.innerHTML = this.index + 1;
        this.dapSize.innerHTML = this.size;
        this.update();
        on(this.dapAdd, "click", function() {
          for(var i=0;i<me.manager._layout.length;i++) {
            var diskg = me.manager._layout[i];
            /*
             * If we have a “peer group” (drives of the same type) already
             * exists, and the largest row have more drives than X, add
             * all disks in one row as spare; otherwise, add as many as
             * possible disks to create rows for that row’s type, and use
             * rest drives as spare row.
             */
            if(diskg.disks.length > 0 && diskg.disks[0].sizeBytes == me.sizeBytes) {
              var perRow = diskg.getDisksPerRow();
              var newRows = Math.floor(me.disks.length / perRow);
              if(newRows > 0) {
                for(var i=0,len=newRows*perRow,row=diskg.rows;i<len;i++) {
                  me.disks[0].addToRow(diskg, Math.floor(diskg.disks.length / perRow), diskg.disks.length % perRow);
                }
                diskg.rows += newRows;
              }
              diskg._adjustSize();
              if(me.disks.length > 0) {
                var diskgspare = me.manager.addVdev({
                  can_delete: true,
                  type: "spare",
                  initialDisks: me.disks
                });
                diskgspare._disksCheck(true);
                diskgspare.colorActive();
              }
              diskg._disksCheck();
              me.manager.updateCapacity();
              diskg.colorActive();
              me.manager.updateSwitch();
              return;
            }
          }
          var can_delete = true;
          if(me.manager._layout[0].disks.length == 0) {
            me.manager._layout[0].remove();
            can_delete = false;
          }
          me.manager.addVdev({
            can_delete: can_delete,
            initialDisks: me.disks
          });
        });
      },
      getChildren: function() {
        if(this._tpDialog !== null) {
          return [this._tpDialog];
        }
        return [];
      },
      update: function() {
        if(this.disks.length > 0) {
          this.dapAdd.set('disabled', false);
          if(this.disks.length > 1) {
            this.dapNum.innerHTML = sprintf("%d drives, ", this.disks.length);
          } else {
            this.dapNum.innerHTML = sprintf("%d drive, ", this.disks.length);
          }
          this._showNode = domConst.create("a", {innerHTML: "show"}, this.dapNum);
          var me = this;
          on(this._showNode, mouse.enter, function() {
            me.show();
          });
          on(this._showNode, mouse.leave, function() {
            me.hide();
          });
        } else {
          this.dapAdd.set('disabled', true);
          this.dapNum.innerHTML = "no more drives";
        }
      },
      show: function() {
        var me = this;
        var table = domConst.create("table");
        for(var i=0;i<this.disks.length;i++) {
          domConst.place(sprintf("<tr><td>%s</td></tr>", this.disks[i].name), table);
        }
        this._tpDialog = new TooltipDialog({
          content: table,
          onMouseLeave: function() {
            popup.close(me._tpDialog);
            me._tpDialog.destroyRecursive();
          }
        });
        popup.open({
          popup: me._tpDialog,
          around: me._showNode,
          orient: ["above", "after", "below-alt"]
        });
      },
      hide: function() {
        if(this._tpDialog !== null) {
          popup.close(this._tpDialog);
        }
      }
    });

    var Vdev = declare("freeadmin.Vdev", [ _Widget, _Templated ], {
      templateString: diskGroupTemplate,
      widgetsInTemplate: true,
      type: "",
      disks: [],
      initialDisks: [],
      can_delete: false,
      vdev: null,
      rows: 1,
      manager: null,
      _currentAvail: null,
      _disksSwitch: null,
      _dragTooltip: null,
      _draggedOnce: false,
      _formVdevs: null,
      _isOptimal: null,
      validate: function(disk) {
        /*
         * Make sure all the disks in the disk group have the same size
         */
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
      getDisksPerRow: function() {
        return this.disks.length / this.rows;
      },
      getCurrentCols: function() {
        /*
         * This function gets the number of disks per vdev/row
         * It should works all times, even while resizing
         */
        if(this.resize._resizingCols === null) {
          return this.disks.length / this.rows;
        } else {
          return this.resize._resizingCols;
        }
      },
      getCurrentRows: function() {
        /*
         * This function gets the number of vdevs/rows
         * It should works all times, even while resizing
         */
        if(this.resize._resizingCols === null) {
          return this.rows;
        } else {
          return this.resize._resizingRows;
        }
      },
      getCurrentDiskSize: function() {
        /*
         * This function gets the current size of the disk in group
         * It should works all times, even while resizing
         */
        if(this.resize._resizingCols === null) {
          if(this.disks.length > 0) {
            return this.disks[0].sizeBytes;
          } else {
            return 0;
          }
        } else {
          if(this.resize._disks[0].length > 0) {
            return this.resize._disks[0][0].sizeBytes;
          } else {
            return 0;
          }
        }
      },
      getCapacity: function() {
        /*
         * Compute the estimated capacity
         * This takes into account the type of the disk group and
         * the size set for the swap
         *
         * Returns: capacity in bytes
         */
        var dataDisks, disks, rows, bytes;
        disks = this.getCurrentCols();
        if(disks == 0) return 0;
        rows = this.getCurrentRows();
        bytes = this.getCurrentDiskSize() - this.manager.swapSize;
        switch(this.vdevtype.get('value')) {
          case 'raidz':
            dataDisks = disks - 1;
            break;
          case 'raidz2':
            dataDisks = disks - 2;
            break;
          case 'raidz3':
            dataDisks = disks - 3;
            break;
          case 'stripe':
            dataDisks = disks;
            break;
          case 'mirror':
            dataDisks = 1;
            break;
          case 'log':
          case 'cache':
          case 'spare':
            dataDisks = 0;
            break;
        }
        return bytes * dataDisks * rows;
      },
      _optimalCheck: {
        /*
         * Lookup table for disk group type as key
         *
         * Function receives the number of disks per row (vdev)
         * and returns a boolean based on whether it is an
         * optimal config (power of 2 data disks + parity) or not.
         */
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
      _vdevTypes: [
        // Minimum number of disks to show | Label name | Value
        [3, "RaidZ", "raidz"],
        [4, "RaidZ2", "raidz2"],
        [5, "RaidZ3", "raidz3"],
        [2, "Mirror", "mirror"],
        [1, "Stripe", "stripe"],
        [1, "Log (ZIL)", "log"],
        [1, "Cache (L2ARC)", "cache"],
        [1, "Spare", "spare"],
      ],
      _disksCheck: function(manual, cols, rows) {
        var me = this, numDisksRow, diskSize;

        numDisksRow = this.getCurrentCols();

        // Empty the whole disk group type options
        this._vdevstore.query({}).forEach(function(item, index) {
          me._vdevstore.remove(item.id);
        });

        // Fill the disk group type with valid choices
        // based on number of disks per row
        for(var i=0;i<this._vdevTypes.length;i++) {
          if(numDisksRow >= this._vdevTypes[i][0]) {
            this._vdevstore.add({
              id: this._vdevTypes[i][2],
              name: this._vdevTypes[i][1]
            });

          }
        }
        if(this.disks.length == 0) {
          this.vdevtype.set('value', '');
        } else if(this.disks.length == 1) {
          if(!this.vdevtype.get("value")) {
            this.vdevtype.set("value", "stripe");
          }
        }

        this._isOptimal = null;
        if(manual !== true) {
          for(var key in this._optimalCheck) {
            if(this._optimalCheck[key](numDisksRow)) {
              // .set will trigger onChange, ignore it once
              this.vdevtype._stopEvent = true;
              this.vdevtype.set('value', key);
              this._isOptimal = true;
              break;
            }
          }
          if(this._isOptimal !== true) {
            var vdevtype = this.vdevtype.get("value");
            if(this._optimalCheck[vdevtype] !== undefined) {
              this._isOptimal = false;
            }
          }
        } else {
          var vdevtype = this.vdevtype.get("value");
          var optimalf = this._optimalCheck[vdevtype];
          if(optimalf !== undefined) {
            this._isOptimal = optimalf(numDisksRow);
          }
        }

        if(this.disks.length > 0) {
          diskSize = this.disks[0].size;
        } else {
          diskSize = '0 B';
        }
        this.dapCapacity.innerHTML = humanizeSize(this.getCapacity());
        this.dapNumCol.innerHTML = sprintf("%dx%dx%s", this.getCurrentCols(), this.getCurrentRows(), diskSize);
        if(this._isOptimal !== null) {
          domStyle.set(this.dapOptimalRow, "display", "");
          if(this._isOptimal) {
            domStyle.set(this.dapOptimal, "fontWeight", "");
            domStyle.set(this.dapOptimal, "color", "");
            this._optimalTooltip.set('content', "Your configuration is optimal!<br /><br />It means you'll have the best performance possible for this number of disks and type of disk group.<br /><br />For further explanation please refer to the <a href='http://doc.freenas.org/index.php/Volumes#ZFS_Volume_Manager' target='_blank'>documentation</a>.");
            this.dapOptimal.innerHTML = 'optimal';
          } else {
            domStyle.set(this.dapOptimal, "fontWeight", "bold");
            domStyle.set(this.dapOptimal, "color", "red");
            this._optimalTooltip.set('content', "Your configuration is not optimal!<br /><br />It means this number of disks will not provide the best performance for that type of disk group.<br /><br />For further explanation please refer to the <a href='http://doc.freenas.org/index.php/Volumes#ZFS_Volume_Manager' target='_blank'>documentation</a>.");
            this.dapOptimal.innerHTML = 'non-optimal';
          }
        } else {
          domStyle.set(this.dapOptimalRow, "display", "none");
        }
      },
      colorActive: function() {
        /*
         * Cosmetical function
         *
         * This is responsible to color the table based on selected
         * disks and whether the selected disks combinated with the
         * disk group type is a optimal config or not
         */

        var cols = this.disks.length / this.rows;
        var cssclass;
        if(this._isOptimal == true) {
          cssclass = "optimal";
        } else if(this._isOptimal == false) {
          cssclass = "nonoptimal";
        } else {
          cssclass = "active";
        }
        query("tr", this.dapTable).forEach(function(item, idx) {
          if(idx == 0) return;
          query("td", item).forEach(function(item, idx) {
            if(idx > cols) {
              domClass.remove(item, ["active", "optimal", "nonoptimal"]);
            } else {
              domClass.remove(item, ["active", "optimal", "nonoptimal"]);
              domClass.add(item, cssclass);
            }
          });
        });
        query("th", this.dapTable).forEach(function(item, idx) {
            if(idx > cols) {
              domClass.remove(item, ["active", "optimal", "nonoptimal"]);
            } else {
              domClass.remove(item, ["active", "optimal", "nonoptimal"]);
              domClass.add(item, cssclass);
            }
        });

      },
      getChildren: function() {
        // This needs investigating
        // For some reason chidlren are not retrieved automatically
        return [this.vdevtype, this.resize, this._dragTooltip];
      },
      _updateSwitch: function() {
        /*
         * From now on we will be dealing with switching the type of disks
         * pre-selected for this group.
         *
         * e.g. Disks of 1TB ha been selected for this group, it will ask
         * if you want to switch for 2TB, whenever possible
         *
         * FIXME: Code is a mess! :)
         */
        var me = this, aDisks = this.manager._avail_disks;
        this._disksSwitch = [];
        for(var i=0;i<aDisks.length;i++) {
          if(this.disks.length > 0) {
            if(aDisks[i].size != this.disks[0].size && aDisks[i].disks.length >= this.disks.length) {
              this._disksSwitch.push(i);
            } else if(aDisks[i].size == me.disks[0].size) {
              this._currentAvail = i;
            }
          }
        }

        if(this._disksSwitch.length > 0) {
          domStyle.set(this._vdevDiskType.domNode, "display", "");

          // Remove all options from disk size choice
          this._store.query({}).forEach(function(item, indexx) {
            me._store.remove(item.id);
          });

          // Add current selected disk size
          this._store.add({
            id: this._currentAvail,
            name: sprintf("%d - %s", aDisks[this._currentAvail].index + 1, aDisks[this._currentAvail].size)
          });
          this._vdevDiskType.set('value', this._currentAvail);

          // Add all other available disk sizes
          for(var i in this._disksSwitch) {
            var idx = this._disksSwitch[i];
            var obj = this._store.get(idx);
            this._store.add({
              id: idx,
              name: sprintf("%d - %s", aDisks[idx].index + 1, aDisks[idx].size)
            });
          }
        } else {
          // There are no other disk sizes available, hide it
          domStyle.set(this._vdevDiskType.domNode, "display", "none");
        }
      },
      _doSwitch: function(widget, value) {
        /*
         * Actually switch the current disk group with
         * another disk sizes available
         */
        if(value === false) return;
        var idx = widget.get("value");
        var num = this.disks.length;
        var rows = this.rows;
        while(this.disks.length > 0) {
          this.disks[0].remove();
        }
        for(var i=0;i<num/rows;i++) {
          for(var j=0;j<rows;j++) {
            this.manager._avail_disks[idx].disks[0].addToRow(this, j, i);
          }
        }
        this.manager.updateSwitch(this);
      },
      _addFormVdev: function(row) {
        if(!this._formVdevs[row]) {
          var vtype = new _Widget();
          this.manager._form.domNode.appendChild(vtype.domNode);
          var vdisks = new _Widget();
          this.manager._form.domNode.appendChild(vdisks.domNode);
          this._formVdevs[row] = [vtype, vdisks];
        }
      },
      _adjustSize: function() {
        domStyle.set(this.resize.domNode.parentNode, "width", (EMPTY_WIDTH + (this.disks.length / this.rows) * PER_NODE_WIDTH) + "px");
        domStyle.set(this.resize.domNode.parentNode, "height", (HEADER_HEIGHT + this.rows * PER_NODE_HEIGHT) + "px");
      },
      postCreate: function() {
        var me = this;

        this.disks = [];
        this._disksSwitch = [];
        this._formVdevs = {};

        this._addFormVdev(0);

        this._store = new Observable(new Memory());

        this._vdevDiskType = new FilteringSelect({
          store: this._store,
          style: {width: "85px", marginRight: "0px", display: "none"},
          onChange: function(value) { lang.hitch(me, me._doSwitch)(this, value); }
        }, this.dapVdevDiskType);

        this._vdevstore = new Observable(new Memory());

        this.vdevtype = new FilteringSelect({
          store: this._vdevstore,
          style: {width: "65px", marginRight: "0px"}
        }, this.dapVdevType);

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
            _resizingRows: 1,
            _resizingCols: null,
            _checkConstraints: function(newW, newH){
              var availDisks = me.disks.length + me.manager.getAvailDisksNum();

              // Subtract the header and the first null column of the table
              // Number of disks is calculated based on size of the resizer
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
              var currentW = PER_NODE_WIDTH * (me.disks.length / me.rows);
              if(newW > currentW) {
                numNodes = (newW - currentW - EMPTY_WIDTH) / EMPTY_NODE;

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
                  this._disks = disks;
                  this._resizingRows = floorR;
                  this._resizingCols = floor;
                  this.lastH = newH;
                  this.lastW = newW;
                  me._draggedOnce = true;
                  me._disksCheck(false, floor, floorR);
                  me.manager.updateCapacity(); // FIXME: double call with _disksCheck
                  me.manager.updateSwitch();
                }
              }

              return { w: newW, h: newH };
            },
            getSlots: function() {
              var width = domStyle.get(this.domNode.parentNode, "width");
              return Math.floor((width - EMPTY_WIDTH) / PER_NODE_WIDTH);
            },
            onResize: function(e) {
              me.rows = this._resizingRows;
              this._resizingCols = null;
              if(this._disks !== null) {

                /*
                 * We need to take care manipulating me.disks
                 * because disk.remove() will interact over the same
                 * structure
                 */
                while(me.disks.length > 0) {
                  me.disks[0].remove();
                }

                /*
                 * Add again every disk automatically selected
                 * to this disk group
                 */
                for(var i=0;i<this._disks.length;i++) {
                  for(var j=0;j<this._disks[i].length;j++) {
                    var disk = this._disks[i][j];
                    var index = me.disks.indexOf(disk);
                    if(index == -1) {
                      disk.addToRow(me, i, j);
                    }
                  }
                }

                /*
                 * We need to maintain dumb structure for each row of the
                 * disk group so the dijit form can query _Widget for the
                 * group type and disks
                 */
                var extraRows = query("tr", me.dapTable).length - this._disks.length - 1;
                for(var i=0;i<extraRows;i++) {
                  query("tr:nth-child("+(this._disks.length+2)+")", me.dapTable).forEach(domConst.destroy);
                  var formVdev = me._formVdevs[this._disks.length+i];
                  if(formVdev) {
                    formVdev[0].destroyRecursive();
                    formVdev[1].destroyRecursive();
                    delete me._formVdevs[this._disks.length+i];
                  }
                }

                this._disks = null;
              }
              // Set the new correct width after releasing mouse
              domStyle.set(this.targetDomNode, "width", (EMPTY_WIDTH + (me.disks.length / me.rows) * PER_NODE_WIDTH) + "px");

              me._disksCheck();
              me.manager.updateCapacity();
              me.colorActive();
              me.manager.updateSwitch();

            }
        }, this.dapRes);
        domStyle.set(this.dapResMain, "height", (HEADER_HEIGHT + PER_NODE_HEIGHT) + "px");
        this.resize.startup();

        this.dapDelete = Button({
          label: "X"
        }, this.dapDelete);

        this._optimalTooltip = new TooltipDialog({
          connectId: [this.dapOptimalHelp],
          onMouseLeave: function() {
            popup.close(me._optimalTooltip);
            //me._tpDialog.destroyRecursive();
          }
        });

        on(this.dapOptimalHelp, mouse.enter, function() {
          popup.open({
            popup: me._optimalTooltip,
            around: me.dapOptimalHelp,
            orient: ["above", "after", "below-alt"]
          });
        });


        if(this.can_delete === true) {
          on(this.dapDelete, "click", lang.hitch(this, this.remove));
        } else {
          this.dapDelete.set('disabled', true);
          domStyle.set(this.dapDelete.domNode, "display", "none");
        }

        on(this.vdevtype, "change", function() {
          if(this._stopEvent !== true) {
            me._disksCheck(true);
            me.colorActive();
          } else {
            this._stopEvent = false;
          }
          me.manager.updateCapacity();
        });
        this._disksCheck();

        // Pre-populate this diskgroup with given disks
        if(this.initialDisks.length > 0) {

          if(this.initialDisks.length == 4 || this.initialDisks.length == 8) {
            for(var i=0,len=this.initialDisks.length;i<len;i++) {
              this.initialDisks[0].addToRow(this, Math.floor(i / (len / 2)), i % (len / 2));
            }
            this.rows = 2;
          } else if(this.initialDisks.length < 12) {

            for(var i=0,len=this.initialDisks.length;i<len;i++) {
              this.initialDisks[0].addToRow(this, 0, i);
            }
          } else if(this.initialDisks.length < 18) {
            //FIXME: We need to handle disks == 16 in a better way
            var div2 = Math.floor(this.initialDisks.length / 2);
            var mod2 = this.initialDisks.length % 2;

            for(var i=0,len=this.initialDisks.length - mod2;i<len;i++) {
              this.initialDisks[0].addToRow(this, ath.floor(i / div2), i % div2);
            }

            // Remaining disks are spare
            if(this.initialDisks.length > 0) {
              var diskgspare = this.manager.addVdev({
                can_delete: true,
                type: "spare",
                initialDisks: this.initialDisks
              });
              diskgspare._disksCheck(true);
              diskgspare.colorActive();
            }

          } else if(this.initialDisks.length < 99) {
            var chosen;
            var div9 = Math.floor(this.initialDisks.length / 9);
            var div10 = Math.floor(this.initialDisks.length / 10);
            var mod9 = this.initialDisks.length % 9;
            var mod10 = this.initialDisks.length % 10;

            if(mod9 >= 0.75 * div9 && mod10 >= 0.75 * div10) {
              // raidz
              chosen = 9;
              this.rows = div9;
            } else {
              // raidz2
              chosen = 10;
              this.rows = div10;
            }
            for(var i=0,len=this.initialDisks.length;i<len;i++) {
              this.initialDisks[0].addToRow(this, Math.floor(i / chosen), i % chosen);
            }

            // Remaining disks are spare
            if(this.initialDisks.length > 0) {
              var diskgspare = this.manager.addVdev({
                can_delete: true,
                type: "spare",
                initialDisks: this.initialDisks
              });
              diskgspare._disksCheck(true);
              diskgspare.colorActive();
            }

          } else {
            var chosen;
            var num = Math.ceil((this.initialDisks.length / 11) * 0.75);
            var mod9 = num % 9;
            var mod10 = num % 10;
            var mod11 = num % 11;
            var min = Math.min(mod9, mod10, mod11);
            if(min == mod11) {
              chosen = 11;
            } else if(min == mod10) {
              chosen = 10;
            } else if(min == mod9) {
              chosen = 9;
            }

            for(var i=0,len=this.initialDisks.length;i<len;i++) {
              this.initialDisks[0].addToRow(this, Math.floor(i / chosen), i % chosen);
            }

            // Remaining disks are spare
            if(this.initialDisks.length > 0) {
              var diskgspare = this.manager.addVdev({
                can_delete: true,
                type: "spare",
                initialDisks: this.initialDisks
              });
              diskgspare._disksCheck(true);
              diskgspare.colorActive();
            }
          }
          me._disksCheck();
          this.manager.updateCapacity();
          this.colorActive();
          this.manager.updateSwitch();
        }

        if(this.type) {
          this.vdevtype.set('value', this.type);
        }

        this._adjustSize();

        this._dragTooltip = Tooltip({
          connectId: [this.resize.domNode],
          label: "Drag and drop this to resize",
          onHide: function() {
            var checkDragTooltip = function() {
              if(!me._draggedOnce) {
                me._dragTooltip.open(me.resize.domNode);
              }
            }
            setTimeout(checkDragTooltip, 5000);
          }
        })
        //on.once(me.resize.domNode, mouse.enter, function() {
        //  Tooltip.hide(me.resize.domNode);
        //});
        this._dragTooltip.startup();
        //FIXME: find a way to do that on instantiation
        setTimeout(function() {
          me._dragTooltip.open(me.resize.domNode);
        }, 100);

      },
      remove: function() {
        /*
         * Remove this disk group from the volume manager
         */
        while(this.disks.length != 0) {
          this.disks[0].remove();
        }
        var iof = this.manager._layout.indexOf(this);
        this.manager._layout.splice(iof, 1);
        this.manager.updateSwitch();
        this.destroyRecursive();
      }
    });

    var VolumeManager = declare("freeadmin.VolumeManager", [ _Widget, _Templated ], {
      templateString: template,
      disks: "{}",
      url: "",
      url_progress: "",
      dedup_warning: "",
      extend: "",
      swapSize: 0,
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
          this.dapDisks.appendChild(dAvail.domNode);
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
        this._avail_disks = [];

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
              var opt = this.getOptions(val);
              if(opt.enc) {
                domStyle.set(me.dapExtendEnc, "display", "");
              } else {
                domStyle.set(me.dapExtendEnc, "display", "none");
              }
            } else {
              volume_name.set('disabled', false);
              enc.set('disabled', false);
              encini.set('disabled', false);
              okbtn.set('label', me.add_label);
              domStyle.set(me.dapExtendEnc, "display", "none");
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

        /*
         * Sort disks by bytes DESC
         */
        var sortKeys = [];
        for(var key in this.disks) {
          sortKeys.push([key, this.disks[key][0]['size']]);
        }
        sortKeys.sort(function(a, b) {
          return b[1] - a[1];
        });

        /*
         * Create the Disk objects for every disk based on the
         * params provided and the available disks grouped by size
         */
        for(var i=0;i<sortKeys.length;i++) {
          var size = sortKeys[i][0];
          var disks = this.disks[size];
          var avail_disks = [];
          for(var key in disks) {
            avail_disks.push(new Disk({
              manager: this,
              name: disks[key]['dev'],
              size: size,
              sizeBytes: disks[key]['size'],
              serial: disks[key]['serial']
            }));
          }
          var dAvail = new DisksAvail({
            disks: avail_disks,
            size: size,
            sizeBytes: avail_disks[0].sizeBytes,
            availDisks: this._avail_disks,
            manager: this,
            index: i
          });
          this._avail_disks.push(dAvail);
        }

        lang.hitch(this, this.drawAvailDisks)();

        /*
         * Add extra row for the layout
         */
        var add_extra = new Button({
          label: "Add Extra Device"
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

        this._total_vdevs = new _Widget({
            name: "layout-TOTAL_FORMS",
            value: 0
        }).placeAt(this._form.domNode);
        this._initial_vdevs = new _Widget({
            name: "layout-INITIAL_FORMS",
            value: 0
        }).placeAt(this._form.domNode);

        new Toaster({
          messageTopic: "volumeManager",
          separator: "<hr/>",
          positionDirection: "br-left",
          duration: "0"
        }, this.dapToaster);

        this.addVdev({can_delete: false});
        this.updateCapacity();

        this.inherited(arguments);

      },
      addVdev: function(attrs) {
        /*
         * Add a new disk group to the volume layout
         *
         * Attributes:
         * can_delete - Disk group is deletable (bool)
         *
         * Returns: disk group object
         */
        var vdev;
        attrs['manager'] = this;
        vdev = new Vdev(attrs);
        domConst.place(vdev.domNode, this.dapLayoutTable);

        this._layout.push(vdev);
        return vdev;

      },
      updateCapacity: function() {
        /*
         * Update the estimated capacity for the whole volume layout
         */
        var capacity = 0;
        for(var key in this._layout) {
          var diskg = this._layout[key];
          capacity += diskg.getCapacity();
        }
        this.dapCapacity.innerHTML = humanizeSize(capacity);
        return capacity;
      },
      updateSwitch: function(exclude) {
        for(var key in this._layout) {
          var diskg = this._layout[key];
          if(exclude == diskg) continue;
          diskg._updateSwitch();
        }
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
      submit: function() {
        /*
         * Set all field names for layout before submit
         * It is easier than keep track of the fields on-the-fly
         */
        for(var i=0,k=0;i<this._layout.length;i++) {
          var vdev = this._layout[i];
          var perRow = vdev.disks.length / vdev.rows;
          for(var j=0;j<vdev.rows;j++,k++) {
            var disks = [];
            for(var d=perRow*j;d<perRow*(j+1);d++) {
              disks.push(vdev.disks[d].get("name"));
            }
            vdev._formVdevs[j][0].set('name', 'layout-' + k + '-vdevtype');
            vdev._formVdevs[j][0].set('value', vdev.vdevtype.get("value"));
            vdev._formVdevs[j][1].set('name', 'layout-' + k + '-disks');
            vdev._formVdevs[j][1].set('value', disks);
          }
        }
        this._total_vdevs.set('value', k);
        doSubmit({
          url: this.url,
          form: this._form,
          progressbar: this.url_progress
        });
      }
    });
    return VolumeManager;
});
