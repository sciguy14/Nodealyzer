#!/usr/bin/python

# Nodealyzer Server Assistant by Jeremy Blum
# Copyright 2014 Jeremy Blum, Blum Idea Labs, LLC.
# http://www.jeremyblum.com
# File: Nodealyzer.py
# License: GPL v3 (http://www.gnu.org/licenses/gpl.html)

#Import needed libraries
import ConfigParser, pyzmail, base64, datetime, time, os, re, pprint, subprocess, gzip, sys, shutil, glob

#Know Script Directory so we can make absolute references
script_dir = os.path.dirname(os.path.realpath(__file__))

#Read configuration file
config = ConfigParser.ConfigParser()
config.read(script_dir + "/config.ini")

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

        #We'll add locations of log files to attach to this list:
        log_file_attachments = []

        #We'll use this to report a high level good/bad summary at the top of the email
        all_good = True
        status_reports = "<h3 style='margin:5px;'>Overview</h3>\n<table>\n"

        #String Constants
        PASS_STYLED = "<td align='left'><font color='green'><b>Pass</b></font></td>"
        FAIL_STYLED = "<td align='left'><font color='red'><b>Fail</b></font></td>"
        NA_STYLED   = "<td align='left'><font color='grey'><b>N/A</b></font></td>"
        

        #DATABASES ---------------------------------
        email_body = email_body + "<h1>Database Backup</h1>"
	
	#Let's Backup some databases!
	sys.stdout.write("Backing up MySQL Databases...")
	[success, details, html] = backupDatabases()
	if success:
                print "Success!"
                email_body = email_body + "<p>The following MySQL databases were backed up successfully:</p>\n"
                status_reports = status_reports + "\t<tr align='right'><td>Database Backups:</td>" + PASS_STYLED + "</tr>\n"
        else:
                print "Failures Occurred!"
                email_body = email_body + "<p>Errors occured while backing up MySQL databases:</p>\n"
                status_reports = status_reports + "\t<tr align='right'><td>Database Backups:</td>" + FAIL_STYLED + "</tr>\n"
                all_good = False
        print details
        email_body = email_body + html
        print ""

        #Adds backups to the long-term archival folder if due for it
        sys.stdout.write("Checking and Updating Backup Archives...")
	[success, details, html] = updateArchives(int(config.get('MySQL','archival_frequency')))
	if success:
                print "Success!"
                email_body = email_body + "<p>Long-term archives were successfully created if due:</p>\n"
                status_reports = status_reports + "\t<tr align='right'><td>Database Archivals:</td>" + PASS_STYLED + "</tr>\n"
        else:
                print "Failures Occurred!"
                email_body = email_body + "<p>Errors occured while checking or creating long-term archives:</p>\n"
                status_reports = status_reports + "\t<tr align='right'><td>Database Archivals:</td>" + FAIL_STYLED + "</tr>\n"
                all_good = False
        print details
        email_body = email_body + html
        print ""

        #Delete Old Daily Backups
        #TODO: Should do this by date instead of number
        num_daily_backups = int(config.get('MySQL','num_daily_backups'))
        if num_daily_backups > 0:
                sys.stdout.write("Trimming Daily Backups to the " + str(num_daily_backups) + " most recent...")
                [success, details, html] = deleteBackups('daily', num_daily_backups)
                if success:
                        print "Success!"
                        email_body = email_body + "<p>Daily backups older than " + str(num_daily_backups) + " days deleted if needed:</p>\n"
                        status_reports = status_reports + "\t<tr align='right'><td>Daily Backup Cleaning:</td>" + PASS_STYLED + "</tr>\n"
                else:
                        print "Failures Occurred!"
                        email_body = email_body + "<p>Errors occured while trying to delete daily backups:</p>\n"
                        status_reports = status_reports + "\t<tr align='right'><td>Daily Backup Cleaning:</td>" + FAIL_STYLED + "</tr>\n"
                        all_good = False
                print details
                email_body = email_body + html
        else:
                sys.stdout.write("Daily Backups Configured to not Expire...")
                print "Moving On."
                email_body = email_body + "<p>Daily backups have not been configured to expire.</p>\n"
                status_reports = status_reports + "\t<tr align='right'><td>Daily Backup Cleaning:</td>" + NA_STYLED + "</tr>\n"
        print ""

        #Delete Old Archives
        num_archives = int(config.get('MySQL','num_archives'))
        if num_archives > 0:
                sys.stdout.write("Trimming Archives to the " + str(num_archives) + " most recent...")
                [success, details, html] = deleteBackups('archive', num_archives)
                if success:
                        print "Success!"
                        email_body = email_body + "<p>Old archives deleted. "+ str(num_archives) + " kept:</p>\n"
                        status_reports = status_reports + "\t<tr align='right'><td>Archive Cleaning:</td>" + PASS_STYLED + "</tr>\n"
                else:
                        print "Failures Occurred!"
                        email_body = email_body + "<p>Errors occured while trying to delete archives:</p>\n"
                        status_reports = status_reports + "\t<tr align='right'><td>Archive Cleaning:</td>" + FAIL_STYLED + "</tr>\n"
                        all_good = False
                print details
                email_body = email_body + html
        else:
                sys.stdout.write("Archives Configured to not Expire...")
                print "Moving On."
                email_body = email_body + "<p>Archives have not been configured to expire.</p>\n"
                status_reports = status_reports + "\t<tr align='right'><td>Archive Cleaning:</td>" + NA_STYLED + "</tr>\n"
        print ""

        #END DATABASES -----------------------------

        #RSYNC -------------------------------------
        email_body = email_body + "<h1>Remote Sync</h1>"
	
	#Let's Syncronize!
	sys.stdout.write("Performing Remote Sync...")
	[success, details, html] = rsync()
	if success:
                print "Success!"
                email_body = email_body + "<p>Files were backed up to " + config.get('RSync','backup_server_fqdn') + "! "
                status_reports = status_reports + "\t<tr align='right'><td>Remote Data Backup:</td>" + PASS_STYLED + "</tr>\n"
        else:
                print "Failures Occurred!"
                email_body = email_body + "<p>Errors occured while backing up to " + config.get('RSync','backup_server_fqdn') + ". "
                status_reports = status_reports + "\t<tr align='right'><td>Remote Data Backup:</td>" + FAIL_STYLED + "</tr>\n"
                all_good = False
        if os.path.isfile(script_dir + '/rsync.log'):
                email_body = email_body + "A log file is attached.</p>\n"
                log_file_attachments.append(script_dir + '/rsync.log')
        else:
                email_body = email_body + "A log file could not be generated.</p>\n"
        print details
        email_body = email_body + html
        print ""
        #END RSYNC ---------------------------------

        #LOG FILE ANALYSIS -------------------------
        '''
        email_body = email_body + "<h1>Log Files</h1>"

        #Let's check the Apache Logs!
	sys.stdout.write("Querying Apache Logs...")
	[success, details, html] = logParse()
	if success:
                print "Success!"
                email_body = email_body + "<p>The following MySQL databases were backed up successfully:</p>\n"
                status_reports = status_reports + "\t<tr align='right'><td>Database Backups:</td>" + PASS_STYLED + "</tr>\n"
        else:
                print "Failures Occurred!"
                email_body = email_body + "<p>Errors occured while backing up MySQL databases:</p>\n"
                status_reports = status_reports + "\t<tr align='right'><td>Database Backups:</td>" + FAIL_STYLED + "</tr>\n"
                all_good = False
        print details
        email_body = email_body + html
        print ""
        '''
        #END LOG FILE ANALYSIS ---------------------
        
	#Send the email report
        status_reports = status_reports + "</ul>"
	sys.stdout.write("Sending Email report...")
	#TODO: More generic file attach for logs
	print sendEmail(status_reports, email_body, log_file_attachments)

        print ""
        print "All Done!"

