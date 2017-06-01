import imaplib2
import time
import subprocess
from threading import *
from subprocess import call
from multiprocessing.dummy import Pool
import requests
import Queue
import processEmail
import initialResponse

class Idler(object):

    def __init__(self, conn):
        self.thread = Thread(target=self.idle)
        self.M = conn
        self.event = Event()
 
    def start(self):
        self.thread.start()
   
    def idle(self):
        # When an email comes in the idle connection is cut when this happen dosync()
        # Unfortunately, this connection is also cut when the state of an email changes from unseen to seen
        # And when an email is deleted. You can verify you have a new email but that isn't within the scope
        # P.S. You can do that through looking for the Seen flag
        while True:
            if self.event.isSet():
                return
            self.needsync = False
            def callback(args):
                if not self.event.isSet():
                    self.needsync = True
                    self.event.set()
            self.M.idle(callback=callback)
            self.event.wait()
            if self.needsync:
                self.event.clear()
                # Default timeout is 29 minutes this ensures processEmail is 
                # only started when an something happens in gmail and not when it times out
                response = M.response('IDLE')
                response = response[1]
                if response[0] != "TIMEOUT":
                    self.dosync()
                else:
                    print "timed out"
 
    def dosync(self):
        global M

        print "An email has been received, please wait...\n"
        M.select("Inbox")
        rv, data = M.search(None, "ALL")
        if rv != "OK":
            print "No messages found"
            return
        # Get the number of emails in the folder and get the id number of the most recent email
        emails = data[0].split()
        if not emails:
            print "Error: There are no emails present"
            return
        else:
            num = emails[-1]
            q.put(num)
            queueLength = q.qsize()
            initialResponse.main(queueLength, num)


def queuing():
    global q

    while True:
        if q.empty() == False:
            print "Creating new thread to process the new email"
            emailID = q.get()
            thread = Thread(target = processEmail.main, args=(q, emailID))
            thread.start()
            thread.join()
        print "The queue is empty checking the queue again."
        time.sleep(5)


def main():
    global M
    
    thread = Thread(target = queuing)
    thread.start()

    email = "example@gmail.com"
    password = "password"

    print "connecting to server"
    # Make a SSL connection to gmail
    M = imaplib2.IMAP4_SSL("imap.gmail.com")
    # Login to gmail ("email","password")
    M.login(email, password)
    # Select the folder you want to check
    M.select("Inbox")
    # Start a thread with the idler running
    print "connected"
    idler = Idler(M)
    idler.start()

q = Queue.Queue()
main()
