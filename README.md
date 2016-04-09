# Rsync Time Machine

I have been use [Back In Time][] as time machine style backup for several
years. It worked very well until I recently need to take periodical snapshots
for a file server.  Backintime cannot directly backup the remote machine, it
must mount remote via sshfs, which is less efficient than running rsync through
ssh, hence this script.


### Features

* Backup from remote host by running rsync through ssh.
* Backup from local directories.
* Support multiple source directories.
* Use hardlinks to save space.
* Smart remove old backups to emulate Apple Time Machine.
* Easy to config multiple backup profiles.

**This script does not attempt to remove old snapshots if there lacks enough
free space.**


### Requirement

* Python.
* The backup destination file system must support hardlinks.
* Rsync must be installed on the remote host if it is the backup source.


### Usage

    time-machine.py -c mybackup.conf

See [time-machine.conf](time-machine.conf) for config example. The config file
splits into five sections:

1. source: the backup source.

2. dest: a local path to store all snapshots.

3. smart_remove: specify how to keep old backups. It recognizes four options.

        keep_all
        keep_one_per_day
        keep_one_per_week
        keep_one_per_month

   The default values will be used if these options is empty or commented out.


4. exclude: the rsync exclude patterns.

5. free space: the minimum free space and inodes requirements. Backup will not
start if there is not enough space or inodes. Again, default value will be used
if option is not set.

Snapshots are named after GMT time stamp. A log file, `time-machine.log`,
is generated under the root of backup destination folder. After run a backup
job periodically for some time, the backup folder should look like:

    ├── 2013-12-31_22:17:01_GMT
    ├── 2014-12-31_22:17:01_GMT
    ├── 2015-05-31_22:17:01_GMT
    ├── 2015-06-30_22:17:01_GMT
    ├── 2015-07-31_22:17:01_GMT
    ├── 2015-08-31_22:17:01_GMT
    ├── 2015-09-30_22:17:01_GMT
    ├── 2015-10-31_22:17:01_GMT
    ├── 2015-11-30_22:17:01_GMT
    ├── 2015-12-31_22:17:01_GMT
    ├── 2016-01-31_22:17:01_GMT
    ├── 2016-02-29_22:17:01_GMT
    ├── 2016-03-20_22:17:01_GMT
    ├── 2016-03-27_22:17:01_GMT
    ├── 2016-03-31_22:17:01_GMT
    ├── 2016-04-03_22:17:01_GMT
    ├── 2016-04-04_22:17:01_GMT
    ├── 2016-04-05_22:17:01_GMT
    ├── 2016-04-06_22:17:01_GMT
    ├── 2016-04-07_22:17:01_GMT
    ├── 2016-04-08_10:17:01_GMT
    ├── 2016-04-08_12:17:01_GMT
    ├── 2016-04-08_14:17:01_GMT
    ├── 2016-04-08_16:17:01_GMT
    ├── 2016-04-08_18:17:01_GMT
    ├── 2016-04-08_20:17:01_GMT
    ├── 2016-04-08_22:17:01_GMT
    ├── 2016-04-09_00:17:01_GMT
    ├── 2016-04-09_02:17:01_GMT
    ├── 2016-04-09_04:17:01_GMT
    ├── 2016-04-09_06:17:01_GMT
    ├── 2016-04-09_08:17:01_GMT
    ├── 2016-04-09_10:17:01_GMT
    ├── latest -> /my/backup/destination/time-capsule/2016-04-09_10:14:13_GMT
    └── time-machine.log

### License

See the [LICENSE](LICENSE) file for license rights and limitations (GNU GPL v2).


[Back In Time]: http://backintime.le-web.org
