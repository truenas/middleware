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

#ifndef __DISPATCHER_H
#define __DISPATCHER_H

struct connection;
struct rpc_call;

typedef struct connection connection_t;
typedef struct rpc_call rpc_call_t;

typedef enum error_code
{
    INVALID_JSON_RESPONSE = 1,
    CONNECTION_TIMEOUT,
    CONNECTION_CLOSED,
    RPC_CALL_TIMEOUT,
    SPURIOUS_RPC_RESPONSE,
    LOGOUT,
    OTHER
} error_code_t;

typedef enum rpc_call_status
{
    RPC_CALL_IN_PROGRESS,
    RPC_CALL_DONE,
    RPC_CALL_ERROR
} rpc_call_status_t;

typedef void (error_callback_t)(connection_t *, error_code_t, void *);
typedef void (event_callback_t)(connection_t *, const char *, json_t *, void *);
typedef void (rpc_callback_t)(connection_t *, const char *, json_t *, json_t *, void *);

connection_t *dispatcher_open(const char *);
void dispatcher_close(connection_t *);
int dispatcher_get_fd(connection_t *);
int dispatcher_login_service(connection_t *, const char *);
int dispatcher_call_sync(connection_t *, const char *, json_t *, json_t **);
rpc_call_t *dispatcher_call_async(connection_t *, const char *, json_t *, rpc_callback_t *, void *);
void dispatcher_on_error(connection_t *, error_callback_t *, void *);
void dispatcher_on_event(connection_t *, event_callback_t *, void *);
void rpc_call_wait(rpc_call_t *);
int rpc_call_success(rpc_call_t *);
json_t *rpc_call_result(rpc_call_t *);
void rpc_call_free(rpc_call_t *);
#endif
