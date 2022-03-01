from middlewared.service import Service, job, private
from middlewared.service_exception import CallError
from middlewared.utils import Popen, run
from middlewared.plugins.smb import SMBCmd, SMBPath

import os
import subprocess
import time
import asyncio


class SMBService(Service):

    class Config:
        service = 'cifs'
        service_verb = 'restart'

    @private
    async def smbpasswd_dump(self):
        out = {}
        p = await run([SMBCmd.PDBEDIT.value, '-d', '0', '-Lw'], check=False)
        if p.returncode != 0:
            raise CallError(f'Failed to dump passdb file: {p.stderr.decode()}')

        for entry in p.stdout.decode().splitlines():
            out.update({
                entry.split(":")[0]: entry
            })

        return out

    @private
    async def passdb_list(self, verbose=False):
        """
        passdb entries for local SAM database. This will be populated with
        local users in an AD environment. Immediately return in ldap enviornment.
        """
        pdbentries = []

        passdb_backend = await self.middleware.call('smb.getparm', 'passdb backend', 'global')
        if not passdb_backend.startswith('tdbsam'):
            return pdbentries

        if not verbose:
            pdb = await run([SMBCmd.PDBEDIT.value, '-L', '-d', '0'], check=False)
            if pdb.returncode != 0:
                raise CallError(f'Failed to list passdb output: {pdb.stderr.decode()}')

            for p in (pdb.stdout.decode()).splitlines():
                entry = p.split(':')
                try:
                    pdbentries.append({
                        'username': entry[0],
                        'full_name': entry[2],
                        'uid': entry[1],
                    })
                except Exception as e:
                    self.logger.debug('Failed to parse passdb entry [%s]: %s', p, e)

            return pdbentries

        pdb = await run([SMBCmd.PDBEDIT.value, '-Lv', '-d', '0'], check=False)
        if pdb.returncode != 0:
            raise CallError(f'Failed to list passdb output: {pdb.stderr.decode()}')

        for p in (pdb.stdout.decode()).split('---------------'):
            pdbentry = {}
            for entry in p.splitlines():
                parm = entry.split(':')
                if len(parm) != 2:
                    continue

                pdbentry.update({parm[0].rstrip(): parm[1].lstrip() if parm[1] else ''})

            if pdbentry:
                pdbentries.append(pdbentry)

        return pdbentries

    @private
    async def update_passdb_user(self, user):
        if user['smbhash'] == user['pdb']:
            return

        smbpasswd_string = user['smbhash'].split(":")
        username = user['username']
        if len(smbpasswd_string) != 7:
            self.logger.warning("SMB hash for user [%s] is invalid. Authentication for SMB "
                                "sessions for this user will fail until this is repaired. "
                                "This may indicate that configuration was restored without a secret "
                                "seed, and may be repaired by resetting the user password.", username)
            return

        if user['pdb'] is None:
            cmd = [SMBCmd.PDBEDIT.value, '-d', '0', '-a', username]

            # If we're clustered, next_rid will be -1 and we _must_ use passdb rid counter
            # this is because database ids can't be relied on to be consistent cluster-wide
            next_rid = await self.middleware.call('smb.get_next_rid', 'USER', user['id'])

            self.logger.debug("User [%s] does not exist in the passdb.tdb file. "
                              "Creating entry with rid [%s].", username, next_rid)
            if next_rid != -1:
                cmd.extend(['-U', str(next_rid)])

            cmd.append('-t')

            pdbcreate = await Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
            )
            out, err = await pdbcreate.communicate(input=" \n \n".encode())
            if pdbcreate.returncode != 0:
                raise CallError(f'{username}: failed to create passdb user: {err.decode()}')

            setntpass = await run([SMBCmd.PDBEDIT.value, '-d', '0', '--set-nt-hash', smbpasswd_string[3], username], check=False)
            if setntpass.returncode != 0:
                raise CallError(f'Failed to set NT password for {username}: {setntpass.stderr.decode()}')

            if user['locked']:
                disableacct = await run([SMBCmd.SMBPASSWD.value, '-d', username], check=False)
                if disableacct.returncode != 0:
                    raise CallError(f'Failed to disable {username}: {disableacct.stderr.decode()}')
            return

        """
        If an invalid global auxiliary parameter is present
        in the smb.conf, then pdbedit will write error messages
        to stdout (two for each invalid parameter, separated by \n).
        The last line of output in this case will be the passdb entry
        in smbpasswd format (-Lw). This is the reason why we pre-emptively
        splitlines() and use last element of resulting list for our checks.
        """
        entry = user['pdb'].split(":")

        if smbpasswd_string[3] != entry[3]:
            setntpass = await run([SMBCmd.PDBEDIT.value, '-d', '0', '--set-nt-hash', smbpasswd_string[3], username], check=False)
            if setntpass.returncode != 0:
                raise CallError(f'Failed to set NT password for {username}: {setntpass.stderr.decode()}')
        if user['locked'] and 'D' not in entry[4]:
            disableacct = await run([SMBCmd.SMBPASSWD.value, '-d', username], check=False)
            if disableacct.returncode != 0:
                raise CallError(f'Failed to disable {username}: {disableacct.stderr.decode()}')
        elif not user['locked'] and 'D' in entry[4]:
            enableacct = await run([SMBCmd.SMBPASSWD.value, '-e', username], check=False)
            if enableacct.returncode != 0:
                raise CallError(f'Failed to enable {username}: {enableacct.stderr.decode()}')

    @private
    async def remove_passdb_user(self, username):
        ha_mode = await self.middleware.call('smb.get_smb_ha_mode')
        if ha_mode == "CLUSTERED":
            self.logger.debug("passdb support not yet implemented in clustered TrueNAS.")
            return

        deluser = await run([SMBCmd.PDBEDIT.value, '-d', '0', '-x', username], check=False)
        if deluser.returncode != 0:
            raise CallError(f'Failed to delete user [{username}]: {deluser.stderr.decode()}')

    @private
    async def passdb_reinit(self, conf_users):
        """
        This method gets called if we need to rebuild passdb.tdb from scratch.
        Back up problematic version first to preserve collateral in case of regression.
        `conf_users` contains results of `user.query`. Since users will receive new
        SID values, we will need to flush samba's cache to ensure consistency.
        """
        private_dir = SMBPath.PASSDB_DIR.platform()
        ts = int(time.time())
        old_path = f'{private_dir}/passdb.tdb'
        new_path = f'{private_dir}/passdb.{ts}.corrupted'
        os.rename(old_path, new_path)
        self.logger.debug("Backing up original passdb to [%s]", new_path)
        for u in conf_users:
            await self.middleware.call('smb.update_passdb_user', u)

        net = await run([SMBCmd.NET.value, 'cache', 'flush'], check=False)
        if net.returncode != 0:
            self.logger.warning("Samba gencache flush failed with error: %s", net.stderr.decode())

    @private
    async def set_cluster_lock_wait(self):
        """
        Set cluster-wide PASS_DB lock with 5 minute timeout.
        In theory this should give us plenty of time to finish passdb operations.
        Other nodes will block waiting for this to be released. Trying once per
        minute to synchronize passdb.
        """
        pnn = await self.middleware.call('ctdb.general.pnn')

        while True:
            try:
                lock = await self.middleware.call('clustercache.get', 'PASSDB_LOCK')
                if lock["node"] == pnn:
                    return
            except KeyError:
                pass

            try:
                await self.middleware.call(
                    'clustercache.put', "PASSDB_LOCK",
                    {"node": pnn}, 300, {"flag": "CREATE"}
                )
                return
            except KeyError:
                self.logger.debug("waiting for clustered PASSDB_LOCK")
                await asyncio.sleep(60)

    @private
    @job(lock="passdb_sync")
    async def synchronize_passdb(self, job):
        """
        Create any missing entries in the passdb.tdb.
        Replace NT hashes of users if they do not match what is the the config file.
        Synchronize the "disabled" state of users
        Delete any entries in the passdb_tdb file that don't exist in the config file.
        This method may cause temporary service disruption for SMB.
        """
        ha_mode = await self.middleware.call('smb.get_smb_ha_mode')

        passdb_backend = await self.middleware.call('smb.getparm',
                                                    'passdb backend',
                                                    'global')

        if not passdb_backend.startswith('tdbsam'):
            return

        if ha_mode == 'CLUSTERED':
            await self.set_cluster_lock_wait()

        conf_users = await self.middleware.call('user.query', [("smb", "=", True)])

        pdb_users = await self.smbpasswd_dump()
        for u in conf_users:
            pdb_entry = pdb_users.pop(u['username'], None)
            u.update({"pdb": pdb_entry})
            await self.middleware.call('smb.update_passdb_user', u)

        for entry in pdb_users.keys():
            self.logger.debug('Synchronizing passdb with config file: deleting user [%s] from passdb.tdb', entry)
            try:
                await self.remove_passdb_user(entry)
            except Exception:
                self.logger.warning("Failed to remove passdb user. This may indicate a corrupted passdb. Regenerating.", exc_info=True)
                await self.passdb_reinit(conf_users)
                break

        if ha_mode == "CLUSTERED":
            await self.middleware.call("clustercache.pop", "PASSDB_LOCK")
