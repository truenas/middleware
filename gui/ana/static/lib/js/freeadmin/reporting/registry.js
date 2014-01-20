define([
    "dojo/_base/declare",
    "dojo/_base/lang",
    "dojo/dom"
    ], function(
    declare,
    lang,
    dom
    ) {

    var registry = declare("freeadmin.reporting.registry", [], {
        constructor: function(/*Object*/ kwArgs){
            lang.mixin(this, kwArgs);
            this._ids = {};
        },
        add: function(obj, identifier) {
            if(identifier in this._ids) {
                var _tmp = this._ids[identifier];
                _tmp.destroy();
            }
            this._ids[identifier] = obj;
        },
        remove: function(identifier) {
            if(identifier in this._ids) {
                var _tmp = this._ids[identifier];
                _tmp.destroy();
            }
        }
    });
    return registry;

});
