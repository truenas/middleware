define([
    "dojo/_base/declare",
    "dojo/_base/lang",
    "dojo/request/xhr",
    "dojox/timing",
    "ddpjs/ddp"
    ], function(
    declare,
    lang,
    xhr,
    timing,
    ddp
    ) {

    var Middleware = declare("freeadmin.Middleware", [], {
      tokenUrl: "",
      _pending: {},
      constructor: function(kwArgs) {
        var me = this;
        this._pending = {};
        this._subs = {};
        this._jobs = {};
        lang.mixin(this, kwArgs);
        this._ddp = new ddp.default({
          endpoint: (window.location.protocol == 'http:' ? 'ws://' : 'wss://') + window.location.host + '/websocket',
          SocketConstructor: WebSocket
        });
        this._ddp.on("connected", lang.hitch(me, me.onConnect));
        this._ddp.on("result", lang.hitch(me, me.onResult));
        this._ddp.on("ready", lang.hitch(me, me.onReady));
        this._ddp.on("changed", lang.hitch(me, me.onChanged));

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
        var me = this;
        xhr.get(this.tokenUrl, {handleAs: "json"}).then(function(data) {
          me.call("auth.token", [data.token], function(data) {
            me.sub("core.get_jobs", lang.hitch(me, me.jobsCallback));
          });
        });
      },
      onResult: function(message) {
        var pending = this._pending[message.id];
        if(pending) {
          if(pending.isJob) {
             this._jobs[message.result] = pending;
            return null;
          }
          if(!message.error) {
            if(pending.onSuccess) pending.onSuccess(message.result);
          } else {
            if(pending.onError) pending.onError(message.error);
            else console.log("Middleware call error:", message.error);
          }
          delete this._pending[message.id];
        } else {
          console.log("Unknown message: ", message);
        }
      },
      onReady: function(message) {
      },
      onChanged: function(message) {
        if(!this._subs[message.collection]) {
          return;
        }
        for(var i=0;i<this._subs[message.collection].length;i++) {
          var sub = this._subs[message.collection][i];
          sub['callback']('CHANGED', message);
        }
      },
      jobsCallback: function(mtype, data) {
        var me = this;
        job = me._jobs[data.fields.id];
        if(!job) return;
        if(data.fields.state == 'SUCCESS') {
          if(job.onSuccess) job.onSuccess(data.fields);
          delete me._jobs[data.fields.id];
        } else if(data.fields.state == 'FAILED' || data.fields.state == 'ABORTED') {
          if(job.onError) job.onError(data.fields);
          delete me._jobs[data.fields.id];
        } else if(data.fields.state == 'RUNNING') {
          if(job.onProgress) job.onProgress(data.fields);
        }
      },
      sub: function(name, callback) {
        var subId = this._ddp.sub(name);
        if(!this._subs[name]) {
          this._subs[name] = [];
        }
        this._subs[name].push({
          callback: callback,
          subId: subId
        });
        return subId;
      },
      unsub: function(subId) {
        for(key in this._subs) {
          for(var i=0;i<this._subs[key].length;i++) {
            var item = this._subs[key][i];
            if(item.subId == subId) {
              this._subs[key].splice(i, 1);
            }
          }
        }
        this._ddp.unsub(subId);
      },
      call: function(method, args, onSuccess, onError, isJob, onProgress) {
        var mid = this._ddp.method(method, args);
        this._pending[mid] = {
          onSuccess: onSuccess,
          onError: onError,
          onProgress: onProgress,
          isJob: isJob
        }
      }
    });
    return Middleware;

});
