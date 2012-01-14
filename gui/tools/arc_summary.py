#!/usr/local/bin/python
#
# $Id: arc_summary.pl,v 388:e27800740aa2 2011-07-08 02:53:29Z jhell $
#
# Copyright (c) 2008 Ben Rockwood <benr@cuddletech.com>,
# Copyright (c) 2010 Martin Matuska <mm@FreeBSD.org>,
# Copyright (c) 2010-2011 Jason J. Hellenthal <jhell@DataIX.net>,
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#
# If you are having troubles when using this script from cron(8) please try
# adjusting your PATH before reporting problems.
#
# /usr/bin & /sbin
#
# Binaries used are:
#
# dc(1), kldstat(8), sed(1), sysctl(8) & vmstat(8)
#
# Binaries that I am working on phasing out are:
#
# dc(1) & sed(1)

import os
import sys
import time
import getopt
import re
import decimal

from subprocess import Popen, PIPE
from decimal import Decimal as D


usetunable = True
show_sysctl_descriptions = False
alternate_sysctl_layout = False
kstat_pobj = re.compile("^([^:]+):\s+(.+)\s*$", flags=re.M)


def get_Kstat():
    Kstats = [
        "hw.pagesize",
        "hw.physmem",
        "kern.maxusers",
        "vm.kmem_map_free",
        "vm.kmem_map_size",
        "vm.kmem_size",
        "vm.kmem_size_max",
        "vm.kmem_size_min",
        "vm.kmem_size_scale",
        "vm.stats",
        "kstat.zfs",
        "vfs.zfs"
    ]

    sysctls = " ".join(str(x) for x in Kstats)
    p = Popen("/sbin/sysctl -q %s" % sysctls, stdin=PIPE,
        stdout=PIPE, stderr=PIPE, shell=True, close_fds=True)
    p.wait()

    kstat_pull = p.communicate()[0].split('\n')
    if p.returncode != 0: 
        sys.exit(1)

    Kstat = {}
    for kstat in kstat_pull:
        kstat = kstat.strip()
        mobj = kstat_pobj.match(kstat)
        if mobj:
            key = mobj.group(1).strip()
            val = mobj.group(2).strip()
            Kstat[key] = D(val)

    return Kstat


def div1():
    i = 1
    l = 18
    sys.stdout.write("\n")
    while i <= l:
        sys.stdout.write("%s" % "----")
        i += 1
    sys.stdout.write("\n")


def div2():
    div1()
    sys.stdout.write("\n")


def fBytes(Bytes=0, Decimal=2):
    kbytes = (2**10)
    mbytes = (2**20)
    gbytes = (2**30)
    tbytes = (2**40)
    pbytes = (2**50)
    ebytes = (2**60)
    zbytes = (2**70)
    ybytes = (2**80)

    if Bytes >= ybytes:
        return str("%0." + str(Decimal) + "f") % (Bytes / ybytes) + "\tYiB"
    elif Bytes >= zbytes:
        return str("%0." + str(Decimal) + "f") % (Bytes / zbytes) + "\tZiB"
    elif Bytes >= ebytes:
        return str("%0." + str(Decimal) + "f") % (Bytes / ebytes) + "\tEiB"
    elif Bytes >= pbytes:
        return str("%0." + str(Decimal) + "f") % (Bytes / pbytes) + "\tPiB"
    elif Bytes >= tbytes:
        return str("%0." + str(Decimal) + "f") % (Bytes / tbytes) + "\tTiB"
    elif Bytes >= gbytes:
        return str("%0." + str(Decimal) + "f") % (Bytes / gbytes) + "\tGiB"
    elif Bytes >= mbytes:
        return str("%0." + str(Decimal) + "f") % (Bytes / mbytes) + "\tMiB"
    elif Bytes >= kbytes:
        return str("%0." + str(Decimal) + "f") % (Bytes / kbytes) + "\tKiB"
    elif Bytes == 0:
        return str("%d" % 0) + "\tBytes"
    else: 
        return str("%d" % Bytes) + "\tBytes"


def fHits(Hits=0, Decimal=2):
    khits = (10**3)
    mhits = (10**6)
    bhits = (10**9)
    thits = (10**12)
    qhits = (10**15)
    Qhits = (10**18)
    shits = (10**21)
    Shits = (10**24)

    if Hits >= Shits:
        return str("%0." + str(Decimal) + "f") % (Hits / Shits) + "S"
    elif Hits >= shits:
        return str("%0." + str(Decimal) + "f") % (Hits / shits) + "s"
    elif Hits >= Qhits:
        return str("%0." + str(Decimal) + "f") % (Hits / Qhits) + "Q"
    elif Hits >= qhits:
        return str("%0." + str(Decimal) + "f") % (Hits / qhits) + "q"
    elif Hits >= thits:
        return str("%0." + str(Decimal) + "f") % (Hits / thits) + "t"
    elif Hits >= bhits:
        return str("%0." + str(Decimal) + "f") % (Hits / bhits) + "b"
    elif Hits >= mhits:
        return str("%0." + str(Decimal) + "f") % (Hits / mhits) + "m"
    elif Hits >= khits:
        return str("%0." + str(Decimal) + "f") % (Hits / khits) + "k"
    elif Hits == 0:
        return str("%d" % 0)
    else:
        return str("%d" % Hits)


