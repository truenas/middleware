

function Middleware(uri)
{
    this.socket = null;
    this.rpcTimeout = 10000;
    this.pendingCalls = {};
}

function uuid()
{
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c)
    {
        var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

Middleware.prototype.connect = function(url)
{
    var self = this;
    this.socket = new eio.Socket(url, {"path": "/socket"});
    this.socket.on("message", function(data) {
        self.on_message(data);
    });
    this.socket.on("open", function() {
        self.emit("connected");
    });
};

Middleware.prototype.subscribe = function(event_masks)
{
    this.socket.send(this.pack("events", "subscribe", event_masks));
};

Middleware.prototype.unsubscribe = function(event_masks)
{
    this.socket.send(this.pack("events", "unsubscribe", event_masks));
};

Middleware.prototype.call = function(method, args, callback)
{
    var self = this;
    var id = uuid();
    var payload = {
        "method": method,
        "args": args,
    }

    this.pendingCalls[id] = {
        "method": method,
        "args": args,
        "callback": callback,
        "timeout": setTimeout(function() {
            self.on_rpc_timeout(id);
        }, this.rpcTimeout)
    };

    this.socket.send(this.pack("rpc", "call", payload, id));
};

Middleware.prototype.on_rpc_timeout = function(data)
{

};

Middleware.prototype.on_message = function(msg)
{
    var data = JSON.parse(msg);

    if (data.namespace == "events" && data.name == "event")
        this.emit("event", data.args);

    if (data.namespace == "rpc") {
        if (data.name == "response") {
            if (!(data.id in this.pendingCalls)) {
                /* Spurious reply, just ignore it */
                return
            }
            call = this.pendingCalls[data.id];
            call.callback(data.args);
            clearTimeout(call.timeout);
            delete this.pendingCalls[data.id];
        }

        if (data.name == "error") {
            this.emit("error", data.args);
        }
    }
};

Middleware.prototype.pack = function(namespace, name, args, id)
{
    return JSON.stringify({
        "namespace": namespace,
        "id": id || uuid(),
        "name": name,
        "args": args
    });
};

Emitter(Middleware.prototype);