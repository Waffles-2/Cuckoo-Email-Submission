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
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from smtplib import SMTP
from subprocess import call
import threading
import Queue

def get_sender(M):

	global email_number
	global email_sender
	
	# Check that there are some messages present
	rv, data = M.search(None, "ALL")
	if rv != "OK":
		print "No messages found"
		return

	num = email_number
	
	# Fetch the most recent email in the folder
	rv, data = M.fetch(num, '(RFC822)')
	if rv != 'OK':
		print "Error getting message", num
		return

	# Decode the email and put it into a string format rather than the raw format
	msg = data[0][1]
	raw_email_string = msg.decode('utf-8')
	email_message = email.message_from_string(raw_email_string)

	# Get the email address that sent the email to us
	received = email_message['From']
	sender = re.findall('.*?\<(.*?)\>.*?', received)
	email_sender = sender[0]
	create_email()



def create_email():
	global email_sender
	global queueSize

	print "Sending an initial email response to: %s...\n" % email_sender
	# Set the recipient and parse the list in case of multiple recipients
	# This must be parsed even if there is only ever one recipient
	recipients = [email_sender] 
	emaillist = [elem.strip().split(',') for elem in recipients]
	# Create the container for the email and fill some fields
	msg = MIMEMultipart()
	msg['Subject'] = 'Malware Labs: Submission Confirmation'
	msg['From'] = 'example@gmail.com'
	
	# Defines some formatting for MIME-aware mail reader 
	msg.preamble = 'You will not see this in a MIME-aware mail reader.\n'

	# Create a maximum estimate for time in queue based upon the number of samples in the queue
	queueTime = (1+ int(queueSize)) * 10

	# Create the body of the email
	part = MIMEText("Hi, \n\nThank you for your submission.\nIf you have submitted a file or URL analysis there is currently {0} file(s) ahead of you in the queue, therefore the analysis could take up to {1} minutes. \n\nThank you for your patience, \nMalware Labs.\n\n\nPlease do not reply to this e-mail.".format(queueSize, queueTime))
	msg.attach(part)
	 
	# Send the email via gmails SMTP server
	server = smtplib.SMTP("smtp.gmail.com:587")
	server.ehlo()
	server.starttls()
	server.login("example@gmail.com", "password")
	server.sendmail(msg['From'], emaillist , msg.as_string())
	print "Initial Email sent."
	return

def main(queueLength, num):

	global email_number
	global queueSize

	email_number = num
	queueSize = queueLength

	# Create an SSL connection to server
	M = imaplib.IMAP4_SSL('imap.gmail.com')

	print "Please wait, the initial response thread is logging into email account..."

	# Login to gmail account, you can use getpass.getpass() to prompt the user for a password
	try:
		email = 'example@gmail.com'
		password = 'password'
		M.login(email, password)
	except imaplib.IMAP4.error:
		print "Login Failed"

	print "Logged in, selecting folder..."

	#this selects the folder Malware Lab and checks if there are unseen items
	rv, data = M.select("Inbox", "UNSEEN")
	if rv == 'OK':
		print "Processing mailbox...\n"
		get_sender(M)
		M.close()
	else:
		print "failure"
	M.logout()