def fPerc(lVal=0, rVal=0, Decimal=2):
        if rVal > 0:
            return str("%0." + str(Decimal) + "f") % (100 * (lVal / rVal)) + "%"
        else:
            return str("%0." + str(Decimal) + "f") % 100 + "%"


def _system_memory():
    def mem_rounded(mem_size):
        chip_size = 1
        chip_guess = (int(mem_size) / 8) - 1
        while chip_guess != 0:
            chip_guess >>= 1
            chip_size <<= 1

        mem_round = (int(mem_size / chip_size) + 1) * chip_size
        return mem_round

    Kstat = get_Kstat()
    pagesize = Kstat["hw.pagesize"]
    mem_hw = mem_rounded(Kstat["hw.physmem"])
    mem_phys = Kstat["hw.physmem"]
    mem_all = Kstat["vm.stats.vm.v_page_count"] * pagesize
    mem_wire = Kstat["vm.stats.vm.v_wire_count"] * pagesize
    mem_active = Kstat["vm.stats.vm.v_active_count"] * pagesize
    mem_inactive = Kstat["vm.stats.vm.v_inactive_count"] * pagesize
    mem_cache = Kstat["vm.stats.vm.v_cache_count"] * pagesize
    mem_free = Kstat["vm.stats.vm.v_free_count"] * pagesize

    mem_gap_vm = mem_all - (mem_wire + mem_active + mem_inactive + mem_cache + mem_free)

    mem_total = mem_hw
    mem_avail = mem_inactive + mem_cache + mem_free
    mem_used = mem_total - mem_avail

    sys.stdout.write("System Memory:\n")
    sys.stdout.write("\n")
    sys.stdout.write("\t%s\t%s Active,\t" % (fPerc(mem_active, mem_all), fBytes(mem_active)))
    sys.stdout.write("%s\t%s Inact\n" % (fPerc(mem_inactive, mem_all), fBytes(mem_inactive)))
    sys.stdout.write("\t%s\t%s Wired,\t" % (fPerc(mem_wire, mem_all), fBytes(mem_wire)))
    sys.stdout.write("%s\t%s Cache\n" % (fPerc(mem_cache, mem_all), fBytes(mem_cache)))
    sys.stdout.write("\t%s\t%s Free,\t" % (fPerc(mem_free, mem_all), fBytes(mem_free)))
    sys.stdout.write("%s\t%s Gap\n" % (fPerc(mem_gap_vm, mem_all), fBytes(mem_gap_vm)))
    sys.stdout.write("\n")
    sys.stdout.write("\tReal Installed:\t\t\t\t%s\n" % fBytes(mem_hw))
    sys.stdout.write("\tReal Available:\t\t\t%s\t%s\n" % (fPerc(mem_phys, mem_hw), fBytes(mem_phys)))
    sys.stdout.write("\tReal Managed:\t\t\t%s\t%s\n" % (fPerc(mem_all, mem_phys), fBytes(mem_all)))
    sys.stdout.write("\n")
    sys.stdout.write("\tLogical Total:\t\t\t\t%s\n" % fBytes(mem_total))
    sys.stdout.write("\tLogical Used:\t\t\t%s\t%s\n" % (fPerc(mem_used, mem_total), fBytes(mem_used)))
    sys.stdout.write("\tLogical Free:\t\t\t%s\t%s\n" % (fPerc(mem_avail, mem_total), fBytes(mem_avail)))
    sys.stdout.write("\n")

    cmd1 = """
        /sbin/kldstat | \
        /usr/bin/awk '
            BEGIN {
                print "16i 0";
            }
            NR > 1 {
                print toupper($4) "+";
            }
           END {
                print "p";
           }
        ' | /usr/bin/dc
    """

    cmd2 = """
        /usr/bin/vmstat -m | \
        /usr/bin/sed -Ee '1s/.*/0/;s/.* ([0-9]+)K.*/\\1+/;$s/$/1024*p/' | \
        /usr/bin/dc
    """

    p1 = Popen(cmd1, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True, close_fds=True)
    p2 = Popen(cmd2, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True, close_fds=True)

    ktext = D(p1.communicate()[0].strip())
    kdata = D(p2.communicate()[0].strip())

    if p1.returncode != 0 or p2.returncode != 0:
        sys.exit(1)

    kmem = ktext + kdata
    kmem_map_size = Kstat["vm.kmem_map_size"]
    kmem_map_free = Kstat["vm.kmem_map_free"]
    kmem_map_total = kmem_map_size + kmem_map_free

    sys.stdout.write("Kernel Memory:\t\t\t\t\t%s\n" % fBytes(kmem))
    sys.stdout.write("\tData:\t\t\t\t%s\t%s\n" % (fPerc(kdata, kmem), fBytes(kdata)))
    sys.stdout.write("\tText:\t\t\t\t%s\t%s\n\n" % (fPerc(ktext, kmem), fBytes(ktext)))

    sys.stdout.write("Kernel Memory Map:\t\t\t\t%s\n" % fBytes(kmem_map_total))
    sys.stdout.write("\tSize:\t\t\t\t%s\t%s\n" % (fPerc(kmem_map_size, kmem_map_total), fBytes(kmem_map_size)))
    sys.stdout.write("\tFree:\t\t\t\t%s\t%s\n" % (fPerc(kmem_map_free, kmem_map_total), fBytes(kmem_map_free)))


