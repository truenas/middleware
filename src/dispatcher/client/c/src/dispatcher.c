/*+
 * Copyright 2015 iXsystems, Inc.
 * All rights reserved
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted providing that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
 * IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 * WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
 * DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
 * STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
 * IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 *
 */

#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <pthread.h>
#include <sys/types.h>
#include <sys/event.h>
#include <sys/time.h>
#include <pthread.h>
#include <jansson.h>

#ifdef __FreeBSD__
#include <uuid.h>
#endif

#ifdef __APPLE__
#include <uuid/uuid.h>
#endif

#include "ws.h"
#include "dispatcher.h"

struct rpc_call
{
    const char *        rc_type;
    const char *        rc_method;
    json_t *            rc_id;
    json_t *            rc_args;
    rpc_call_status_t   rc_status;
    json_t *            rc_result;
    json_t *            rc_error;
    pthread_cond_t      rc_completed;
    pthread_mutex_t     rc_mtx;
    rpc_callback_t *    rc_callback;
    TAILQ_ENTRY(rpc_call) rc_link;
};

struct connection
{
    const char *        conn_uri;
    ws_conn_t *         conn_ws;
    error_callback_t *  conn_error_handler;
    void *              conn_error_handler_arg;
    event_callback_t *  conn_event_handler;
    void *              conn_event_handler_arg;
    int                 conn_rpc_timeout;
    TAILQ_HEAD(rpc_calls_head, rpc_call) conn_calls;
};

static json_t *dispatcher_new_id();
static int dispatcher_call_internal(connection_t *conn, const char *type, struct rpc_call *call);
static json_t *dispatcher_pack_msg(connection_t *conn, const char *ns,
    const char *name, json_t *id, json_t *args);
static int dispatcher_send_msg(connection_t *conn, json_t *msg);
static void dispatcher_process_msg(ws_conn_t *conn, void *frame, size_t len, void *arg);
static void dispatcher_process_rpc(connection_t *conn, json_t *msg);
static void dispatcher_process_events(connection_t *conn, json_t *msg);

connection_t *
dispatcher_open(const char *hostname)
{
    char *uri;

    asprintf(&uri, "http://%s:5000/socket", hostname);
    connection_t *conn = malloc(sizeof(connection_t));
    TAILQ_INIT(&conn->conn_calls);

    conn->conn_ws = ws_connect(uri);
    if (conn->conn_ws == NULL) {
        free(conn);
        return (NULL);
    }

    conn->conn_ws->ws_message_handler = dispatcher_process_msg;
    conn->conn_ws->ws_message_handler_arg = conn;

    if (conn->conn_ws == NULL)
        return (NULL);

    free(uri);
    return (conn);
}

void
dispatcher_close(connection_t *conn)
{

}

int
dispatcher_get_fd(connection_t *conn)
{
    return ws_get_fd(conn->conn_ws);
}

int
dispatcher_login_service(connection_t *conn, const char *name)
{
    struct rpc_call *call;
    json_t *id = dispatcher_new_id();
    json_t *msg;

    call = malloc(sizeof(struct rpc_call));
    pthread_cond_init(&call->rc_completed, NULL);
    pthread_mutex_init(&call->rc_mtx, NULL);
    call->rc_id = id;
    call->rc_type = "auth";
    call->rc_args = json_object();

    TAILQ_INSERT_TAIL(&conn->conn_calls, call, rc_link);

    json_object_set(call->rc_args, "name", json_string(name));

    dispatcher_call_internal(conn, "auth_service", call);
    rpc_call_wait(call);
    return rpc_call_success(call);
}

int dispatcher_subscribe_event(connection_t *conn, const char *name)
{
    json_t *msg;

    msg = dispatcher_pack_msg(conn, "events", "subscribe", json_null(), json_pack("[s]", name));
    return (dispatcher_send_msg(conn, msg));
}

int dispatcher_unsubscribe_event(connection_t *conn, const char *name)
{
    json_t *msg;

    msg = dispatcher_pack_msg(conn, "events", "unsubscribe", json_null(), json_pack("[s]", name));
    return (dispatcher_send_msg(conn, msg));
}

int
dispatcher_call_sync(connection_t *conn, const char *name, json_t *args, json_t **result)
{
    rpc_call_t *call = dispatcher_call_async(conn, name, args, NULL, NULL);
    rpc_call_wait(call);
    *result = rpc_call_result(call);
    return rpc_call_success(call);
}

rpc_call_t *
dispatcher_call_async(connection_t *conn, const char *name, json_t *args,
    rpc_callback_t *cb, void *cb_arg)
{
    struct rpc_call *call;
    json_t *id = dispatcher_new_id();
    json_t *msg;

    call = malloc(sizeof(struct rpc_call));
    pthread_mutex_init(&call->rc_mtx, NULL);
    pthread_cond_init(&call->rc_completed, NULL);
    call->rc_id = id;
    call->rc_type = "call";
    call->rc_method = name;
    call->rc_args = json_object();

    TAILQ_INSERT_TAIL(&conn->conn_calls, call, rc_link);

    json_object_set(call->rc_args, "method", json_string(name));
    json_object_set(call->rc_args, "args", args);
    dispatcher_call_internal(conn, "call", call);

    return (call);
}

