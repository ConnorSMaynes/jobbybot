'''
Purpose: Automatically race through job postings for which you qualify /
         are in your area of study / have not previously applied to,
         find the jobs with easy apply button and apply. '''

import inspect
import json
import logging
import queue
import sys
import urllib
from contextlib import contextmanager
from datetime import datetime
from os.path import dirname, abspath
from threading import Thread
from time import sleep
from urllib.parse import urlparse
from urllib.parse import urlparse, parse_qs
from urllib.parse import urlsplit, parse_qsl
from urllib.request import ProxyHandler

import docx2txt
import os
import gspread
import pygame
import requests
import scrapy
from scrapy.spiders import BaseSpider
from scrapy.http import FormRequest
import textract
from PyQt5.QtWebEngineWidgets import QWebEnginePage
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import *
from bs4 import BeautifulSoup
from bs4 import BeautifulSoup as bs
from indeed import IndeedClient
from lxml import html
from oauth2client.service_account import ServiceAccountCredentials
from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.common.exceptions import ElementNotVisibleException
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from sqlalchemy import create_engine, inspect, and_, or_
from sqlalchemy.orm import sessionmaker, scoped_session

from common_resources import *
from apps_db_declaratives import *


# import all bot classes
THIS_DIR = dirname(abspath(__file__))
GOOGLE_SHEETS_ID_PATH = THIS_DIR + r'//' + 'google_client_secret.json'
DB_PATH = r"sqlite:///%s\db.db" % THIS_DIR
CHROME_DRIVER_PATH = THIS_DIR + r'/' + 'drivers\chromedriver.exe'
PHANTOMJS_DRIVER_PATH = THIS_DIR +  r'/' + 'drivers\phantomjs.exe'

