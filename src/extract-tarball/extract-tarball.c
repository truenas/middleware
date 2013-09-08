/*-
 * Copyright 2013 iXsystems, Inc.
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

#include <sys/types.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sysexits.h>
#include <errno.h>
#include <err.h>
#include <fetch.h>
#include <libgen.h>

ssize_t
read_it(char *buf, size_t size, FILE *fp)
{
	int fails;
	int numfails;
	ssize_t  nbytes;

	if (buf == NULL || size <= 0 || fp == NULL)
		return (-1);

	fails = 5;
	numfails = 0;

read_again:
	nbytes = fread(buf, 1, size, fp);
	if (nbytes < 0) {
 		if (errno == EINTR)
			goto read_again;
		else if (errno == EWOULDBLOCK || errno == EAGAIN)
			return (-1);
		else {
			numfails++;
			if (numfails == fails) {
				perror("fread");
				exit(EXIT_FAILURE);
			}
			goto read_again;
		}
	}

	return (nbytes);
}

ssize_t
write_it(const char *buf, size_t size, FILE *fp)
{
	int fails;
	int numfails;
	ssize_t  nbytes;
	size_t  totalbytes;

	if (buf == NULL || size <= 0 || fp == NULL)
		return (-1);
        
	fails = 5;
	numfails = 0;
	totalbytes = 0;
	while (totalbytes < size) {
		nbytes = fwrite(buf + totalbytes, 1, size - totalbytes, fp);
		if (nbytes < 0) {
			if (errno == EINTR)
				continue;
			else if (errno == EWOULDBLOCK || errno == EAGAIN)
				return (-1);
			else {
				numfails++;
				perror("fwrite");
				if (numfails == fails)
					exit(EXIT_FAILURE);
				continue;
			}
		}
		totalbytes += nbytes;
    }
        
	return (totalbytes);
}

void
usage(int argc, char **argv)
{
	fprintf(stderr, "Usage: %s [options]\n"
		"Where option in:\n"
		"  -d <directory>\n"
		"  -f <tar flags>\n"
		"  -s <status file>\n"
		"  -u <url>\n\n",
		basename(argv[0])
	);
}

void
get_the_stuff_we_need(int argc, char **argv,
	char **url, char **dir, char **sfile, char **tflags)
{
	int ch;

	if (argc < 2) {
		usage(argc, argv);
		exit(1);
	}

	opterr = 0;
	while ((ch = getopt(argc, argv, "d:f:s:u:")) != -1) {
		switch (ch) {
			case 'd':
				if (*dir != NULL)
					free(*dir);
				*dir = strdup(optarg);	
				break;
			case 'f':
				if (*tflags != NULL)
					free(*tflags);
				*tflags = strdup(optarg);	
				break;
			case 's':
				if (*sfile != NULL)
					free(*sfile);
				*sfile = strdup(optarg);	
				break;
			case 'u':
				if (*url != NULL)
					free(*url);
				*url = strdup(optarg);
				break;
			case '?':
				usage(argc, argv);
				exit(1);
		}
	}

	if (*url == NULL) {
		fprintf(stderr, "A URL must be specified for this to work!\n");
		exit(1);
	}

	if (*tflags == NULL)
		*tflags = strdup("opzxvf");
	if (*dir == NULL) {
		char *p1, *p2;

		p1 = basename(*url);
		p2 = strsep(&p1, ".");
		if (p2 != NULL && p2[0] != 0)
			*dir = strdup(p2);
		else {
			fprintf(stderr, "A directory must be specified!");
			exit(1);
		}
	}

	if (*sfile == NULL)
		asprintf(sfile, "/var/tmp/.extract.%d", getpid());
}

/*
 *	This program will grab a tarball from a remote site and unpack it
 *	into the filesystem without saving it to the filesystem. 
 */
int
main(int argc, char **argv)
{
	int fd;
	struct stat st;
	char buf[1024];
	FILE *rfp, *fp, *sfp;
	ssize_t rbytes, wbytes, nbytes, total_bytes;
	char *url, *dir, *sfile, *tflags, *cmd, *file;
	struct  url_stat us;

	url = dir = sfile = tflags = cmd = NULL;
	get_the_stuff_we_need(argc, argv, &url, &dir, &sfile, &tflags);

	rfp = fetchGetURL(url, NULL);
	if (rfp == NULL) {
		if (fetchLastErrCode == FETCH_URL) {
			bzero(&st, sizeof(st));
			if (stat(url, &st) == 0) {
				if ((rfp = fopen(url, "r")) == NULL) {
					perror("fopen");
					exit(1);
				}
				total_bytes = st.st_size;
			}

		} else {
			fprintf(stderr, "%s: %s\n", url, fetchLastErrString);
			exit(1);
		}

	} else {
		bzero(&us, sizeof(us));
		if (fetchStatURL(url, &us, NULL) >= 0)
			total_bytes = us.size;
	}

	bzero(&st, sizeof(st));
	if (stat(dir, &st) < 0) {
		if ((fd = mkdir(dir,
			S_IRWXU|S_IRGRP|S_IXGRP|S_IROTH|S_IXOTH)) < 0) {
			perror("stat");
			exit(1);
		}
		if (close(fd) < 0)
			warn("close");
	}

	asprintf(&cmd, "/usr/bin/tar -C %s -%s -", dir, tflags);
	if ((fp = popen(cmd, "w")) == NULL) {
		perror("popen");
		exit(1);
	}
	free(cmd);

	nbytes = 0;
	while (!feof(rfp)) {
		bzero(&buf, sizeof(buf));

		rbytes = read_it(buf, sizeof(buf), rfp);
		wbytes = write_it(buf, rbytes, fp);

		if (rbytes != wbytes) {
			warnx("Houston! We have a problem!\n");
			continue;
		}

		if ((sfp = fopen(sfile, "w")) != NULL) {
			fprintf(sfp, "%s\t%ld\t%ld", basename(url), nbytes, total_bytes);
			fclose(sfp);

		} else
			warnx("Couldn't create status file!");

		nbytes += wbytes;
	}

	if (pclose(fp) < 0)
		warn("pclose");

	if (unlink(sfile) < 0)
		warn("unlink");

	free(url);
	free(dir);
	free(sfile);
	free(tflags);

	return (0);
}
