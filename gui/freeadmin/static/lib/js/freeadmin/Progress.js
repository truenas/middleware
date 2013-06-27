define([
  "dojo/_base/declare",
  "dojo/dom-attr",
  "dijit/_Widget",
  "dijit/_TemplatedMixin",
  "dijit/form/TextBox",
  "dijit/form/Button",
  "dijit/layout/TabContainer",
  "dijit/layout/ContentPane",
  "dojox/timing",
  "dojo/text!freeadmin/templates/progress.html"
  ], function(declare, domAttr, _Widget, _Templated, TextBox, Button, TabContainer, ContentPane, timing, template) {

  var Progress = declare("freeadmin.Progress", [ _Widget, _Templated ], {
      templateString : template,
      name : "",
      steps: 1,
      postCreate : function() {

          var me = this;

          this.inherited(arguments);

      },
      destroy: function() {
          //this.timer.stop();
          this.inherited(arguments);
      }
  });
  return Progress;
});
