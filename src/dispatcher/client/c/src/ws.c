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

#define _WITH_GETLINE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/event.h>
#include <sys/queue.h>
#include <netinet/in.h>
#include <netdb.h>
#include <regex.h>
#include <pthread.h>
#include <jansson.h>
#include "ws.h"

#define LINEMAX 1024

static void *xmalloc(size_t nbytes);
static int xread(int fd, void *buf, size_t nbytes);
static int xwrite(int fd, void *buf, size_t nbytes);
static char *xsubstrdup(char *str, int start, int end);
static int ws_handshake(ws_conn_t *conn);
static int http_parse_uri(ws_conn_t *conn, char *uri);
static void ws_mask(char *buf, size_t len, uint32_t key);
static void *ws_event_loop(void *arg);

static void *
xmalloc(size_t nbytes)
{
    void *ptr = malloc(nbytes);
    memset(ptr, 0, nbytes);
    return ptr;
}

static int
xread(int fd, void *buf, size_t nbytes)
{
    int ret, done = 0;

    while (done < nbytes) {
        ret = read(fd, (void *)(buf + done), nbytes - done);
        if (ret < 0) {
            if (errno == EINTR || errno == EAGAIN)
                continue;

            return (-1);
        }

        done += ret;
    }

    return (done);
}

static int
xwrite(int fd, void *buf, size_t nbytes)
{
    int ret, done = 0;

    while (done < nbytes) {
        ret = write(fd, (void *)(buf + done), nbytes - done);
        if (ret < 0) {
            if (errno == EINTR || errno == EAGAIN)
                continue;

            return (-1);
        }

        done += ret;
    }

    return (done);
}

char *xfgetln(FILE *f)
{
    size_t nbytes = LINEMAX;
    char *buf = xmalloc(nbytes + 1);
    getline(&buf, &nbytes, f);
    return buf;
}

static char *
xsubstrdup(char *str, int start, int end)
{
    char *ret = xmalloc(sizeof(char) * (end - start + 1));
    strncpy(ret, (char *)(str + start), end - start);
    return ret;
}

static int
http_parse_uri(ws_conn_t *conn, char *uri)
{
    int status;
    regex_t re;
    regmatch_t match[4];

    if (regcomp(&re, "http://([^/:]+):([0-9]+)/(.*)", REG_EXTENDED|REG_ICASE) < 0)
        return -1;

    if ((status = regexec(&re, uri, re.re_nsub + 1, match, 0)) < 0)
        return -1;

    struct addrinfo hints = {
            .ai_family = AF_INET,
            .ai_socktype = SOCK_STREAM
    };

    conn->ws_host = xsubstrdup(uri, match[1].rm_so, match[1].rm_eo);
    conn->ws_port = xsubstrdup(uri, match[2].rm_so, match[2].rm_eo);
    conn->ws_path = xsubstrdup(uri, match[3].rm_so, match[3].rm_eo);

    if ((status = getaddrinfo(conn->ws_host, conn->ws_port, &hints, &conn->ws_addrinfo)))
        return -1;

    return 0;
}

ws_conn_t *
ws_connect(const char *uri)
{
    ws_conn_t *conn;
    char *hostname;
    struct addrinfo *ptr;

    conn = xmalloc(sizeof(ws_conn_t));
    conn->ws_uri = strdup(uri);
    conn->ws_fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);

    if (conn->ws_fd < 0)
        goto fail;

    if (http_parse_uri(conn, conn->ws_uri) < 0)
        goto fail;

    for (ptr = conn->ws_addrinfo; ptr; ptr = ptr->ai_next) {
        if (connect(conn->ws_fd, ptr->ai_addr, ptr->ai_addrlen) < 0)
            continue;

        if (ws_handshake(conn) < 0) {
            shutdown(conn->ws_fd, SHUT_RDWR);
            goto fail;
        }

        break;
    }

    if (pthread_create(&conn->ws_thread, NULL, ws_event_loop, conn)) {
        shutdown(conn->ws_fd, SHUT_RDWR);
        goto fail;
    }

    return (conn);

fail:
    free(conn);
    return (NULL);

}