#Backup the databases
def backupDatabases():
	backup_dir = script_dir + "/SQL_Backups/"

	suffix = time.strftime('%Y-%m-%d_%H-%M-%S')

	all_success = True
	details = ""
	html = "<ul>\n"
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
                        html = html + "\t<li>Error creating or finding backup directory for " + description + "</li>\n"
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
                                        html = html + "\t<li>There was a problem writing " + description + " to the gzipped output file</li>\n"
                                        all_success = False
                                else:
                                        details = details + description + " was successfully dumped to SQL_Backups/" + name + "/" + filename + "\n"
                                        html = html + "\t<li>" + description + " was successfully dumped to SQL_Backups/" + name + "/" + filename + "</li>\n"

        details = details.strip('\n')
        html = html + "</ul>\n"
        return [all_success, details, html]

#Clean old backups and add to the archive
def updateArchives(archival_frequency):
        backup_dir = script_dir + "/SQL_Backups/"
	all_success = True
	details = ""
	html = "<ul>\n"
        #Iterate through the database backup folders
	backup_folders = sorted(os.listdir(backup_dir))
	if not backup_folders:
                details = details + "No database backups were found for archival.\n"
                html = html + "\t<li>No database backups were found for archival.</li>\n"
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
                                        html = html + "\t<li>Error creating or finding archive directory for SQL_Backups/" + name + "</li>\n"
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
                                                                html = html + "\t<li>Suitable backup for SQL_Backups/" + name + " could not be found for Archival!</li>\n"
                                                                
                                                except:
                                                        all_success = False
                                                        details = details + "Backup archival failed!\n"
                                                        html = html + "\t<li>Backup archival for SQL_Backups/" + name + " failed!</li>\n"
                                                else:
                                                        details = details + "Latest backup archived successfully!\n"
                                                        html = html + "\t<li>Latest backup of SQL_Backups/" + name + " archived successfully!</li>\n"
                                                        
                                        else:
                                                details = details + "SQL_Backups/" + name + " archives are up-to-date. No archive added.\n"
                                                html = html + "\t<li>SQL_Backups/" + name + " archives are up-to-date. No archive added.</li>\n"


        details = details.strip('\n')
        html = html + "</ul>\n"
        return [all_success, details, html]

