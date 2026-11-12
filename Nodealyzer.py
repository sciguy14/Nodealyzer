#!/usr/bin/python

# Nodealyzer Server Assistant by Jeremy Blum
# Copyright 2014 Jeremy Blum, Blum Idea Labs, LLC.
# http://www.jeremyblum.com
# File: Nodealyzer.py
# License: GPL v3 (http://www.gnu.org/licenses/gpl.html)

#Import needed libraries
import ConfigParser, pyzmail, base64, datetime, time, os, re, pprint, subprocess, gzip, sys, shutil, glob, tempfile, urllib2

#Know Script Directory so we can make absolute references
script_dir = os.path.dirname(os.path.realpath(__file__))

#Read configuration file
config = ConfigParser.ConfigParser()
config.read(script_dir + "/config.ini")

#SSH options for every connection to the Receiver: never prompt (cron has no TTY),
#never trust an unknown host key, and detect a dead link instead of hanging forever.
SSH_OPTS = ('-o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 '
            '-o ServerAliveInterval=30 -o ServerAliveCountMax=4')

#Max rsync error lines included in the emailed report (the rest are counted, not shown).
RSYNC_ERR_MAX_LINES = 40

#Main program execution
def main():

        print "\nNodealyzer is taking care of business! Stand by, this shouldn't take long...\n"

        #Dead-man's switch: tell the monitor a run has started (no-op if not configured).
        pingHealthcheck('/start')

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
        #Amber "succeeded but needed intervention" + red "skipped" statuses for backup-drive auto-recovery
        PASS_STAR_STYLED = "<td align='left'><font color='#cc7a00'><b>Pass&#42;</b></font></td>"
        REPAIR_STYLED    = "<td align='left'><font color='#cc7a00'><b>Repaired</b></font></td>"
        REMOUNT_STYLED   = "<td align='left'><font color='#cc7a00'><b>Remounted</b></font></td>"
        SKIPPED_STYLED   = "<td align='left'><font color='red'><b>Fail (SKIPPED)</b></font></td>"


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

        #Pre-flight hard gate: confirm the backup drive is actually mounted on the
        #Receiver before we rsync. If it's mounted with 'nofail' but absent, the
        #mount point is just an empty directory on the Receiver's root disk, and
        #rsync would silently fill the root filesystem. Never write into that.
        sys.stdout.write("Checking that the backup drive is mounted on the Receiver...")
        [mount_outcome, mount_details, mount_html] = ensureRemoteDriveMounted()
        if mount_outcome == 'ok':
                print "Mounted."
                status_reports = status_reports + "\t<tr align='right'><td>Backup Drive Mounted:</td>" + PASS_STYLED + "</tr>\n"
        elif mount_outcome == 'remounted':
                print "Was unmounted; remounted before backup."
                status_reports = status_reports + "\t<tr align='right'><td>Backup Drive Mounted:</td>" + REMOUNT_STYLED + "</tr>\n"
        else:  #blocked
                print "NOT MOUNTED and could not remount - skipping backup!"
                status_reports = status_reports + "\t<tr align='right'><td>Backup Drive Mounted:</td>" + FAIL_STYLED + "</tr>\n"
        print mount_details
        email_body = email_body + mount_html

        if mount_outcome == 'blocked':
                #Hard stop: do NOT run rsync. Report the skip unmistakably and move on.
                email_body = email_body + ("<p><b>&#9888; BACKUP SKIPPED</b> &mdash; the backup drive was NOT "
                        "mounted on the Receiver and could not be remounted automatically. The sync was "
                        "deliberately skipped to avoid writing into the unmounted mount point on the Receiver's "
                        "root filesystem (which would silently fill it). <b>No files were backed up this run.</b> "
                        "Mount the drive (and, if this was a permissions failure, follow the README instructions "
                        "for enabling passwordless sudo for disk recovery on the Receiver), then re-run.</p>\n")
                status_reports = status_reports + "\t<tr align='right'><td>Remote Data Backup:</td>" + SKIPPED_STYLED + "</tr>\n"
                all_good = False
        else:
                #Pre-flight filesystem health check: if the Receiver's kernel has already
                #flagged the backup filesystem as having errors, repair it BEFORE syncing.
                #A corrupted drive makes rsync emit huge volumes of errors and leaves
                #directories un-backed-up, so fix first rather than after the fact.
                sys.stdout.write("Checking the backup drive's filesystem health on the Receiver...")
                [repair_outcome, preflight_details, repair_html] = preflightRemoteDriveHealth()
                print repair_outcome
                print preflight_details
                if repair_outcome == 'healthy':
                        repair_outcome = 'not_needed'
                        repair_html = ""

                #A repair attempt that went wrong part-way could leave the drive unmounted.
                #Re-run the mount gate so we never rsync into the bare mount point.
                skip_sync = False
                if repair_outcome not in ('not_needed', 'not_applicable', 'repaired'):
                        [mount_outcome, mount_details, mount_html] = ensureRemoteDriveMounted()
                        print mount_details
                        if mount_outcome == 'blocked':
                                skip_sync = True

                #Let's Syncronize!
                if skip_sync:
                        print "Backup drive not mounted after a failed repair - skipping the sync!"
                        success = False
                        details = mount_details
                        html = "<p><b>&#9888; BACKUP SKIPPED</b> &mdash; the drive repair failed and the drive is not mounted. " + mount_html
                else:
                        sys.stdout.write("Performing Remote Sync...")
                        [success, details, html] = rsync()

                #If rsync failed, see whether it's a filesystem error we can safely auto-repair.
                #(Fallback for corruption the kernel hadn't flagged yet. Skipped if the
                #pre-flight already attempted a repair this run.)
                if not success and repair_outcome in ('not_needed', 'not_applicable'):
                        sys.stdout.write("rsync reported errors; checking for an auto-repairable drive fault...")
                        [repair_outcome, repair_details, repair_html] = repairRemoteBackupDrive(details)
                        print repair_outcome
                        print repair_details
                        if repair_outcome == 'repaired':
                                #Drive is repaired; re-run the sync once.
                                sys.stdout.write("Drive auto-repaired; retrying Remote Sync...")
                                [success, details, html] = rsync()

                if success:
                        print "Success!"
                        if repair_outcome == 'repaired':
                                email_body = email_body + "<p>Files were backed up to " + config.get('RSync','backup_server_fqdn') + " (after an automatic drive repair). "
                                status_reports = status_reports + "\t<tr align='right'><td>Remote Data Backup:</td>" + PASS_STAR_STYLED + "</tr>\n"
                        else:
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

                #Report on any backup-drive auto-repair that took place.
                if repair_outcome in ('not_needed', 'not_applicable'):
                        status_reports = status_reports + "\t<tr align='right'><td>Backup Drive Repair:</td>" + NA_STYLED + "</tr>\n"
                elif repair_outcome == 'repaired':
                        status_reports = status_reports + "\t<tr align='right'><td>Backup Drive Repair:</td>" + REPAIR_STYLED + "</tr>\n"
                else:  #permission_denied / skipped_unsafe / failed (rsync already marked Fail above)
                        status_reports = status_reports + "\t<tr align='right'><td>Backup Drive Repair:</td>" + FAIL_STYLED + "</tr>\n"
                if repair_html:
                        email_body = email_body + "<h3 style='margin:5px;'>Backup Drive Repair</h3>\n" + repair_html
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
	email_result = sendEmail(status_reports, email_body, log_file_attachments)
	print email_result

        #Dead-man's switch: report success only if the backup was clean AND the email
        #went out. Anything else pings /fail so the monitor alerts immediately.
        if all_good and email_result == 'Success!':
                pingHealthcheck('')
        else:
                pingHealthcheck('/fail', "all_good=" + str(all_good) + " email=" + str(email_result))

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
               '--timeout=600 '
               '-e "ssh -l ' + b_user + ' -p ' + b_port + ' ' + SSH_OPTS + '" '
               '' + b_ldir + ' ' + b_fqdn + ':' + b_rdir)
        #stderr goes to a temp FILE, not a pipe. With a pipe, rsync blocks forever once
        #it writes >64KB of errors (e.g. thousands of "Bad message (74)" lines from a
        #corrupted Receiver drive) because we only drain stdout below.
        err_file = tempfile.TemporaryFile()
        p1 = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=err_file)
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
        p1.wait()
        err_file.seek(0)
        err = err_file.read()
        err_file.close()
        if p1.returncode != 0:
                #Keep the report readable: a corrupted drive can produce thousands of lines.
                err_lines = err.strip('\n').split('\n')
                if len(err_lines) > RSYNC_ERR_MAX_LINES:
                        omitted = len(err_lines) - RSYNC_ERR_MAX_LINES
                        err = '\n'.join(err_lines[:RSYNC_ERR_MAX_LINES] + err_lines[-1:]) + \
                              "\n[... " + str(omitted - 1) + " more error lines omitted ...]\n"
                details = details + "rsync exited with code " + str(p1.returncode) + ":\n" + err
                html = html + ("rsync exited with code " + str(p1.returncode) + ":<br />" + err).replace('\n','<br />')
                all_success = False
        else:
                details = details + "\n" + stats
                stats_cleaned_up = stats.strip('\n').replace('\n\n','\n').replace('\n', '<br />')
                html = html + stats_cleaned_up
                
        details = details.strip('\n')
        html = html + "</p>\n"
        
        return [all_success, details, html]

