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
* stuff

Install the Linux Prerequisites
-------------------------------
sudo apt-get install logwatch
sudo apt-get install rsync
sudo apt-get install rsnapshot


Install the Python Prerequisites
--------------------------------
* Install Python 2.7 if don't already have it installed: sudo apt-get install python2.7
* Install Python PIP if you haven't already: sudo apt-get install python-dev python-pip
* Install Mailer: sudo pip install pyzmail

Configure Rsync on the machine that will be receiving the backups (Backup Machine)
----------------------------------------------------------------------------------
* SSH into the backup machine (or log on directly if it is local)
* Run `ssh-keygen`
* An ssh private key will be generated at `~/.ssh/id_rsa` and a public key will be generated at `~/.ssh/id_rsa.pub`
* Use secure copy to send the public key to your Server to be backed up:
    * scp ~/.ssh/id_rsa.pub user@hostname.com:/home/user/.ssh/uploaded_key.pub
	* ssh user@hostname.com "echo `cat ~/.ssh/uploaded_key.pub` >> ~/.ssh/authorized_keys"

TODO: Complete this documentation
Git clone my repo
make the program executable: chmod 755 Nodealyzer.py
Setup a cron job

License
=======
This work is licensed under the [GNU GPL v3](http://www.gnu.org/licenses/gpl.html).
Please share improvements or remixes with the community, and attribute me (Jeremy Blum, <http://www.jeremyblum.com>) when reusing portions of my code.



