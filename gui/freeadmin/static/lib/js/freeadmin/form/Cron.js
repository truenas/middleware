define([
    "dojo/_base/array",
    "dojo/_base/declare",
    "dojo/query",
    "dijit/_Widget",
    "dijit/_TemplatedMixin",
    "dijit/registry",
    "dijit/form/HorizontalSlider",
    "dijit/form/HorizontalRule",
    "dijit/form/HorizontalRuleLabels",
    "dijit/form/ToggleButton",
    "dijit/layout/TabContainer",
    "dijit/layout/ContentPane",
    "dojox/string/sprintf",
    "dojo/text!freeadmin/templates/chooser.html"
    ], function(array,
    declare,
    query,
    _Widget,
    _Templated,
    registry,
    HorizontalSlider,
    HorizontalRule,
    HorizontalRuleLabels,
    ToggleButton,
    TabContainer,
    ContentPane,
    sprintf,
    template) {

    var Cron = declare("freeadmin.form.Cron", [ _Widget, _Templated ], {
        templateString: template,
        name: "",
        numChoices: "",
        label: "minute",
        typeChoice: "every",
        value: "",
        start: "0",
        postCreate: function() {

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
                 query(':checked', sel.containerNode).forEach(function(node, index, arr){
                     varr.push(registry.getEnclosingWidget(node).get('label'));
                 });
                 cron.set('value', varr.join(','));
            }

            var sel = new ContentPane({
              id: cron.name + "_pane_each",
              title: gettext('Each selected') + ' ' + this.label,
              onShow: function(ev) {
                varr = [];
                query(':checked', sel.containerNode).forEach(function(node, index, arr){
                  varr.push(registry.getEnclosingWidget(node).get('label'));
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
            var slider = new HorizontalSlider({
                id: cron.name + "_slider",
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

            var every = new ContentPane({
              id: cron.name + "_pane_every",
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
                var checked = (array.indexOf(myvals, sprintf("%.2d", i+this.start)) != -1) ? true : false;
                var tg = new ToggleButton({
                    id: cron.name + "_toggle_" + (cron.start + i),
                    showLabel: true,
                    checked: checked,
                    baseClass: 'mytoggle',
                    onChange: function(val) {
                      varr = [];
                      query(':checked', sel.containerNode).forEach(function(node, index, arr){
                        varr.push(registry.getEnclosingWidget(node).get('label'));
                      });
                      cron.set('value', varr.join(','));
                    },
                    label: sprintf("%.2d", i+cron.start),
                });
                tg.set('checked', checked);
                sel.containerNode.appendChild(tg.domNode);
            }

            var tc = new TabContainer({
                id: cron.name + "_tab",
                name: "tab",
                style: "height: 100%; width: 100%;",
            }, this.tab);
            tc.startup();

            if(this.typeChoice=='every') {
                tc.selectChild(every);
            } else if(this.typeChoice=='selected') {
                tc.selectChild(sel);
            }

            this._supportingWidgets.push(tc);
            this._supportingWidgets.push(slider);

            this.inherited(arguments);

        }
    });
    return Cron;
});
