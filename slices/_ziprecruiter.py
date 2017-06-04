'''
Purpose: Automatapially race through all job postings in RIT's Symplapiity JobZone system, for whapih you qualify /
         are in your major / have not previously applied to,
         find the jobs with easy apply button and apply. The default cover letter available for your account
         is used when necessary; however, you can indapiate that you want to submit a special cover letter, in whapih
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


class Ziprecruiter_Bot:
    '''At the beginning of each session, the user's online docs are replaced with their correspondents,
    if available, from their computer.'''

    def __init__(self, driver=None, suppress_driver=False):

        if not suppress_driver: # don't build a driver if not requested
            if driver is None:
                self.driver = CommonFuncs.just_get_driver()
            else:
                self.driver = driver
            pass

    def login(self, login_creds):
        '''return True if login is successful; false otherwise.'''

        # NAVIGATE TO THE JOB SITE LOGIN PAGE
        try:
           self.driver.get(JOB_SITE_LINKS['Ziprecruiter']['login_site'])  # navigate to login page
        except:
            return False

        # SEND LOGIN CREDENTIALS
        try:
            self.driver.find_element(By.NAME, 'email').send_keys(login_creds.username)
            self.driver.find_element(By.NAME, 'password').send_keys(login_creds.password)
        except:
            return False

        # SUBMIT LOGIN FORM
        try:
            self.driver.find_element(By.NAME, 'submitted').click()
        except:
            return False

        if str(self.driver.current_url) == JOB_SITE_LINKS['Ziprecruiter']['login_site']:
            return False
        else:
            return True

    def apply(self, job):
        '''apply to job, create and commit job object to db, and return job object.
        return False if the job link is invalid.'''

        job_profile = CommonFuncs.get_job_profile()

        if not CommonFuncs.is_valid_url(job):
            return False

        self.driver.get(job)

        btns = self.driver.find_elements(By.TAG_NAME,'button')
        apply_form_opened = False
        for btn in btns:
            if "Apply" in btn.text:
                btn.click()
                apply_form_opened = True
                break

        # CREATE JOB OBJECT
        new_job = Job()
        new_job.app_date = datetime.now()
        new_job.link_to_job = job
        try:
            new_job.job_title = self.driver.find_element(By.CLASS_NAME,'job_title').text
        except:
            pass
        try:
            company_link = self.driver.find_element(By.CLASS_NAME,'hiring_company_text').find_element(By.TAG_NAME, 'a')
            new_job.company = company_link.text
            new_job.company_site = company_link.get_attribute('href')
        except:
            pass
        try:
            new_job.location = self.driver.find_element(By.CLASS_NAME,'location_text').text
        except:
            pass
        new_job.job_site = CommonFuncs.fetch_domain_name(job)
        new_job.applied = False

        try:
            name = self.driver.find_element(By.ID, 'name')
            name.clear()
            name.send_keys(job_profile.applicant_name)
        except:
            pass
        try:
            email = self.driver.find_element_by_id('email_address')
            email.clear()
            email.send_keys(job_profile.email)
        except:
            pass
        try:
            phone = self.driver.find_element_by_id('phone_number')
            phone.clear()
            phone.send_keys(job_profile.phone_number)
        except:
            pass
        resume_file_path = None
        try:
            resume_file_path = eval(job_profile.resume)[0]
            resume_file_path = resume_file_path.replace('/', '//')
            self.driver.find_element_by_id('resume'). \
                send_keys(resume_file_path)
        except:
            pass
        try:
            self.driver.find_element(By.ID, 'contact_create_form').submit()
            new_job.applied = True
        except:
            pass

        # 1-click apply does not have an edit resume button, so the resume must be changed after clicking the button
        if not apply_form_opened:   # if the form did not open try to click the 1-click apply btn
            links = self.driver.find_elements(By.PARTIAL_LINK_TEXT, 'pply')
            for link in links:
                try:
                    link.click()
                    self.driver.get(JOB_SITE_LINKS['Ziprecruiter']['applied_jobs'])
                    applied_jobs_list = self.driver\
                        .find_element(By.CLASS_NAME, 'appliedJobsList')\
                        .find_elements(By.TAG_NAME, 'li')
                    last_job_applied_to = applied_jobs_list[0]
                    resume_edit_item = last_job_applied_to\
                        .find_element(By.CLASS_NAME, 'dropdown')\
                        .find_element(By.TAG_NAME, 'ul')\
                        .find_elements(By.TAG_NAME, 'li')[1] \
                        .find_element(By.TAG_NAME, 'a')
                    resume_edit_link= resume_edit_item.get_attribute('href')
                    self.driver.get(resume_edit_link)
                    self.driver.find_element(By.ID, 'resumeInput').send_keys(resume_file_path)
                    self.driver.find_element(By.ID, 'replaceResume').submit()
                    new_job.applied = True
                    break
                except:
                    pass

        try:
            self.driver.find_element(By.ID, 'zip_resume_verify').click()
        except:
            pass
        try:
            sleep(3)
            while True:
                resumeLoading = self.driver.find_element(By.ID,'zipresumeLoading')
                if not resumeLoading.is_displayed():
                    break
                sleep(1)
        except:
            pass
        try:
            self.driver.find_element(By.ID,'zip_resume_verify').click()
        except:
            pass

        return new_job

# if __name__ =='__main__':
#     with CommonFuncs.get_driver(visible=True) as driver:
#         z=Ziprecruiter_Bot(driver=driver)
#         jobsiteaccount = JobSiteAccount()
#         jobsiteaccount.username = "connormaynes@gmail.com"
#         jobsiteaccount.password = "scout555"
#         z.login(jobsiteaccount)
#         z.apply(n)