#Run a command on the Receiver over the existing key-based SSH connection.
#Returns (returncode, stdout, stderr). Privileged commands should be passed with
#a leading 'sudo -n ' so a missing NOPASSWD rule fails fast (non-interactively)
#instead of hanging a cron job waiting for a password.
def _remote_ssh(command):
	b_user = config.get('RSync','backup_server_username')
	b_port = config.get('RSync','backup_server_ssh_port')
	b_fqdn = config.get('RSync','backup_server_fqdn')
	cmd = ['ssh', '-l', b_user, '-p', str(b_port)] + SSH_OPTS.split() + [b_fqdn, command]
	p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	out, err = p.communicate()
	return (p.returncode, out, err)

#Whether the filesystem auto-recovery feature is enabled (defaults ON if the
#config key is absent, so existing config.ini files keep working unchanged).
def _autofix_enabled():
	if config.has_option('RSync', 'autofix_filesystem'):
		return config.get('RSync', 'autofix_filesystem').strip().lower() in ('1', 'true', 'yes', 'on')
	return True

#Did a remote 'sudo -n' command fail specifically because of missing privileges?
def _is_sudo_permission_error(returncode, err):
	if returncode == 0:
		return False
	low = err.lower()
	return ('a password is required' in low or
	        'a terminal is required' in low or
	        'no tty present' in low or
	        'not allowed to execute' in low or
	        'is not in the sudoers' in low)

