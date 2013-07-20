define([
    "dojo/_base/declare",
    "dojo/dom-attr",
    "dojo/io-query",
    "dijit/_Widget",
    "dijit/_TemplatedMixin",
    "dijit/form/TextBox",
    "dijit/form/Button",
    "dijit/layout/TabContainer",
    "dijit/layout/ContentPane",
    "dojox/timing",
    "dojo/text!freeadmin/templates/rrdcontrol.html"
    ], function(declare, domAttr, ioQuery, _Widget, _Templated, TextBox, Button, TabContainer, ContentPane, timing, template) {

    var RRDControl = declare("freeadmin.RRDControl", [ _Widget, _Templated ], {
        templateString : template,
        name : "",
        value: "",
        href: "",
        step: 0,
        unit: "hourly",
        plugin: "",
        identifier: "",
        postCreate: function() {

            var me, zoomIn, zoomOut, left, right, t;

            this.name = this.plugin + "_" + this.identifier;

            me = this;
            zoomIn = new Button({
                id: "rrd_" + me.name + "_zoomIn",
                label: this.zoomInButton.innerHTML,
                onClick: function(e) {
                    var newunit = me.zoomInUnit(me.unit)
                    if(newunit == me.unit || newunit == 'hourly') {
                        zoomIn.set('disabled', true);
                    } else {
                        zoomOut.set('disabled', false);
                    }
                    me.unit = newunit;
                    me.query();
                },
                disabled: true,
            }, this.zoomInButton);

            zoomOut = new Button({
                id: "rrd_" + me.name + "_zoomOut",
                label: this.zoomOutButton.innerHTML,
                onClick: function(e) {
                    var newunit = me.zoomOutUnit(me.unit)
                    if(newunit == me.unit || newunit == 'yearly') {
                        zoomOut.set('disabled', true);
                    } else {
                        zoomIn.set('disabled', false);
                    }
                    me.unit = newunit;
                    me.query();
                }
            }, this.zoomOutButton);

            right = new Button({
                id: "rrd_" + me.name + "_right",
                label: '>>',
                onClick: function(e) {
                    var newstep = me.step - 1;
                    if(newstep <= 0) {
                        right.set('disabled', true);
                    } else {
                        right.set('disabled', false);
                    }
                    me.step = newstep;
                    me.query();
                },
                disabled: true
            }, this.rightButton);

            left = new Button({
                id: "rrd_" + me.name + "_left",
                label: '<<',
                onClick: function(e) {
                    var newstep = me.step + 1;
                    if(me.step == 0) {
                        right.set('disabled', false);
                    } else {
                        //zoomIn.set('disabled', false);
                    }
                    me.step = newstep;
                    me.query();
                }
            }, this.leftButton);
            this.query();
            this.timer = new timing.Timer(300000);
            this.timer.onTick = function() {
                me.query();
            }
            this.timer.start();

            this._supportingWidgets.push(left);
            this._supportingWidgets.push(right);
            this._supportingWidgets.push(zoomIn);
            this._supportingWidgets.push(zoomOut);

            this.inherited(arguments);

        },
        zoomInUnit: function(unit) {
            if(unit == 'hourly') {
                return 'hourly';
            } else if(unit == 'daily') {
                return 'hourly';
            } else if(unit == 'weekly') {
                return 'daily';
            } else if(unit == 'monthly') {
                return 'weekly';
            } else if(unit == 'yearly') {
                return 'monthly';
            }
            return unit;
        },
        zoomOutUnit: function(unit) {
            if(unit == 'hourly') {
                return 'daily';
            } else if(unit == 'daily') {
                return 'weekly';
            } else if(unit == 'weekly') {
                return 'monthly';
            } else if(unit == 'monthly') {
                return 'yearly';
            } else if(unit == 'yearly') {
                return 'yearly';
            }
            return unit;
        },
        query: function() {

            var query = ioQuery.objectToQuery({
                unit: this.unit,
                plugin: this.plugin,
                step: this.step,
                identifier: this.identifier,
                cache: new Date().getTime()
                })
            var uri = this.href + "?" + query;
            domAttr.set(this.imageNode, "src", uri);

        },
        destroy: function() {
            this.timer.stop();
            this.inherited(arguments);
        }
    });
    return RRDControl;
});
