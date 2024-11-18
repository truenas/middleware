# Websocket Events

Events are triggers that are generated under certain scenarios or at a certain period of time.

Some events can accept arguments and return results that are influenced by those arguments.
Follow this format to pass arguments to events:

`event_name:arg`

If  `arg` is accepted by the event, it is parsed automatically. Events that do not accept
arguments only use the event name when subscribing to the event.

% for name, attrs in events.items():
${'###'} ${name}
% if attrs['description']:
${'#####'}  ${attrs['description']|markdown}
% endif

% if attrs['wildcard_subscription']:
This event can be subscribed to with the wildcard `*` as the event name.
% else:
This event cannot be subscribed to with the wildcard `*` as the event name.
% endif

% if attrs['accepts']:
${'####'} Accept Arguments

    :::javascript
    ${attrs['accepts']|n,json,indent}

% endif
% if attrs['returns']:
${'####'} Return Arguments

    :::javascript
    ${attrs['returns']|n,json,indent}

% endif
% endfor

${'##'} Subscribing to Events

Events are generated by the system based on when certain conditions are met. It is not useful
if the system is generating an event and there is no event listener. Listening to events 
is called `subscribing`.

A client can subscribe to all system events by specifying `*`. This only applies to events
that accept `*` as a wildcard (refer to the list above for events that accept `*`).

${'###'} Websocket Client Subscription

Request:

    :::javascript
    {
        "id": "ad4dea8f-53a8-9a5c-1825-523e218c13ca",
        "name": "*",
        "msg": "sub"
    }

Response:

    :::javascript
    {
        "msg": "ready",
        "subs": ["ad4dea8f-53a8-9a5c-1825-523e218c13ca"]
    }
 
The example above subscribes the websocket client to system events that accept `*` as a wildcard.

Each time an event is generated by the system the websocket client would get the event.

Event Response Example:

    :::javascript
    {
        "msg": "changed",
        "collection": "core.get_jobs",
        "id": 79,
        "fields": {
            "id": 79, "method": "pool.scrub.scrub",
            "arguments": ["vol1", "START"], "logs_path": null,
            "logs_excerpt": null,
            "progress": {"percent": 0.001258680822502356, "description": "Scrubbing", "extra": null},
            "result": null, "error": null, "exception": null, "exc_info": null,
            "state": "RUNNING", "time_started": {"$date": 1571297741181},
            "time_finished": null
        }
    }

The event above was generated by the system when a pool is scrubbed.

The example below is how to subscribe to the `reporting.realtime` event.

Request:

    :::javascript
    {
        "id": "8592f7c2-ce2b-4466-443a-80bbae5937d9",
        "name": "reporting.realtime",
        "msg": "sub"
    }

Response:

    :::javascript
    {
        "msg": "ready",
        "subs": ["8592f7c2-ce2b-4466-443a-80bbae5937d9"]
    }

Event Response Example:

    :::javascript
    {
        "msg": "added", "collection": "reporting.realtime",
        "fields": {
            "virtual_memory": {
                "total": 4784615424, "available": 854155264, "percent": 82.1,
                "used": 3779424256, "free": 136634368, "active": 894599168,
                "inactive": 717520896, "buffers": 0, "cached": 0,
                "shared": 188002304, "wired": 2884825088
            },
            "cpu": {"temperature": {}},
            "interfaces": {
                "em0": {
                    "received_bytes": 1068597254, "received_bytes_last": 1068597254,
                    "sent_bytes": 78087857, "sent_bytes_last": 78087857
                },
                "lo0": {
                    "received_bytes": 358364554, "received_bytes_last": 358364554,
                    "sent_bytes": 358360787, "sent_bytes_last": 358360787
                }
            }
        }
    }

The example below is how to subscribe to jobs.

Request:

    :::javascript
    {
        "id": "19922f7c2-ce2b-4455-443a-80bbae5937a2",
        "name": "core.get_jobs",
        "msg": "sub"
    }

Response:

    :::javascript
    {
        "msg": "ready",
        "subs": ["19922f7c2-ce2b-4455-443a-80bbae5937a2"]
    }

Event Response Example:

    :::javascript
    {
        "msg": "added", "collection": "core.get_jobs", "id": 26,
        "fields": {
            "id": 26, "method": "failover.reboot.other_node", "arguments": [],
            "logs_path": null, "logs_excerpt": null,
            "progress": {"percent": null, "description": null, "extra": null},
            "result": null, "error": null, "exception": null, "exc_info": null,
            "state": "WAITING", "time_started": {"$date": 1571305262662},
            "time_finished": null
        }
    }

The event above was generated when a reboot for other HA node was started.
The event response shows that system has registered the job and the job is waiting to be executed.

${'###'} Websocket Client Unsubscription

After the client has consumed the information required and no more updates are required,
an event can be unsubscribed as shown here:

Request:

    :::javascript
    {
        "id": "8592f7c2-ce2b-4466-443a-80bbae5937d9",
        "msg": "unsub"
    }

The server does not send a response for this call. This example unsubscribes
from the `reporting.realtime` event that was subscribed to above. The `id` is the same value
sent when subscribing to the event.