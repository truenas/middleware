#!/usr/bin/env python
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


class Merge(object):

    def __init__(self, repo, commit):
        self._repo = repo
        self._commit = commit

    def do(self):

        values = ''
        for name, value in RE_NAME.findall(self._commit.message):
            if name.lower() == 'merge':
                values = value
                break

        repo = self._repo
        ext_repos = repo.config.get_multivar("automerge.repos")
        defaultrepos = repo.config.get_multivar("automerge.default")

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
        print cmd
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )
        rv = proc.communicate()
        if proc.returncode != 0:
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

        try:
            ref = repo.lookup_reference("refs/heads/%s" % refname)
        except KeyError:
            self._git_run("git checkout remotes/%s/%s -b %s" % (
                remote,
                branch,
                refname,
            ))
            ref = repo.lookup_reference("refs/heads/%s" % refname)

        repo.checkout(pygit2.GIT_CHECKOUT_FORCE, ref)

        self._git_run("git reset --hard")
        self._git_run("git rebase remotes/%s/%s" % (remote, branch))

        try:
            self._git_run("git cherry-pick -x %s" % self._commit.hex)
        except:
            output = self._git_run("git diff HEAD")
            raise ValueError(output[0])

        self._git_run("git push %s %s:%s" % (remote, refname, branch))


def _pack(rev):
    return struct.pack(
        'B' * (len(rev) / 2),
        *[int(rev[i*2:i*2+2], 16) for i in xrange(len(rev) / 2)]
    )


def mail(repo, commit, errors):

    host = repo.config.get_multivar("automerge.smtphost") or ["localhost"]
    port = repo.config.get_multivar("automerge.smtpport") or [25]
    user = repo.config.get_multivar("automerge.smtpuser")
    passwd = repo.config.get_multivar("automerge.smtppassword")
    sendto = repo.config.get_multivar("automerge.toemail") or [
        "spam@agencialivre.com.br"
    ]

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
""" % {'name': branch, 'desc': str(error)}
    msg = MIMEText(text, _charset='utf-8')

    try:
        server.sendmail(
            commit.committer.email,
            sendto,
            msg.as_string()
        )
    except Exception, e:
        print e


def revrange(string):

    reg = re.search(r'^([0-9a-f]{7,40})\.\.([0-9a-f]{7,40})$', string)
    if not reg:
        raise argparse.ArgumentTypeError(
            "Not a valid commit range"
        )

    return reg.groups()


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'revs', metavar='oldrev..newrev', type=revrange, nargs='?',
        help='Git commit range',
    )
    args = parser.parse_args()

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

    if args.revs:
        fetch = [args.revs + ("origin/master", )]
    else:
        fetch = RE_FETCH.findall(stderr)
    for oldrev, newrev, ref in fetch:
        if ref != "origin/master":
            continue
        newoid = repo[_pack(newrev)].oid
        oldoid = repo[_pack(oldrev)].oid
        commits = []
        for commit in repo.walk(newoid, pygit2.GIT_SORT_TOPOLOGICAL):
            if commit.oid == oldoid:
                break
            commits.append(commit)
        for commit in reversed(commits):
            errors = Merge(repo, commit).do()
            # Workaround bug in pygit2
            repo = pygit2.Repository(repo_path)
            if errors:
                mail(repo, commit, errors)


if __name__ == "__main__":
    main()