#Resolve the backup drive's fstab mount point and backing device from the
#configured rsync remote directory. Uses /etc/fstab as the source of truth, so
#it works even while the drive is unmounted and never hardcodes /dev/sdX. Returns
#(mountpoint, device), or (None, None) if the path is not an fstab-managed mount.
def _resolve_backup_drive():
	remote_dir = config.get('RSync','backup_server_remote_directory')
	rc_m, mp_out, _  = _remote_ssh("findmnt --fstab -n -o TARGET --target " + remote_dir)
	rc_d, dev_out, _ = _remote_ssh("findmnt --fstab -n -o SOURCE --target " + remote_dir)
	mountpoint = mp_out.strip()
	device = dev_out.strip()
	if rc_m != 0 or rc_d != 0 or not mountpoint or not device.startswith('/dev/'):
		return (None, None)
	return (mountpoint, device)

#Build the standard "we lack permission" result used whenever a recovery step
#fails because passwordless sudo isn't configured on the Receiver.
def _repair_permission_denied(details, html):
	msg = ("We tried to auto-recover the remote backup drive, but don't have permission to do so. "
	       "Follow the README instructions for enabling passwordless sudo for disk-recovery commands "
	       "on the receiving machine.")
	details = details + msg + "\n"
	html = html + "<b>" + msg + "</b></p>\n"
	return ['permission_denied', details.strip('\n'), html]

