define(["dijit/Dialog","dojo/_base/declare"], function(Dialog, declare) {

    var MyDialog = declare("freeadmin.ESCDialog", [Dialog], {
        _onKey: function(evt) {
            if(evt.charOrCode == dojo.keys.ESCAPE) return;
            this.inherited(arguments);
        },
    });
    return MyDialog;

});