#Delete Expired Backups
#backup_type = "daily" or "archive"
#num_to_maintain = the number of the selected backups to hold on to
def deleteBackups(backup_type, num_to_maintain):
        backup_dir = script_dir + "/SQL_Backups/"
	all_success = True
	details = ""
        html = "<ul>\n"
        #Which kinds of backups are we cleaning?
        if backup_type == 'daily':
                suffix = "/"
        elif backup_type == 'archive':
                suffix = "/archives/"
        else:
                all_success = False
                details = details + "Invalid backup type specified for cleaning.\n"
                html = html + "\t<li>The specified backup type was invalid.</li>\n"
	if all_success:
                #Iterate through the database backup folders
                backup_folders = sorted(os.listdir(backup_dir))
                if not backup_folders:
                        details = details + "No database backups were found for cleaning.\n"
                        html = html + "\t<li>No database backups were found for cleaning.</li>\n"
                else:
                        for name in backup_folders:
                                if os.path.isfile(name): pass
                                else:
                                        cleaning_dir = backup_dir + name + suffix
                                        #Make sure folder exists
                                        if backup_type == 'archive' and not os.path.exists(cleaning_dir):
                                                details = details + "Archive directory not found for SQL_Backups/" + name + suffix + ".\n"
                                                html = html + "\t<li>Archive directory not found for SQL_Backups/" + name + suffix + ".</li>\n"
                                                all_success = False
                                        else:
                                                #List out the files so we can find expired ones
                                                backups = sorted(os.listdir(cleaning_dir))
                                                backups = filter(os.path.isfile, [os.path.join(cleaning_dir, backup) for backup in backups])
                                                if not backups:
                                                        details = details + "No backups found for cleaning in SQL_Backups/" + name + suffix + ".\n"
                                                        html = html + "\t<li>No backups found for cleaning in SQL_Backups/" + name + suffix + ".</li>\n"
                                                elif len(backups) <= num_to_maintain:
                                                        details = details + str(num_to_maintain) + " or fewer backups exist in in SQL_Backups/" + name + suffix + ". No cleaning needed.\n"
                                                        html = html + "\t<li>" + str(num_to_maintain) + " or fewer backups exist in in SQL_Backups/" + name + suffix + ". No cleaning needed.</li>\n"
                                                else:
                                                        for backup in backups[0:len(backups)-num_to_maintain]:
                                                                try:
                                                                        os.remove(backup)
                                                                except:
                                                                        all_success = False
                                                                        details = details + "Could not delete " + backup + ".\n"
                                                                        html = html + "\t<li>Could not delete " + backup + ".</li>\n"
                                                                else:
                                                                        details = details + "Deleted backup " + backup + ".\n"
                                                                        html = html + "\t<li>Deleted backup " + backup + ".</li>\n"

        details = details.strip('\n')
        html = html + "</ul>\n"
        return [all_success, details, html]