def _arc_summary():
    Kstat = get_Kstat()
    if not Kstat["vfs.zfs.version.spa"]:
        return 

    spa = Kstat["vfs.zfs.version.spa"]
    zpl = Kstat["vfs.zfs.version.zpl"]
    memory_throttle_count = Kstat["kstat.zfs.misc.arcstats.memory_throttle_count"]

    sys.stdout.write("ARC Summary: ")
    if memory_throttle_count > 0:
        sys.stdout.write("(THROTTLED)\n")
    else:
        sys.stdout.write("(HEALTHY)\n")

    sys.stdout.write("\tStorage pool Version:\t\t\t%d\n" % spa)
    sys.stdout.write("\tFilesystem Version:\t\t\t%d\n" % zpl)
    sys.stdout.write("\tMemory Throttle Count:\t\t\t%s\n" % fHits(memory_throttle_count))
    sys.stdout.write("\n")

    ### ARC Misc. ###
    deleted = Kstat["kstat.zfs.misc.arcstats.deleted"]
    evict_skip = Kstat["kstat.zfs.misc.arcstats.evict_skip"]
    mutex_miss = Kstat["kstat.zfs.misc.arcstats.mutex_miss"]
    recycle_miss = Kstat["kstat.zfs.misc.arcstats.recycle_miss"]

    sys.stdout.write("ARC Misc:\n")
    sys.stdout.write("\tDeleted:\t\t\t\t%s\n" % fHits(deleted))
    sys.stdout.write("\tRecycle Misses:\t\t\t\t%s\n" % fHits(recycle_miss))
    sys.stdout.write("\tMutex Misses:\t\t\t\t%s\n" % fHits(mutex_miss))
    sys.stdout.write("\tEvict Skips:\t\t\t\t%s\n" % fHits(mutex_miss))
    sys.stdout.write("\n")

    ### ARC Sizing ###
    arc_size = Kstat["kstat.zfs.misc.arcstats.size"]
    mru_size = Kstat["kstat.zfs.misc.arcstats.p"]
    target_max_size = Kstat["kstat.zfs.misc.arcstats.c_max"]
    target_min_size = Kstat["kstat.zfs.misc.arcstats.c_min"]
    target_size = Kstat["kstat.zfs.misc.arcstats.c"]
        
    target_size_ratio = (target_max_size / target_min_size)
        
    sys.stdout.write("ARC Size:\t\t\t\t%s\t%s\n" %
        (fPerc(arc_size, target_max_size), fBytes(arc_size)))
    sys.stdout.write("\tTarget Size: (Adaptive)\t\t%s\t%s\n" %
        (fPerc(target_size, target_max_size), fBytes(target_size)))
    sys.stdout.write("\tMin Size (Hard Limit):\t\t%s\t%s\n" %
        (fPerc(target_min_size, target_max_size), fBytes(target_min_size)))
    sys.stdout.write("\tMax Size (High Water):\t\t%d:1\t%s\n" %
        (target_size_ratio, fBytes(target_max_size)))

    sys.stdout.write("\nARC Size Breakdown:\n")
    if arc_size > target_size:
        mfu_size = (arc_size - mru_size)
        sys.stdout.write("\tRecently Used Cache Size:\t%s\t%s\n" %
            (fPerc(mru_size, arc_size), fBytes(mru_size)))
        sys.stdout.write("\tFrequently Used Cache Size:\t%s\t%s\n" %
            (fPerc(mfu_size, arc_size), fBytes(mfu_size)))
        
    if arc_size < target_size:
        mfu_size = (target_size - mru_size)
        sys.stdout.write("\tRecently Used Cache Size:\t%s\t%s\n" %
            (fPerc(mru_size, target_size), fBytes(mru_size)))
        sys.stdout.write("\tFrequently Used Cache Size:\t%s\t%s\n" %
            (fPerc(mfu_size, target_size), fBytes(mfu_size)))
    sys.stdout.write("\n")

    ### ARC Hash Breakdown ###
    hash_chain_max = Kstat["kstat.zfs.misc.arcstats.hash_chain_max"]
    hash_chains = Kstat["kstat.zfs.misc.arcstats.hash_chains"]
    hash_collisions = Kstat["kstat.zfs.misc.arcstats.hash_collisions"]
    hash_elements = Kstat["kstat.zfs.misc.arcstats.hash_elements"]
    hash_elements_max = Kstat["kstat.zfs.misc.arcstats.hash_elements_max"]

    sys.stdout.write("ARC Hash Breakdown:\n")
    sys.stdout.write("\tElements Max:\t\t\t\t%s\n" % fHits(hash_elements_max))
    sys.stdout.write("\tElements Current:\t\t%s\t%s\n" %
        (fPerc(hash_elements, hash_elements_max), fHits(hash_elements)))
    sys.stdout.write("\tCollisions:\t\t\t\t%s\n" % fHits(hash_collisions))
    sys.stdout.write("\tChain Max:\t\t\t\t%s\n" % fHits(hash_chain_max))
    sys.stdout.write("\tChains:\t\t\t\t\t%s\n" % fHits(hash_chains))