void
dispatcher_on_error(connection_t *conn, error_callback_t *cb, void *arg)
{
    conn->conn_error_handler = cb;
    conn->conn_error_handler_arg = arg;
}

void
dispatcher_on_event(connection_t *conn, event_callback_t *cb, void *arg)
{
    conn->conn_event_handler = cb;
    conn->conn_event_handler_arg = arg;
}

void rpc_call_wait(rpc_call_t *call)
{
    pthread_cond_wait(&call->rc_completed, &call->rc_mtx);
}

int rpc_call_success(rpc_call_t *call)
{
    return call->rc_status;
}

json_t *rpc_call_result(rpc_call_t *call)
{
    return call->rc_status == RPC_CALL_DONE ? call->rc_result : call->rc_error;
}

static int
dispatcher_call_internal(connection_t *conn, const char *type, struct rpc_call *call)
{
    json_t *msg;

    msg = dispatcher_pack_msg(conn, "rpc", type, call->rc_id, call->rc_args);
    if (msg == NULL)
        return (-1);

    pthread_mutex_lock(&call->rc_mtx);

    if (dispatcher_send_msg(conn, msg) < 0) {
        json_decref(msg);
        return (-1);
    }

    return (0);
}

static json_t *
dispatcher_pack_msg(connection_t *conn, const char *ns, const char *name, json_t *id, json_t *args)
{
    json_t *obj;

    obj = json_object();
    json_object_set(obj, "namespace", json_string(ns));
    json_object_set(obj, "name", json_string(name));
    json_object_set(obj, "id", id);
    json_object_set(obj, "args", args);

    return (obj);
}

static int
dispatcher_send_msg(connection_t *conn, json_t *msg)
{
    char *str = json_dumps(msg, 0);
    return (ws_send_msg(conn->conn_ws, str, strlen(str), WS_TEXT));
}

static void
dispatcher_process_msg(ws_conn_t *ws, void *frame, size_t len, void *arg)
{
    connection_t *conn = (connection_t *)arg;
    json_t *msg;
    json_error_t err;
    char *framestr;
    const char *ns;

    framestr = (char *)frame;
    framestr = realloc(framestr, len + 1);
    framestr[len] = '\0';

    msg = json_loads(framestr, 0, &err);
    if (msg == NULL) {
        if (conn->conn_error_handler)
            conn->conn_error_handler(conn, INVALID_JSON_RESPONSE, conn->conn_error_handler_arg);

        return;
    }

    ns = json_string_value(json_object_get(msg, "namespace"));

    if (!strcmp(ns, "rpc"))
        dispatcher_process_rpc(conn, msg);

    if (!strcmp(ns, "events"))
        dispatcher_process_events(conn, msg);

}

static void
dispatcher_process_rpc(connection_t *conn, json_t *msg)
{
    rpc_call_t *call;
    const char *name;
    const char *id;
    bool error;

    name = json_string_value(json_object_get(msg, "name"));
    error = !strcmp(name, "error");
    id = json_string_value(json_object_get(msg, "id"));

    TAILQ_FOREACH(call, &conn->conn_calls, rc_link) {
        if (!strcmp(id, json_string_value(call->rc_id))) {
            if (error) {
                call->rc_status = RPC_CALL_ERROR;
                call->rc_error = json_object_get(msg, "args");
            } else {
                call->rc_status = RPC_CALL_DONE;
                call->rc_result = json_object_get(msg, "args");
            }

            pthread_cond_broadcast(&call->rc_completed);
        }
    }
}

static void
dispatcher_process_events(connection_t *conn, json_t *msg)
{
    const char *name;
    const char *evname;
    json_t *args;

    name = json_string_value(json_object_get(msg, "name"));
    args = json_object_get(msg, "args");
    evname = json_string_value(json_object_get(args, "name"));

    if (strcmp(name, "event") != 0)
        return;

    if (conn->conn_event_handler)
        conn->conn_event_handler(conn, evname, json_object_get(args, "args"), conn->conn_event_handler_arg);
}

#ifdef __FreeBSD__
static json_t *
dispatcher_new_id(void)
{
    json_t *id;
    uuid_t uuid;
    uint32_t status;
    char *str;

    uuid_create(&uuid, &status);
    if (status != uuid_s_ok)
        return (NULL);

    uuid_to_string(&uuid, &str, &status);
    if (status != uuid_s_ok)
        return (NULL);

    return json_string(str);
}
#endif

#ifdef __APPLE__
static json_t *
dispatcher_new_id()
{
    uuid_t uuid;
    char str[37];

    uuid_generate(uuid);
    uuid_unparse_lower(uuid, str);
    return json_string(str);
}
#endif
