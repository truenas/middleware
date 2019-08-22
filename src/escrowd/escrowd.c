/*-
 * Copyright (c) 2015 iXsystems, Inc.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 */

/*
 * Escrow daemon.
 *
 * The escrow daemon accepts incoming commands via /tmp/escrowd.sock and
 * responds requests from a client.
 *
 * The daemon expects each request be passed via the socket in one message.
 *
 * Commands:
 *
 * - SETKEY <passphrase>
 *   Sets the stored passphrase to specified one.
 *
 * - CLEAR
 *   Clears the saved passphrase.
 *
 * - REVEAL
 *   Reveal the passphrase.
 *
 * - STATUS
 *   Request the status of daemon.  Which can be one of:
 *   init, keyd, transferred.
 *
 * - SHUTDOWN
 *   Shutdown daemon.
 *
 * - QUIT
 *   Gracefully end session.  The daemon would close connection anyway so
 *   this is optional.
 */

#include <sys/cdefs.h>
#include <sys/param.h>
#include <sys/types.h>
#include <sys/event.h>
#include <sys/mman.h>
#include <sys/time.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/queue.h>
#include <sys/procctl.h>

#include <err.h>
#include <errno.h>
#include <libutil.h>
#include <pthread.h>
#include <paths.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <syslog.h>
#include <sysexits.h>
#include <unistd.h>

static int	local_s;

#define MSGBUF_SIZE	256
#define _PATH_ESCROWDPID	_PATH_VARRUN "escrowd.pid"

/* Stored passphrase */
static char *passphrase = NULL;

static int		escrow_ncpus	= -1;
static int		escrow_workers	= 0;
static const char	*pid_file	= _PATH_ESCROWDPID;
static struct pidfh	*pfh		= NULL;

static TAILQ_HEAD(req_head, req) req_head = TAILQ_HEAD_INITIALIZER(req_head);
typedef struct req {
	int	fd;
	size_t	msglen;
	char	msg[MSGBUF_SIZE];
	TAILQ_ENTRY(req)	entries;
} req_t;

static pthread_mutex_t	req_mtx = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t	req_cv = PTHREAD_COND_INITIALIZER;

/*
 * Enqueue a task
 */
static void
enqueue_task(int fd, char *message, size_t msglen)
{
	req_t *request;

	request = calloc(1, sizeof(*request));
	if (request == NULL)
		err(1, "Unable to allocate memory");

	request->fd = fd;
	request->msglen = msglen;
	strlcpy(request->msg, message, sizeof(request->msg));

	pthread_mutex_lock(&req_mtx);
	TAILQ_INSERT_TAIL(&req_head, request, entries);
	pthread_cond_signal(&req_cv);
	pthread_mutex_unlock(&req_mtx);
}

static int
conn_add(int fd)
{
	return (0);
}

static void
conn_delete(int fd)
{

	close(fd);
}

static void
send_msg(int s, char *message, ...)
{
	char buf[MSGBUF_SIZE];
	int len;

	memset(buf, 0, sizeof(buf));

	va_list ap;
	va_start(ap, message);
	len = vsnprintf(buf, sizeof(buf), message, ap);
	va_end(ap);
	send(s, buf, len, 0);
}

static void
handle_setkey(req_t *request)
{
	char *cmdbuf = request->msg;
	char *phrase, *token, *string;
	size_t phraselen;

	token = string = cmdbuf;

	token = strsep(&string, " \n");
	if (token != NULL)
		token = strsep(&string, " \n");
	if (token != NULL) {
		phraselen = strlen(token) + 1;
		if (phraselen <= 1) {
			send_msg(request->fd, "450 empty phrase.\n");
			return;
		}
		phrase = malloc(phraselen);
		strlcpy(phrase, token, phraselen);

		free(passphrase);
		passphrase = phrase;

		send_msg(request->fd, "250 setkey accepted.\n");
		return;
	} else {
		send_msg(request->fd, "500 Error.\n");
	}
}

static void
handle_clear(req_t *request)
{

	free(passphrase);
	passphrase = NULL;

	send_msg(request->fd, "200 clear succeeded.\n");
}

static void
handle_quit(req_t *request)
{

	send_msg(request->fd, "250 Goodbye.\n");
	close(request->fd);
}

static void
handle_shutdown(req_t *request)
{
	send_msg(request->fd, "250 Shutting down.\n");
	pidfile_remove(pfh);
	exit(0);
}

static void
handle_reveal(req_t *request)
{

	if (passphrase == NULL) {
		send_msg(request->fd, "404 No passphrase present\n");
		return;
	}

	send_msg(request->fd, "200 Approved\n");
	send_msg(request->fd, "%s\n", passphrase);
}

static void
handle_status(req_t *request)
{
	if (passphrase == NULL)
		send_msg(request->fd, "200 init\n");
	else
		send_msg(request->fd, "200 keyd\n");
}

typedef struct cmdtab_t {
	void (*handle)(req_t *);
	const char	*cmd;
	size_t		 cmdlen;
} cmdtab_t;

cmdtab_t cmdtab[] = {
	{ .handle = handle_setkey, .cmd = "SETKEY" },
	{ .handle = handle_quit, .cmd = "QUIT" },
	{ .handle = handle_shutdown, .cmd = "SHUTDOWN" },
	{ .handle = handle_reveal, .cmd = "REVEAL" },
	{ .handle = handle_clear, .cmd = "CLEAR" },
	{ .handle = handle_status, .cmd = "STATUS" },
};

