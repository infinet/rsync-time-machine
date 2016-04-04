# Rsync Time Machine

I have been a happy [Back In Time][] user for several years. But recently I need
to take periodical snapshots for a file server. Backintime cannot directly
backup the remote machine, it must mount remote via sshfs, which is less
efficient than running rsync through ssh.


### Features

* backup from remote host by running rsync through ssh
* backup from local directories
* support multiple source directories
* use hardlinks to save space
* smart remove old backups to emulate Apple Time Machine
* easy to config multiple backup profiles

**This script does not attempt to remove old snapshots if there lacks enough
free space.**


### Requirement

The backup destination file system must support hardlinks.

Rsync must be installed on the remote host if it is the backup source.


### Usage

    time-machine.py -c mybackup.conf

See [time-machine.conf](time-machine.conf) for config example. The config file
splits into four sections:

1. source: the backup source

2. dest: a local path to store all snapshots

3. smart_remove: specify how to keep old backups. It recognizes four options.

        keep_all
        keep_one_per_day
        keep_one_per_week
        keep_one_per_month


4. exclude: the rsync exclude patterns

The snapshot folder use GMT time stamp as its name. A log file,
`time-machine.log`, is under the root of backup destination folder.

### License

See the [LICENSE](LICENSE) file for license rights and limitations (GNU GPL v2).


[Back In Time]: http://backintime.le-web.org
