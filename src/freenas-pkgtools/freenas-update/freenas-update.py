#!/usr/local/bin/python

import getopt
import logging
import logging.config
import os
import sys
import tempfile
sys.path.append("/usr/local/lib")
import freenasOS.Configuration as Configuration
import freenasOS.Manifest as Manifest
import freenasOS.Update as Update


def PrintDifferences(diffs):
    for type in diffs:
        if type == "Packages":
            pkg_diffs = diffs[type]
            for (pkg, op, old) in pkg_diffs:
                if op == "delete":
                    print >> sys.stderr, "Delete package {0}".format(pkg.Name())
                elif op == "install":
                    print >> sys.stderr, "Install package {0}-{1}".format(
                        pkg.Name(), pkg.Version()
                    )
                elif op == "upgrade":
                    print >> sys.stderr, "Upgrade package {0} {1}->{2}".format(
                        pkg.Name(), old.Version(), pkg.Version()
                    )
                else:
                    print >> sys.stderr, "Unknown package operation {0} for packge {1}-{2}".format(
                        op, pkg.Name(), pkg.Version()
                    )
        elif type == "Restart":
            from freenasOS.Update import GetServiceDescription
            for svc in diffs[type]:
                desc = GetServiceDescription(svc)
                if desc:
                    print desc
                else:
                    print "Unknown service restart {0}?!".format(svc)
        elif type in ("Train", "Sequence"):
            # Train and Sequence are a single tuple, (old, new)
            old, new = diffs[type]
            print >> sys.stderr, "{0} {1} -> {2}".format(type, old, new)
        elif type == "Reboot":
            rr = diffs[type]
            print >> sys.stderr, "Reboot is (conditionally) {0}required".format(
                "" if rr else "not "
            )
        else:
            print >> sys.stderr, "*** Unknown key {0} (value {1})".format(type, str(diffs[type]))


class ProgressBar(object):
    def __init__(self):
        self.message = None
        self.percentage = 0
        self.write_stream = sys.stderr
        self.write_stream.write('\n')

    def draw(self):
        progress_width = 40
        filled_width = int(self.percentage * progress_width)
        self.write_stream.write('\033[2K\033[A\033[2K\r')
        self.write_stream.write('Status: {}\n'.format(self.message))
        self.write_stream.write('Total Progress: [{}{}] {:.2%}'.format(
            '#' * filled_width,
            '_' * (progress_width - filled_width),
            self.percentage))

        self.write_stream.flush()

    def update(self, percentage=None, message=None):
        if percentage:
            self.percentage = float(percentage / 100.0)

        if message:
            self.message = message

        self.draw()

    def finish(self):
        self.percentage = 1
        self.draw()
        self.write_stream.write('\n')


class UpdateHandler(object):
    "A handler for Downloading and Applying Updates calls"

    def __init__(self, update_progress=None):
        self.progress = 0
        self.details = ''
        self.finished = False
        self.error = False
        self.indeterminate = False
        self.reboot = False
        self.pkgname = ''
        self.pkgversion = ''
        self.operation = ''
        self.filesize = 0
        self.numfilestotal = 0
        self.numfilesdone = 0
        self._baseprogress = 0
        self.master_progress = 0
        # Below is the function handle passed to this by the caller so that
        # its status and progress can be updated accordingly
        self.update_progress = update_progress

    def check_handler(self, index, pkg, pkgList):
        self.pkgname = pkg.Name()
        self.pkgversion = pkg.Version()
        self.operation = 'Downloading'
        self.details = 'Downloading {0}'.format(self.pkgname)
        stepprogress = int((1.0 / float(len(pkgList))) * 100)
        self._baseprogress = index * stepprogress
        self.progress = (index - 1) * stepprogress

    def get_handler(self, method, filename, size=None, progress=None, download_rate=None):
        if progress is not None:
            self.progress = (progress * self._baseprogress) / 100
            if self.progress == 0:
                self.progress = 1
            display_size = ' Size: {0}'.format(size) if size else ''
            display_rate = ' Rate: {0} B/s'.format(download_rate) if download_rate else ''
            self.details = 'Downloading: {0} Progress:{1}{2}{3}'.format(
                self.pkgname, progress, display_size, display_rate
                )

        # Doing the drill below as there is a small window when
        # step*progress logic does not catch up with the new value of step
        if self.progress >= self.master_progress:
            self.master_progress = self.progress
        if self.update_progress is not None:
            self.update_progress(self.master_progress, self.details)


def download_update_call(train, download_dir, pkg_type, verbose=False):
    if not verbose:
        progress_bar = ProgressBar()
        handler = UpdateHandler(progress_bar.update)
        rv = Update.DownloadUpdate(
            train,
            download_dir,
            get_handler=handler.get_handler,
            check_handler=handler.check_handler,
            pkg_type=pkg_type,
        )
        progress_bar.finish()
    else:
        rv = Update.DownloadUpdate(
            train,
            download_dir,
            pkg_type=pkg_type,
        )
    return rv


# Lets try to write a logging Filter to sift "TryGetNetworkFile" logs
class StartsWithFilter(logging.Filter):
    def __init__(self, params):
        self.params = params

    def filter(self, record):
        if self.params:
            allow = not any(record.msg.startswith(x) for x in self.params)
        else:
            allow = True
        return allow


