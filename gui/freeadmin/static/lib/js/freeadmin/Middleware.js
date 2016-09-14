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
      constructor: function(kwArgs) {
        var me = this;
        lang.mixin(this, kwArgs);
        this._ddp = new ddp.default({
          endpoint: 'ws://' + window.location.host + '/websocket',
          SocketConstructor: WebSocket
        });
        this._ddp.on("connected", lang.hitch(me, me.onConnect));

        var timer = new timing.Timer(1000*60*5);
        timer.onTick = lang.hitch(me, me.authToken);
        timer.start();
      },
      onConnect: function() {
        this.authToken();
      },
      authToken: function() {
        var mid = this._ddp.method("auth.token", [this.token]);
      }
    });
    return Middleware;

});
