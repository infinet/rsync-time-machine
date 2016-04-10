#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Time Machine Style backup, https://github.com/infinet/rsync-time-machine

Inspired by Back In Time, http://backintime.le-web.org
'''

__license__ = 'GNU GPL v2'
__copyright__ = '2016, Chen Wei <weichen302@gmail.com>'
__version__ = '0.0.2'

import os
import sys
import time
import fcntl
import subprocess
import shutil
import ConfigParser
from datetime import datetime, timedelta
from hashlib import md5
from collections import OrderedDict

ONEK = 1024.0
ONEM = 1048576.0
ONEG = 1073741824.0
ONET = 1099511627776.0
ONEDAY = timedelta(days=1)

# global var
logfp = None
cfg = {}

# default value
KEEP_ALL = 1               # keep all snapshots for last x days
KEEP_ONE_PER_DAY = 7       # keep one snapshots per day for last x days
KEEP_ONE_PER_WEEK = 4      # ...
KEEP_ONE_PER_MONTH = 12    # ...
MIN_SPACE_REQUIREMENT = 1024  # in MB
MIN_INODES_REQUIREMENT = 100000
LOG_FILE = 'time-machine.log'


RSYNC_ARGS = (
    '--recursive',
    '--hard-links',
    '--links',
    '-D',
    '--times',
    '--delete',
    '--delete-excluded',
    '-v',
    '--itemize-changes',
    '--progress',
    '--relative',
)
#        '--perms',
#        '--partial',
#        '--human-readable',
#        '--dry-run',

RSYNC_EXIT_CODE = {
    0: 'Success',
    1: 'Syntax or usage error',
    2: 'Protocol incompatibility',
    3: 'Errors selecting input/output files, dirs',
    4: 'Requested action not supported: an attempt was made  to  manipulate  64-bit files on a platform that cannot support them; or an option was specified that is supported by the client and not by the server.',
    5: 'Error starting client-server protocol',
    6: 'Daemon unable to append to log-file',
    10: 'Error in socket I/O',
    11: 'Error in file I/O',
    12: 'Error in rsync protocol data stream',
    13: 'Errors with program diagnostics',
    14: 'Error in IPC code',
    20: 'Received SIGUSR1 or SIGINT',
    21: 'Some error returned by waitpid()',
    22: 'Error allocating core memory buffers',
    23: 'Partial transfer due to error',
    24: 'Partial transfer due to vanished source files',
    25: 'The --max-delete limit stopped deletions',
    30: 'Timeout in data send/receive',
    35: 'Timeout waiting for daemon connection',
}


class MultiOrderedDict(OrderedDict):
    ''' help configParse get multiple values for same key '''
    def __setitem__(self, key, value):
        if isinstance(value, list) and key in self:
            self[key].extend(value)
        else:
            super(OrderedDict, self).__setitem__(key, value)


def logger(msg):
    ''' simple logger write to log file under snapshot root '''
    logfp.write('%s: %s\n' % (datetime.utcnow()
                              .strftime("%Y-%m-%d %H:%M:%S +0000"), msg))
    print msg


def flock_exclusive():
    ''' lock so only one snapshot of current config is running '''
    fd = os.open(cfg['lock_file'], os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0600)
    try:
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        return False
    return fd


def flock_release(fd):
    ''' Release lock so next snapshots can continue '''

    fcntl.lockf(fd, fcntl.LOCK_UN)
    os.close(fd)
    os.remove(cfg['lock_file'])


def run_rsync(args, verbose=False):
    cmd = ['rsync']
    cmd.extend(args)
    logger('running cmd: %s' % ' '.join(cmd))
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)

        for line in iter(p.stdout.readline, ''):
            line = line.replace('\r', '').replace('\n', '')
            print 'rsync: %s' % line
            sys.stdout.flush()
        p.wait()
        ret = p.returncode
        if ret == 0:
            logger('===== %s synced successfully ====' % args[-2])
        else:
            logger('Rsync Error %d, %s' % ret, RSYNC_EXIT_CODE[ret])

    except:
        ret = -1
        logger('Rsync Exception')

    return ret


def find_snapshots():
    dir = os.listdir(cfg['dest_path'])
    res = []
    for x in dir:
        try:
            dt = datetime.strptime(x, "%Y-%m-%d_%H:%M:%S_GMT")
            res.append((dt, os.path.join(cfg['dest_path'], x)))
        except ValueError:
            pass

    res.sort()
    return res


def take_snapshot():
    snapshots = find_snapshots()

    now = datetime.utcnow()
    backup_dst = os.path.join(cfg['dest_path'],
                              now.strftime("%Y-%m-%d_%H:%M:%S_GMT"))
    args = [x for x in RSYNC_ARGS]
    exclude_patterns = ['--exclude=%s' % x for x in cfg['exclude_patterns']]
    args.extend(exclude_patterns)

    latest = os.path.join(cfg['dest_path'], 'latest')
    if len(snapshots) > 0 and os.path.exists(latest):
        last_snapshot = os.path.realpath(latest)
        print 'Creating hard links ...'
        p = subprocess.Popen(['cp', '-arl', last_snapshot, backup_dst])
        p.wait()
        if p.returncode != 0:
            logger('**** unable to clone last snapshot, abort ****')
            exit(2)

    elif len(snapshots) > 0 and not os.path.exists(latest):
        if os.path.lexists(latest):
            logger('Error, the "latest" symbol link is broken. Remove'
                   ' "latest" and recreate that link by run:\n'
                   'ln -fs yyyy-mm-dd_HH:MM:SS_GMT latest')
        else:
            logger('Error, cannot find the last snapshot, maybe the "latest" '
                   'symbol link has been deleted. Please create that link by '
                   'run:\nln -s yyyy-mm-dd_HH:MM:SS_GMT latest')
        exit(2)

    else:  # len(snapshots) == 0
        if os.path.lexists(latest):
            os.remove(latest)

    args.extend(cfg['sources'])
    args.append(backup_dst)

    ret = run_rsync(args)
    if ret == 0:
        if os.path.exists(latest):
            os.remove(latest)

        os.symlink(backup_dst, latest)

    return now


# function from Back In Time
def inc_month(dt):
    """
    First day of next month of ``date`` with respect on new years. So if
    ``date`` is December this will return 1st of January next year.

    Args:
        date (datetime.date):   old date that should be increased

    Returns:
        datetime.date:          1st day of next month
    """
    y = dt.year
    m = dt.month + 1
    if m > 12:
        m = 1
        y = y + 1
    return datetime(y, m, 1)


# function from Back In Time
def dec_month(dt):
    """
    First day of previous month of ``date`` with respect on previous years.
    So if ``date`` is January this will return 1st of December previous
    year.

    Args:
        date (datetime.date):   old date that should be decreased

    Returns:
        datetime.date:          1st day of previous month
    """
    y = dt.year
    m = dt.month - 1
    if m < 1:
        m = 12
        y = y - 1
    return datetime(y, m, 1)


# function from Back In Time
def smart_remove_keep_all(snapshots, min_date, max_date):
    '''
    Add all snapshots between min_date and max_date to keep_snapshots

    Args:
        snapshots (list):  [(dt1, snapshot_path1), ...]
        min_date (datetime.datetime):   minimum date for snapshots to keep
        max_date (datetime.datetime):   maximum date for snapshots to keep

    Returns:
        list: list of snapshots that should be kept
    '''
    res = []
    for (dt, spath) in snapshots:
        if min_date <= dt and dt <= max_date:
            res.append(spath)

    return res


def smart_remove_keep_last(snapshots, min_date, max_date):
    '''
    Add only the lastest snapshots between min_date and max_date to
    keep_snapshots.

    Args:
        snapshots (list):  [(dt1, snapshot_path1), ...]
        min_date (datetime.datetime):   minimum date for snapshots to keep
        max_date (datetime.datetime):   maximum date for snapshots to keep

    Returns:
        string: the snapshot to be kept
    '''
    res = []
    for (dt, spath) in snapshots:
        if min_date <= dt and dt < max_date:
            res.append((dt, spath))

    if res:
        res.sort()
        return [res[-1][1]]
    else:
        return []


# function from Back In Time
def smart_remove(snapshots,
                 now,
                 keep_all,
                 keep_one_per_day,
                 keep_one_per_week,
                 keep_one_per_month):
    '''
    Remove old snapshots based on configurable intervals.

    Args:
        now (datetime.datetime):        date and time when take_snapshot was
                                        started
        keep_all (int):                 keep all snapshots for the
                                        last ``keep_all`` days
        keep_one_per_day (int):         keep one snapshot per day for the
                                        last ``keep_one_per_day`` days
        keep_one_per_week (int):        keep one snapshot per week for the
                                        last ``keep_one_per_week`` weeks
        keep_one_per_month (int):       keep one snapshot per month for the
                                        last ``keep_one_per_month`` months
    '''
    if len(snapshots) <= 1:
        logger("There is only one snapshots, so keep it")
        return

    if now is None:
        now = datetime.utcnow()

    # utc 00:00:00
    today = datetime(now.year, now.month, now.day, 0, 0, 0)
    snapshots.sort()

    # keep the last snapshot
    keep_snapshots = [snapshots[-1][1]]

    # keep all for the last keep_all days x 24 hours
    if keep_all > 0:
        tmp = smart_remove_keep_all(snapshots,
                                    now - timedelta(days=keep_all), now)
        keep_snapshots.extend(tmp)

    # keep one per days for the last keep_one_per_day days
    if keep_one_per_day > 0:
        d = today
        for i in range(0, keep_one_per_day):
            tmp = smart_remove_keep_last(snapshots, d, d + ONEDAY)
            keep_snapshots.extend(tmp)
            d -= ONEDAY

    # keep one per week for the last keep_one_per_week weeks
    if keep_one_per_week > 0:
        d = today - timedelta(days=today.weekday() + 1)
        for i in range(0, keep_one_per_week):
            tmp = smart_remove_keep_last(snapshots, d,
                                         d + timedelta(days=8))
            keep_snapshots.extend(tmp)
            d -= timedelta(days=7)

    # keep one per month for the last keep_one_per_month months
    if keep_one_per_month > 0:
        d1 = datetime(now.year, now.month, 1)
        d2 = inc_month(d1)
        for i in range(0, keep_one_per_month):
            tmp = smart_remove_keep_last(snapshots, d1, d2)
            keep_snapshots.extend(tmp)
            d2 = d1
            d1 = dec_month(d1)

    # keep one per year for all years
    first_year = snapshots[0][0].year

    for i in range(first_year, now.year + 1):
        tmp = smart_remove_keep_last(snapshots,
                                     datetime(i, 1, 1),
                                     datetime(i + 1, 1, 1))
        keep_snapshots.extend(tmp)

    tmp = set(keep_snapshots)
    keep_snapshots = tmp
    del_snapshots = []
    for dt, s in snapshots:
        if s in keep_snapshots:
            continue

        del_snapshots.append(s)

    if not del_snapshots:
        logger('[Smart remove] no snapshot to remove')
        return

    for s in del_snapshots:
        logger('[Smart remove] delete snapshot %s' % s)
        shutil.rmtree(s)


def get_config(conf):
    global cfg
    global logfp
    config = ConfigParser.RawConfigParser(dict_type=MultiOrderedDict,
                                          allow_no_value=True)
    config.read(conf)
    cfg = {'dest_path': None,
           'min_space': MIN_SPACE_REQUIREMENT,
           'min_inodes': MIN_INODES_REQUIREMENT,
           'keep_all': KEEP_ALL,
           'keep_one_per_day': KEEP_ONE_PER_DAY,
           'keep_one_per_week': KEEP_ONE_PER_WEEK,
           'keep_one_per_month': KEEP_ONE_PER_MONTH
           }
    try:
        source_host = config.get('source', 'host')[0]
    except ConfigParser.NoOptionError:
        source_host = None

    try:
        source_user = config.get('source', 'user')[0]
    except ConfigParser.NoOptionError:
        source_user = None

    source_paths = config.get('source', 'path')

    if source_host and source_user:  # ssh remote
        cfg['sources'] = ['%s@%s:%s' % (source_user, source_host, p)
                          for p in source_paths]
    elif source_host and not source_user:  # ssh username in .ssh/config
        cfg['sources'] = ['%s:%s' % (source_host, p)
                          for p in source_paths]
    else:  # local path
        cfg['sources'] = source_paths

    cfg['exclude_patterns'] = config.get('exclude', 'pattern')

    cfg['dest_path'] = config.get('dest', 'path')[0]
    for k in ('keep_all', 'keep_one_per_day', 'keep_one_per_week',
              'keep_one_per_month'):
        try:
            tmp = config.get('smart_remove', k)[0]
            if tmp:
                cfg[k] = int(tmp)
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            pass

    for k in ('min_space', 'min_inodes'):
        try:
            tmp = config.get('free space', k)[0]
            if tmp:
                cfg[k] = int(tmp)
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            pass

    m = md5()
    m.update(cfg['dest_path'])
    cfg['lock_file'] = '/tmp/time-machine-%s.lock' % m.hexdigest()

    if not os.path.exists(cfg['dest_path']):
        os.makedirs(cfg['dest_path'])

    logfp = open(os.path.join(cfg['dest_path'], LOG_FILE), 'a')
    return cfg


def humanize_bytes(n):
    n = int(n)
    if n >= ONET:
        ret = '%.2f TB' % (n / ONET)
    elif n >= ONEG:
        ret = '%.2f GB' % (n / ONEG)
    elif n >= ONEM:
        ret = '%.0f MB' % (n / ONEM)
    elif n >= ONEK:
        ret = '%.0f KB' % (n / ONEK)
    else:
        ret = '%d Bytes' % n

    return ret


def humanize_inodes(n):
    n = int(n)
    if n >= ONET:
        ret = '%.0f T' % (n / ONET)
    elif n >= ONEG:
        ret = '%.0f G' % (n / ONEG)
    elif n >= ONEM:
        ret = '%.0f M' % (n / ONEM)
    elif n >= ONEK:
        ret = '%.0f K' % (n / ONEK)
    else:
        ret = '%d ' % n

    return ret


def print_fs_stat(stat):
    inodes_free = stat.f_favail
    inodes_used = (stat.f_files - stat.f_favail) * 100.0 / stat.f_files

    space_free = stat.f_bavail * stat.f_bsize
    space_total = stat.f_blocks * stat.f_bsize
    space_used = (space_total - space_free) * 100.0 / space_total

    logger('    free space: %s, %.1f%% used' % (humanize_bytes(space_free),
                                                space_used))
    logger('    free inodes: %s, %.1f%% used' % (humanize_inodes(inodes_free),
                                                 inodes_used))


def check_freespace(stat):
    ''' abort backup if not enough free space or inodes '''
    inodes_free = stat.f_favail
    space_free = stat.f_bavail * stat.f_bsize / ONEM
    if inodes_free < cfg['min_inodes']:
        logger('Error: not enough inodes, the backup filesystem has %d free '
               'inodes, the minimum requirement is %d'
               % (inodes_free, cfg['min_inodes']))
        logger('Backup task aborted!')
        sys.exit(2)

    if space_free < cfg['min_space']:
        logger('Error: not enough space, the backup filesystem has %.0f MB '
               'free space, the minimum requirement is %d MB'
               % (space_free, cfg['min_space']))
        logger('Backup task aborted!')
        sys.exit(2)


def main():
    if len(sys.argv) != 3:
        print 'Usage: %s -c configfile' % sys.argv[0]
        sys.exit(2)

    get_config(sys.argv[2])
    fd = flock_exclusive()
    if not fd:
        logger('Error: cannot obtain lock, there maybe another time-machine '
               'is running')
        logger('Backup task aborted!')
        sys.exit(2)

    stat_before = os.statvfs(cfg['dest_path'])
    check_freespace(stat_before)

    t_start = datetime.now()
    take_snapshot()
    snapshots = find_snapshots()
    smart_remove(snapshots, None,
                 cfg['keep_all'],
                 cfg['keep_one_per_day'],
                 cfg['keep_one_per_week'],
                 cfg['keep_one_per_month'])

    # report
    stat_after = os.statvfs(cfg['dest_path'])
    logger('Filesystem before backup:')
    print_fs_stat(stat_before)
    logger('Filesystem after backup:')
    print_fs_stat(stat_after)

    t_used = datetime.now() - t_start
    logger('Backup runtime: %s' % str(t_used).split('.')[0])
    flock_release(fd)


if __name__ == "__main__":
    main()