def main():
    global log

    log_config_dict = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'simple': {
                'format': '[%(name)s:%(lineno)s] %(message)s',
            },
        },
        'filters': {
            'cleandownload': {
                '()': StartsWithFilter,
                'params': ['TryGetNetworkFile', 'Searching']
            }
        },
        'handlers': {
            'std': {
                'class': 'logging.StreamHandler',
                'level': 'DEBUG',
                'stream': 'ext://sys.stderr',
            },
        },
        'loggers': {
            '': {
                'handlers': ['std'],
                'level': 'DEBUG',
                    'propagate': True,
            },
        }
    }

    def usage():
        print >> sys.stderr, """Usage: %s [-C cache_dir] [-d] [-T train] [--no-delta] [-v] <cmd>, where cmd is one of:
        check\tCheck for updates
        update\tDo an update""" % sys.argv[0]
        sys.exit(1)

    try:
        short_opts = "C:dT:v"
        long_opts = [
            "cache=",
            "debug",
            "train=",
            "verbose",
            "no-delta"
        ]
        opts, args = getopt.getopt(sys.argv[1:], short_opts, long_opts)
    except getopt.GetoptError as err:
        print str(err)
        usage()

    verbose = False
    debug = 0
    config = None
    cache_dir = None
    train = None
    pkg_type = None

    for o, a in opts:
        if o in ("-v", "--verbose"):
            verbose = True
        elif o in ("-d", "--debug"):
            debug += 1
        elif o in ('-C', "--cache"):
            cache_dir = a
        elif o in ("-T", "--train"):
            train = a
        elif o in ("--no-delta"):
            pkg_type = Update.PkgFileFullOnly
        else:
            assert False, "unhandled option {0}".format(o)

    if not verbose:
        log_config_dict['handlers']['std']['filters'] = ['cleandownload']
    logging.config.dictConfig(log_config_dict)

    log = logging.getLogger('freenas-update')

    config = Configuration.Configuration()
    if train is None:
        train = config.SystemManifest().Train()

    if len(args) != 1:
        usage()

    if args[0] == "check":
        # To see if we have an update available, we
        # call Update.DownloadUpdate.  If we have been
        # given a cache directory, we pass that in; otherwise,
        # we make a temporary directory and use that.  We
        # have to clean up afterwards in that case.

        if cache_dir is None:
            download_dir = tempfile.mkdtemp(prefix="UpdateCheck-", dir=config.TemporaryDirectory())
            if download_dir is None:
                print >> sys.stderr, "Unable to create temporary directory"
                sys.exit(1)
        else:
            download_dir = cache_dir

        rv = download_update_call(train, download_dir, pkg_type, verbose)
        if rv is False:
            if verbose:
                print "No updates available"
            if cache_dir is None:
                Update.RemoveUpdate(download_dir)
            sys.exit(1)
        else:
            diffs = Update.PendingUpdatesChanges(download_dir)
            if diffs is None or len(diffs) == 0:
                print >> sys.stderr, "Strangely, DownloadUpdate says there updates, but PendingUpdates says otherwise"
                sys.exit(1)
            PrintDifferences(diffs)
            if cache_dir is None:
                Update.RemoveUpdate(download_dir)
            sys.exit(0)

    elif args[0] == "update":
        # This will attempt to apply an update.
        # If cache_dir is given, then we will only check that directory,
        # not force a download if it is already there.  If cache_dir is not
        # given, however, then it downloads.  (The reason is that you would
        # want to run "freenas-update -c /foo check" to look for an update,
        # and it will download the latest one as necessary, and then run
        # "freenas-update -c /foo update" if it said there was an update.
        try:
            update_opts, update_args = getopt.getopt(args[1:], "R", "--reboot")
        except getopt.GetoptError as err:
            print str(err)
            usage()

        force_reboot = False
        for o, a in update_opts:
            if o in ("-R", "--reboot"):
                force_reboot = True
            else:
                assert False, "Unhandled option {0}".format(o)

        if cache_dir is None:
            download_dir = tempfile.mkdtemp(
                prefix="UpdateUpdate-",
                dir=config.TemporaryDirectory()
            )
            if download_dir is None:
                print >> sys.stderr, "Unable to create temporary directory"
                sys.exit(1)
            rv = download_update_call(train, download_dir, pkg_type, verbose)
            if rv is False:
                if verbose or debug:
                    print >> sys.stderr, "DownloadUpdate returned False"
                sys.exit(1)
        else:
            download_dir = cache_dir

        diffs = Update.PendingUpdatesChanges(download_dir)
        if diffs is None or diffs == {}:
            if verbose:
                print >> sys.stderr, "No updates to apply"
        else:
            if verbose:
                PrintDifferences(diffs)
            try:
                rv = Update.ApplyUpdate(download_dir, force_reboot=force_reboot)
            except BaseException as e:
                print >> sys.stderr, "Unable to apply update: {0}".format(e)
                sys.exit(1)
            if cache_dir is None:
                Update.RemoveUpdate(download_dir)
            if rv:
                print >> sys.stderr, "System should be rebooted now"
            sys.exit(0)
    else:
        usage()

if __name__ == "__main__":
    sys.exit(main())
