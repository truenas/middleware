#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>

#include <sys/select.h>

#define BUFFER_SIZE 1048576


int main(int argc, char **argv) {

	fd_set fds_read, fds_write;
	char buffer[BUFFER_SIZE];
	struct timeval timeout = {1, 0};
	int rv, read_size, write_size, write_accum_size, noop_read_interval, noop_write_interval, flags;

	if(argc != 2) {
		fprintf(stderr, "pipewatcher needs a pid!\n");
		exit(1);
	}

	flags = fcntl(STDIN_FILENO, F_GETFL);
	fcntl(STDIN_FILENO, F_SETFL, flags|O_NONBLOCK);

	flags = fcntl(STDOUT_FILENO, F_GETFL);
	fcntl(STDOUT_FILENO, F_SETFL, flags|O_NONBLOCK);

	signal(SIGPIPE, SIG_IGN);

	noop_read_interval = noop_write_interval = 0;
	FD_ZERO(&fds_read);
	FD_ZERO(&fds_write);

	for(;;) {

		FD_SET(STDIN_FILENO, &fds_read);
		rv = select(STDIN_FILENO+1 , &fds_read, NULL, NULL, &timeout);
		if (rv < 0) {
			exit(1);
		} else if (rv == 0) {
			noop_read_interval++;
			if(noop_read_interval >= 3600) {
				/* We are over 3600 loops (~60 minutes) without receiving data, lets abort!
				 * See #16023 */
				kill(atoi(argv[1]), SIGTERM);
				exit(2);
			}
		} else if (rv) {
			if(!FD_ISSET(STDIN_FILENO, &fds_read)) continue;
			// Reset read interval if something could be read
			noop_read_interval = 0;
			if((read_size = read(STDIN_FILENO, &buffer, BUFFER_SIZE)) == 0) {
				exit(0);
			} else if(read_size == -1 && errno != EAGAIN) {
				perror("Failed to read from stdin");
				exit(1);
			}

			write_accum_size = 0;
			for(;;) {

				write_size = write(STDOUT_FILENO, buffer + write_accum_size, read_size - write_accum_size);

				if(write_size == -1) {
					if(errno != EAGAIN) {
						perror("Failed to write to stdout");
						exit(1);
					}
				} else {
					write_accum_size += write_size;
				}
				if(write_accum_size == read_size) break;


				FD_SET(STDOUT_FILENO, &fds_write);
				rv = select(STDOUT_FILENO+1 , NULL, &fds_write, NULL, &timeout);
				if(rv < 0) {
					exit(1);
				} else if(rv == 0) {
					noop_write_interval++;
					if(noop_write_interval >= 3600) {
						/* We are over 3600 loops (~60 minutes) without receiving data, lets abort!
						 * See #16023 */
						kill(atoi(argv[1]), SIGTERM);
						exit(2);
					}
				} else if(rv) {
					// Reset write interval if something could be written
					noop_write_interval = 0;
				}

			}
		}

	}

	return 0;
}
