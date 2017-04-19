#!/usr/local/bin/python
"""
Simple script to automerge commits to external repositories and branches.

Example .git/config:

    [automerge]
        repos = ix
        default = ix

    [automerge-ix]
        path = /path/to/ix/git/repo


Examples of commit messages:

    --- Merge the commit to repo ix and local branch "stable-1.0" ---
    Commit 1

    Merge:  stable-1.0
    -----------------------

    --- Merge the commit to repo ix (master and stable-1.1 branches ---
    --- and local branch "stable-1.0"                               ---
    Commit 2

    Merge:  ix[master stable-1.1] stable-1.0
    -----------------------

    --- Prevent commit from being merge to repo ix                  ---
    Commit 2

    Merge:  ix[master stable-1.1] stable-1.0
    -----------------------


Author: William Grzybowski <wg@FreeBSD.org>
"""
import argparse
import logging
import os
import re
import smtplib
import struct
import subprocess
from email.mime.text import MIMEText

import pygit2

RE_FETCH = re.compile(
    r'^\s*(?P<oldrev>[0-9a-f]+)\.\.(?P<newrev>[0-9a-f]+)\s+.*\->\s*(\S+)$',
    re.M
)
RE_NAME = re.compile(r'^(?P<name>\S+):\s*(?P<value>.+)$', re.M)
RE_REPO = re.compile(r'(?P<name>[^\[\s]+)(?:\[(?P<values>[^\]]+)\])?')
RE_BRANCH = re.compile(r'(?P<name>\S+)')

log = logging.getLogger("tools.automerge")


class Merge(object):

    def __init__(self, repo, commit, nopush=False):
        self._repo = repo
        self._commit = commit
        self._nopush = nopush

    def do(self):

        values = ''
        for name, value in RE_NAME.findall(self._commit.message):
            if name.lower() == 'merge':
                values = value
                break

        repo = self._repo
        ext_repos = repo.config.get_multivar("automerge.repos")
        defaultrepos = repo.config.get_multivar("automerge.default")

        log.debug("Defaulting merge to repos: %s", ", ".join(defaultrepos))

        repos = RE_REPO.findall(values)
        for default in defaultrepos:
            found = False
            for name, branches in list(repos):
                reverse = False
                if name.startswith("!"):
                    oname = name[1:]
                    reverse = True
                else:
                    oname = name
                if oname == default:
                    if reverse:
                        repos.remove((name, branches))
                    found = True
                    break
            if not found:
                repos.append((default, 'master'))

        failed = []
        for name, branches in repos:
            if name not in ext_repos and branches:
                raise ValueError("Invalid repo name: %s" % name)
            if name in ext_repos and not branches:
                branches = 'master'
            if name and not branches:
                try:
                    self._do_merge(repo, "origin", name)
                except Exception, e:
                    failed.append((name, e))
            else:
                failed.extend(self._external_do(name, branches))
            values = RE_REPO.sub("", values, 1)
        return failed

    def _git_run(self, cmd):
        log.debug("Running command: %s", cmd)
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )
        rv = proc.communicate()
        if proc.returncode != 0:
            log.debug("Failed with error(%d): %s", proc.returncode, rv[1])
            raise ValueError(rv[1])
        return rv

    def _external_repo(self, name):
        path = self._repo.config.get_multivar("automerge-%s.path" % name)
        if not path:
            raise ValueError(name)
        return pygit2.Repository(path[0])

    def _external_do(self, name, branches):
        erepo = self._external_repo(name)

        remote = None
        for rem in self._repo.remotes:
            if rem.name == name:
                remote = rem
                break
        if not remote:
            remote = self._repo.create_remote(name, erepo.path)
        remote.fetch()

        branches = RE_BRANCH.findall(branches)
        if not branches:
            #TODO: configurable default merge branch
            branches.append("%s/master" % name)

        failed = []
        for branch in branches:
            try:
                self._do_merge(self._repo, name, branch)
            except Exception, e:
                failed.append(
                    ("%s-%s" % (name, branch), e)
                )

        return failed

    def _do_merge(self, repo, remote, branch):
        os.chdir(os.path.join(repo.path, ".."))
        if remote != "origin":
            refname = "%s/%s" % (remote, branch)
        else:
            refname = branch

        # For some reason git reset --hard hungs
        # Workaround it checking out to another branch first
        #repo.checkout(
        #    refname="refs/remotes/origin/master",
        #    strategy=pygit2.GIT_CHECKOUT_FORCE,
        #)
        #FIXME: For some reason repo.checkout doesnt work the same way
        self._git_run("git checkout -f origin/master")

        try:
            repo.checkout(
                refname="refs/heads/%s" % refname,
                strategy=pygit2.GIT_CHECKOUT_FORCE,
            )
        except KeyError:
            self._git_run("git checkout remotes/%s/%s -b %s" % (
                remote,
                branch,
                refname,
            ))

        self._git_run("git reset --hard")
        self._git_run("git rebase remotes/%s/%s" % (remote, branch))

        try:
            self._git_run("git cherry-pick -x %s" % self._commit.hex)
        except Exception, e:
            output = self._git_run("git diff HEAD")
            log.error(
                "Cherry-pick of %s failed on %s %s.",
                self._commit.hex,
                remote,
                branch,
            )
            log.debug("Diff:\n%s", output)
            raise ValueError("Cherry-pick %s:\n%s\n\nDiff:\n%s" % (
                self._commit.hex,
                e,
                output[0]
            ))

        if not self._nopush:
            self._git_run("git push %s %s:%s" % (remote, refname, branch))
        else:
            log.debug("Skipping git push as told (--no-push)")


