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

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <jansson.h>
#include "dispatcher.h"

void on_event(connection_t *conn, const char *name, json_t *args, void *arg)
{
    printf("Event: %s\n", name);
    json_dumpf(args, stdout, JSON_INDENT(4));
    printf("\n");
}

int main(int argc, char *argv[])
{
    json_t *services;
    json_t *methods;
    json_t *i;
    size_t idx;
    connection_t *conn;

    conn = dispatcher_open(argv[1]);
    if (conn == NULL) {
        perror("cannot open dispatcher connection");
        return (1);
    }

    dispatcher_on_event(conn, on_event, NULL);

    if (dispatcher_login_service(conn, "listener") < 0) {
        perror("cannot login to dispatcher");
        return (1);
    }

    if (dispatcher_subscribe_event(conn, "*") < 0) {
        perror("cannot subscribe events");
        return (1);
    }

    pause();
    return (0);
}