def _arc_efficiency():
    Kstat = get_Kstat() 
    if not Kstat["vfs.zfs.version.spa"]:
        return

    arc_hits = Kstat["kstat.zfs.misc.arcstats.hits"]
    arc_misses = Kstat["kstat.zfs.misc.arcstats.misses"]
    demand_data_hits = Kstat["kstat.zfs.misc.arcstats.demand_data_hits"]
    demand_data_misses = Kstat["kstat.zfs.misc.arcstats.demand_data_misses"]
    demand_metadata_hits = Kstat["kstat.zfs.misc.arcstats.demand_metadata_hits"]
    demand_metadata_misses = Kstat["kstat.zfs.misc.arcstats.demand_metadata_misses"]
    mfu_ghost_hits = Kstat["kstat.zfs.misc.arcstats.mfu_ghost_hits"]
    mfu_hits = Kstat["kstat.zfs.misc.arcstats.mfu_hits"]
    mru_ghost_hits = Kstat["kstat.zfs.misc.arcstats.mru_ghost_hits"]
    mru_hits = Kstat["kstat.zfs.misc.arcstats.mru_hits"]
    prefetch_data_hits = Kstat["kstat.zfs.misc.arcstats.prefetch_data_hits"]
    prefetch_data_misses = Kstat["kstat.zfs.misc.arcstats.prefetch_data_misses"]
    prefetch_metadata_hits = Kstat["kstat.zfs.misc.arcstats.prefetch_metadata_hits"]
    prefetch_metadata_misses = Kstat["kstat.zfs.misc.arcstats.prefetch_metadata_misses"]
                
    anon_hits = arc_hits - (mfu_hits + mru_hits + mfu_ghost_hits + mru_ghost_hits)
    arc_accesses_total = (arc_hits + arc_misses)
    demand_data_total = (demand_data_hits + demand_data_misses)
    prefetch_data_total = (prefetch_data_hits + prefetch_data_misses)
    real_hits = (mfu_hits + mru_hits)
        
    sys.stdout.write("ARC Efficiency:\t\t\t\t\t%s\n" % fHits(arc_accesses_total))
    sys.stdout.write("\tCache Hit Ratio:\t\t%s\t%s\n" %
        (fPerc(arc_hits, arc_accesses_total), fHits(arc_hits)))
    sys.stdout.write("\tCache Miss Ratio:\t\t%s\t%s\n" %
        (fPerc(arc_misses, arc_accesses_total), fHits(arc_misses)))
    sys.stdout.write("\tActual Hit Ratio:\t\t%s\t%s\n" %
        (fPerc(real_hits, arc_accesses_total), fHits(real_hits)))
    sys.stdout.write("\n")
    sys.stdout.write("\tData Demand Efficiency:\t\t%s\t%s\n" %
        (fPerc(demand_data_hits, demand_data_total), fHits(demand_data_total)))

    if prefetch_data_total > 0:
        sys.stdout.write("\tData Prefetch Efficiency:\t%s\t%s\n" %
            (fPerc(prefetch_data_hits, prefetch_data_total), fHits(prefetch_data_total)))
    sys.stdout.write("\n")

    sys.stdout.write("\tCACHE HITS BY CACHE LIST:\n")
    if anon_hits > 0:
        sys.stdout.write("\t  Anonymously Used:\t\t%s\t%s\n" %
            (fPerc(anon_hits, arc_hits), fHits(anon_hits)))

    sys.stdout.write("\t  Most Recently Used:\t\t%s\t%s\n" %
        (fPerc(mru_hits, arc_hits), fHits(mru_hits)))
    sys.stdout.write("\t  Most Frequently Used:\t\t%s\t%s\n" %
        (fPerc(mfu_hits, arc_hits), fHits(mfu_hits)))
    sys.stdout.write("\t  Most Recently Used Ghost:\t%s\t%s\n" %
        (fPerc(mru_ghost_hits, arc_hits), fHits(mru_ghost_hits)))
    sys.stdout.write("\t  Most Frequently Used Ghost:\t%s\t%s\n" %
        (fPerc(mfu_ghost_hits, arc_hits), fHits(mfu_ghost_hits)))

    sys.stdout.write("\n\tCACHE HITS BY DATA TYPE:\n")
    sys.stdout.write("\t  Demand Data:\t\t\t%s\t%s\n" %
        (fPerc(demand_data_hits, arc_hits), fHits(demand_data_hits)))
    sys.stdout.write("\t  Prefetch Data:\t\t%s\t%s\n" %
        (fPerc(prefetch_data_hits, arc_hits), fHits(prefetch_data_hits)))
    sys.stdout.write("\t  Demand Metadata:\t\t%s\t%s\n" %
        (fPerc(demand_metadata_hits, arc_hits), fHits(demand_metadata_hits)))
    sys.stdout.write("\t  Prefetch Metadata:\t\t%s\t%s\n" %
        (fPerc(prefetch_metadata_hits, arc_hits), fHits(prefetch_metadata_hits)))

    sys.stdout.write("\n\tCACHE MISSES BY DATA TYPE:\n")
    sys.stdout.write("\t  Demand Data:\t\t\t%s\t%s\n" %
        (fPerc(demand_data_misses, arc_misses), fHits(demand_data_misses)))
    sys.stdout.write("\t  Prefetch Data:\t\t%s\t%s\n" %
        (fPerc(prefetch_data_misses, arc_misses), fHits(prefetch_data_misses)))
    sys.stdout.write("\t  Demand Metadata:\t\t%s\t%s\n" %
        (fPerc(demand_metadata_misses, arc_misses), fHits(demand_metadata_misses)))
    sys.stdout.write("\t  Prefetch Metadata:\t\t%s\t%s\n" %
        (fPerc(prefetch_metadata_misses, arc_misses), fHits(prefetch_metadata_misses)))