#Run RSync
def rsync():
        b_user = config.get('RSync','backup_server_username')
        b_port = config.get('RSync','backup_server_ssh_port')
        b_fqdn = config.get('RSync','backup_server_fqdn')
        b_rdir = config.get('RSync','backup_server_remote_directory')
        b_ldir = config.get('RSync','directories_to_backup')

	all_success = True
	details = ""
	html = "<p>\n"

        #Delete Old Log and Run RSync
        cmd = ('rm -f ' + script_dir + '/rsync.log; '
               'rsync '
               '--progress '
               '--relative '
               '--archive '
               '--compress '
               '--human-readable '
               '--stats '
               '--delete '
               '--exclude-from=' + script_dir + '/rsync_exclusions.txt ' + ' '
               '--log-file=' + script_dir + '/rsync.log '
               '-e "ssh -l ' + b_user + ' -p ' + b_port + '" '
               '' + b_ldir + ' ' + b_fqdn + ':' + b_rdir)
        p1 = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Poll process for new output until finished
        save_output = False
        stats = ""
        while True:
                nextline = p1.stdout.readline()
                if nextline == '' and p1.poll() != None:
                        break
                #Once we get to the stats, we want to save those for the email
                if "Number of files: " in nextline or save_output == True:
                        save_output = True
                        stats = stats + nextline
                else:
                        sys.stdout.write(nextline)
                        sys.stdout.flush()
        err = p1.communicate()[1]
        if p1.returncode is not 0:
                details = details + err
                html = html + err.replace('\n','<br />')
                all_success = False
        else:
                details = details + "\n" + stats
                stats_cleaned_up = stats.strip('\n').replace('\n\n','\n').replace('\n', '<br />')
                html = html + stats_cleaned_up
                
        details = details.strip('\n')
        html = html + "</p>\n"
        
        return [all_success, details, html]

