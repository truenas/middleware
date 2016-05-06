#!/usr/local/bin/python
from __future__ import print_function

import getopt
import logging
import logging.config
import os
import sys
import tarfile
import shutil

sys.path.append("/usr/local/lib")

import freenasOS.Configuration as Configuration
import freenasOS.Update as Update
import freenasOS.Exceptions as Exceptions


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


class StartsWithFilter(logging.Filter):
    def __init__(self, params):
        self.params = params

    def filter(self, record):
        if self.params:
            allow = not any(record.msg.startswith(x) for x in self.params)
        else:
            allow = True
        return allow


def ExtractFrozenUpdate(tarball, dest_dir, verbose=False):
    """
    Extract the files in the given tarball into dest_dir.
    This assumes dest_dir already exists.
    """
    try:
        tf = tarfile.open(tarball)
    except BaseException as e:
        print("Unable to open tarball %s: %s" % (tarball, str(e)), file=sys.stderr)
        sys.exit(1)
    files = tf.getmembers()
    for f in files:
        if f.name in ("./", ".", "./."):
            continue
        if not f.name.startswith("./"):
            if verbose:
                print("Illegal member %s" % f, file=sys.stderr)
            continue
        if len(f.name.split("/")) != 2:
            if verbose:
                print("Illegal member name %s has too many path components" % f.name, file=sys.stderr)
            continue
        if verbose:
            print("Extracting %s" % f.name, file=sys.stderr)
        tf.extract(f.name, path=dest_dir)
        if verbose:
            print("Done extracting %s" % f.name, file=sys.stderr)
    return True


def PrintDifferences(diffs):
    for type in diffs:
        if type == "Packages":
            pkg_diffs = diffs[type]
            for (pkg, op, old) in pkg_diffs:
                if op == "delete":
                    print("Delete package %s" % pkg.Name(), file=sys.stderr)
                elif op == "install":
                    print("Install package %s-%s" % (pkg.Name(), pkg.Version()), file=sys.stderr)
                elif op == "upgrade":
                    print("Upgrade package %s %s->%s" % (pkg.Name(), old.Version(), pkg.Version()), file=sys.stderr)
                else:
                    print("Unknown package operation %s for packge %s-%s" % (op, pkg.Name(), pkg.Version()), file=sys.stderr)
        elif type == "Restart":
            for svc in diffs[type]:
                desc = Update.GetServiceDescription(svc)
                if desc:
                    print("%s" % desc)
                else:
                    print("Unknown service restart %s?!" % svc)
        elif type in ("Train", "Sequence"):
            # Train and Sequence are a single tuple, (old, new)
            old, new = diffs[type]
            print("%s %s -> %s" % (type, old, new), file=sys.stderr)
        elif type == "Reboot":
            rr = diffs[type]
            print("Reboot is (conditionally) %srequired" % ("" if rr else "not "), file=sys.stderr)
        else:
            print("*** Unknown key %s (value %s)" % (type, str(diffs[type])), file=sys.stderrr)


