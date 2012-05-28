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
    "dojo/text!freeadmin/templates/rrdcontrol.html"
    ], function(declare, domAttr, ioQuery, _Widget, _Templated, TextBox, Button, TabContainer, ContentPane, template) {

    var RRDControl = declare("freeadmin.RRDControl", [ _Widget, _Templated ], {
        templateString : template,
        name : "",
        value: "",
        href: "",
        step: 0,
        unit: "hourly",
        identifier: "",
        postCreate : function() {

            var me, zoomIn, zoomOut, left, right;

            me = this;
            zoomIn = new Button({
                label: 'Zoom In',
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
                label: 'Zoom Out',
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
            console.log(uri);
            domAttr.set(this.imageNode, "src", uri);

        }
    });
    return RRDControl;
});