#Pre-flight hard gate, run before rsync. Confirms the backup drive is mounted on
#the Receiver; if not, tries to remount it. Returns [outcome, details, html] where
#outcome is 'ok', 'remounted', or 'blocked'. On 'blocked' the caller MUST skip
#rsync so we never write into an unmounted mount point on the Receiver's root fs.
def ensureRemoteDriveMounted():
	details = ""
	html = "<p>\n"

	mountpoint, device = _resolve_backup_drive()
	if mountpoint is None:
		#Fall back to the configured remote directory just for the mount check.
		mountpoint = config.get('RSync','backup_server_remote_directory')

	#Is it currently mounted?
	rc, out, err = _remote_ssh("mountpoint -q " + mountpoint + " && echo MOUNTED || echo UNMOUNTED")
	if 'MOUNTED' in out:
		details = "Backup drive is mounted at " + mountpoint + "."
		html = html + "Backup drive is mounted at " + mountpoint + ".</p>\n"
		return ['ok', details, html]

	#Not mounted - attempt a remount (relies on the Receiver's /etc/fstab entry).
	details = details + "Backup drive is NOT mounted at " + mountpoint + ". Attempting to remount...\n"
	rc, out, err = _remote_ssh("sudo -n mount " + mountpoint)
	rc2, out2, err2 = _remote_ssh("mountpoint -q " + mountpoint + " && echo MOUNTED || echo UNMOUNTED")
	if 'MOUNTED' in out2:
		details = details + "Successfully remounted the backup drive at " + mountpoint + "."
		html = html + ("Backup drive was not mounted; it was successfully remounted at "
		        + mountpoint + " before the backup ran.</p>\n")
		return ['remounted', details, html]

	#Could not remount -> blocked. Surface why, prominently.
	if _is_sudo_permission_error(rc, err):
		why = ("We tried to remount the backup drive on the Receiver, but don't have permission to do so. "
		       "Follow the README instructions for enabling passwordless sudo for disk-recovery commands "
		       "on the receiving machine.")
	else:
		why = "The mount command failed: " + (err.strip() or out.strip() or "unknown error") + "."
	details = details + why
	html = html + ("<b>&#9888; BACKUP SKIPPED</b> &mdash; the backup drive was NOT mounted on the Receiver "
	        "and could not be remounted automatically. The sync was deliberately skipped to avoid writing "
	        "into the unmounted mount point on the Receiver's root filesystem (which would silently fill "
	        "it). No files were backed up this run. " + why + "</p>\n")
	return ['blocked', details, html]

#Atomic, conservative backup-drive recovery, called only when rsync has failed.
#Detects the specific, safely-repairable filesystem faults we saw in the wild
#(ext4 directory checksum corruption -> rsync "Bad message (74)", and read-only
#remounts), and repairs them via: umount -> e2fsck -D -f -y -> mount, all over
#SSH as 'sudo -n'. Refuses to act on suspected hardware failure or a full disk,
#and only ever touches a mount point that /etc/fstab explicitly declares.
#Returns [outcome, details, html] where outcome is one of:
#  not_applicable | repaired | permission_denied | skipped_unsafe | failed
def repairRemoteBackupDrive(failure_text):
	details = ""
	html = "<p>\n"

	if not _autofix_enabled():
		msg = "Filesystem auto-repair is disabled in the config (autofix_filesystem)."
		return ['not_applicable', msg, html + msg + "</p>\n"]

	#Guardrail: never auto-fix suspected failing hardware or a full disk.
	if 'Input/output error' in failure_text or 'No space left on device' in failure_text:
		msg = ("Detected a possible hardware failure (I/O error) or a full disk on the backup drive. "
		       "Refusing to auto-repair, because running e2fsck on failing hardware, or deleting files "
		       "to free a full disk, could be destructive. Manual attention required.")
		return ['skipped_unsafe', msg, html + msg + "</p>\n"]

	#Only act on the known, safely-repairable signatures.
	if not ('Bad message (74)' in failure_text or 'Read-only file system' in failure_text):
		msg = "The rsync failure did not match a repairable filesystem signature; taking no action."
		return ['not_applicable', msg, html + msg + "</p>\n"]

	#Resolve the device strictly from /etc/fstab, so we only ever touch a declared mount point.
	mountpoint, device = _resolve_backup_drive()
	if mountpoint is None or device is None:
		msg = ("Could not resolve an /etc/fstab-managed device for the configured backup directory; "
		       "refusing to run a filesystem repair on an undeclared mount point.")
		return ['not_applicable', msg, html + msg + "</p>\n"]

	details = details + "Detected a repairable filesystem error on " + device + " (mounted at " + mountpoint + ").\n"
	return _runRemoteDriveRepair(mountpoint, device, details, html)

