define([
    "dojo/_base/declare",
    "dojo/dom-attr",
    "dojo/io-query",
    "dojo/date/stamp",
    "dijit/_Widget",
    "dijit/_TemplatedMixin",
    "dijit/form/TextBox",
    "dijit/form/Button",
    "dijit/layout/TabContainer",
    "dijit/layout/ContentPane",
    "dojox/charting/Chart",
    "dojox/charting/themes/Claro",
    "dojox/charting/axis2d/Default",
    "dojox/charting/plot2d/Areas",
    "dojox/charting/plot2d/Grid",
    "dojox/charting/plot2d/Lines",
    "dojox/charting/action2d/MouseIndicator",
    "dojox/timing",
    "dojo/text!freeadmin/templates/rrdcontrol.html"
    ], function(declare, domAttr, ioQuery,
    stamp,
    _Widget, _Templated, TextBox, Button, TabContainer, ContentPane,
    Chart,
    Claro,
    chartingAxis,
    chartingAreas,
    chartingGrid,
    chartingLines,
    MouseIndicator,
    timing, template) {

    var RRDControl = declare("freeadmin.RRDControl", [ _Widget, _Templated ], {
        templateString : template,
        name : "",
        value: "",
        href: "",
        step: 0,
        unit: "hourly",
        plugin: "",
        sources: "",
        identifier: "",
        verticalLabel: "",
        title: "",
        postCreate: function() {

            var me, zoomIn, zoomOut, left, right, t;
            me = this;

            this.name = this.plugin + "_" + this.identifier;

            me.sources = JSON.parse(me.sources);

            var chart = new Chart(this.chartNode, {title: me.title});
            chart.setTheme(Claro);

            chart.addAxis("x", {
              labelFunc: function(index) {
                return index;
              }
              //fixLower: "minor",
              //natural: true,
              //stroke: "grey",
              //majorTick: {stroke: "black", length: 4},
              //minorTick: {stroke: "gray", length: 2}
            });
            chart.addAxis("y", {
              vertical: true,
              fixLower: "major",
              fixUpper: "major",
              //majorTickStep: 5,
              //minorTickStep: 1,
              //stroke: "grey",
              //majorTick: {stroke: "black", length: 4}, minorTick: {stroke: "gray", length: 2}
              title: me.verticalLabel
            });
            chart.addPlot("default", {type: chartingLines, animate: {duration: 1800}});

            var query = function(source, x) {
              var start, end;
              end = new Date();
              start = new Date(end.getTime() - (60 * 60 * 1000));

              _ws.call("statd.output.query", [key, {
                start: stamp.toISOString(start),
                end: stamp.toISOString(end),
                frequency: "60S"
              }], function(response) {
                var series = [];
                for(var k in response.data) {
                  series.push({x: response.data[k][0], y: parseFloat(response.data[k][1])});
                }
                chart.addSeries("Series " + x, series);
                chart.render();
              });

            }

            var i = 1;
            for(var key in me.sources) {
              var source = me.sources[key];
              query(source, i);
              i++;
            }

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
            //this.timer = new timing.Timer(300000);
            //this.timer.onTick = function() {
            //    me.query();
            //}
            //this.timer.start();

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

            //var query = ioQuery.objectToQuery({
            //    unit: this.unit,
            //    plugin: this.plugin,
            //    step: this.step,
            //    identifier: this.identifier,
            //    cache: new Date().getTime()
            //    })
            //var uri = this.href + "?" + query;
            //domAttr.set(this.imageNode, "src", uri);

        },
        destroy: function() {
            //this.timer.stop();
            this.inherited(arguments);
        }
    });
    return RRDControl;
});