const size_t cmdtab_entries = howmany(sizeof(cmdtab), sizeof(cmdtab[0]));

static void
recv_msg(int s)
{
	char buf[MSGBUF_SIZE];
	size_t bytes_read;

	memset(buf, 0, sizeof(buf));

	bytes_read = recv(s, buf, sizeof(buf), 0);
	enqueue_task(s, buf, bytes_read);
}

static void
handle_msg(req_t *request)
{
	int i;

	for (i = 0; i< cmdtab_entries; i++) {
		if (request->msglen >= cmdtab[i].cmdlen) {
			if (memcmp(request->msg, cmdtab[i].cmd, cmdtab[i].cmdlen) == 0) {
				cmdtab[i].handle(request);
				memset(request, 0, sizeof(*request));
				return;
			}
		}
	}
	send_msg(request->fd, "550 Unrecognized command.\n");
}

static void *
message_worker(void *dummy __unused)
{
	req_t *qe;

	pthread_mutex_lock(&req_mtx);
	for (;;) {
		qe = TAILQ_FIRST(&req_head);
		if (qe == NULL) {
			pthread_cond_wait(&req_cv, &req_mtx);
		} else {
			TAILQ_REMOVE(&req_head, qe, entries);
			pthread_mutex_unlock(&req_mtx);
			handle_msg(qe);
			pthread_mutex_lock(&req_mtx);
		}
	}
}

static void
event_loop(int kq)
{
	int nev, i;
	struct kevent kev;
	struct kevent event_list[32];
	struct sockaddr_storage addr;
	socklen_t socklen = sizeof(addr);
	int fd;

	while(1) {
		nev = kevent(kq, NULL, 0, event_list, 32, NULL);
		if (nev < 1)
			err(1, "kevent");
		for (i = 0; i < nev; i++) {
			if (event_list[i].flags & EV_EOF) {
				fd = event_list[i].ident;
				EV_SET(&kev, fd, EVFILT_READ, EV_DELETE, 0, 0, NULL);
				if (kevent(kq, &kev, 1, NULL, 0, NULL) == -1)
					err(1, "kevent");
				conn_delete(fd);
			} else if (event_list[i].ident == local_s) {
				fd = accept(event_list[i].ident,
					(struct sockaddr *)&addr, &socklen);
				if (fd == -1)
					err(1, "accept");

				if (conn_add(fd) == 0) {
					EV_SET(&kev, fd, EVFILT_READ, EV_ADD, 0, 0, NULL);
					if (kevent(kq, &kev, 1, NULL, 0, NULL) == -1)
						err(1, "kevent");
					send_msg(fd, "220 Ready, go ahead\n");
				} else {
					printf("connection refused\n");
					close(fd);
				}
			} else {
				recv_msg(event_list[i].ident);
			}
		}
	}

	exit(EX_OK);
}

#define NUM_OF_THREADS 1
pthread_t threads[NUM_OF_THREADS];

int
main(void)
{
	int kq, i;
#ifdef PROC_TRACE_CTL_DISABLE_EXEC
	int flags = PROC_TRACE_CTL_DISABLE_EXEC;
#endif
	pid_t otherpid;
	struct sockaddr_un sun;
	struct kevent kev;

	pfh = pidfile_open(pid_file, 0644, &otherpid);
	if (pfh == NULL) {
		if (errno == EEXIST) {
			fprintf(stderr, "%s already running, pid: %d\n",
				getprogname(), otherpid);
			syslog(LOG_ERR, "%s already running, pid: %d",
				getprogname(), otherpid);
			exit(EX_OSERR);
		}
		warnx("pidfile_open() failed: ");
		syslog(LOG_WARNING, "pidfile_open() failed: %m");
	}

	if (daemon(0, 0) == -1) {
		warn("Cannot daemonize");
		pidfile_remove(pfh);
		exit(EXIT_FAILURE);
	}

	unlink("/tmp/escrowd.sock");
	pidfile_write(pfh);

	memset(&threads, 0, sizeof(threads));

	/* Spawn workers */
	for (int i = 0; i < NUM_OF_THREADS; i++)
		pthread_create(&threads[i], NULL, message_worker, NULL);

	memset(&sun, 0, sizeof(struct sockaddr_un));
	local_s = socket(AF_UNIX, SOCK_STREAM, 0);
	sun.sun_family = AF_UNIX;
	strlcpy(sun.sun_path, "/tmp/escrowd.sock", sizeof(sun.sun_path));
	bind(local_s, (struct sockaddr *)&sun, SUN_LEN(&sun));
	listen(local_s, 8);

	kq = kqueue();

	for (i = 0; i < cmdtab_entries; i++)
		cmdtab[i].cmdlen = strlen(cmdtab[i].cmd);

	/* Add listening socket to watch list */
	EV_SET(&kev, local_s, EVFILT_READ, EV_ADD, 0, 0, NULL);
	if (kevent(kq, &kev, 1, NULL, 0, NULL) == -1)
		err(1, "kevent");

	if (mlockall(MCL_CURRENT | MCL_FUTURE) == -1) {
		fprintf(stderr, "Unable to lock memory, exiting\n");
		exit(EX_UNAVAILABLE);
	}
#ifdef PROC_TRACE_CTL
	procctl(P_PID, getpid(), PROC_TRACE_CTL, &flags);
#endif

	event_loop(kq);
	return 0;
}