#Did the Receiver's kernel log I/O errors for this device since boot? That points
#at failing hardware (or a flaky USB link), where e2fsck could make things worse.
def _remote_device_has_io_errors(device):
	disk = os.path.basename(device).rstrip('0123456789')  #/dev/sda1 -> sda
	rc, out, err = _remote_ssh("sudo -n dmesg | grep -E 'I/O error.*dev " + disk + "' | tail -3")
	return out.strip()

#Pre-flight health check, run before rsync. Reads the ext4 superblock on the
#Receiver (read-only, safe while mounted). If the kernel has flagged the
#filesystem with errors, runs the same umount -> e2fsck -> mount repair used for
#rsync failures. Returns [outcome, details, html] where outcome is one of:
#  healthy | not_applicable | repaired | permission_denied | skipped_unsafe | failed
def preflightRemoteDriveHealth():
	details = ""
	html = "<p>\n"

	if not _autofix_enabled():
		return ['not_applicable', "Filesystem auto-repair is disabled in the config (autofix_filesystem).", ""]

	mountpoint, device = _resolve_backup_drive()
	if mountpoint is None or device is None:
		msg = ("Could not resolve an /etc/fstab-managed device for the configured backup directory; "
		       "skipping the filesystem health check.")
		return ['not_applicable', msg, html + msg + "</p>\n"]

	rc, out, err = _remote_ssh("sudo -n dumpe2fs -h " + device + " 2>/dev/null")
	if _is_sudo_permission_error(rc, err):
		return _repair_permission_denied("Could not read the filesystem state on " + device + ".\n", html)
	state = ""
	error_count = 0
	for line in out.split('\n'):
		if line.startswith('Filesystem state:'):
			state = line.split(':', 1)[1].strip()
		elif line.startswith('FS Error count:'):
			try:
				error_count = int(line.split(':', 1)[1].strip())
			except ValueError:
				pass
	if not state:
		msg = "Could not read the filesystem state on " + device + " (dumpe2fs exit " + str(rc) + "); skipping the health check."
		return ['not_applicable', msg, html + msg + "</p>\n"]

	if 'error' not in state:
		return ['healthy', "Filesystem on " + device + " is healthy (state: " + state + ").", ""]

	details = (details + "Filesystem on " + device + " (" + mountpoint + ") is flagged with errors before the sync "
	           + "(state: " + state + ", " + str(error_count) + " errors logged).\n")

	#Guardrail: never auto-fix suspected failing hardware.
	io_errors = _remote_device_has_io_errors(device)
	if io_errors:
		msg = ("The Receiver's kernel logged I/O errors for this disk since boot, which suggests failing "
		       "hardware or a bad USB link. Refusing to auto-repair, because running e2fsck on failing "
		       "hardware could be destructive. Manual attention required.\n" + io_errors)
		details = details + msg
		return ['skipped_unsafe', details.strip('\n'), html + details.replace('\n', '<br />') + "</p>\n"]

	return _runRemoteDriveRepair(mountpoint, device, details, html)

