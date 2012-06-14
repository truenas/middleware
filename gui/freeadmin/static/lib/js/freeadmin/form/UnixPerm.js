define([
    "dojo/_base/declare",
    "dijit/_Widget",
    "dijit/_TemplatedMixin",
    "dijit/form/TextBox",
    "dijit/form/CheckBox",
    "dijit/layout/TabContainer",
    "dijit/layout/ContentPane",
    "dojox/string/sprintf",
    "dojo/text!freeadmin/templates/unixperm.html"
    ], function(declare, _Widget, _Templated, TextBox, CheckBox, TabContainer, ContentPane, sprintf, template) {

    var UnixPerm = declare("freeadmin.form.UnixPerm", [ _Widget, _Templated ], {
        templateString: template,
        name: "",
        value: "",
        boxes: "",
        disabled: false,
        _getValueAttr: function() {
            if(this.disabled == true) {
                return '';
            }
            var mode = 0;
            for(i=0;i<this.boxes.length;i++) {
                if(this.boxes[i].get('checked')) {
                    mode |= Math.pow(2, 8 - i);
                }
            }
            return sprintf("%o", mode);
        },
        _setDisabledAttr: function(value) {
            console.log(value);
            for(i=0;i<this.boxes.length;i++) {
                this.boxes[i].set('disabled', true);
            }
            this.disabled = value;
        },
        setPerm: function(value) {
            var mode = parseInt(value, 8);
            for(i=0;i<this.boxes.length;i++) {
                isset = (mode & Math.pow(2, 8 - i)) != 0;
                this.boxes[i].set('checked', isset);
            }
        },
        postCreate: function() {

            var uperm = this;

            //this.numChoices = parseInt(this.numChoices);
            //this.start = parseInt(this.start);
            this.boxes = [];

            new TextBox({
                type: 'hidden',
                name: this.name
                }, this.input);

            var or = CheckBox({

            });
            this.boxes.push(or);
            this.or.appendChild(or.domNode);

            var ow = CheckBox({

            });
            this.boxes.push(ow);
            this.ow.appendChild(ow.domNode);

            var oe = CheckBox({

            });
            this.boxes.push(oe);
            this.oe.appendChild(oe.domNode);


            var gr = CheckBox({

            });
            this.boxes.push(gr);
            this.gr.appendChild(gr.domNode);



            var gw = CheckBox({

            });
            this.boxes.push(gw);
            this.gw.appendChild(gw.domNode);




            var ge = CheckBox({

            });
            this.boxes.push(ge);
            this.ge.appendChild(ge.domNode);

            var otr = CheckBox({

            });
            this.boxes.push(otr);
            this.otr.appendChild(otr.domNode);

            var otw = CheckBox({

            });
            this.boxes.push(otw);
            this.otw.appendChild(otw.domNode);

            var ote = CheckBox({

            });
            this.boxes.push(ote);
            this.ote.appendChild(ote.domNode);

            this.setPerm(this.value);

            //this._supportingWidgets.push(tc);

            this.inherited(arguments);

        }
    });
    return UnixPerm;
});
