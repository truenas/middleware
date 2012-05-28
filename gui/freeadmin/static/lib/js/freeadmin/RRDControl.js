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
        unit: "hourly",
        postCreate : function() {

            var me, zoomIn;

            me = this;
            domAttr.set(this.imageNode, "src", this.href);
            zoomIn = new Button({
                label: 'Zoom In',
                onClick: function(e) {
                    newunit = me.zoomInUnit(me.unit)
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
                    newunit = me.zoomOutUnit(me.unit)
                    if(newunit == me.unit || newunit == 'yearly') {
                        zoomOut.set('disabled', true);
                    } else {
                        zoomIn.set('disabled', false);
                    }
                    me.unit = newunit;
                    me.query();
                }
            }, this.zoomOutButton);

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
                cache: new Date().getTime()
                })
            var uri = this.href + "?" + query;
            console.log(uri);
            domAttr.set(this.imageNode, "src", uri);

        }
    });
    return RRDControl;
});
