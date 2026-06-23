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
and an ext4 volume that has flipped read-only after an error. When it detects one
of these after a failed sync, it runs `umount` → `e2fsck -D -f -y` → `mount` on
the Receiver over the existing SSH connection and then retries the sync once. The
email report says whether a repair was needed and whether it succeeded.

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

	command -v umount mount e2fsck

Then create a restricted sudoers drop-in (replace `USER` and the paths to match
the `command -v` output above):

	sudo visudo -f /etc/sudoers.d/nodealyzer-recovery

with contents like:

	USER ALL=(root) NOPASSWD: /usr/bin/umount, /usr/bin/mount, /usr/sbin/e2fsck

If passwordless sudo is not configured, Nodealyzer still runs normally and the
backup proceeds; the email report just notes that it lacked the permissions to
auto-recover and points back to these instructions.

See `test_failures.md` for how to safely validate each recovery path.


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



