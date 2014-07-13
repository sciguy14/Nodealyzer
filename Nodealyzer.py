#!/usr/bin/python

# Nodealyzer Server Assistant by Jeremy Blum
# Copyright 2014 Jeremy Blum, Blum Idea Labs, LLC.
# http://www.jeremyblum.com
# File: Nodealyzer.py
# License: GPL v3 (http://www.gnu.org/licenses/gpl.html)

#Import needed libraries
import ConfigParser, pyzmail, base64, datetime, time, os, re, pprint, subprocess, gzip, sys, shutil, glob

#Read configuration file
config = ConfigParser.ConfigParser()
config.read("config.ini")

#Main program execution
def main():

        print "\nNodealyzer is taking care of business! Stand by, this shouldn't take long...\n"

	#Perform Preflight Checks
	#print "Performing Preflight Checks..."
	#TODO: Confirm valid values in the config file

	#Get some initial info
	#print "Gathering Info..."

        #We'll fill in the email report body as we go
        email_body = ""
	
	#Let's Backup some databases!
	sys.stdout.write("Backing up MySQL Databases...")
	[success, details] = backupDatabases()
	if success:
                print "Success!"
        else:
                print "Failures Occurred!"
        print details
        print ""

        #Adds backups to the long-term archival folder if due for it
        sys.stdout.write("Checking and Updating Backup Archives...")
	[success, details] = updateArchives(int(config.get('MySQL','archival_frequency')))
	if success:
                print "Success!"
        else:
                print "Failures Occurred!"
        print details
        print ""

        #Delete Old Daily Backups
        num_daily_backups = int(config.get('MySQL','num_daily_backups'))
        if num_daily_backups > 0:
                sys.stdout.write("Trimming Daily Backups to the " + str(num_daily_backups) + " most recent...")
                [success, details] = deleteBackups('daily', num_daily_backups)
                if success:
                        print "Success!"
                else:
                        print "Failures Occurred!"
                print details
        else:
                sys.stdout.write("Daily Backups Configured to not Expire...")
                print "Moving On."
        print ""

        #Delete Old Archives
        num_archives = int(config.get('MySQL','num_archives'))
        if num_archives > 0:
                sys.stdout.write("Trimming Archives to the " + str(num_archives) + " most recent...")
                [success, details] = deleteBackups('archive', num_archives)
                if success:
                        print "Success!"
                else:
                        print "Failures Occurred!"
                print details
        else:
                sys.stdout.write("Archives Configured to not Expire...")
                print "Moving On."
        print ""
        
	#Send the email report
	#print "Sending Email report...",
	#sys.stdout.write(sendEmail())

        print "All Done!"

#Backup the databases
def backupDatabases():
	backup_dir = os.path.dirname(os.path.realpath(__file__)) + "/SQL_Backups/"

	suffix = time.strftime('%Y-%m-%d_%H-%M-%S')

	all_success = True
	details = ""
        #Iterate through the configured databases
        for db in xrange(int(config.get('MySQL', 'num_databases'))):
                #Setup database and backup variables
                description = config.get('DB' + str(db+1), 'description')
                name = config.get('DB' + str(db+1), 'name')
                host = config.get('DB' + str(db+1), 'host')
                username = config.get('DB' + str(db+1), 'username')
                password = config.get('DB' + str(db+1), 'password')
                this_backup_dir = backup_dir + name + "/"


                #Create backup folder if needed
                try:
                        if not os.path.exists(this_backup_dir):
                                os.makedirs(this_backup_dir)
                except:
                        details = details + "Error creating or finding backup directory for " + description + "\n"
                        all_success = False
                else:
                        #Execute Database dump and gzip
                        filename = name + "_" + suffix + ".sql.gz"
                        cmd = ['mysqldump', '--add-drop-table', '-h', host, '--user', username, '--password='+password, name]
                        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        dump_output, err = p1.communicate()
                        if p1.returncode is not 0:
                                details = details + err
                                all_success = False
                        else:
                                try:
                                        f = gzip.open(this_backup_dir + filename, "wb")
                                        f.write(dump_output)
                                        f.close()
                                except:
                                        details = details + "There was a problem writing " + description + " to the gzipped output file\n"
                                        all_success = False
                                else:
                                        details = details + description + " was successfully dumped to SQL_Backups/" + name + "/" + filename + "\n"

        details = details.strip('\n')       
        return [all_success, details]

