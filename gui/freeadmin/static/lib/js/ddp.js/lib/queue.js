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
        global.queue = mod.exports;
    }
})(this, function (exports) {
    "use strict";

    Object.defineProperty(exports, "__esModule", {
        value: true
    });

    function _classCallCheck(instance, Constructor) {
        if (!(instance instanceof Constructor)) {
            throw new TypeError("Cannot call a class as a function");
        }
    }

    var _createClass = function () {
        function defineProperties(target, props) {
            for (var i = 0; i < props.length; i++) {
                var descriptor = props[i];
                descriptor.enumerable = descriptor.enumerable || false;
                descriptor.configurable = true;
                if ("value" in descriptor) descriptor.writable = true;
                Object.defineProperty(target, descriptor.key, descriptor);
            }
        }

        return function (Constructor, protoProps, staticProps) {
            if (protoProps) defineProperties(Constructor.prototype, protoProps);
            if (staticProps) defineProperties(Constructor, staticProps);
            return Constructor;
        };
    }();

    var Queue = function () {

        /*
        *   As the name implies, `consumer` is the (sole) consumer of the queue.
        *   It gets called with each element of the queue and its return value
        *   serves as a ack, determining whether the element is removed or not from
        *   the queue, allowing then subsequent elements to be processed.
        */

        function Queue(consumer) {
            _classCallCheck(this, Queue);

            this.consumer = consumer;
            this.queue = [];
        }

        _createClass(Queue, [{
            key: "push",
            value: function push(element) {
                this.queue.push(element);
                this.process();
            }
        }, {
            key: "process",
            value: function process() {
                if (this.queue.length !== 0) {
                    var ack = this.consumer(this.queue[0]);
                    if (ack) {
                        this.queue.shift();
                        this.process();
                    }
                }
            }
        }, {
            key: "empty",
            value: function empty() {
                this.queue = [];
            }
        }]);

        return Queue;
    }();

    exports.default = Queue;
});