import sys
import imaplib
import getpass
import email
import email.header
import datetime
import sqlite3
import re
import smtplib
import os
import time
import hashlib
import subprocess
import zipfile
import tarfile
import errno
import logging
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from smtplib import SMTP
from subprocess import call
import threading
import Queue

log = logging.getLogger('email-automation')
monitor = logging.getLogger('user-monitoring')


# Local database location
sqlite_file = '/home/mal/cuckoo-modified-master/db/cuckoo.db'



def get_content(M):
# This definition gets the md5 hash value that is within the most recent email received
# If no md5 hash value is in the email it will go on to look for attachments
	global md5
	global sha1
	global sha256
	global sha512
	global url
	global sender
	global number
	global att_path
	global sampleName
	global sqlite_file
	
	log.info("Checking that there are some messages present")
	rv, data = M.search(None, "ALL")
	if rv != "OK":
		log.debug("No messages found")
		return
	
	log.info("Fetch the most recent email in the folder")
	rv, data = M.fetch(number, '(RFC822)')
	if rv != 'OK':
		log.debug("Error getting message: %s", number)
		return

	log.info("Decoding the email from the faw format to a string")
	msg = data[0][1]
	raw_email_string = msg.decode('utf-8')
	email_message = email.message_from_string(raw_email_string)

	log.info("Parsing header to get the sender email address")
	received = email_message['From']
	sender = re.findall('.*?\<(.*?)\>.*?', received)
	sender = sender[0]
	monitor.info("Email received from: %s", sender)

	i = datetime.datetime.now() 
	monitor.info("Current date & time = %s" % i)

	for part in email_message.walk():
		if part.get('Content-Disposition') is not None:
			if 'attachment;' in part.get('Content-Disposition'):

				log.info("Selecting the attachment & ignoring inline attachments")

				download_dir = '/home/mal/email-submissions'
				sampleName = part.get_filename()
				att_path = os.path.join(download_dir, sampleName)
				
				monitor.info("Attachment name: %s", sampleName)
				log.debug("Opening %s and writing the attachment to disk", att_path)

				fp = open(att_path, 'wb')
				fp.write(part.get_payload(decode=True))
				fp.close()
				
				if att_path.endswith((".zip")):
					log.info("If attachment is in a compressed zip file extract and pass the extracted file name into att_path")
					zip_ref = zipfile.ZipFile(att_path, 'r')
					password = "infected"
					sampleName = zip_ref.namelist()
					sampleName = sampleName[0]
					monitor.info("Extracted sample name: %s", sampleName)
					try:
						zip_ref.extract(member=sampleName,path=download_dir,pwd="password")
					except RuntimeError:
						log.debug("Extracting of .zip file has failed")
						extraction_failure()
						return
					zip_ref.close()
					att_path = os.path.join(download_dir, sampleName)

				elif att_path.endswith(("tar.gz")) or att_path.endswith(("tar")):
					log.info("If attachment is in a compressed tar file extract and pass the extracted file name into att_path")
					tar = tarfile.open(att_path, 'r:')
					sampleName = tar.getnames()
					monitor.info("Extracted sample name: %s", sampleName[0])
					try:
						tar.extractall(download_dir)
					except RuntimeError:
						log.debug("Extracting of .zip file has failed")
						extraction_failure()
						return
					tar.close()	
					att_path = os.path.join(download_dir, sampleName[0])

				cuckoo_submission()
				return

		# Select the main body of the email
		if part.get_content_type() == "text/plain":

			log.info("Select and decode the body so it is readable")
			body = part.get_payload(decode=True)

			# Regular Expression to select the 32 character long hexadecimal string (MD5 Hash)
			md5 = re.search(r'\b[0-9a-fA-F]{32}\b', body)
			# Regular Expression to select the 40 character long hexadecimal string (sha-1 Hash)
			sha1 = re.search(r'\b[0-9a-fA-F]{40}\b', body)
			# Regular Expression to select the 64 character long hexadecimal string (sha-256 Hash)
			sha256 = re.search(r'\b[0-9a-fA-F]{64}\b', body)
			# Regular Expression to select the 128 character long hexadecimal string (sha-512 Hash)
			sha512 = re.search(r'\b[0-9a-fA-F]{128}\b', body)
			# A regular expression to get any URL help within the body of the email
			url = re.search('(?<!<)http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', body)
			
			if md5 is not None:
				log.info("MD5 hash contained within the email")
				md5 = md5.group(0)
				monitor.info("MD5 submitted: %s", md5)
				get_hash_report()
				return
			
			elif sha1 is not None:
				log.info("SHA-1 hash contained within the email")
				sha1 = sha1.group(0)
				monitor.info("SHA-1 submitted: %s", sha1)
				get_hash_report()
				return

			elif sha256 is not None:
				log.info("SHA-256 hash contained within the email")
				sha256 = sha256.group(0)
				monitor.info("SHA-256 submitted: %s", sha256)
				get_hash_report()
				return

			elif sha512 is not None:
				log.info("SHA-512 hash contained within the email")
				sha512 = sha512.group(0)
				monitor.info("SHA-512 submitted: %s", sha512)
				get_hash_report()
				return

			elif url is not None:
				log.info("URL contained within the email")
				url = url.group(0)
				monitor.info("URL submitted: %s", url)
				url_submission()
				return
	else:
		log.info("No hash, URL or attachment contained within the email")
		send_no_content()


