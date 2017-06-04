'''
Purpose: Automatically race through all job postings in RIT's Symplicity JobZone system, for which you qualify /
         are in your major / have not previously applied to,
         find the jobs with easy apply button and apply. The default cover letter available for your account
         is used when necessary; however, you can indicate that you want to submit a special cover letter, in which
         case the program will open up that webpage in Google Chrome and skip the autoapply. Get the same results as
         doing this manually, but faster.
         You can see all jobs you have applied to using the other functions of the website.'''

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
from common_funcs import CommonFuncs
from apps_db_declaratives import *


class Rit_Jobzone_Bot:
    '''At the beginning of each session, the user's online docs are replaced with their correspondents,
    if available, from their computer.'''

    def __init__(self, driver=None):

        if driver is None:
            self.driver = CommonFuncs.just_get_driver()
        else:
            self.driver = driver

        pass

    def login(self, login_creds):
        '''return True if login is successful; false otherwise.'''

        # NAVIGATE TO RIT JOBZONE JOB SITE
        try:
            self.driver.get(JOB_SITE_LINKS['login_site'])  # navigate to login page
        except:
            return False

        # ENTER USERNAME AND PASSWORD
        try:
            self.driver.find_element_by_id('username').send_keys(login_creds.username)
            self.driver.find_element_by_id('password').send_keys(login_creds.password)
        except:
            return False

        # SUBMIT LOGIN FORM
        try:
            self.driver.find_element_by_xpath(r'//*[@id="userInput"]/form/button').click()
        except:
            return False

        try:    # if the error message cannot be found, login was successful
            self.driver.find_element_by_id('baduserpass')
            return False
        except:
            return True

    def get_new_link(self, desired_result_count=1, need_new_results=True):
        '''apply filters from the job_profile and return a new job link.'''

        job_profile = None
        with CommonFuncs.get_db() as db:  # if no job profile, return an empty link
            try:
                job_profile = db.query(JobProfile).one()
            except:
                return ''

        self.driver.get(JOB_SITE_LINKS['job_site'])  # navigate to the job site

        self.driver.find_element_by_link_text('Advanced Search').click()  # open the filter settings

        # Open the ajax more filters form expander
        hyperlinks = self.driver.find_element_by_class_name("content-container-inner").find_elements_by_tag_name('a')
        for hyperlink in hyperlinks:
            try:
                if str(hyperlink.text).lower() == "more filters":
                    hyperlink.click()
                    break
            except:
                pass

        # FILL IN ALL COMBOBOXES AND LISTBOXES
        combobox_filters = \
            {
                "//*[@id='advsearch_ocr_']": 'job_types',
                "//*[@id='jobfilters_industry___']": 'industries',
                "//*[@id='jobfilters_job_type___']": 'job_types',
                "//*[@id='advsearch_job_custom_field_2___']": 'terms_of_employment',
                "//*[@id='advsearch_multi_state___']": 'states',
                "//*[@id='advsearch_multi_country___']": 'countries',
                "//*[@id='advsearch_work_authorization___']": 'work_authorizations'
            }
        for box_filter in combobox_filters:
            combo_selections = CommonFuncs.combo_select(
                combobox=self.driver.find_element_by_xpath(box_filter),
                visible_text_list=getattr(job_profile, combobox_filters[box_filter]))

        # FILL IN ZIP CODE AND RADIUS IF APPLICABLE
        zip_box = self.driver.find_element_by_xpath("//*[@id='jobfilters_distance_search__base_']")
        radius_box = self.driver.find_element_by_xpath("//*[@id='jobfilters_distance_search__distance_']")
        if len(job_profile.zip_code) > 0:
            try:
                zip_box.send_keys(job_profile.zip_code)
                radius_box.send_keys(job_profile.radius)
            except:
                pass

        # EXCLUDE JOBS ALREADY APPLIED TO
        self.driver.find_element_by_name("jobfilters[exclude_applied_jobs]").click()  # exclude jobs applied for

        # ONLY INCLUDE JOBS IN THE SELECTED MAJOR
        self.driver.find_element_by_name("advsearch[major_ignore_all_pick]").click()  # include only selected major

        # APPLY FILTERS
        self.driver.find_element_by_xpath(
            r'//*[@id="frame"]/div[4]/div/div/div[2]/div[1]/div/form/div/div[2]/span[1]/input[1]').click()  # apply filters

        # SUBMIT KEYWORDS
        try:
            keywords_string = job_profile.keywords
            search_box = self.driver.find_element_by_name("jobfilters[keywords]")
            search_box.clear()
            sleep(3)
            search_box.send_keys(keywords_string)
            # CLICK SEARCH BUTTON
            self.driver.find_element_by_xpath(
                "//*[@id='frame']/div[4]/div/div/div[2]/div[1]/div/form/div/div[1]/input[2]").click()
        except WebDriverException:
            pass

        # FIND A NEW LINK NOT YET PROCESSED BY ANY BOT THAT MATCHES THE FILTER RESULTS
        try:
            soup = BeautifulSoup(self.driver.page_source)
            jobs_on_page_container = soup.find('div', {'id': 'student_job_list_content'})
            jobs_on_page = jobs_on_page_container.find('ul').findAll('li')
            pages = self.driver.find_element_by_name('_pager').find_elements_by_tag_name('option')
        except AttributeError:
            return []

        new_jobs_list=[]

        for page in pages:
            try:
                soup = BeautifulSoup(self.driver.page_source)  # get  the page source html
            except:
                return []
            try:
                jobs_on_page_container = soup.find('div', {'id': 'student_job_list_content'})
                jobs_on_page = jobs_on_page_container.find('ul').findAll('li')
            except:
                pass

            if jobs_on_page:

                for job in jobs_on_page:
                    job_links = job.findAll('a')  # find all links in list item

                    for link in job_links:

                        if '?mode' in link['href']:  # urls with this encoding goto the page for that job

                            if need_new_results:
                                with CommonFuncs.get_db() as db:
                                    db_matches = db.query(Job).filter(
                                        Job.link_to_job.contains(link['href'])).all()
                            else:
                                db_matches = []

                            if not db_matches:  # if this job has not been processed by any bot yet, return the link
                                if desired_result_count == 1:
                                    return JOB_SITE_LINKS['job_site_base'] + link['href']
                                elif len(new_jobs_list) < desired_result_count:
                                    new_jobs_list.append(JOB_SITE_LINKS['job_site_base'] + link['href'])
                                else:
                                    return new_jobs_list

            try:
                self.driver.find_element_by_link_text('Next').click()
            except (NoSuchElementException, AttributeError):
                pass

        return [] # if no new links

    def apply(self, job):
        '''apply to the job and store in db. return the job object.'''

        job_profile = None
        with CommonFuncs.get_db() as db:  # if no job profile, return
            try:
                job_profile = db.query(JobProfile).one()
            except:
                return

        self.driver.get(job)  # navigate to job page

        # build job object
        new_job = Job()
        new_job.app_date = datetime.now()
        new_job.link_to_job = job
        new_job.job_title = self.driver.find_element_by_xpath(
            '//*[@id="frame"]/div[4]/div/div/div/div[2]/div/div[1]/div[1]/div[1]/div/div[2]/h1').text
        new_job.job_site = CommonFuncs.fetch_domain_name(self.driver.current_url)
        new_job.applied = False  # default

        # GET EMPLOYER NAME
        try:
            employer_name = self.driver.find_element_by_class_name('job_emp_details').find_element_by_tag_name(
                'a').text
            new_job.company = employer_name
        except:
            pass

        # GET LOCATION
        try:
            other_data = self.driver.find_elements_by_class_name('job-bfields')
            for datum in other_data:
                if "location" in datum.find_element_by_class_name('label').text.lower():
                    job_location = datum.find_element_by_class_name('widget').text
                    new_job.location = job_location
                    break
        except:
            pass

        # GET CONTACT INFO - if available
        try:
            contact_block = self.driver.find_element_by_id('sb_contactinfo')
            contents = contact_block.text.split('\n')
            new_job.contact_name = contents[1]
            for item in contents:
                if "@" in item:
                    new_job.contact_email = item
                elif "http" in item:
                    new_job.company_site = item
        except:
            pass

        # OPEN APPLICATION FORM
        try:
            job_apply_button = self.driver.find_element_by_id('job_send_docs')
            job_apply_button.click()
            docs_used = []
            # make doc selections
            doc_fields = ['resume', 'cover_letter', 'writing_sample', 'transcript']
            supporting_docs = []
            for doc_field in doc_fields:
                try:
                    select = Select(self.driver.find_element_by_name(
                        "dnf_class_values[non_ocr_job_resume][%s]" % doc_field))
                    if doc_field == "resume":
                        select.select_by_index(0)
                    else:
                        select.select_by_index(1)  # select the first available cover letter
                except:
                    pass

            # SUBMIT APPLICATION
            try:
                self.driver.find_element_by_xpath("//*[@id='job_resume_form']").find_element_by_name(
                    "dnf_opt_submit").click()
                new_job.applied = True
            except:
                new_job.appled = False
        except:
            new_job.appled = False

        return new_job