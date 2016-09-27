(function (global, factory) {
    if (typeof define === "function" && define.amd) {
        define(["exports", "wolfy87-eventemitter"], factory);
    } else if (typeof exports !== "undefined") {
        factory(exports, require("wolfy87-eventemitter"));
    } else {
        var mod = {
            exports: {}
        };
        factory(mod.exports, global.wolfy87Eventemitter);
        global.socket = mod.exports;
    }
})(this, function (exports, _wolfy87Eventemitter) {
    "use strict";

    Object.defineProperty(exports, "__esModule", {
        value: true
    });

    var _wolfy87Eventemitter2 = _interopRequireDefault(_wolfy87Eventemitter);

    function _interopRequireDefault(obj) {
        return obj && obj.__esModule ? obj : {
            default: obj
        };
    }

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

    function _possibleConstructorReturn(self, call) {
        if (!self) {
            throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
        }

        return call && (typeof call === "object" || typeof call === "function") ? call : self;
    }

    function _inherits(subClass, superClass) {
        if (typeof superClass !== "function" && superClass !== null) {
            throw new TypeError("Super expression must either be null or a function, not " + typeof superClass);
        }

        subClass.prototype = Object.create(superClass && superClass.prototype, {
            constructor: {
                value: subClass,
                enumerable: false,
                writable: true,
                configurable: true
            }
        });
        if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass;
    }

    var Socket = function (_EventEmitter) {
        _inherits(Socket, _EventEmitter);

        function Socket(SocketConstructor, endpoint) {
            _classCallCheck(this, Socket);

            var _this = _possibleConstructorReturn(this, (Socket.__proto__ || Object.getPrototypeOf(Socket)).call(this));

            _this.SocketConstructor = SocketConstructor;
            _this.endpoint = endpoint;
            _this.rawSocket = null;
            return _this;
        }

        _createClass(Socket, [{
            key: "send",
            value: function send(object) {
                var message = JSON.stringify(object);
                this.rawSocket.send(message);
                // Emit a copy of the object, as the listener might mutate it.
                this.emit("message:out", JSON.parse(message));
            }
        }, {
            key: "open",
            value: function open() {
                var _this2 = this;

                /*
                *   Makes `open` a no-op if there's already a `rawSocket`. This avoids
                *   memory / socket leaks if `open` is called twice (e.g. by a user
                *   calling `ddp.connect` twice) without properly disposing of the
                *   socket connection. `rawSocket` gets automatically set to `null` only
                *   when it goes into a closed or error state. This way `rawSocket` is
                *   disposed of correctly: the socket connection is closed, and the
                *   object can be garbage collected.
                */
                if (this.rawSocket) {
                    return;
                }
                this.rawSocket = new this.SocketConstructor(this.endpoint);

                /*
                *   Calls to `onopen` and `onclose` directly trigger the `open` and
                *   `close` events on the `Socket` instance.
                */
                this.rawSocket.onopen = function () {
                    return _this2.emit("open");
                };
                this.rawSocket.onclose = function () {
                    _this2.rawSocket = null;
                    _this2.emit("close");
                };
                /*
                *   Calls to `onerror` trigger the `close` event on the `Socket`
                *   instance, and cause the `rawSocket` object to be disposed of.
                *   Since it's not clear what conditions could cause the error and if
                *   it's possible to recover from it, we prefer to always close the
                *   connection (if it isn't already) and dispose of the socket object.
                */
                this.rawSocket.onerror = function () {
                    // It's not clear what the socket lifecycle is when errors occurr.
                    // Hence, to avoid the `close` event to be emitted twice, before
                    // manually closing the socket we de-register the `onclose`
                    // callback.
                    delete _this2.rawSocket.onclose;
                    // Safe to perform even if the socket is already closed
                    _this2.rawSocket.close();
                    _this2.rawSocket = null;
                    _this2.emit("close");
                };
                /*
                *   Calls to `onmessage` trigger a `message:in` event on the `Socket`
                *   instance only once the message (first parameter to `onmessage`) has
                *   been successfully parsed into a javascript object.
                */
                this.rawSocket.onmessage = function (message) {
                    var object;
                    try {
                        object = JSON.parse(message.data);
                    } catch (ignore) {
                        // Simply ignore the malformed message and return
                        return;
                    }
                    // Outside the try-catch block as it must only catch JSON parsing
                    // errors, not errors that may occur inside a "message:in" event
                    // handler
                    _this2.emit("message:in", object);
                };
            }
        }, {
            key: "close",
            value: function close() {
                /*
                *   Avoid throwing an error if `rawSocket === null`
                */
                if (this.rawSocket) {
                    this.rawSocket.close();
                }
            }
        }]);

        return Socket;
    }(_wolfy87Eventemitter2.default);

    exports.default = Socket;
});