def get_hash_report():
	
	global md5
	global sha1
	global sha256
	global sha512
	global reportLocation
	global sqlite_file

	log.debug("Connecting to the SQLite database")
	conn = sqlite3.connect(sqlite_file)
	# Cursor is how we navigate the database
	c = conn.cursor()

	log.debug("Selecting columns from the samples table")
	if md5 is not None:
		c.execute("SELECT id, md5 FROM samples WHERE md5 = '%s'" % md5)
	elif sha1 is not None:
		# Select id and md5 columns from the samples table where the md5 is the same as the md5 from the email
		c.execute("SELECT id, sha1 FROM samples WHERE sha1 = '%s'" % sha1)
	elif sha256 is not None:
		# Select id and md5 columns from the samples table where the md5 is the same as the md5 from the email
		c.execute("SELECT id, sha256 FROM samples WHERE sha256 = '%s'" % sha256)
	elif sha512 is not None:
		# Select id and md5 columns from the samples table where the md5 is the same as the md5 from the email
		c.execute("SELECT id, sha512 FROM samples WHERE sha512 = '%s'" % sha512)

	# Fetch one result as in this table a hash value has a one to one relationship with the id field
	data = c.fetchone()
	if data == None:
		# Print, this needs to be developed to send an email back 
		log.info("No report regarding the hash value submitted.")
		send_no_hash()
	else:
		log.info("Found hash: %s" % data[1])
		# Take the id out of an array 
		sampleID = data[0]
		log.info("Select id and sample_id from tasks table where sample_id is the same as the id retrieved from the previous table")
		c.execute("SELECT id, sample_id FROM tasks WHERE sample_id = '%s'" %sampleID)

		# Fetches one results, this fetches the earliest report ID of the sample
		# SampleID has a one to many relationship with reportID
		# However we are just selecting the first report of the sample
		reportID = c.fetchone()
		reportID = reportID[0]

		reportLocation = '/home/mal/cuckoo-modified-master/storage/analyses/' + str(reportID) + '/reports/summary-reportCompact2.html'
		send_hash_report()


def send_no_content():
# A definition to send an email reply if the email recieved does not contain a MD5 hash, a URL or an attachment
	global sender

	time.sleep(5)
	# Set the recipient and parse the list in case of multiple recipients
	# This must be parsed even if there is only ever one recipient
	recipients = [sender] 
	emaillist = [elem.strip().split(',') for elem in recipients]
	# Create the container for the email and fill some fields
	msg = MIMEMultipart()
	msg['Subject'] = 'Malware Labs: Failure to anaylse'
	msg['From'] = 'example@gmail.com'
	
	# Defines some formatting for MIME-aware mail reader 
	msg.preamble = 'You will not see this in a MIME-aware mail reader.\n'
	
	# Define the body of the email
	part = MIMEText("Hi, \n\n Please disregard the submission confirmation email as unfortunately your submission could not be analysed.\n Please ensure that the email you send contains one of the following: MD5 Hash, URL or Attachment\n\nThanks, \nMalware Labs.\n\n\nPlease do not reply to this e-mail.")
	msg.attach(part)
	 
	# Send the email via gmails SMTP server
	server = smtplib.SMTP("smtp.gmail.com:587")
	server.ehlo()
	server.starttls()
	server.login("example@gmail.com", "password")
	server.sendmail(msg['From'], emaillist , msg.as_string())
	print "Email sent."
	return