def _l2arc_summary():
    Kstat = get_Kstat()
    if not Kstat["vfs.zfs.version.spa"]:
        return

    l2_abort_lowmem = Kstat["kstat.zfs.misc.arcstats.l2_abort_lowmem"]
    l2_cksum_bad = Kstat["kstat.zfs.misc.arcstats.l2_cksum_bad"]
    l2_evict_lock_retry = Kstat["kstat.zfs.misc.arcstats.l2_evict_lock_retry"]
    l2_evict_reading = Kstat["kstat.zfs.misc.arcstats.l2_evict_reading"]
    l2_feeds = Kstat["kstat.zfs.misc.arcstats.l2_feeds"]
    l2_free_on_write = Kstat["kstat.zfs.misc.arcstats.l2_free_on_write"]
    l2_hdr_size = Kstat["kstat.zfs.misc.arcstats.l2_hdr_size"]
    l2_hits = Kstat["kstat.zfs.misc.arcstats.l2_hits"]
    l2_io_error = Kstat["kstat.zfs.misc.arcstats.l2_io_error"]
    l2_misses = Kstat["kstat.zfs.misc.arcstats.l2_misses"]
    l2_rw_clash = Kstat["kstat.zfs.misc.arcstats.l2_rw_clash"]
    l2_size = Kstat["kstat.zfs.misc.arcstats.l2_size"]
    l2_write_buffer_bytes_scanned = Kstat["kstat.zfs.misc.arcstats.l2_write_buffer_bytes_scanned"]
    l2_write_buffer_iter = Kstat["kstat.zfs.misc.arcstats.l2_write_buffer_iter"]
    l2_write_buffer_list_iter = Kstat["kstat.zfs.misc.arcstats.l2_write_buffer_list_iter"]
    l2_write_buffer_list_null_iter = Kstat["kstat.zfs.misc.arcstats.l2_write_buffer_list_null_iter"]
    l2_write_bytes = Kstat["kstat.zfs.misc.arcstats.l2_write_bytes"]
    l2_write_full = Kstat["kstat.zfs.misc.arcstats.l2_write_full"]
    l2_write_in_l2 = Kstat["kstat.zfs.misc.arcstats.l2_write_in_l2"]
    l2_write_io_in_progress = Kstat["kstat.zfs.misc.arcstats.l2_write_io_in_progress"]
    l2_write_not_cacheable = Kstat["kstat.zfs.misc.arcstats.l2_write_not_cacheable"]
    l2_write_passed_headroom = Kstat["kstat.zfs.misc.arcstats.l2_write_passed_headroom"]
    l2_write_pios = Kstat["kstat.zfs.misc.arcstats.l2_write_pios"]
    l2_write_spa_mismatch = Kstat["kstat.zfs.misc.arcstats.l2_write_spa_mismatch"]
    l2_write_trylock_fail = Kstat["kstat.zfs.misc.arcstats.l2_write_trylock_fail"]
    l2_writes_done = Kstat["kstat.zfs.misc.arcstats.l2_writes_done"]
    l2_writes_error = Kstat["kstat.zfs.misc.arcstats.l2_writes_error"]
    l2_writes_hdr_miss = Kstat["kstat.zfs.misc.arcstats.l2_writes_hdr_miss"]
    l2_writes_sent = Kstat["kstat.zfs.misc.arcstats.l2_writes_sent"]

    l2_access_total = (l2_hits + l2_misses);
    l2_health_count = (l2_writes_error + l2_cksum_bad + l2_io_error);

    if l2_size > 0 and l2_access_total > 0:
        sys.stdout.write("L2 ARC Summary: ")
        if l2_health_count > 0:
            sys.stdout.write("(DEGRADED)\n")
        else:
            sys.stdout.write("(HEALTHY)\n")
        sys.stdout.write("\tPassed Headroom:\t\t\t%s\n" % fHits(l2_write_passed_headroom))
        sys.stdout.write("\tTried Lock Failures:\t\t\t%s\n" % fHits(l2_write_trylock_fail))
        sys.stdout.write("\tIO In Progress:\t\t\t\t%s\n" % fHits(l2_write_io_in_progress))
        sys.stdout.write("\tLow Memory Aborts:\t\t\t%s\n" % fHits(l2_abort_lowmem))
        sys.stdout.write("\tFree on Write:\t\t\t\t%s\n" % fHits(l2_free_on_write))
        sys.stdout.write("\tWrites While Full:\t\t\t%s\n" % fHits(l2_write_full))
        sys.stdout.write("\tR/W Clashes:\t\t\t\t%s\n" % fHits(l2_rw_clash))
        sys.stdout.write("\tBad Checksums:\t\t\t\t%s\n" % fHits(l2_cksum_bad))
        sys.stdout.write("\tIO Errors:\t\t\t\t%s\n" % fHits(l2_io_error))
        sys.stdout.write("\tSPA Mismatch:\t\t\t\t%s\n" % fHits(l2_write_spa_mismatch))
        sys.stdout.write("\n")

        sys.stdout.write("L2 ARC Size: (Adaptive)\t\t\t\t%s\n", fBytes(l2_size));
        sys.stdout.write("\tHeader Size:\t\t\t%s\t%s\n" %
            (fPerc(l2_hdr_size, l2_size), fBytes(l2_hdr_size)))
        sys.stdout.write("\n")

        if (l2_evict_lock_retry + l2_evict_reading) > 0:
            sys.stdout.write("L2 ARC Evicts:\n")
            sys.stdout.write("\tLock Retries:\t\t\t\t%s\n" % fHits(l2_evict_lock_retry))
            sys.stdout.write("\tUpon Reading:\t\t\t\t%s\n" % fHits(l2_evict_reading))
            sys.stdout.write("\n")

        sys.stdout.write("L2 ARC Breakdown:\t\t\t\t%s\n" % fHits(l2_access_total))
        sys.stdout.write("\tHit Ratio:\t\t\t%s\t%s\n" %
            (fPerc(l2_hits, l2_access_total), fHits(l2_hits)))
        sys.stdout.write("\tMiss Ratio:\t\t\t%s\t%s\n" %
            (fPerc(l2_misses, l2_access_total), fHits(l2_misses)))
        sys.stdout.write("\tFeeds:\t\t\t\t\t%s\n" % fHits(l2_feeds))
        sys.stdout.write("\n")

        sys.stdout.write("L2 ARC Buffer:\n")
        sys.stdout.write("\tBytes Scanned:\t\t\t\t%s\n" % fBytes(l2_write_buffer_bytes_scanned))
        sys.stdout.write("\tBuffer Iterations:\t\t\t%s\n" % fHits(l2_write_buffer_iter))
        sys.stdout.write("\tList Iterations:\t\t\t%s\n" % fHits(l2_write_buffer_list_iter))
        sys.stdout.write("\tNULL List Iterations:\t\t\t%s\n" % fHits(l2_write_buffer_list_null_iter))
        sys.stdout.write("\n")

        sys.stdout.write("L2 ARC Writes:\n")
        if l2_writes_done != l2_writes_sent:
            sys.stdout.write("\tWrites Sent: (%s)\t\t\t\t%s\n" %
                ("FAULTED", fHits(l2_writes_sent)))
            sys.stdout.write("\t  Done Ratio:\t\t\t%s\t%s\n" %
                (fPerc(l2_writes_done, l2_writes_sent), fHits(l2_writes_done)))
            sys.stdout.write("\t  Error Ratio:\t\t\t%s\t%s\n" %
                (fPerc(l2_writes_error, l2_writes_sent), fHits(l2_writes_error)))
        else:
            sys.stdout.write("\tWrites Sent:\t\t\t%s\t%s\n" % (fPerc(100), fHits(l2_writes_sent)))


