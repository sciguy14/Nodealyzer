Nodealyzer
=============
Info soon!

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