static int
ws_handshake(ws_conn_t *conn)
{
    int status;
    json_t *hdr;
    FILE *f = fdopen(conn->ws_fd, "a+");

    fprintf(f, "GET /%s HTTP/1.1\r\n", conn->ws_path);
    fprintf(f, "Host: %s:%s\r\n", conn->ws_host, conn->ws_port);
    fprintf(f, "Upgrade: websocket\r\n");
    fprintf(f, "Connection: Upgrade\r\n");
    fprintf(f, "Sec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==\r\n");
    fprintf(f, "Sec-WebSocket-Version: 13\r\n");
    fprintf(f, "\r\n");

    if (fscanf(f, "HTTP/1.%*1d %3d %*[^\r\n]\r\n", &status) < 1) {
        errno = EINVAL;
        return (-1);
    }

    conn->ws_headers = json_object();

    for (;;) {
        char *line = xfgetln(f);
        char name[LINEMAX], value[LINEMAX];

        if (line[0] == '\n') {
            free(line);
            break;
        }

        if (sscanf(line, "%[^:\n]: %[^\r\n]\r\n", name, value) < 2) {
            free(line);
            break;
        }

        json_object_set(conn->ws_headers, name, json_string(value));
        free(line);
    }

    if (status == 301 || status == 302) {
        fclose(f);
        shutdown(conn->ws_fd, SHUT_RDWR);
    }

    /*hdr = json_object_get(conn->ws_headers, "Upgrade");
    if (hdr == NULL)
        goto fail;

    if (strcmp(json_string_value(hdr), "websocket"))
        goto fail;

    hdr = json_object_get(conn->ws_headers, "Connection");
    if (hdr == NULL)
        goto fail;

    if (strcmp(json_string_value(hdr), "Upgrade"))
        goto fail;*/

    //fclose(f);
    return (0);

fail:
    json_decref(conn->ws_headers);
    fclose(f);
    return (-1);
}

void
ws_close(ws_conn_t *conn)
{
    shutdown(conn->ws_fd, SHUT_RDWR);

    free(conn->ws_uri);
    free(conn->ws_host);
    free(conn->ws_port);
    free(conn->ws_path);
    freeaddrinfo(conn->ws_addrinfo);
}

int
ws_send_msg(ws_conn_t *conn, void *msg, size_t len, uint8_t opcode)
{
    uint16_t header;
    uint16_t len16;
    uint64_t len64;
    uint32_t mask = 0;
    uint8_t payload_len;

    if (len > 65535) {
        header = WS_FIN | WS_MASK | opcode | WS_PAYLOAD_LEN(127);
        len64 = (uint64_t)len;
        xwrite(conn->ws_fd, &header, sizeof(uint16_t));
        xwrite(conn->ws_fd, &len64, sizeof(uint64_t));
    } else if (len > 125) {
        header = WS_FIN | WS_MASK | opcode | WS_PAYLOAD_LEN(126);
        len64 = (uint16_t)len;
        xwrite(conn->ws_fd, &header, sizeof(uint16_t));
        xwrite(conn->ws_fd, &len16, sizeof(uint16_t));
    } else {
        header = WS_FIN | WS_MASK | opcode | WS_PAYLOAD_LEN(len);
        xwrite(conn->ws_fd, &header, sizeof(uint16_t));
    }

    ws_mask(msg, len, mask);
    xwrite(conn->ws_fd, &mask, sizeof(uint32_t));
    xwrite(conn->ws_fd, msg, len);

    return (0);
}

static void
ws_mask(char *buf, size_t len, uint32_t key)
{
    uint8_t *mask = (uint8_t*)&key;
    int i;

    for (i = 0; i < len; i++)
        buf[i] ^= mask[i % 4];
}

int
ws_recv_msg(ws_conn_t *conn, void **frame, size_t *size, uint8_t *type)
{
    uint16_t header;
    uint16_t len16;
    uint64_t len64;
    uint32_t mask;
    size_t length;
    size_t total = 0;

    for (;;) {
        if (xread(conn->ws_fd, &header, sizeof(uint16_t)) < 0)
            return -1;

        if (WS_PAYLOAD_GET_LEN(header) == 127) {
            xread(conn->ws_fd, &len64, sizeof(uint64_t));
            length = (size_t)ntohl(len64);
        } else if (WS_PAYLOAD_GET_LEN(header) == 126) {
            xread(conn->ws_fd, &len16, sizeof(uint16_t));
            length = (size_t)ntohs(len16);
        } else
            length = (size_t) WS_PAYLOAD_GET_LEN(header);


        *frame = realloc(*frame, length);
        total += length;

        xread(conn->ws_fd, *frame, length);

        if (header & WS_FIN)
            break;
    }

    if (type)
        *type = (uint8_t)(header & 0x7f);
    
    *size = total;
    return (0);
}

static void
ws_process_msg(ws_conn_t *conn, void *frame, size_t size)
{
    conn->ws_message_handler(conn, frame, size, conn->ws_message_handler_arg);
}

static void *
ws_event_loop(void *arg)
{
    ws_conn_t *conn = (ws_conn_t *)arg;
    struct kevent event;
    struct kevent change;
    int i, evs;
    int kq = kqueue();
    void *frame;
    size_t size;

    EV_SET(&change, conn->ws_fd, EVFILT_READ, EV_ADD | EV_ENABLE, 0, 0, 0);

    for (;;) {
        evs = kevent(kq, &change, 1, &event, 1, NULL);
        if (evs < 0) {

        }

        for (i = 0; i < evs; i++) {
            if (event.ident == conn->ws_fd) {
                if (event.flags & EV_EOF)
                    return NULL;

                if (ws_recv_msg(conn, &frame, &size, NULL) < 0)
                    continue;

                ws_process_msg(conn, frame, size);
            }
        }
    }
}

int
ws_get_fd(ws_conn_t *conn)
{
    return conn->ws_fd;
}
