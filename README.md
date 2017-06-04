GUI IN PROGRESS!

STILL WORKING ON ALPHA

# Jobbybot
Automatically apply to jobs using your own filters. 

#### Supported Job Sites:
> RIT Jobzone (DOWN)

> Indeed (DOWN)

> Ziprecruiter (UP)

## How To Setup
### How To Setup: THE PACKAGE
1. download the zip file, unzip, and put unzipped folder somewhere you won't delete it
2. open a console in the directory of the package containing the file "setup.py" and type the following. This will install any dependencies missing from your computer, so that you can run the module
   
   >>> pip setup.py install
   
3. open the "jobbybot_settings.json" file in a text editor and fill in the fields as you desire (maintain json formatting)
   > NOTE: in the docs section, you must replace'\' with '\\'
   > NOTE: location should be a list as follows: ["zip_code", "radius"]  . the program only supports one zip_code and one radius.

4. download Google Chrome, if you have not already.

### How To Setup: RIT JobZone
NOTE: This part of the program relies on files already uploaded to this site and will not upload them for you using the "jobbybot_settings.json" doc paths. You must update these, before starting the program
1. setup your account with RIT's Jobzone
2. fill in your login credentials in the "site_settings.json" file in the rit_jobzone folder

### How To Setup: Indeed
1. goto https://www.indeed.com/publisher to create a publisher account with an id
2. fill in the publisher_id in the "indeed_client_secret.json" file
3. wait a few minutes, because indeed takes a little while to register publisher accounts, before running the program. continue to next step.
4. open the "site_settings.json" file in the indeed folder and write in your credentials
5. in your cover letter, you can use the variables {{company_name}} and {{job_title}}. the program will replace these variables with the appropriate company name and job title based on the job the program is applying to for you.

Note: You do not need to upload any files to indeed. the jobbybot_indeed program will upload the files you referred to in jobbybot_settings.json for you for every application

### How To Setup: Optional: Connect to Google Sheets for Live Updates (read through all steps before starting)
1. goto https://console.developers.google.com/start/api?id=sheets.googleapis.com
   > create a poject
   > enable the Google Drive API
2. place the json credentials file in the same folder as "jobbybot.py"
   > rename json credentials file to "google_client_secret.json"
3. open "jobbybot_settings.json"
   > put your email address into the "email" field
   > set "gsheets" in the "settings" section to "True"
4. all applications the program has applied to for you will be listed in this sheet. the program is additive and will check, on startup, whether any entries are missing and add them if need be. the program does not check for missing fields.

Note: if you accidentally delete some values or columns, just wipe out the entire sheet and restart the program. the program will then rewrite the entire spreadsheet.

IMPORTANT: Do not move column positions in Google Sheets! 

IMPORTANT: Do not rename the google sheet. If you do, a new sheet with the same name as before will be created and written to.

## How to Use
1. ensure you have all of the docs needed available on the jobs site you want to use (if they are not available, but the employer requests   them, the application will be skipped)
2. goto each site module and click the autorun bat file and that module will start applying to jobs
   > all modules will use the same profile
   
## Sidenotes
1. SQLAlchemy is used in each module to store all jobs the module has reviewed for you (both those you applied to and did not apply to, but the module attempted to apply to)