def _dmu_summary():
    Kstat = get_Kstat()
    if not Kstat["vfs.zfs.version.spa"]:
        return

    zfetch_bogus_streams = Kstat["kstat.zfs.misc.zfetchstats.bogus_streams"]
    zfetch_colinear_hits = Kstat["kstat.zfs.misc.zfetchstats.colinear_hits"]
    zfetch_colinear_misses = Kstat["kstat.zfs.misc.zfetchstats.colinear_misses"]
    zfetch_hits = Kstat["kstat.zfs.misc.zfetchstats.hits"]
    zfetch_misses = Kstat["kstat.zfs.misc.zfetchstats.misses"]
    zfetch_reclaim_failures = Kstat["kstat.zfs.misc.zfetchstats.reclaim_failures"]
    zfetch_reclaim_successes = Kstat["kstat.zfs.misc.zfetchstats.reclaim_successes"]
    zfetch_streams_noresets = Kstat["kstat.zfs.misc.zfetchstats.streams_noresets"]
    zfetch_streams_resets = Kstat["kstat.zfs.misc.zfetchstats.streams_resets"]
    zfetch_stride_hits = Kstat["kstat.zfs.misc.zfetchstats.stride_hits"]
    zfetch_stride_misses = Kstat["kstat.zfs.misc.zfetchstats.stride_misses"]
        
    zfetch_access_total = (zfetch_hits + zfetch_misses)
    zfetch_colinear_total = (zfetch_colinear_hits + zfetch_colinear_misses)
    zfetch_health_count = (zfetch_bogus_streams)
    zfetch_reclaim_total = (zfetch_reclaim_successes + zfetch_reclaim_failures)
    zfetch_streams_total = (zfetch_streams_resets + zfetch_streams_noresets + zfetch_bogus_streams)
    zfetch_stride_total = (zfetch_stride_hits + zfetch_stride_misses)
                
    if zfetch_access_total > 0:
        sys.stdout.write("File-Level Prefetch: ")
        if zfetch_health_count > 0:
            sys.stdout.write("(DEGRADED)\n\n")
        else:
            sys.stdout.write("(HEALTHY)\n\n")

        sys.stdout.write("DMU Efficiency:\t\t\t\t\t%s\n" % fHits(zfetch_access_total))
        sys.stdout.write("\tHit Ratio:\t\t\t%s\t%s\n" %
            (fPerc(zfetch_hits, zfetch_access_total), fHits(zfetch_hits)))
        sys.stdout.write("\tMiss Ratio:\t\t\t%s\t%s\n" %
            (fPerc(zfetch_misses, zfetch_access_total), fHits(zfetch_misses)))
        sys.stdout.write("\n")

        sys.stdout.write("\tColinear:\t\t\t\t%s\n" % fHits(zfetch_colinear_total))
        sys.stdout.write("\t  Hit Ratio:\t\t\t%s\t%s\n" %
            (fPerc(zfetch_colinear_hits, zfetch_colinear_total), fHits(zfetch_colinear_hits)))
        sys.stdout.write("\t  Miss Ratio:\t\t\t%s\t%s\n" %
            (fPerc(zfetch_colinear_misses, zfetch_colinear_total), fHits(zfetch_colinear_misses)))
        sys.stdout.write("\n")

        sys.stdout.write("\tStride:\t\t\t\t\t%s\n" % fHits(zfetch_stride_total))
        sys.stdout.write("\t  Hit Ratio:\t\t\t%s\t%s\n" %
            (fPerc(zfetch_stride_hits, zfetch_stride_total), fHits(zfetch_stride_hits)))
        sys.stdout.write("\t  Miss Ratio:\t\t\t%s\t%s\n" %
            (fPerc(zfetch_stride_misses, zfetch_stride_total), fHits(zfetch_stride_misses)))
        sys.stdout.write("\n")

        if zfetch_health_count > 0:
            sys.stdout.write("DMU Misc: (%s)\n" % "FAULTED")
        else:
            sys.stdout.write("DMU Misc:\n")

        sys.stdout.write("\tReclaim:\t\t\t\t%s\n" % fHits(zfetch_reclaim_total))
        sys.stdout.write("\t  Successes:\t\t\t%s\t%s\n" %
            (fPerc(zfetch_reclaim_successes, zfetch_reclaim_total), fHits(zfetch_reclaim_successes)))
        sys.stdout.write("\t  Failures:\t\t\t%s\t%s\n" %
            (fPerc(zfetch_reclaim_failures, zfetch_reclaim_total), fHits(zfetch_reclaim_failures)))
        sys.stdout.write("\n\tStreams:\t\t\t\t%s\n" % fHits(zfetch_streams_total));
        sys.stdout.write("\t  +Resets:\t\t\t%s\t%s\n" %
            (fPerc(zfetch_streams_resets, zfetch_streams_total), fHits(zfetch_streams_resets)))
        sys.stdout.write("\t  -Resets:\t\t\t%s\t%s\n" %
            (fPerc(zfetch_streams_noresets, zfetch_streams_total), fHits(zfetch_streams_noresets)))
        sys.stdout.write("\t  Bogus:\t\t\t\t%s\n" % fHits(zfetch_bogus_streams))


