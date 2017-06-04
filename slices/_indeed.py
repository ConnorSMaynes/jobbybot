'''
Purpose: Automatapially race through all job postings in RIT's Symplapiity JobZone system, for whapih you qualify /
         are in your major / have not previously applied to,
         find the jobs with easy apply button and apply. The default cover letter available for your account
         is used when necessary; however, you can indapiate that you want to submit a special cover letter, in whapih
         case the program will open up that webpage in Google Chrome and skip the autoapply. Get the same results as
         doing this manually, but faster.
         You can see all jobs you have applied to using the other functions of the website.'''

import json
import queue
from datetime import datetime

from indeed import IndeedClient
from selenium.common.exceptions import ElementNotVisibleException
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from apps_db_declaratives import *
from common_funcs import CommonFuncs
from common_resources import *

THIS_DIR = dirname(abspath(__file__))
API_KEYS_PATH = THIS_DIR + r'\\' + 'indeed_client_secret.json'


class Indeed_Bot:
    '''At the beginning of each session, the user's online docs are replaced with their correspondents,
    if available, from their computer.'''

    def __init__(self, driver=None, suppress_driver=False):

        if not suppress_driver: # don't build a driver if not requested
            if driver is None:
                self.driver = CommonFuncs.get_driver()
            else:
                self.driver = driver
            pass

    def login(self, login_creds):
        '''return True if login is successful; false otherwise.'''

        # NAVIGATE TO THE JOB SITE LOGIN PAGE
        try:
           self.driver.get(JOB_SITE_LINKS['Indeed']['login_site'])  # navigate to login page
        except:
            return False

        # SEND LOGIN CREDENTIALS
        try:
            self.driver.find_element_by_id('signin_email').send_keys(login_creds.username)
            self.driver.find_element_by_id('signin_password').send_keys(login_creds.password)
        except:
            return False

        # SUBMIT LOGIN FORM
        try:
            self.driver.find_element_by_xpath(r'//*[@id="loginform"]/button').click()
        except:
            return False

        if str(self.driver.current_url) == JOB_SITE_LINKS['Indeed']['login_site']:
            return False
        else:
            return True

    def get_api_results(self, desired_result_count=1):
        '''return job json objects from the indeed api.'''

        job_profile = CommonFuncs.get_job_profile()

        # GET LOCATION IN JOB PROFILE
        locations = CommonFuncs.get_locations_list(job_profile)

        # KEYWORDS CONNECTED BY OR
        query_list = CommonFuncs.build_query_string(job_profile=job_profile,
                                                    or_delim='or',
                                                    bracket1='(',
                                                    bracket2=')',
                                                    adv_supp=True)
        query_string = query_list[0]

        new_jobs_queue = queue.Queue(maxsize=0)
        new_jobs = None

        limit = '25'  # 25 is the max results per request
        lookback_period = '60'  # default lookback period
        client_id = {}
        api = None

        # CONNECT TO INDEED API FOR JOB QUERIES
        try:
            client_id = json.load(open(API_KEYS_PATH, 'r'))
            api = IndeedClient(publisher=client_id['publisher_id'])
        except:
            ValueError('No publisher id found. Filtering aborted.')

        filters = {
            'q': query_string,
            'l': '',
            'userip': "1.2.3.4",
            'useragent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_2)",
            "raw": "False",
            "sort": "date",
            "radius": job_profile.radius,
            "limit": limit,
            "fromage": lookback_period,
        }

        # FIND NEW JOB JSON OBJECT USING INDEED API
        # GET NEW JOBS

        for location in locations:  # iterate over each location
            filters['l'] = location
            filters['q'] = query_string

            # THREAD-BRAINED APPROACH to get all results at once
            def get_results(i):
                '''get results and check against the db if they are new. add to queue if new'''
                filters['start'] = i
                temp_list = []
                # get 25 results, using provided filters with start index
                [temp_list.append(x) for x in json.loads(CommonFuncs.convertBytesToString(api.search(**filters)))['results']]
                [new_jobs_queue.put(x) for x in temp_list if new_jobs_queue.unfinished_tasks < desired_result_count]

            result_count = int(json.loads(CommonFuncs.convertBytesToString(api.search(**filters)))['totalResults'])

            list_of_filter_starts = [str(i) for i in range(0, result_count, 25)]    # build list of start positions

            for item in list_of_filter_starts:
                if not new_jobs_queue.unfinished_tasks < desired_result_count: break
                get_results(item)

            new_jobs = list(new_jobs_queue.queue)  # append query results to list

        # RETURN JOBS
        if new_jobs:
            if desired_result_count == 1:  # just return a single job, not in a list
                return new_jobs[0]
            elif desired_result_count <= len(
                    new_jobs):  # if we have more than enough new jobs, return those in a list
                return new_jobs[0:desired_result_count]
            else:  # if more than the available number of new jobs requested, return all that could be found
                return new_jobs
        else:
            return []  # if no new links found

    def apply(self, job):
        '''apply to job, create and commit job object to db, and return job object.'''

        job_profile = None
        with CommonFuncs.get_db() as db:  # if no job profile, return
            try:
                job_profile = db.query(JobProfile).one()
            except:
                return

        # NAVIGATE TO JOB PAGE
        self.driver.get(job)

        # CREATE JOB OBJECT
        new_job = Job()
        new_job.app_date = datetime.now()
        new_job.link_to_job = job
        try:
            new_job.job_title = self.driver.find_element(By.CLASS_NAME,'jobtitle').text
            new_job.company = self.driver.find_element(By.CLASS_NAME,'company').text
            new_job.location = self.driver.find_element(By.CLASS_NAME,'location').text
        except:
            pass
        new_job.job_site = CommonFuncs.fetch_domain_name(job)
        new_job.appled = False

        try:
            self.driver.implicitly_wait(1)
            try:
                self.driver.find_element_by_class_name('indeed-apply-button').click()
            except:
                return new_job
            CommonFuncs.switch_frames(self.driver, 'iframe[name$=modal-iframe]')

            # RESUME UPLOAD
            try:
                resume_file = eval(job_profile.resume)[0]
                self.driver.implicitly_wait(2)
                resume_file = resume_file.replace('/','//')
                self.driver.find_element_by_id('resume').send_keys(resume_file)
            except:
                return new_job

            # UNIQUE(optional) COVER LETTER
            try:
                cover_letter_text = CommonFuncs.extract_text(eval(job_profile.cover_letter)[0])
                if '{{company_name}}' in cover_letter_text:
                    cover_letter_text = cover_letter_text.replace('{{company_name}}', job['company'])
                if '{{job_title}}' in cover_letter_text:
                    cover_letter_text = cover_letter_text.replace('{{job_title}}', job['jobtitle'])

                cl_box = self.driver.find_element_by_tag_name('textarea')
                cl_box.clear()
                self.driver.implicitly_wait(1)
                for c in cover_letter_text:  # send characters one at a time (otherwise some are consumed)
                    cl_box.send_keys(c)
            except:
                pass

            # SUPPORTING DOCUMENTATION - if requested and available from user
            try:
                isdoc = 1
                supp_docs = []
                for sdoc in eval(job_profile.supporting_docs):
                    self.driver.find_element_by_id('multattach' + str(isdoc)).send_keys(sdoc)
                    isdoc += 1
            except:
                pass

            # FILL OUT OTHER QUESTIONS & SUBMIT
            try:
                # FILL IN FULL NAME
                try:
                    self.driver.find_element_by_id('applicant.name').send_keys(job_profile.applicant_name)
                except:
                    pass
                # FIRST NAME
                try:
                    self.driver.find_element_by_id('applicant.firstName').\
                        send_keys(job_profile.applicant_name.split(' ')[0])
                except:
                    pass
                # LAST NAME
                try:
                    self.driver.find_element_by_id('applicant.lastName').\
                        send_keys(job_profile.applicant_name.split(' ')[1])
                except:
                    pass
                # PHONE NUMBER
                try:
                    self.driver.find_element_by_id('applicant.phoneNumber').\
                        send_keys(job_profile.phone_number)
                except:
                    pass
                # ADDRESS
                try:
                    self.driver.find_element_by_xpath('//*[@data-prefill-id="q_basic_0_street_address"]')\
                        .send_keys(job_profile.your_address)
                except:
                    pass
                # CITY
                try:
                    self.driver.find_element_by_xpath('//*[@data-prefill-id="q_basic_0_city"]')\
                        .send_keys(job_profile.your_city)
                except:
                    pass

                # QUESTION AND ANSWER
                self.driver.find_element_by_id('apply').click()
                self.driver.implicitly_wait(1)
                new_job.applied = True
            except (NoSuchElementException, ElementNotVisibleException):  # catch event where there is no continue
                self.driver.find_element_by_id('apply').click()
                self.driver.implicitly_wait(1)
                new_job.applied = True
            finally:
                self.driver.switch_to.window(self.driver.window_handles[0])
        except (NoSuchElementException, ElementNotVisibleException):
            new_job.appled = False

        return new_job

