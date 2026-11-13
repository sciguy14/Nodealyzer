Nodealyzer
=============
Info soon!

Terminology
=============
* **Server** — the machine Nodealyzer runs on and backs up.
* **Receiver** — the remote machine that receives and stores the backups (it has the backup drive attached).

Note: the config keys prefixed `backup_server_*` (fqdn, ssh port, username, remote directory) historically describe the **Receiver**, not the Server. They are kept under that name for backwards compatibility.

Getting Setup
=============
What you'll need
----------------
* stuff

Prepare the Configuration File
------------------------------
* Rename "config_sample.ini" to "config.ini".
* Rename "rsync_exclusions_sample.txt" to "rsync_exclusions.txt"
* stuff

Install the Linux Prerequisites
-------------------------------
sudo apt-get install logwatch
sudo apt-get install rsync


Install the Python Prerequisites
--------------------------------
* Install Python 2.7 if don't already have it installed: sudo apt-get install python2.7
* Install Python PIP if you haven't already: sudo apt-get install python-dev python-pip
* Install Mailer: sudo pip install pyzmail

Configure Rsync on the machine that will be receiving the backups (Backup Machine)
----------------------------------------------------------------------------------
* SSH into the Server that you are backing up
* Run `ssh-keygen`
* An ssh private key will be generated at `~/.ssh/id_rsa` and a public key will be generated at `~/.ssh/id_rsa.pub`
* Use secure copy to send the public key to your Backup machine (The first two commands will ask for your backup machine password. The last command will not, because it can authenticate via the authorized public key that you just installed.)
    * scp -P REMOTE_SSH_PORT_NUM ~/.ssh/id_rsa.pub USER@HOSTNAME.com:/home/REMOTE_USER/.ssh/uploaded_key.pub
	* ssh -p REMOTE_SSH_PORT_NUM user@hostname.com "cat ~/.ssh/uploaded_key.pub >> ~/.ssh/authorized_keys"
	* ssh -p REMOTE_SSH_PORT_NUM user@hostname.com "rm ~/.ssh/uploaded_key.pub"


Backup Drive Auto-Recovery (on the Receiver)
--------------------------------------------
Nodealyzer can automatically recover the Receiver's backup drive from a few
recoverable filesystem faults — most notably the ext4 directory-checksum
corruption that surfaces as a flood of `rsync: ... Bad message (74)` errors
(`EXT4-fs error ... No space for directory leaf checksum. Please run e2fsck -D`),
and an ext4 volume that has flipped read-only after an error. It checks at two
points, and in both cases runs `umount` → `e2fsck -D -f -y` → `mount` on the
Receiver over the existing SSH connection:

1. **Before the sync (pre-flight).** It reads the ext4 superblock with
   `dumpe2fs -h`, which is read-only and safe while the drive is mounted. If the
   kernel has flagged the filesystem (`Filesystem state: clean with errors`), it
   repairs the drive first and then syncs.
2. **After a failed sync (fallback).** This catches corruption the kernel hadn't
   flagged yet. If the rsync errors match a repairable signature, it repairs the
   drive and retries the sync once.

The email report says whether a repair was needed and whether it succeeded.
If a repair fails part-way and leaves the drive unmounted, the sync is skipped
rather than writing into the Receiver's root filesystem.

rsync's stderr is captured to a temporary file, not a pipe. A corrupted drive can
produce hundreds of KB of errors; with a pipe, that filled the 64 KB buffer and
deadlocked the run until cron's `timeout` killed it, so no email was ever sent.
rsync also runs with `--timeout=600`, and SSH runs with `ServerAliveInterval`, so
a dead link fails the run instead of hanging it.

It is deliberately conservative: it will **not** auto-repair on a suspected
hardware failure (`Input/output error`) or a full disk (`No space left on
device`) — those are reported for manual attention only. It also only ever acts
on a mount point that is declared in the Receiver's `/etc/fstab`.