def send_no_hash():
# This will send an email to the initial sender containing the report identified in the sqlite database
# IMAP does not allow for sending mail so we use SMTP
	global sender

	print "Sending an email to: %s...\n" % sender
	# Set the recipient and parse the list in case of multiple recipients
	# This must be parsed even if there is only ever one recipient
	recipients = [sender] 
	emaillist = [elem.strip().split(',') for elem in recipients]
	# Create the container for the email and fill some fields
	msg = MIMEMultipart()
	msg['Subject'] = 'Malware Labs'
	msg['From'] = 'example@gmail.com'
	
	# Defines some formatting for MIME-aware mail reader 
	msg.preamble = 'You will not see this in a MIME-aware mail reader.\n'
	
	# Define the body of the email
	part = MIMEText("Hi, \n\nUnfortunately we do not currently have a report regarding the hash you have submitted.\nFeel free to follow up with an email containing a sample you would like analysed.\n\nThanks, \nMalware Labs.\n\n\nPlease do not reply to this e-mail.")
	msg.attach(part)
	 
	# Send the email via gmails SMTP server
	server = smtplib.SMTP("smtp.gmail.com:587")
	server.ehlo()
	server.starttls()
	server.login("example@gmail.com", "password")
	server.sendmail(msg['From'], emaillist , msg.as_string())
	print "Email sent."
	return


def send_hash_report():
# This will send an email to the initial sender containing the report identified in the sqlite database
# IMAP does not allow for sending mail so we use SMTP
	global sender
	global reportLocation
	global md5

	print "Sending an email to: %s...\n" % sender
	# Set the recipient and parse the list in case of multiple recipients
	# This must be parsed even if there is only ever one recipient
	recipients = [sender] 
	emaillist = [elem.strip().split(',') for elem in recipients]
	# Create the container for the email and fill some fields
	msg = MIMEMultipart()
	msg['Subject'] = 'Malware Labs: Hash Report'
	msg['From'] = 'example@gmail.com'
	
	# Defines some formatting for MIME-aware mail reader 
	msg.preamble = 'You will not see this in a MIME-aware mail reader.\n'
	
	# Define the body of the email
	part = MIMEText("Hi, \n\nPlease find the attached file that contains a basic report regarding your inquiry. \n\nThanks, \nMalware Labs.\n\n\nPlease do not reply to this e-mail.")
	msg.attach(part)
	 
	# Attach the report to the email
	# put in error handling
	try:
		part = MIMEApplication(open(reportLocation,"rb").read())
	except IOError:
		send_no_hash()
		return

	part.add_header('Content-Disposition', 'attachment', filename=reportLocation)
	msg.attach(part)
	 
	# Send the email via gmails SMTP server
	server = smtplib.SMTP("smtp.gmail.com:587")
	server.ehlo()
	server.starttls()
	server.login("example@gmail.com", "password")
	server.sendmail(msg['From'], emaillist , msg.as_string())

	print "Email sent."

	return

def send_new_report():
# This will send an email to the initial sender containing a report regarding the file they emailed to us
	global waiting
	global sender
	global newReportLocation

	print "\nSending an email to: %s...\n" % sender
	# Set the recipient and parse the list in case of multiple recipients
	# This must be parsed even if there is only ever one recipient
	recipients = [sender] 
	emaillist = [elem.strip().split(',') for elem in recipients]
	# Create the container for the email and fill some fields
	msg = MIMEMultipart()
	msg['Subject'] = 'Malware Labs: Submission Report'
	msg['From'] = 'example@gmail.com'
	 
	# Define some formatting for MIME-aware mail reader 
	msg.preamble = 'You will not see this in a MIME-aware mail reader.\n'
	
	# Define the body of the email
	part = MIMEText("Hi, \n\nPlease find the attached file that contains a basic report regarding your inquiry.\n\nThanks, \nMalware Labs.\n\n\nPlease do not reply to this e-mail.")
	msg.attach(part)
	 
	# Attach the new report to the email
	part = MIMEApplication(open(newReportLocation,"rb").read())
	part.add_header('Content-Disposition', 'attachment', filename=newReportLocation)
	msg.attach(part)
	 
	# Send the email via gmails SMTP server
	server = smtplib.SMTP("smtp.gmail.com:587")
	server.ehlo()
	server.starttls()
	server.login("example@gmail.com", "password")
	server.sendmail(msg['From'], emaillist , msg.as_string())

	print "Email sent."

	return

def cuckoo_submission():
# This submits the file to cuckoo through the command line interface

	global att_path
	global sender
	global newReportLocation
	global tasksNum

	print "Submitting file to cuckoo...\n"

	# Submit the file downloaded from the email to cuckoo through the command line
	call(["/Volumes/Storage/cuckoo-modified-master/utils/submit.py", "%s" % att_path])

	get_task_number()

	# Create the path of the new report location
	newReportLocation = '/home/mal/cuckoo-modified-master/storage/analyses/' + str(tasksNum) + '/reports/summary-reportCompact2.html'

	# Check if the report exists and waits until it does exist
	while not os.path.exists(newReportLocation):
		time.sleep(0.1)

	# A secondary check to make sure the report exists
	if os.path.isfile(newReportLocation):
		send_new_report()
	else:
		raise ValueError("%s is not a file." % newReportLocation)

	return