def _vdev_summary():
    Kstat = get_Kstat()
    if not Kstat["vfs.zfs.version.spa"]:
        return

    vdev_cache_delegations = Kstat["kstat.zfs.misc.vdev_cache_stats.delegations"]
    vdev_cache_misses = Kstat["kstat.zfs.misc.vdev_cache_stats.misses"]
    vdev_cache_hits = Kstat["kstat.zfs.misc.vdev_cache_stats.hits"]
    vdev_cache_total = (vdev_cache_misses + vdev_cache_hits + vdev_cache_delegations)

    if vdev_cache_total > 0:
        sys.stdout.write("VDEV Cache Summary:\t\t\t\t%s\n" % fHits(vdev_cache_total))
        sys.stdout.write("\tHit Ratio:\t\t\t%s\t%s\n" %
            (fPerc(vdev_cache_hits, vdev_cache_total), fHits(vdev_cache_hits)))
        sys.stdout.write("\tMiss Ratio:\t\t\t%s\t%s\n" %
            (fPerc(vdev_cache_misses, vdev_cache_total), fHits(vdev_cache_misses)))
        sys.stdout.write("\tDelegations:\t\t\t%s\t%s\n" %
            (fPerc(vdev_cache_delegations, vdev_cache_total), fHits(vdev_cache_delegations)))