#The repair itself: umount -> e2fsck -D -f -y -> mount, then verify read-write.
#Shared by the pre-flight check and the post-rsync-failure fallback.
def _runRemoteDriveRepair(mountpoint, device, details, html):
	#Step 1: unmount.
	rc, out, err = _remote_ssh("sudo -n umount " + mountpoint)
	if _is_sudo_permission_error(rc, err):
		return _repair_permission_denied(details, html)
	if rc != 0:
		details = details + "umount failed (exit " + str(rc) + "): " + (err.strip() or out.strip()) + "\n"
		return ['failed', details.strip('\n'), html + details.replace('\n', '<br />') + "</p>\n"]

	#Step 2: filesystem check + repair (also rebuilds oversized dir indexes via -D).
	rc, out, err = _remote_ssh("sudo -n e2fsck -D -f -y " + device)
	fsck_output = (out + "\n" + err).strip()
	if _is_sudo_permission_error(rc, err):
		return _repair_permission_denied(details, html)
	#e2fsck exit: 0 = clean, 1/2 = errors corrected (success); >= 4 = uncorrected/failure.
	if rc >= 4:
		details = details + "e2fsck failed (exit " + str(rc) + "):\n" + fsck_output + "\n"
		_remote_ssh("sudo -n mount " + mountpoint)  #best-effort: don't leave the drive unmounted
		return ['failed', details.strip('\n'), html + details.replace('\n', '<br />') + "</p>\n"]

	#Step 3: remount.
	rc, out, err = _remote_ssh("sudo -n mount " + mountpoint)
	if _is_sudo_permission_error(rc, err):
		return _repair_permission_denied(details, html)
	if rc != 0:
		details = details + "Remount failed after e2fsck (exit " + str(rc) + "): " + (err.strip() or out.strip()) + "\n"
		return ['failed', details.strip('\n'), html + details.replace('\n', '<br />') + "</p>\n"]

	#Verify it came back mounted read-write.
	rc, mout, _  = _remote_ssh("mountpoint -q " + mountpoint + " && echo MOUNTED || echo UNMOUNTED")
	rc2, opts, _ = _remote_ssh("findmnt -n -o OPTIONS --target " + mountpoint)
	if 'MOUNTED' not in mout:
		details = details + "Repair completed but the drive is not mounted afterwards.\n"
		return ['failed', details.strip('\n'), html + details.replace('\n', '<br />') + "</p>\n"]
	if 'ro' in opts.strip().split(','):
		details = details + "Repair completed but the drive remounted read-only.\n"
		return ['failed', details.strip('\n'), html + details.replace('\n', '<br />') + "</p>\n"]

	details = (details + "Ran umount -> e2fsck -D -f -y -> mount. Drive remounted read-write.\n"
	           + "e2fsck output:\n" + fsck_output + "\n")
	html = (html + "Auto-repair succeeded: ran <code>umount</code> &rarr; <code>e2fsck -D -f -y</code> &rarr; "
	        "<code>mount</code> on " + device + " (" + mountpoint + "). Drive remounted read-write.</p>\n")
	return ['repaired', details.strip('\n'), html]

#Generate and send the Email
def sendEmail(overview, body, log_file_attachments):

	#encoded inline image
	logo=base64.b64decode(	"""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
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
	
	
#Dead-man's switch ping (healthchecks.io-style). suffix is '' for success,
#'/start' at the beginning of a run, or '/fail' for a failed run. If no success
#ping arrives on schedule, the monitoring service alerts the owner, which catches
#hangs, crashes, broken email and a dead server alike. Optional: does nothing
#unless [Monitoring] healthcheck_url is set. Never raises.
def pingHealthcheck(suffix, message=''):
	if not config.has_option('Monitoring', 'healthcheck_url'):
		return
	url = config.get('Monitoring', 'healthcheck_url').strip().rstrip('/')
	if not url:
		return
	try:
		urllib2.urlopen(url + suffix, data=(message[:10000] if message else None), timeout=15).read()
	except Exception as e:
		print "Healthcheck ping" + (suffix or '') + " failed: " + str(e)

#Run the Main function when this python script is executed
if __name__ == '__main__':
	try:
		main()
	except Exception:
		import traceback
		tb = traceback.format_exc()
		print tb
		pingHealthcheck('/fail', tb)
		raise
