#!/usr/sbin/dtrace -s

#pragma D option quiet
#pragma D option defaultargs
#pragma D option switchrate=10hz
#pragma D option dynvarsize=20m

dtrace:::BEGIN {
    printf("%-20s %-16s %1s %4s %6s %s\n", "TIME", "PROCESS", "D", "KB", "ms", "FILE");
    min_ns = $1 * 1000000;
}

/* https://github.com/hybridlogic/freebsd-base-stable-9/blob/master/sys/cddl/contrib/opensolaris/uts/common/fs/zfs/zfs_vnops.c */

fbt::zfs_freebsd_read:entry, fbt::zfs_freebsd_write:entry
/this->fi_name != "unknown"/
{

    /* http://svn0.us-west.freebsd.org/base/vendor/dtracetoolkit/dist/Snippits/fd2pathname.txt 
    this->filep =
    curthread->t_procp->p_user.u_finfo.fi_list[this->fd].uf_file;
    this->vnodep = this->filep != 0 ? this->filep->f_vnode : 0;
    self->vpath = this->vnodep ? (this->vnodep->v_path != 0 ?
        cleanpath(this->vnodep->v_path) : "<unknown>") : "<unknown>";*/

    this->vp = args[0]->a_vp;
    this->ncp = this->vp != NULL ? (&(this->vp->v_cache_dst) != NULL ? 
            this->vp->v_cache_dst.tqh_first : 0) : 0;
    this->fi_name = this->ncp ? (this->ncp->nc_name != 0 ? 
            stringof(this->ncp->nc_name) : "<unknown>") : "<unknown>"; 

    self->path = this->fi_name; /* args[0]->v_path; */
    /*printf("0x%x", args[0]); */
    /* TODO Put kb back in... */
    /*self->kb = args[1]->uio_resid / 1024;*/
    self->start = timestamp;
}

fbt::zfs_freebsd_read:return, fbt::zfs_freebsd_write:return
/self->start && (timestamp - self->start) >= min_ns/
{
    this->iotime = (timestamp - self->start) / 1000000;
    this->dir = probefunc == "zfs_freebsd_read" ? "R" : "W";
    printf("%-20Y %-16s %1s %4d %6d %s\n", walltimestamp,
            execname, this->dir, 0 /*self->kb*/, this->iotime,
            self->path != NULL ? stringof(self->path) : "<null>");
}
fbt::zfs_freebsd_read:return, fbt::zfs_freebsd_write:return
{
    self->path = 0; self->kb = 0; self->start = 0;
}

/* Now start printing when we start and stop taking snapshots. */

fbt::zfs_ioc_snapshot:entry
{
    printf("%-20Y <snapshot-create>\n", walltimestamp);
    self->snapshot_start = timestamp;
}

fbt::zfs_ioc_snapshot:return
{
    printf("%-20Y </snapshot-create took %dms>\n", walltimestamp,
            (timestamp - self->snapshot_start) / 1000000);
    self->snapshot_start = 0;
}