#Clean old backups and add to the archive
def updateArchives(archival_frequency):
        backup_dir = os.path.dirname(os.path.realpath(__file__)) + "/SQL_Backups/"
	all_success = True
	details = ""
        #Iterate through the database backup folders
	backup_folders = sorted(os.listdir(backup_dir))
	if not backup_folders:
                details = details + "No database backups were found for archival.\n"
        else:
                for name in backup_folders:
                        if os.path.isfile(name): pass
                        else:
                                archive_dir = backup_dir + name + "/archives/"
                                #Create archive folder if needed and add to archive if appropriate
                                try:
                                        if not os.path.exists(archive_dir):
                                                os.makedirs(archive_dir)
                                except:
                                        details = details + "Error creating or finding archive directory for SQL_Backups/" + name + "\n"
                                        all_success = False
                                else:
                                        #Look through the archives and identify the latest archived file
                                        archives = sorted(os.listdir(archive_dir))
                                        archive_update_needed = False
                                        if not archives:
                                                archive_update_needed = True
                                                details = details + "No previous archive of SQL_Backups/" + name + " found. "
                                        else:
                                                newest_archive = archive_dir + archives[-1]
                                                if os.path.isfile(newest_archive):
                                                        name_split = newest_archive.split("_")
                                                        name_date = name_split[-2]
                                                        name_time = name_split[-1].split('.')[0]
                                                        file_creation_datetime = datetime.datetime.strptime(name_date + "_" + name_time, '%Y-%m-%d_%H-%M-%S')
                                                        
                                                        #If it's more than the desired days old, we should add the newest backup the archive
                                                        if datetime.timedelta.total_seconds(datetime.datetime.now() - file_creation_datetime) > archival_frequency*24*60*60:
                                                                archive_update_needed = True
                                                                details = details + "Latest archive of SQL_Backups/" + name + " is more than " + str(archival_frequency) + " days old. "

                                        if archive_update_needed:
                                                #Find newest backup
                                                
                                                try:
                                                        backups = sorted(glob.glob(backup_dir + name + "/*.sql.gz"))
                                                        newest_backup = backups[-1]
                                                        if os.path.isfile(newest_backup):
                                                                shutil.copyfile(newest_backup, archive_dir + newest_backup.split("/")[-1])
                                                        else:
                                                                all_success = False
                                                                details = details + "Suitable backup could not be found for Archival!\n"
                                                except:
                                                        all_success = False
                                                        details = details + "Backup archival failed!\n"
                                                else:
                                                        details = details + "Latest backup archived successfully!\n"
                                                        
                                        else:
                                                details = details + "SQL_Backups/" + name + " archives are up-to-date. No archive added.\n"   


        details = details.strip('\n') 
        return [all_success, details]