def _sysctl_summary():
    global show_sysctl_descriptions
    global alternate_sysctl_layout

    Tunable = [
        "kern.maxusers",
        "vm.kmem_size",
        "vm.kmem_size_scale",
        "vm.kmem_size_min",
        "vm.kmem_size_max",
        "vfs.zfs"
    ]

    if not usetunable:
        return

    sysctl_descriptions = {}
    if show_sysctl_descriptions:
        tunables = " ".join(str(x) for x in Tunable)
        p = Popen("/sbin/sysctl -qde %s" % tunables, stdin=PIPE,
            stdout=PIPE, stderr=PIPE, shell=True, close_fds=True)
        p.wait()

        descriptions = p.communicate()[0].split('\n')
        if p.returncode != 0: 
            sys.exit(1)

        for tunable in descriptions:
            if not tunable:
                continue
            tunable = tunable.strip()
            name, description = split("=")[0:2]
            name = name.strip()
            description = description.strip()
            if not description:
                description = "Description unavailable"
            sysctl_descriptions[name] = description


    tunables = " ".join(str(x) for x in Tunable)
    p = Popen("/sbin/sysctl -qe %s" % tunables, stdin=PIPE,
        stdout=PIPE, stderr=PIPE, shell=True, close_fds=True)
    p.wait()

    zfs_tunables = p.communicate()[0].split('\n')
    if p.returncode != 0: 
        sys.exit(1)

    sys.stdout.write("ZFS Tunable (sysctl):\n")
    for tunable in zfs_tunables:
        if not tunable:
            continue
        tunable = tunable.strip()
        name, value = tunable.split("=")[0:2]
        name = name.strip()
        value = D(value.strip())
        format = "\t%s=%d\n" if alternate_sysctl_layout else "\t%-40s%d\n"
        if show_sysctl_descriptions:
            sys.stdout.write("\t\# %s\n" % sysctl_descriptions[name])
        sys.stdout.write(format % (name, value))


unSub = [
    _system_memory,
    _arc_summary,
    _arc_efficiency,
    _l2arc_summary,
    _dmu_summary,
    _vdev_summary,
    _sysctl_summary
]

def _call_all():
    page = 1
    for unsub in unSub:
        unsub()
        sys.stdout.write("\t\t\t\t\t\t\t\tPage: %2d" % page)
        div2()
        page += 1

    page -= 1
    sys.stdout.write("\t\t\t\t\t\t\t\tPage: %2d" % page)
    div2()


def zfs_header():
    daydate = time.strftime("%a %b %d %H:%M:%S %Y")

    div1()
    sys.stdout.write("ZFS Subsystem Report\t\t\t\t%s" % daydate)
    div2()


def main():
    global show_sysctl_descriptions
    global alternate_sysctl_layout

    opts, args = getopt.getopt(
        sys.argv[1:], "adp:"
    )
    
    args = {}
    for opt, arg in opts:
        if opt == '-a':
            args['a'] = True
        if opt == '-d':
            args['d'] = True
        if opt == '-p':
            args['p'] = arg 

    if args:
        alternate_sysctl_layout = True if args.has_key('a') else False
        show_sysctl_descriptions = True if args.has_key('d') else False
        try:
            zfs_header()
            unSub[int(args['p']) - 1]()
            div2()

        except:
            _call_all()

    else:
        _call_all()


if __name__ == '__main__':
    main()
