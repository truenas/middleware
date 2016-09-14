(function (global, factory) {
    if (typeof define === "function" && define.amd) {
        define(["exports", "wolfy87-eventemitter", "./queue", "./socket", "./utils"], factory);
    } else if (typeof exports !== "undefined") {
        factory(exports, require("wolfy87-eventemitter"), require("./queue"), require("./socket"), require("./utils"));
    } else {
        var mod = {
            exports: {}
        };
        factory(mod.exports, global.wolfy87Eventemitter, global.queue, global.socket, global.utils);
        global.ddp = mod.exports;
    }
})(this, function (exports, _wolfy87Eventemitter, _queue, _socket, _utils) {
    "use strict";

    Object.defineProperty(exports, "__esModule", {
        value: true
    });

    var _wolfy87Eventemitter2 = _interopRequireDefault(_wolfy87Eventemitter);

    var _queue2 = _interopRequireDefault(_queue);

    var _socket2 = _interopRequireDefault(_socket);

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

    function _possibleConstructorReturn(self, call) {
        if (!self) {
            throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
        }

        return call && (typeof call === "object" || typeof call === "function") ? call : self;
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

    var _get = function get(object, property, receiver) {
        if (object === null) object = Function.prototype;
        var desc = Object.getOwnPropertyDescriptor(object, property);

        if (desc === undefined) {
            var parent = Object.getPrototypeOf(object);

            if (parent === null) {
                return undefined;
            } else {
                return get(parent, property, receiver);
            }
        } else if ("value" in desc) {
            return desc.value;
        } else {
            var getter = desc.get;

            if (getter === undefined) {
                return undefined;
            }

            return getter.call(receiver);
        }
    };

    var DDP_VERSION = "1";
    var PUBLIC_EVENTS = [
    // Subscription messages
    "ready", "nosub", "added", "changed", "removed",
    // Method messages
    "result", "updated",
    // Error messages
    "error"];
    var DEFAULT_RECONNECT_INTERVAL = 10000;

    var DDP = function (_EventEmitter) {
        _inherits(DDP, _EventEmitter);

        _createClass(DDP, [{
            key: "emit",
            value: function emit() {
                var _get2;

                setTimeout((_get2 = _get(DDP.prototype.__proto__ || Object.getPrototypeOf(DDP.prototype), "emit", this)).bind.apply(_get2, [this].concat(Array.prototype.slice.call(arguments))), 0);
            }
        }]);

        function DDP(options) {
            _classCallCheck(this, DDP);

            var _this = _possibleConstructorReturn(this, (DDP.__proto__ || Object.getPrototypeOf(DDP)).call(this));

            _this.status = "disconnected";

            // Default `autoConnect` and `autoReconnect` to true
            _this.autoConnect = options.autoConnect !== false;
            _this.autoReconnect = options.autoReconnect !== false;
            _this.reconnectInterval = options.reconnectInterval || DEFAULT_RECONNECT_INTERVAL;

            _this.messageQueue = new _queue2.default(function (message) {
                if (_this.status === "connected") {
                    _this.socket.send(message);
                    return true;
                } else {
                    return false;
                }
            });

            _this.socket = new _socket2.default(options.SocketConstructor, options.endpoint);

            _this.socket.on("open", function () {
                // When the socket opens, send the `connect` message
                // to establish the DDP connection
                _this.socket.send({
                    msg: "connect",
                    version: DDP_VERSION,
                    support: [DDP_VERSION]
                });
            });

            _this.socket.on("close", function () {
                _this.status = "disconnected";
                _this.messageQueue.empty();
                _this.emit("disconnected");
                if (_this.autoReconnect) {
                    // Schedule a reconnection
                    setTimeout(_this.socket.open.bind(_this.socket), _this.reconnectInterval);
                }
            });

            _this.socket.on("message:in", function (message) {
                if (message.msg === "connected") {
                    _this.status = "connected";
                    _this.messageQueue.process();
                    _this.emit("connected");
                } else if (message.msg === "ping") {
                    // Reply with a `pong` message to prevent the server from
                    // closing the connection
                    _this.socket.send({ msg: "pong", id: message.id });
                } else if ((0, _utils.contains)(PUBLIC_EVENTS, message.msg)) {
                    _this.emit(message.msg, message);
                }
            });

            if (_this.autoConnect) {
                _this.connect();
            }

            return _this;
        }

        _createClass(DDP, [{
            key: "connect",
            value: function connect() {
                this.socket.open();
            }
        }, {
            key: "disconnect",
            value: function disconnect() {
                /*
                *   If `disconnect` is called, the caller likely doesn't want the
                *   the instance to try to auto-reconnect. Therefore we set the
                *   `autoReconnect` flag to false.
                */
                this.autoReconnect = false;
                this.socket.close();
            }
        }, {
            key: "method",
            value: function method(name, params) {
                var id = (0, _utils.uniqueId)();
                this.messageQueue.push({
                    msg: "method",
                    id: id,
                    method: name,
                    params: params
                });
                return id;
            }
        }, {
            key: "sub",
            value: function sub(name, params) {
                var id = arguments.length <= 2 || arguments[2] === undefined ? null : arguments[2];

                id || (id = (0, _utils.uniqueId)());
                this.messageQueue.push({
                    msg: "sub",
                    id: id,
                    name: name,
                    params: params
                });
                return id;
            }
        }, {
            key: "unsub",
            value: function unsub(id) {
                this.messageQueue.push({
                    msg: "unsub",
                    id: id
                });
                return id;
            }
        }]);

        return DDP;
    }(_wolfy87Eventemitter2.default);

    exports.default = DDP;
});