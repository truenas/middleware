(function (global, factory) {
    if (typeof define === "function" && define.amd) {
        define(["exports"], factory);
    } else if (typeof exports !== "undefined") {
        factory(exports);
    } else {
        var mod = {
            exports: {}
        };
        factory(mod.exports);
        global.utils = mod.exports;
    }
})(this, function (exports) {
    "use strict";

    Object.defineProperty(exports, "__esModule", {
        value: true
    });
    exports.uniqueId = uniqueId;
    exports.contains = contains;
    var i = 0;
    function uniqueId() {
        return (i++).toString();
    }

    function contains(array, element) {
        return array.indexOf(element) !== -1;
    }
});