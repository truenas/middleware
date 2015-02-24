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

void print_methods(json_t *methods)
{
    json_t *i;
    size_t idx;

    json_array_foreach(methods, idx, i) {
        printf("\t%s\n", json_string_value(json_object_get(i, "name")));
    }
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

    if (dispatcher_login_service(conn, "enumerator") < 0) {
        perror("cannot login to dispatcher");
        return (1);
    }

    if (dispatcher_call_sync(conn, "discovery.get_services", json_null(), &services) < 0) {
        perror("cannot call get.services");
        return (1);
    }

    json_array_foreach(services, idx, i) {
        printf("Service: %s\n", json_string_value(i));
        if (dispatcher_call_sync(conn, "discovery.get_methods", json_pack("[o]", i), &methods) < 0) {
            perror("cannot call get.methods");
            return (1);
        }

        print_methods(methods);
    }

    dispatcher_close(conn);
    return (0);
}
