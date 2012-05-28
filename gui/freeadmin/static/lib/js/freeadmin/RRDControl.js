define([
    "dojo/_base/declare",
    "dijit/_Widget",
    "dijit/_TemplatedMixin",
    "dijit/form/TextBox",
    "dijit/form/Button",
    "dijit/layout/TabContainer",
    "dijit/layout/ContentPane",
    "dojo/text!freeadmin/templates/rrdcontrol.html",
    ], function(declare, _Widget, _Templated, TextBox, Button, TabContainer, ContentPane, template) {

    var RRDControl = declare("freeadmin.RRDControl", [ _Widget, _Templated ], {
        templateString : template,
        name : "",
        value: "",
        postCreate : function() {

            var me = this;
            console.log("created");

        }
    });
    return RRDControl;
});