#Delete Expired Backups
#backup_type = "daily" or "archive"
#num_to_maintain = the number of the selected backups to hold on to
def deleteBackups(backup_type, num_to_maintain):
        backup_dir = os.path.dirname(os.path.realpath(__file__)) + "/SQL_Backups/"
	all_success = True
	details = ""

        #Which kinds of backups are we cleaning?
        if backup_type == 'daily':
                suffix = "/"
        elif backup_type == 'archive':
                suffix = "/archives/"
        else:
                all_success = False
                details = details + "Invalid backup type specified for cleaning.\n"

	if all_success:
                #Iterate through the database backup folders
                backup_folders = sorted(os.listdir(backup_dir))
                if not backup_folders:
                        details = details + "No database backups were found for cleaning.\n"
                else:
                        for name in backup_folders:
                                if os.path.isfile(name): pass
                                else:
                                        cleaning_dir = backup_dir + name + suffix
                                        #Make sure folder exists
                                        if backup_type == 'archive' and not os.path.exists(cleaning_dir):
                                                details = details + "Archive directory not found for SQL_Backups/" + name + suffix + "\n"
                                                all_success = False
                                        else:
                                                #List out the files so we can find expired ones
                                                backups = sorted(os.listdir(cleaning_dir))
                                                backups = filter(os.path.isfile, [os.path.join(cleaning_dir, backup) for backup in backups])
                                                if not backups:
                                                        details = details + "No backups found for cleaning in SQL_Backups/" + name + suffix + ".\n"
                                                elif len(backups) <= num_to_maintain:
                                                        details = details + str(num_to_maintain) + " or fewer backups exist in in SQL_Backups/" + name + suffix + ". No cleaning needed.\n"
                                                else:
                                                        for backup in backups[0:len(backups)-num_to_maintain]:
                                                                try:
                                                                        os.remove(backup)
                                                                except:
                                                                        all_success = False
                                                                        details = details + "Could not delete " + backup + ".\n"
                                                                else:
                                                                        details = details + "Deleted backup " + backup + ".\n"

        details = details.strip('\n') 
        return [all_success, details]
        
	
#Generate and send the Email
def sendEmail():

	#encoded inline image
	logo=base64.b64decode(	"""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
	""")
	
	#Get Current Date & Time
	datetime_string = datetime.datetime.now().strftime('%A, %B %d, %Y | %H:%M%p %Z')
	
	#Create Email Template
	text_content=u'Daily Nodealyzer Report Content'
	with open ("email_template_inlined.html", "r") as template:
		html_content=template.read().replace('\n', '')
	
	#Fill in Template Information
	html_content = html_content.replace('[ENCODED_LOGO]', '<img src="cid:logo"/>')
	html_content = html_content.replace('[DATE_TIME]', datetime_string)
	html_content = html_content.replace('[TITLE]', 'Daily Nodealyzer Report')
	html_content = html_content.replace('[SUBTITLE]', config.get('ServerInfo','friendly_server_name'))
	html_content = html_content.replace('[PANEL]', 'Eventually, a high-level summary will go here.')
	html_content = html_content.replace('[BODY]', """
		<p>Hi!<br>
		Something much more useful will go here eventually.<br>
		Here is a <a href="http://www.jeremyblum.com">link</a>.</p>
		""")
	html_content = html_content.replace('[FOOTER]', 'Generated by <a href="https://www.github.com/sciguy14/Nodealyzer" title="Nodealyzer on GitHub">Nodealyzer</a>')
	
	payload, mail_from, rcpt_to, msg_id=pyzmail.compose_mail(\
        (config.get('ServerInfo','friendly_server_name'), config.get('ServerInfo','server_email')), \
        [(config.get('OwnerInfo','owner_name'), config.get('OwnerInfo','owner_email')),], \
        u'Daily Nodealyzer Report', \
        'iso-8859-1', \
        (text_content, 'iso-8859-1'), \
        (html_content, 'iso-8859-1'), \
        embeddeds=[(logo, 'image', 'gif', 'logo', None), ])

	ret=pyzmail.send_mail(payload, mail_from, rcpt_to, config.get('ServerInfo','smtp_host'), \
        smtp_port=config.get('ServerInfo','smtp_port'), smtp_mode=config.get('ServerInfo','smtp_mode'), \
        smtp_login=config.get('ServerInfo','smtp_login'), smtp_password=config.get('ServerInfo','smtp_password'))

	if isinstance(ret, dict):
		if ret:
			return 'Failed recipients:', ', '.join(ret.keys())
		else:
			return 'Success!'
	else:
		return 'Error:', ret
	
#Database Class
class database:
	def __init__(self, description, name, host, username, password):
		self.description = description
		self.name        = name
		self.host        = host
		self.username    = username
		self.password    = password
	
#Run the Main function when this python script is executed
if __name__ == '__main__':
	main()
