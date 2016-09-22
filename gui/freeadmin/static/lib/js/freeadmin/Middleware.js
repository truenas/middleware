define([
    "dojo/_base/declare",
    "dojo/_base/lang",
    "dojox/timing",
    "ddpjs/ddp"
    ], function(
    declare,
    lang,
    timing,
    ddp
    ) {

    var Middleware = declare("freeadmin.Middleware", [], {
      token: "",
      _pending: {},
      constructor: function(kwArgs) {
        var me = this;
        this._pending = {};
        lang.mixin(this, kwArgs);
        this._ddp = new ddp.default({
          endpoint: 'ws://' + window.location.host + '/websocket',
          SocketConstructor: WebSocket
        });
        this._ddp.on("connected", lang.hitch(me, me.onConnect));
        this._ddp.on("result", lang.hitch(me, me.onResult));

        var timer = new timing.Timer(1000*50);
        timer.onTick = lang.hitch(me, me.ping);
        timer.start();
      },
      onConnect: function() {
        this.authToken();
      },
      ping: function() {
        this.call("core.ping");
      },
      authToken: function() {
        this.call("auth.token", [this.token]);
      },
      onResult: function(message) {
        var pending = this._pending[message.id];
        if(pending) {
          if(!message.error) {
            if(pending.onSuccess) pending.onSuccess(message.result);
          } else {
            if(pending.onError) pending.onError(message.error);
            else console.log("Middleware call error:", message.error);
          }
        } else {
          console.log("Unknown message: ", message);
        }
      },
      call: function(method, args, onSuccess, onError) {
        var mid = this._ddp.method(method, args);
        this._pending[mid] = {
          onSuccess: onSuccess,
          onError: onError,
        }
      }
    });
    return Middleware;

});
