# Cuckoo-Email-Submission

This repo aims to add functionality to Cuckoo Sandbox (specifically Cuckoo Modified which is now deprecated) by taking emails from a specified email account using IMAP, determining the contents, and then submitting it to Cuckoo Sandbox. The scripts are quite obviously not optimised, but that is on a to do list.

Priority Order:
- Sample submission via attachment (can take 1 or multiple attachments, inline attachments are ignored)
- Hash value, queries the SQLite database for previous reports (Only takes one of the following: MD5, SHA1, SHA256 or SHA512)
- URL, submits the URL to Cuckoo. This does not query the database for previous reports as malicious websites regularly change. 

It should be noted that it only takes one of the above 3 per email therefore an email should not contain both attachments and hashes as it will only recognise the attachments.

Functionality:
- Attachments
  - Submit the attachment to Cuckoo.
  - Wait for the report to be generated.
  - Email the new report to the original sender.
- Hash 
  - Determine hash type.
  - Query the SQLite database.
  - If report is present email it to the user else send an email stating there is no report present.
- URL
  - Submit the URL to Cuckoo.
  - Wait for the report to be generated.
  - Email the new report to the original sender.

 
 
 
 
 
 
 
To Do:
- Optimise Code
- Less email / password entries
  - Maybe change it so it isn't hardcoded - enter in the terminal
- In URL submission attach any previous reports to the email