def DoDownload(train, cache_dir, pkg_type, verbose):

    try:
        if not verbose:
            progress_bar = ProgressBar()
            handler = UpdateHandler(progress_bar.update)
            rv = Update.DownloadUpdate(
                train,
                cache_dir,
                get_handler=handler.get_handler,
                check_handler=handler.check_handler,
                pkg_type=pkg_type,
            )
            if rv is False:
                progress_bar.update(message="No updates available")
            progress_bar.finish()
        else:
            rv = Update.DownloadUpdate(train, cache_dir, pkg_type=pkg_type)
    except Exceptions.ManifestInvalidSignature:
        log.error("Manifest has invalid signature")
        print("Manifest has invalid signature", file=sys.stderr)
        sys.exit(1)
    except Exceptions.UpdateBusyCacheException as e:
        log.error(str(e))
        print("Download cache directory is busy", file=sys.stderr)
        sys.exit(1)
    except Exceptions.UpdateIncompleteCacheException:
        log.error(str(e))
        print("Incomplete download cache, cannot update", file=sys.stderr)
        sys.exit(1)
    except Exceptions.ChecksumFailException as e:
        log.error(str(e))
        print("Checksum error, cannot update", file=sys.stderr)
        sys.exit(1)
    except Exceptions.UpdateInvalidUpdateException as e:
        log.error(str(e))
        print("Update not allowed:\n%s" % e.value, file=sys.stderr)
        sys.exit(1)
    except BaseException as e:
        log.error(str(e))
        print("Received exception during download phase, cannot update", file=sys.stderr)
        sys.exit(1)

    return rv


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
        },
    }

    def usage():
        print("""Usage: %s [-C cache_dir] [-d] [-T train] [--no-delta] [-v] <cmd>, where cmd is one of:
        check\tCheck for updates
        update\tDo an update""" % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    try:
        short_opts = "C:dT:v"
        long_opts = [
            "cache=",
            "debug",
            "train=",
            "verbose",
            "no-delta",
            "snl"
        ]
        opts, args = getopt.getopt(sys.argv[1:], short_opts, long_opts)
    except getopt.GetoptError as err:
        print(str(err))
        usage()

    verbose = False
    debug = 0
    config = None
    # Should I get this from a configuration file somewhere?
    cache_dir = "/var/db/system/update"
    train = None
    pkg_type = None
    snl = False

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
        elif o in ("--snl"):
            snl = True
        else:
            assert False, "unhandled option %s" % o

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

        rv = DoDownload(train, cache_dir, pkg_type, verbose)
        if rv is False:
            if verbose:
                print("No updates available")
            Update.RemoveUpdate(cache_dir)
            sys.exit(1)
        else:
            diffs = Update.PendingUpdatesChanges(cache_dir)
            if diffs is None or len(diffs) == 0:
                print("Strangely, DownloadUpdate says there updates, but PendingUpdates says otherwise", file=sys.stderr)
                sys.exit(1)
            PrintDifferences(diffs)
            if snl:
                print("I've got a fever, and the only prescription is applying the pending update.")
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
            print(str(err))
            usage()

        force_reboot = False
        for o, a in update_opts:
            if o in ("-R", "--reboot"):
                force_reboot = True
            else:
                assert False, "Unhandled option %s" % o

        # See if the cache directory has an update downloaded already
        do_download = True
        try:
            f = Update.VerifyUpdate(cache_dir)
            if f:
                f.close()
                do_download = False
        except Exceptions.UpdateBusyCacheException:
            print("Cache directory busy, cannot update")
            sys.exit(0)
        except (Exceptions.UpdateInvalidCacheException, Exceptions.UpdateIncompleteCacheException):
            pass
        except:
            raise

        if do_download:
            rv = DoDownload(train, cache_dir, pkg_type, verbose)

        diffs = Update.PendingUpdatesChanges(cache_dir)
        if diffs is None or diffs == {}:
            if verbose:
                print("No updates to apply", file=sys.stderr)
        else:
            if verbose:
                PrintDifferences(diffs)
            try:
                rv = Update.ApplyUpdate(cache_dir, force_reboot=force_reboot)
            except BaseException as e:
                print("Unable to apply update: %s" % str(e), file=sys.stderr)
                sys.exit(1)
            if rv:
                print("System should be rebooted now", file=sys.stderr)
                if snl:
                    print("Really explore the space.")
            sys.exit(0)
    elif tarfile.is_tarfile(args[0]):
        # Frozen tarball.  We'll extract it into the cache directory, and
        # then add a couple of things to make it pass sanity, and then apply it.
        # For now we just copy the code above.
        # First, remove the cache directory
        # Hrm, could overstep a locked file.
        shutil.rmtree(cache_dir, ignore_errors=True)
        try:
            os.makedirs(cache_dir)
        except BaseException as e:
            print("Unable to create cache directory %s: %s" % (cache_dir, str(e)))
            sys.exit(1)
        try:
            ExtractFrozenUpdate(args[0], cache_dir, verbose=verbose)
        except BaseException as e:
            print("Unable to extract frozen update %s: %s" % (args[0], str(e)))
            sys.exit(1)
        # Exciting!  Now we need to have a SEQUENCE file, or it will fail verification.
        with open(os.path.join(cache_dir, "SEQUENCE"), "w") as s:
            s.write(config.SystemManifest().Sequence())
        # And now the SERVER file
        with open(os.path.join(cache_dir, "SERVER"), "w") as s:
            s.write(config.UpdateServerName())

        try:
            diffs = Update.PendingUpdatesChanges(cache_dir)
        except BaseException as e:
            print("Attempt to verify extracted frozen update failed: %s" % str(e), file=sys.stderr)
            sys.exit(1)

        if diffs is None or diffs == {}:
            if verbose:
                print("No updates to apply", file=sys.stderr)
        else:
            if verbose:
                PrintDifferences(diffs)
            try:
                rv = Update.ApplyUpdate(cache_dir)
            except BaseException as e:
                print("Unable to apply update: %s" % str(e), file=sys.stderr)
                sys.exit(1)
            if rv:
                print("System should be rebooted now", file=sys.stderr)
                if snl:
                    print("Really explore the space.")
            sys.exit(0)

        pass
    else:
        usage()

if __name__ == "__main__":
    sys.exit(main())