def mail(repo, commit, errors):

    log.debug("Sending email for failed merge of commit %s", commit.hex)

    try:
        host = repo.config.get_multivar("automerge.smtphost")
    except KeyError:
        host = ["localhost"]
    try:
        port = repo.config.get_multivar("automerge.smtpport")
    except KeyError:
        port = [25]
    try:
        user = repo.config.get_multivar("automerge.smtpuser")
    except KeyError:
        user = []
    try:
        passwd = repo.config.get_multivar("automerge.smtppassword")
    except KeyError:
        passwd = []
    try:
        sendto = repo.config.get_multivar("automerge.toemail")
    except KeyError:
        sendto = ["spam@agencialivre.com.br"]

    log.debug("Using SMTP host %s port %s", host[0], port[0])

    server = smtplib.SMTP(
        host[0],
        int(port[0]),
        timeout=5
    )
    if user and passwd:
        server.login(user[0], passwd[0])

    text = """Hi,

The commit "%(hex)s" failed to automerge for the following branches:
""" % {'hex': commit.hex}
    for branch, error in errors:
        text += """
----
%(name)s:
%(desc)s
----
""" % {'name': branch, 'desc': unicode(str(error), errors='ignore')}
    msg = MIMEText(text, _charset='utf-8')
    msg['Subject'] = "Merge failed for %s" % commit.hex[:8]
    msg['From'] = commit.committer.email
    msg['To'] = ', '.join(sendto)

    try:
        server.sendmail(
            commit.committer.email,
            sendto,
            msg.as_string()
        )
    except Exception, e:
        log.warn("Email send failed: %s", e)
        print e
    finally:
        server.quit()


def revrange(string):

    reg = re.search(r'^([0-9a-f]{7,40})\.\.([0-9a-f]{7,40})$', string)
    reg2 = re.search(r'^([0-9a-f]{7,40})$', string)
    if not reg and not reg2:
        raise argparse.ArgumentTypeError(
            "Not a valid commit or range"
        )
    if reg:
        return reg.groups()
    else:
        return (string, )


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'revs', metavar='oldrev[..newrev]', type=revrange, nargs='?',
        help='Git commit range',
    )
    parser.add_argument(
        '-n', '--no-push', action='store_true', dest='nopush',
        help='Do not git push the merges',
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)

    repo_path = os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        ".."
    )
    repo = pygit2.Repository(repo_path)

    proc = subprocess.Popen([
        "git",
        "fetch",
        "origin",
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stderr = proc.communicate()[1]

    log.debug("Git fetch: %s", stderr)

    if args.revs:
        if len(args.revs) == 1:
            args.revs = (None, ) + args.revs
        fetch = [args.revs + ("origin/master", )]
    else:
        fetch = RE_FETCH.findall(stderr)
    for oldrev, newrev, ref in fetch:
        if ref != "origin/master":
            continue
        newcommit = repo[newrev]
        commits = []
        if oldrev:
            oldoid = repo[oldrev].oid
            for commit in repo.walk(newcommit.oid, pygit2.GIT_SORT_TOPOLOGICAL):
                if commit.oid == oldoid:
                    break
                log.debug("Adding commit %s", commit.hex)
                commits.append(commit)
        else:
            commits = [newcommit]
        for commit in reversed(commits):
            errors = Merge(repo, commit, nopush=args.nopush).do()
            # Workaround bug in pygit2
            repo = pygit2.Repository(repo_path)
            if errors:
                mail(repo, commit, errors)


if __name__ == "__main__":
    main()