This feature is controlled by the optional `autofix_filesystem` key in the
`[RSync]` section of `config.ini` (defaults to `true` if omitted; set to `false`
to disable).

**Requirement 1 — mount the backup drive via `/etc/fstab`.** The backup drive
must be an fstab-managed mount on the Receiver (Nodealyzer reads fstab to find
the device, and refuses to touch anything fstab doesn't declare). Use the
`nofail` option so a missing drive doesn't block boot. Example:

	/dev/sda1  /home/USER/BackupDrive  ext4  nofail,defaults  0  0

**Requirement 2 — passwordless sudo for the recovery commands on the Receiver.**
The SSH user runs the recovery commands via `sudo -n`, so it needs NOPASSWD sudo
for *exactly* those commands (nothing more). First confirm the real binary paths
on the Receiver (they vary by distro):

	command -v umount mount e2fsck dumpe2fs dmesg

Then create a restricted sudoers drop-in (replace `USER` and the paths to match
the `command -v` output above):

	sudo visudo -f /etc/sudoers.d/nodealyzer-recovery

with contents like:

	USER ALL=(root) NOPASSWD: /usr/bin/umount, /usr/bin/mount, /usr/sbin/e2fsck, /usr/sbin/dumpe2fs, /usr/bin/dmesg

If you use the locked-down receiver account (below), use
`receiver/sudoers-nodealyzer-recovery.sample` instead. It allows those commands only with
the exact arguments Nodealyzer uses.

(`dumpe2fs` is for the pre-flight health check. `dmesg` lets Nodealyzer refuse to
auto-repair when the kernel has logged I/O errors for the disk, which points to
failing hardware.)

If passwordless sudo is not configured, Nodealyzer still runs normally and the
backup proceeds; the email report just notes that it lacked the permissions to
auto-recover and points back to these instructions.

See `test_failures.md` for how to safely validate each recovery path.

**Requirement 3: the Receiver's host key must already be in `known_hosts`.**
All SSH connections use `StrictHostKeyChecking=yes` and `BatchMode=yes`, so an
unknown or changed host key fails the run instead of being trusted silently. Add
the entry once, and check its fingerprint against the Receiver's own key first:

	ssh-keyscan -p PORT HOSTNAME | ssh-keygen -lf -          # on the Server
	ssh-keygen -lf /etc/ssh/ssh_host_ecdsa_key.pub           # on the Receiver; must match
	ssh-keyscan -p PORT HOSTNAME >> ~/.ssh/known_hosts       # only if it matches


Locked-Down Receiver Account (Recommended)
------------------------------------------
Don't let the Server log into the Receiver as a personal or sudo-capable
account. The Server's key has no passphrase (cron needs it that way), so
whoever gets the Server gets that account. Instead, use a dedicated user that
can only push files into the backup directory and run the fixed drive-recovery
commands above. The files are in `receiver/`:

| File | Install to (on the Receiver) |
|---|---|
| `receiver/nodealyzer-gate` | `/usr/local/sbin/nodealyzer-gate` (root:root 755). Install as-is, no edits. |
| `receiver/nodealyzer-gate.conf.sample` | `/etc/nodealyzer-gate.conf` (root:root 644). Set `BACKUP_DIR` and `BACKUP_DEV`. |
| `receiver/sudoers-nodealyzer-recovery.sample` | `/etc/sudoers.d/nodealyzer-recovery` (root:root 440). Replace the placeholders. |
| `receiver/sshd-nodealyzer.conf.sample` | `/etc/ssh/sshd_config.d/50-nodealyzer.conf` (root:root 644). Replace the placeholders. |

All machine-specific values go in those installed copies on the Receiver, never
in this repo. `.gitignore` excludes local non-`.sample` copies under
`receiver/`. The gate refuses to run if `/etc/nodealyzer-gate.conf` is missing,
not owned by root, writable by group or others, or has an invalid value.

The gate matches each incoming command string **exactly** and runs it with
hard-coded arguments. It never passes the incoming string to a shell. rsync is
sent to `rrsync -wo -absolute BACKUP_DIR` (rsync 3.2.4+ ships `/usr/bin/rrsync`):

* `-wo` (write-only) is enough because Nodealyzer only pushes. `--delete` is a
  receiver-side action, so it still works. Pulls (`--sender`) are refused.
* `-absolute` lets Nodealyzer keep using the absolute path in
  `backup_server_remote_directory`. The recovery code also needs that path for
  `findmnt`. Paths outside `BACKUP_DIR` and paths containing `..` are rejected.

If you change the rsync flags or add a new remote command to `Nodealyzer.py`,
add it to the gate too, or it will be refused. Refusals are logged on the
Receiver: `journalctl -t nodealyzer-gate`.

Setup (on the Receiver, as an admin):

	sudo useradd --system --create-home --home-dir /var/lib/nodealyzer --shell /bin/sh nodealyzer
	sudo install -o root -g root -m 755 receiver/nodealyzer-gate /usr/local/sbin/nodealyzer-gate
	sudo install -o root -g root -m 644 receiver/nodealyzer-gate.conf.sample /etc/nodealyzer-gate.conf
	sudoedit /etc/nodealyzer-gate.conf                  # set BACKUP_DIR and BACKUP_DEV
	sudo install -d -o root -g root -m 755 /var/lib/nodealyzer/.ssh
	# one line, with the Server's public key and IP:
	echo 'from="SERVER_IP",restrict,command="/usr/local/sbin/nodealyzer-gate" ssh-ed25519 AAAA... server' \
	  | sudo tee /var/lib/nodealyzer/.ssh/authorized_keys
	sudo chown -R nodealyzer:nodealyzer BACKUP_DIR      # the backup tree must be owned by the new user
	sudo sshd -t && sudo systemctl reload ssh

The shell must be a real shell (`/bin/sh`), not `nologin`, because sshd runs the
forced command through the user's shell. The forced command keeps it from ever
being an interactive shell. Don't put `BACKUP_DIR` inside a `700` home
directory, because the new user can't get into it there. Then set
`backup_server_username` and `backup_server_remote_directory` in `config.ini`.

Note: rsync runs as a non-root user here, so it can't preserve file owners or
groups. Everything on the Receiver is owned by the backup user. File modes and
timestamps are still kept.


Dead-Man's Switch (Optional, Recommended)
-----------------------------------------
The email report only helps if it arrives. If Nodealyzer hangs, crashes, can't
send email, or the server is down, you get silence, which is easy to miss. To
catch that, Nodealyzer can ping a monitoring service such as
[healthchecks.io](https://healthchecks.io) (the free tier is enough):

* `<url>/start` when a run begins
* `<url>` when the backup was clean **and** the email was sent
* `<url>/fail` for any failure (backup errors, email failure, or a crash), with a short reason attached

If no success ping arrives on schedule, the service alerts you by email, push or
SMS. Setup:

1. Create a check with a cron schedule matching your crontab (e.g. `0 1 * * *`),
   the server's timezone, and a grace time longer than the cron `timeout`
   (e.g. 2 hours for `timeout 3600`).
2. Copy its ping URL into `config.ini`:

		[Monitoring]
		healthcheck_url : https://hc-ping.com/your-uuid-here

Treat the ping URL as a secret: anyone who has it can mark your backups healthy.
If the key is missing or empty, the pings are skipped.


TODO: Complete this documentation
Git clone my repo
make the program executable: chmod 755 Nodealyzer.py
Setup a cron job
#Daily Nodealyzer Run
0 1 * * * /home/jeremy/Nodealyzer/Nodealyzer.py > /dev/null


License
=======
This work is licensed under the [GNU GPL v3](http://www.gnu.org/licenses/gpl.html).
Please share improvements or remixes with the community, and attribute me (Jeremy Blum, <http://www.jeremyblum.com>) when reusing portions of my code.



