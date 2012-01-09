define([
    "dojo/_base/declare",
    "dojo/cache",
    "dijit/_Widget",
    "dijit/_TemplatedMixin",
    "dijit/form/HorizontalSlider",
    "dijit/form/HorizontalRule",
    "dijit/form/HorizontalRuleLabels",
    "dijit/layout/TabContainer",
    "dijit/layout/ContentPane",
    "dojox/string/sprintf",
    ], function(declare, cache, _Widget, _Templated, HorizontalSlider, HorizontalRule, HorizontalRuleLabels, TabContainer, ContentPane) {

    var Cron = declare("freeadmin.form.Cron", [ _Widget, _Templated ], {
        templateString : cache("freeadmin", "templates/chooser.html"),
        name : "",
        numChoices: "",
        label: "minute",
        typeChoice: "every",
        value: "",
        start: "0",
        postCreate : function() {

            var cron = this;
            if(!gettext) {
                gettext = function(s) { return s; }
            }
            if(!this.value || this.value=="") {
                this.value = "*/1";
            }
            this.numChoices = parseInt(this.numChoices);
            this.start = parseInt(this.start);
            var sldval = this.sliderValue;

            setSelected = function() {
                 varr = [];
                 dojo.query(':checked', sel.containerNode).forEach(function(node, index, arr){
                     varr.push(dijit.getEnclosingWidget(node).get('label'));
                 });
                 cron.set('value', varr.join(','));
            }

            var sel = new dijit.layout.ContentPane({
                 title: gettext('Each selected') + ' ' + this.label,
                 onShow: function(ev) {
                 varr = [];
                 dojo.query(':checked', sel.containerNode).forEach(function(node, index, arr){
                     varr.push(dijit.getEnclosingWidget(node).get('label'));
                 });
                 cron.set('value', varr.join(','));
                 },
            }, this.selectedNode);

            //var rulesNode = document.createElement('div'); 
            //var rulesNodeLabels = document.createElement('ol'); 
            //var sliderRule= new dijit.form.HorizontalRule( { 
            //       count: 5, 
            //       style: "height:1em;font-size:75%;color:gray;" 
            //    }, rulesNode); 
            //var sliderLabels= new dijit.form.HorizontalRuleLabels( { 
            //       container: "bottomDecoration", 
            //       count: 5, 
            //       labels: [0,15,30,45,59], 
            //       style: "height:2em;font-size:75%;color:gray;" 
            //    }, rulesNodeLabels); 

            if(this.typeChoice == 'every'){
                if(this.value == '*')
                    this.sliderValue.innerHTML = '1';
                else
                    this.sliderValue.innerHTML = this.value.split('/')[1];
            } else {
                this.sliderValue.innerHTML = Math.floor((this.numChoices+this.start)/4).toString();
            }
            var slider = new dijit.form.HorizontalSlider({
                name: "slider",
                value: parseInt(this.sliderValue.innerHTML),
                minimum: 1,
                maximum: Math.floor((this.numChoices)/2),
                discreteValues: Math.floor((this.numChoices+this.start)/2)-this.start,
                intermediateChanges: true,
                style: "width:300px;",
                onChange: function(value) {
                    sldval.innerHTML = Math.floor(value);
                    if(Math.floor(value) == 1) {
                        cron.set('value', '*');
                    } else {
                        cron.set('value', '*/'+Math.floor(value).toString());
                    }
                }
            }, this.sliderNode);
            //slider.domNode.appendChild(sliderRule);
            //slider.domNode.appendChild(sliderLabels);
            slider.startup();

            var every = new dijit.layout.ContentPane({
                 title: gettext('Every N')+' '+this.label,
                 onShow: function(ev) {
                    var value = slider.get('value');
                    sldval.innerHTML = Math.floor(value);
                    if(Math.floor(value) == 1)
                        cron.set('value', '*');
                    else
                        cron.set('value', '*/'+Math.floor(value).toString());
                 },
            }, this.everyNode);

            var myvals = [];
            if(this.typeChoice == 'selected'){
                myvals = this.value.split(',');
            }
            for(var i=0;i<this.numChoices;i++) {
                var tg = new dijit.form.ToggleButton({
                    showLabel: true,
                    checked: (dojo.indexOf(myvals, dojox.string.sprintf("%.2d", i+this.start)) != -1) ? true : false,
                    baseClass: 'mytoggle',
                    onChange: function(val) {
                 varr = [];
                 dojo.query(':checked', sel.containerNode).forEach(function(node, index, arr){
                     varr.push(dijit.getEnclosingWidget(node).get('label'));
                 });
                 cron.set('value', varr.join(','));
                    },
                    label: dojox.string.sprintf("%.2d", i+this.start),
                });
                sel.containerNode.appendChild(tg.domNode);
            }

            var tc = new dijit.layout.TabContainer({
                name: "tab",
                style: "height: 100%; width: 100%;",
            }, this.tab);
            tc.startup();

            if(this.typeChoice=='every') {
                tc.selectChild(every);
            } else if(this.typeChoice=='selected') {
                tc.selectChild(sel);
            }

        }
    });
    return Cron;
});
