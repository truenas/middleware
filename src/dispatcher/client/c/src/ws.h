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

#ifndef __WS_H
#define __WS_H

#include <stdint.h>
#include <pthread.h>
#include <jansson.h>

#define WS_FIN              (1 << 7)
#define WS_TEXT             (0x01)
#define WS_BINARY           (0x02)
#define WS_CLOSE            (0x08)
#define WS_PING             (0x09)
#define WS_PONG             (0x10)
#define WS_MASK             (1 << 15)
#define WS_PAYLOAD_LEN(x)   ((x & 0x7f) << 8)
#define WS_PAYLOAD_GET_LEN(x) ((x >> 8) & 0x7f)

typedef struct ws_conn
{
    int ws_fd;
    char *ws_uri;
    char *ws_host;
    char *ws_path;
    char *ws_port;
    struct addrinfo *ws_addrinfo;
    pthread_t ws_thread;
    json_t *ws_headers;
    void (*ws_message_handler)(struct ws_conn *conn, void *msg, size_t len, void *arg);
    void *ws_message_handler_arg;
} ws_conn_t;

ws_conn_t *ws_connect(const char *);
void ws_close(ws_conn_t *);
int ws_send_msg(ws_conn_t *, void *, size_t, uint8_t);
int ws_recv_msg(ws_conn_t *, void **, size_t *, uint8_t *);
int ws_get_fd(ws_conn_t *);

#endif  /* __WS_H */