def url_submission():
# This submits a URL to cuckoo through the command line interface
	global url
	global newReportLocation
	global sqlite_file

	print "Submitting URL to cuckoo... \n"

	# Submit the URL from the email to cuckoo through the command line
	call("/home/mal/cuckoo-modified-master/utils/submit.py --url %s" % url, shell=True)

	time.sleep(3)

	conn = sqlite3.connect(sqlite_file)
	c = conn.cursor()
	c.execute("SELECT id, target FROM tasks WHERE target = '%s'" % url)
	
	data = c.fetchall()
	if data == None:
		print "Critical Error: the samples is not in our database and has not been submitted"
		return
	
	urlID = data[-1]
	urlID = urlID[0]
	
	print "The URL has the folllowing report & ID number: %s" % urlID
	
	newReportLocation = '/home/mal/cuckoo-modified-master/storage/analyses/' + str(urlID) + '/reports/summary-reportCompact2.html'

	# Check if the report exists and waits until it does exist
	while not os.path.exists(newReportLocation):
		time.sleep(0.1)

	# A secondary check to make sure the report exists
	if os.path.isfile(newReportLocation):
		print "The report exists, prepareing to email the report..."
		send_new_report()
	else:
		raise ValueError("%s is not a file." % newReportLocation)

	return


def get_task_number():
	global sqlite_file
	global tasksNum
	global att_path

	# Hash the file that has been submitted
	hasher = hashlib.md5()
	with open(att_path, 'rb') as afile:
		buf = afile.read()
		hasher.update(buf)
	attachment_hash = hasher.hexdigest()

	time.sleep(3)

	# Connect to the database
	conn = sqlite3.connect(sqlite_file)
	
	# Cursor is how you navigate the database
	c = conn.cursor()
	
	# Find the id for the hash
	c.execute("SELECT id FROM samples WHERE md5 = '%s'" % attachment_hash)
	
	# Fetch one result as in this table a hash value has a one to one relationship
	data = c.fetchone()
	if data == None:
		print "Critical Error: the samples is not in our database and has not been submitted"
		return

	# Take the id out of an array 
	sampleID = data[0]
	print "This sample is ID number:%s\n" % sampleID
	# Select id and sample_id from tasks table where sample_id is the same as the id retrieved earlier
	c.execute("SELECT id, sample_id FROM tasks WHERE sample_id = '%s'" %sampleID)
	# Fetch one results, this fetches the earliest report ID of the sample
	# SampleID has a one to many relationship with reportID
	# However we are just selecting the first occurence of a report regarding the sample
	reportID = c.fetchall()
	tasksNum = reportID[-1]
	tasksNum = tasksNum[0]
	print "The report number for this sample is: %s\n" % tasksNum
	return

def extraction_failure():
# This will send an email to the initial sender containing the report identified in the sqlite database
# IMAP does not allow for sending mail so we use SMTP
	global sender

	print "Sending an email to: %s...\n" % sender
	# Set the recipient and parse the list in case of multiple recipients
	# This must be parsed even if there is only ever one recipient
	recipients = [sender] 
	emaillist = [elem.strip().split(',') for elem in recipients]
	# Create the container for the email and fill some fields
	msg = MIMEMultipart()
	msg['Subject'] = 'Malware Labs: Analysis Failure'
	msg['From'] = 'example@gmail.com'
	
	# Defines some formatting for MIME-aware mail reader 
	msg.preamble = 'You will not see this in a MIME-aware mail reader.\n'
	
	# Define the body of the email
	part = MIMEText("Hi, \n\n You have used AES256 to encrypt your .zip file, please ensure to use ZipCrypto otherwise we can not analyse your submission.\n\nThanks, \nMalware Labs.\n\n\nPlease do not reply to this e-mail.")
	msg.attach(part)
	 
	# Send the email via gmails SMTP server
	server = smtplib.SMTP("smtp.gmail.com:587")
	server.ehlo()
	server.starttls()
	server.login("example@gmail.com", "password")
	server.sendmail(msg['From'], emaillist , msg.as_string())
	print "Email sent."
	return



def main(q, emailID):
	global password
	global number
	number = emailID

	# Create an SSL connection to server
	log.debug("Connecting to the gmail imap server")
	M = imaplib.IMAP4_SSL('imap.gmail.com')

	log.info("Process email thread is attempting to log into the email account")
	try:
		email = 'example@gmail.com'
		password = 'password'
		M.login(email, password)
		log.debug("Email login successful")
	except imaplib.IMAP4.error:
		log.debug("Email login failed")

	rv, data = M.select("Inbox", "UNSEEN")
	if rv == 'OK':
		log.info("Processing mailbox")
		get_content(M)
		M.close()
	else:
		log.debug("Failure to process email mailbox")
	M.logout()