#!/usr/bin/python

# Nodealyzer Server Assistant by Jeremy Blum
# Copyright 2014 Jeremy Blum, Blum Idea Labs, LLC.
# http://www.jeremyblum.com
# File: Nodealyzer.py
# License: GPL v3 (http://www.gnu.org/licenses/gpl.html)

#Import needed libraries
import ConfigParser, pyzmail, base64 

#Read configuration file
config = ConfigParser.ConfigParser()
config.read("config.ini")

#Main program execution
def main():

	#Perform Preflight Checks
	print "Performing Preflight Checks..."
	#TODO: Confirm valid values in the config file

	#Get some initial info
	print "Gathering Info..."
	
	#Let's Backup some databases!
	print "Backing up MySQL Databases..."
	
	#Send the email report
	print "Sending Email report..."
	sendEmail()

#Generate and send the Email
def sendEmail():

	#encoded inline image
	logo=base64.b64decode(
	"""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
	""")
	
	text_content=u'Daily Nodealyzer Report Content'
	html_content = """
		<img src="cid:logo" />
		<h1>Title</h1>
		<p>Hi!<br>
		How are you?<br>
		Here is a <a href="http://www.google.com">link</a>.</p>
		"""
	
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
			print 'failed recipients:', ', '.join(ret.keys())
		else:
			print 'success'
	else:
		print 'error:', ret
	
	
#Run the Main function when this python script is executed
if __name__ == '__main__':
	main()