#Generate and send the Email
def sendEmail(overview, body, log_file_attachments):

	#encoded inline image
	logo=base64.b64decode(	"""R0lGODlhMgAyAPcAAAAAAP///yCQkCCPjyKRkSSRkSaTkyaSkieUlCeTkyiUlCiTkymVlSmUlCqVlSqUlCuVlSyWliyVlS2Wli6Xly6Wli+XlzCYmC+WljCXlzGYmDKZmTKYmDOZmTSamjWbmzSZmTWamjabmzaamjebmzicnDqdnTqcnDudnTyenjydnT+fn0CgoEKhoUOiokKgoEOhoUSiokWjo0ShoUajo0Wiokaiokejo0mkpEqlpUqkpEulpUympk2mpk6np06mpk+np1Cnp1GoqFKpqVKoqFOpqVSqqlOoqFSpqVarq1WqqlaqqlisrFerq1msrFqtrVutrVyurl2urlytrV6vr1+wsF+vr16urmCwsGCvr2KxsWKwsGOxsWSxsWazs2Wysmaysmi0tGezs2izs2q1tWm0tGu1tW63t222tm62tnC4uG+3t3C3t3G4uHK4uHG3t3S6unO5uXa7u3W6une7u3m8vHy+vn6/v32+vn6+vn+/v4LAwIbDw4vFxYzFxY7Hx43GxpDIyJHIyJDHx5LIyJXKypjMzJfLy5nMzJzOzpvNzZ3OzqDQ0J/Pz6DPz6PR0aLQ0KTR0abT06XS0qbS0qvV1arU1K3W1qzV1a/X167W1rDX17LY2LTa2rfb27ba2rfa2rnc3Ljb27ze3rvd3bzd3cDg4L/f38Hg4MPh4cTi4sXi4sjk5Mfj48bi4srl5cvl5crk5M/o6M7n583m5s/n59Ho6NDn59Pp6dLo6NTp6dbr69js7Nfr69rt7dns7Nzu7tvt7d7v793u7tzt7eDw8N/v797u7uDv7+Lx8eHw8OTy8uLw8OTx8eby8ur19en09Ojz8+z29uv19e329u/39/L5+fH4+PP5+fb7+/X6+vj8/Pf7+/n8/Pz+/vv9/f7///3+/v7+/v///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACH5BAEAAOMALAAAAAAyADIAAAj/ADtsGEiwoMGDCBMqJCiwg8OHECNKnEix4sOBFjNq3OgQI8ePIDtuCElyo8eSKCeeTMlSZMuXAkfCZLnyoYQHOC08BEHhQQUQECE84KDhQQSHPI06FJpBpUyIGp6MCfNlRQWHGXqMAdJUoIcsY0ysGONEQ4cMPsYYkUDhypgYFyTW3CBBVoC7wGroPLAowKMEDjWUiBZAiJYAryB0MMAogLUdZMAFkNNA7tOOEmAF2PMoABwFHQ4gCtAIcAfBzAIEwRJglWIDie4ee3YXTuWIcyW8CkCMthzQokkfGIk6AJAqrV/HvsvctmXcugPYOpVtGAkNwRcRiCu4WQAdUQK0/1IegNY2aMQ834aYW3OfMtS+tbAQHBqtQRA2UKgVwFSsAJuABlsAguRhBinqPcdeXcwFoMhRfDH3CQIdQCCGNndBI8QEizXGyAAH7EaZglBJFUYYTFgwUlZjtEhEXBUuUYggOUAAFFpj+GCBBk68BSN7l9mE0wMSyJQUThMA5VAEBiRwFVI9UQBUBA90hVuQM4VU01INXKAkBw0ooAAEHEAEwgQNpNlAmTtVkKZZFG2pQRdw2NCUBirAQYccVligE1ZTwCGoGyjA2YEFQMARR6FxBrnBBLoE8EZlE/jQYCjXOdSAJw0CcZSmo9xFxwKN4jYBLQGkQWkP3XTjijUOgv/WQQOctHaIISzAaEENsAYwynpXmoqqqh1M0IM300BwRgC/EDVrrdUk84sLfyaQRwDLYIONDBg4JWyqq3ojzQd4BLBLBmXSGoAvo3iSq0AQpBJAKccEoIdpwbJ3KrjFsvpNMOIEAMht6tqCySV6dVBBDtk06BqWc02ASwBsUPpDwAFs84gGcDYASoNHHJUAIAHw4gYf4ajGYb5QQTHGC9ydAMYYYgThgKEXINHiGF6YYFYGTZjhQwEOWFEGDD9ehGUHN/3IwZArQzTBkEMhhWaSFT5gKJBZprRlBxFAsLVDHEAAwZ8PUWD22RFp0ECTinkbkQdNUIECmx2NEAUVNfz/eMEOVFAhxQtRa+CBHITwwcXSNWlAgjIBOCEBRA+EcZco6yUgCXPOJLHyBJowN0vcLAdGQjGRT/5QApfcdQ0M1VISwCV9OGiAwjuE040jjbRBOtdQkWBM6g9lkMIz3VATgB2kdpDAJAEg00sAhtxOwQ3dmJvJFlED/5Djww9RQMdqRN9JAKg44NDzATjDSjXV7ECBwmuEMkwA3PAwf+mnkVDvLalQAocU8IkGaQMHV2FfJYqQiwBYQTETQMMfAoGNAFzhdy4J3jKYIwYGWIAG2YNEH4QRAD8AxgCWaJAqQqCBDUSAF8zRhQjGFhPceKAMgoJDCy5wgRnUQQ0REAARW+AghaZYoAmCmkMZSKCTkdwhEpU4xA32xz+HOEBNcNKAAhqwgTM1AGteTJPWINKABCggAVKSW9dI8rU1aqSNbrQIHONYKjp+ZI52rGIe67jHjIxkIYAMpCAxEhAAOw==
	""")
	
	#Get Current Date & Time
	datetime_string = datetime.datetime.now().strftime('%A, %B %d, %Y | %H:%M%p %Z')
	
	#Create Email Template
	text_content=u'Daily Nodealyzer Report Content'
	with open (script_dir + "/email_template_inlined.html", "r") as template:
		html_content=template.read().replace('\n', '')
	
	#Fill in Template Information
	html_content = html_content.replace('[ENCODED_LOGO]', '<img src="cid:logo"/>')
	html_content = html_content.replace('[DATE_TIME]', datetime_string)
	html_content = html_content.replace('[TITLE]', 'Daily Nodealyzer Report')
	html_content = html_content.replace('[SUBTITLE]', config.get('ServerInfo','friendly_server_name'))
	html_content = html_content.replace('[PANEL]', overview)
	html_content = html_content.replace('[BODY]', body)
	html_content = html_content.replace('[FOOTER]', 'Generated by <a href="https://www.github.com/sciguy14/Nodealyzer" title="Nodealyzer on GitHub">Nodealyzer</a>')

        #Generate Log File attachment list
        attachment_list = []
        for filename in log_file_attachments:
                with open (filename, "r") as attachment_file:
                        attachment_text=attachment_file.read()
                attachment_list.append([attachment_text, 'text', 'plain', filename, 'us-ascii'])
	
	payload, mail_from, rcpt_to, msg_id=pyzmail.compose_mail(\
        (config.get('ServerInfo','friendly_server_name'), config.get('ServerInfo','server_email')), \
        [(config.get('OwnerInfo','owner_name'), config.get('OwnerInfo','owner_email')),], \
        u'Daily Nodealyzer Report', \
        'iso-8859-1', \
        (text_content, 'iso-8859-1'), \
        (html_content, 'iso-8859-1'), \
        embeddeds=[(logo, 'image', 'gif', 'logo', None)], \
        attachments=attachment_list )

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
	
	
#Run the Main function when this python script is executed
if __name__ == '__main__':
	main()