class CommonFuncs:

    @staticmethod
    def convertBytesToString(bytes):
        '''convert a string with a  bytes prefix to a string and return the string'''
        return bytes.decode('UTF-8')

    @staticmethod
    def log( self=None, message=None, level='info' ):
        '''log a message to the session log. after a new session is started the old log is overwritten.
        level OPTIONS: debug, info, warning'''
        # WRITE TO LOG FILE
        # level = level.lower()
        # LOG_OPTIONS = ['info', 'debug', 'warning']
        # if isinstance( message, str ) and level in LOG_OPTIONS:
        #     def async_log():
        #         logging.basicConfig(filename='log.log', level=eval('logging.' + level.upper()))
        #         log_func = eval('logging.' + level)
        #         log_func(message)
        #     Thread(target=async_log).start()
        #
        # # WRITE TO LOG LISTBOX IN GUI
        # try:
        #     self.ui.log_listbox.addItem( message )
        #     self.ui.log_listbox.scrollToBottom()
        # except:
        #     pass

    @staticmethod
    def conv_listlist_to_listtuple(listlist):
        '''convert a list of lists and return a list of tuples'''
        if not isinstance(listlist,list):
            return False
        num_iterations = len( listlist[0] )
        num_args = len( listlist )
        listtuple = []
        for i in range( num_iterations ):
            temp_list = []
            for arg_map in listlist:
                temp_list.append(arg_map[i])
            listtuple.append(tuple(temp_list))
        return listtuple

    @staticmethod
    def combo_select(combobox,visible_text_list):
        '''return list of filters in combobox applied.'''
        filters_applied = []    # list of filters applied
        select = Select(combobox)
        for option in select.options: # iterate over Show Me options
            for item in visible_text_list: # iterate over job type selections
                if item.lower().strip() in option.text.lower():   # if job type matches option, select that option
                    try:
                        select.select_by_visible_text(option.text)
                        filters_applied.append(option.text)
                    except:
                        pass

        return filters_applied

    @staticmethod
    def find_tag_contents_by_visible_text(driver, utag, keyword, subids=None):
        '''return the full text of the tag with the keyword you entered in its contents'''
        tag_contents = ''
        soup = BeautifulSoup(driver.page_source,"html5lib")
        if subids:
            tag_objects = soup.findAll(utag, subids)
        else:
            tag_objects = soup.findAll(utag)
        for obj in tag_objects:
            try:
                obj_text = obj.text
                if keyword in obj_text:
                    tag_contents = obj.text
                    break
            except:
                pass
        return tag_contents

    @staticmethod
    def fetch_domain_name(url):
        '''return the base domain. return empty string if fails.'''
        if url:
            parsed_uri = urlparse(url)
            domain = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)
            return domain
        else:
            return ""

    @staticmethod
    def next_available_row(worksheet):
        '''return next empty row from column 1'''
        str_list = filter(None, worksheet.col_values(1))  # fastest
        return len(str_list) + 1

    @staticmethod
    def extract_text(file_path):
        '''return the text extracted from a doc, docx, pdf or text file.'''
        txt = ''
        try:  # try to read doc/docx file cover letter
            txt = docx2txt.process(file_path)
        except:
            try:  # try to read pdf file cover letter
                with open(file_path) as f:
                    txt = textract.process(f)
            except:
                try:    # try to read text file cover letter
                    with open(file_path) as f:
                        txt = f.readlines()
                except:
                    pass
        return txt
	
    @staticmethod
    def switch_frames(driver, frame_name):
        '''returns True is successful and False otherwise.'''
        #src: Job-Automate module
        try:
            wait = WebDriverWait(driver, 3)
            frame = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, frame_name)))
            driver.switch_to.frame(frame)
            wait.until(EC.frame_to_be_available_and_switch_to_it(0))
            return True
        except:
            return False

    @staticmethod
    def get_db_job_links(parse_qs_string=None):
        '''return list of job links, query parsing the string if parse_qs_string is none.'''
        with CommonFuncs.get_db() as db:
            db_jobs = db.query(Job).all()
        db_list = []
        for x in db_jobs:
            if parse_qs_string:
                try:
                    db_list.append(parse_qs(urlparse(x.link_to_job).query)[parse_qs_string][0])  # job keys db list
                except:
                    pass
            else:
                db_list.append(x.link_to_job)
        return db_list

    @staticmethod
    def is_valid_url(url):
        '''check if the link works, return False if it doesn't.'''
        try:
            response = urllib.request.urlopen(url)
            return True
        except:
            return False

    @staticmethod
    @contextmanager
    def get_db():
        '''return thread-safe db session.'''
        try:
            engine = create_engine(DB_PATH)
            session = scoped_session(sessionmaker(bind=engine))
            yield session
        finally:
            session.remove()

    @staticmethod
    def get_dict_from_obj(obj):
        dict = {}
        for name in dir(obj):
            try:
                if not name.startswith('_') and not 'meta' in name:
                    dict.update({name: getattr(obj, name)})
            except:
                pass
        return dict

    @staticmethod
    def get_gsheet(db):
        '''connect to google and return the job application tracking spreadsheet.'''
        wks = None
        settings = db.query(JobbybotSettings).filter(JobbybotSettings.connect_to_gsheets == True).one()
        if settings.connect_to_gsheets == True:
            try:
                scopes = ['https://www.googleapis.com/auth/drive',
                          'https://spreadsheets.google.com/feeds']
                credentials = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_ID_PATH, scopes)
                gconnection = gspread.authorize(credentials)
                spreadsheet = None
                try:
                    try:  # try to open the job tracking sheet by the key from the db
                        spreadsheet = gconnection.open_by_key(settings.job_tracking_gsheet)
                    except:
                        pass
                except:
                    try:
                        spreadsheet = gconnection.create("job_app_tracking")
                        settings.job_tracking_gsheet = spreadsheet.id
                        spreadsheet.share(settings.email, perm_type='user', role='owner')
                        db.add(settings)
                        db.commit()  # save the key
                    except:
                        pass

                wks = spreadsheet.get_worksheet(0)

            except ValueError:
                raise ValueError('No client_secret file...cannot connect to Google Sheets API')
        else:
            pass

        return wks

    @staticmethod
    def sync_gsheet():
        '''check google spreadsheet against the db, to make sure all jobs applied to are in the worksheet.'''

        db = CommonFuncs.get_db()   # open db connection

        wks = CommonFuncs.get_gsheet(db)  # get the google sheet

        applied_in_db_raw = db.query(Job).filter(Job.applied == True).all()
        applied_in_db = []
        for a in applied_in_db_raw:
            applied_in_db.append(CommonFuncs.object_to_dict(a))

        if len(applied_in_db) > 0:

            i = 1
            for header in Job.__table__.columns.keys():
                if header == 'link_to_job':
                    break
                i += 1

            applied_in_wks = wks.col_values(i)  # get all job links currently in google sheets

            for a in reversed(range(len(applied_in_db))):  # remove any jobs from the list that are already in wks
                if applied_in_db[a]['link_to_job'] in applied_in_wks:
                    applied_in_db.pop()

            CommonFuncs.print_to_google_sheets(applied_in_db)  # print any jobs that remain to wks

    @staticmethod
    def print_to_google_sheets(jobs):
        '''print the jobs to google sheets. return nothing'''

        db = CommonFuncs.get_db()   # open db connection

        wks = CommonFuncs.get_gsheet(db)  # refresh connection to google sheets

        jobs_json = []
        for job in jobs:  # convert Job objects to json
            jobs_json.append(CommonFuncs.object_to_dict(job))

        headers = Job.__table__.columns.keys()  # get properties of Job object

        if wks and len(jobs_json) > 0:  # if we have a sheet object, continue

            next_row = CommonFuncs.next_available_row(wks)  # get next empty row

            if next_row == 1:  # print headers if first row
                h = 1
                header_cell_list = wks.range(1, 1, 1, len(headers))
                for header_cell in header_cell_list:
                    header_cell.value = headers[h]
                    h += 1
                wks.update_cells(cell_list=header_cell_list)
                next_row = 2  # get next empty row

            # UPDATE THE RANGE OF CELLS WITH THE JOBS DATA
            col_count = len(headers)  # get number of columns
            row_count = len(jobs_json)  # get number of rows to be written to
            cell_list = wks.range(next_row, 1, next_row + row_count - 1, col_count)

            icell = 0
            ijob = 0
            col = 0
            for cell in cell_list:
                cell.value = jobs_json[ijob][headers[col]]
                icell += 1
                sleep(0.01)
                if col >= len(headers) - 1:
                    col = 0
                    ijob += 1
                else:
                    col += 1

            wks.update_cells(cell_list=cell_list)

    @staticmethod
    def just_get_driver(headless=False):
        if headless == True:
            driver = webdriver.PhantomJS(PHANTOMJS_DRIVER_PATH)
        else:
            driver = webdriver.Chrome(CHROME_DRIVER_PATH)
        return driver

    @staticmethod
    def get_locations_list(job_profile):
        '''return list of locations in the job profile.'''
        locations = []
        try:  # try for zip code in job profile
            locations += job_profile.zip_code.split(',')
        except:
            try:  # if no zip code, try for states
                locations = job_profile.states.split(',')
            except:
                try:  # if no states, try for countries
                    locations = job_profile.countries.split(',')
                except:
                    pass
        if len(locations) == 0:  # if no locations in job profile, create list with one element
            locations = ['']
        return locations

    @staticmethod
    def is_bot_running(bot_name):
        '''return True if bot is running. False otherwise.'''
        try:
            with CommonFuncs.get_db() as db:
                bot = db.query(JobSiteAccount).filter(
                    JobSiteAccount.site_bot_name == bot_name).one()  # get latest version of bot from db
            if bot.is_running:
                return True
            else:
                return False
        except:
            return False

    @staticmethod
    def get_job_profile():
        '''get the latest job profile and return it.'''
        job_profile = None
        with CommonFuncs.get_db() as db:  # if no job profile, return an empty link
            try:
                job_profile = db.query(JobProfile).one()
            except:
                raise ValueError('no job profile found!')
        return job_profile

    @staticmethod
    @contextmanager
    def get_driver(headless=False, visible=False):
        browser_x, browser_y = -2000, -2000
        try:
            if headless==True:
                driver = webdriver.PhantomJS(PHANTOMJS_DRIVER_PATH)
            else:
                driver = webdriver.Chrome(CHROME_DRIVER_PATH)
            if not visible and not headless: # hide browser offscreen
                driver.set_window_position(browser_x, browser_y)
            yield driver
        finally:
            driver.quit()

    @staticmethod
    def chunk_string(x, n):
        if isinstance(x, str):
            return [x[i:i+n] for i in range(0, len(x), n)]

    @staticmethod
    def get_list_matchup_ratio(list_primary, list_secondary):
        '''return ratio of number of terms in both lists to number of terms in primary list'''
        if not isinstance(list_primary,list) or not isinstance(list_secondary, list):
            raise ValueError('lists expected, but not given.')

        in_both_sets = set(list_primary).intersection(list_secondary)   # get the terms that intersect
        ratio = len(in_both_sets) / len(list_primary)

        return ratio

    def is_element_present(*locator, driver):
        '''return true if element exists'''
        driver.implicitly_wait(0)
        try:
            driver.find_element(*locator)
            return True
        except:
            return False
        finally:
            # set back to where you once belonged
            driver.implicitly_wait(1)

    @staticmethod
    def play_sound(path, **kwargs):
        pygame.mixer.init()
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy() == True:
            continue

    @staticmethod
    def get_rendered_webpage(url):
        source_html = requests.get(url).text  # get the raw HTML
        with Display(visible=0, size=(800, 600)):  # return the JavaScript rendered HTML
            rendered_html = Render(source_html).html
        soup = BeautifulSoup(rendered_html, 'html.parser')
        return soup

    @staticmethod
    def get_proxy(test_url=None):
        '''return random proxy dict,list of proxies dicts.'''

        def is_working(proxy_dict, url='https://www.google.com/'):
            '''return true if proxy works.'''
            try:
                response = requests.get(url, proxies=proxy_dict)
                response.raise_for_status()
                return True
            except:
                return False

        proxysites = ['https://www.us-proxy.org/']
        proxies = []  # proxy:port
        rows = None
        for psite in proxysites:
            response = requests.get(psite)
            soup = BeautifulSoup(response.text,'lxml')
            rows = soup.findAll('tr')
            for row in rows:
                try:
                    cols = [x.text for x in row.findAll('td')]
                    if len(cols)>=7 and cols[6] == 'yes':    # if supports https
                        proxy_dict = {
                            'http': 'http://' + cols[0] + ':' + cols[1]
                        }
                        if is_working(proxy_dict,test_url):
                            return proxy_dict
                except: # 'https': 'https://' + cols[0] + ':' + cols[1]
                    pass
        return False

    @staticmethod
    def get_bot(bot_name):
        '''return most recent version of the bot from the database.'''
        bot = None
        try:
            with CommonFuncs.get_db() as db:
                bot = db.query(JobSiteAccount).filter(JobSiteAccount.site_bot_name == bot_name).one()
        except:
            pass
        return bot

    @staticmethod
    def build_query_string(job_profile=None,
                                         or_delim='or',
                                         bracket1="(",
                                         bracket2=")",
                                         adv_supp=False):
        '''if adv_supp, return one long string. if not adv_supp, return list of strings,
        with each possible combination of each or-item ( terms of employ, job types ) with
        each and-item ( keywords, areas of study, industries ).'''

        if job_profile is None:
            return ['']

        and_fields = ['keywords', 'areas_of_study', 'industries']
        or_fields = ['terms_of_employment', 'job_types']
        query_list = []
        and_list = []  # contains terms used for AND type queries
        or_list = []  # contains terms used for OR type queries

        for and_field in and_fields:
            if getattr(job_profile, and_field) != '':
                and_list += getattr(job_profile, and_field).split(',')
        if and_list == []: and_list = ['']
        for or_field in or_fields:
            if getattr(job_profile, or_field) != '':
                or_list += getattr(job_profile, or_field).split(',')
        if or_list == []: or_list = ['']

        # BUILD QUERY STRING
        if adv_supp:
            temp_string = ''
            or_items = bracket1 + ' or '.join(or_list) + bracket2
            if or_items == "()": or_items = ''
            for and_item in and_list:
                temp_string += bracket1 + ' ' + and_item + ' ' + or_items + bracket2 + ' ' + or_delim + ' '
            temp_string = temp_string[0:len(temp_string) - 4]  # remove the last " or "
            query_list.append(temp_string)
        else:
            for or_item in or_list:
                for and_item in and_list:
                    query_list.append(or_item + ' ' + and_item)
        return query_list


class Render(QWebEnginePage):
    """Render HTML with PyQt5 WebKit."""

    def __init__(self, html):
        self.html = None
        self.app = QApplication(sys.argv)
        QWebEnginePage.__init__(self)
        self.loadFinished.connect(self._loadFinished)
        self.mainFrame().setHtml(html)
        self.app.exec_()

    def _loadFinished(self, result):
        self.html = self.mainFrame().toHtml()
        self.app.quit()