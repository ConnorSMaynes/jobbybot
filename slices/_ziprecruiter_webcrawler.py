
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
from twisted.internet import reactor
import os
import gspread
import pygame
import requests
import scrapy
from scrapy.spiders import BaseSpider
from scrapy.crawler import CrawlerRunner
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


class ZiprecruiterWebcrawler(scrapy.Spider):
    name = 'ziprecruiterwebcrawler'

    def start_requests(self):
        '''return iterable of job links'''

        with CommonFuncs.get_db() as db:
            todoforsite = db.query(UnprocessedJob).filter(UnprocessedJob.bot_type == 'Ziprecruiter_Bot').all()
        if len(todoforsite) >= 100:
            return

        start_time = datetime.now()

        job_profile = CommonFuncs.get_job_profile()
        locations = CommonFuncs.get_locations_list(job_profile)
        query_list = CommonFuncs.build_query_string(job_profile=job_profile,or_delim='',bracket1='',bracket2='',adv_supp=False)

        if len(query_list) == 0: return

        ##########
        # URL ENCODE EACH QUERY
        ##########
        start_urls = []
        for location in locations:
            for query_string in query_list:
                bot = CommonFuncs.get_bot('Ziprecruiter_Bot')
                if bot.is_running:  # verify that the bot is running before continuing to the next page
                    query_dict = {'search':query_string, 'location':location}
                    encoded_query = urllib.parse.urlencode(query_dict, safe='')
                    job_url = JOB_SITE_LINKS['Ziprecruiter']['query'] + '&' + encoded_query
                    start_urls.append( job_url )
                    response = html.fromstring( requests.get( job_url ).content )
                    temp = response.xpath("//menu[@class='select-menu-submenu t_filter_dropdown_titles']/a/@href")
                    temp = [JOB_SITE_LINKS['Ziprecruiter']['job_site_base'] + i for i in temp]
                    start_urls += temp  # append all of the links from filtering by job title
                    temp = response.xpath("//menu[@class='select-menu-submenu t_filter_dropdown_companies']/a/@href")
                    temp = [JOB_SITE_LINKS['Ziprecruiter']['job_site_base'] + i for i in temp]
                    start_urls += temp  # append all of the links from filtering by company
                else:
                    return

        msg = 'time spent building start_urls for Ziprecruiter: ' + str(datetime.now() - start_time)
        # CommonFuncs.log( msg )
        print( msg )

        ##########
        # GET URL RESPONSES AND CALL PARSE FUNCTION TO ITERATE OVER PAGES
        ##########
        print('TOTAL START URLs: ' + str(len( start_urls )))
        i = 1
        for url in start_urls:
            print('LINK#: ' + str(i) + ' WORKING ON NEW START URL: ' + url)
            yield scrapy.Request(url=url, callback=self.parse)
            i+=1

    def parse(self, response):

        with CommonFuncs.get_db() as db:
            todoforsite = db.query(UnprocessedJob).filter(UnprocessedJob.bot_type == 'Ziprecruiter_Bot').all()
        if len(todoforsite) >= 100:
            return

        # EXTRACT JOB LINKS ON THE PAGE AND COMMIT TO DB
        this_url = response._url
        try:
            searching_by = dict( parse_qsl( urlsplit( this_url ).query ) )
            print('searching by: ' + str(searching_by) )
        except:
            pass
        # CommonFuncs.log('starting parsing job page for ZiprecruiterWebcrawler: ' + response.url)

        new_jobs = None
        try:#@data-tracking='quick_apply'
            new_jobs = response.xpath(
                "//div[@class='job_results']/article/div[@class='job_tools']/" +
                "button[@data-tracking='quick_apply']" +
                "/ancestor::article" +
                "/div[@class='job_content']/a/@href").extract()
        except:
            # CommonFuncs.log('could not find jobs on the page: ' + this_url)
            pass
        new_count = 0
        if not new_jobs is None: # if no results found return
            for job_link in new_jobs:   # dump the job links to the db
                with CommonFuncs.get_db() as db:
                    db_results = db.query(Job).filter(Job.link_to_job == job_link).all()
                if db_results is None or db_results == []:
                    try:
                        with CommonFuncs.get_db() as db:
                            u_job = UnprocessedJob()
                            u_job.bot_type = 'Ziprecruiter_Bot'
                            u_job.job = job_link
                            db.add(u_job)
                            db.commit()
                            new_count += 1
                    except:
                        # CommonFuncs.log('something went wrong in ZiprecruiterWebcrawler trying to commit job link: %s' % job_link, level='debug')
                        pass

        # CommonFuncs.log('%s new jobs found on page %s' % (new_count, response._url) )
        if new_count > 0: print('%s new jobs found on page' % new_count)

        ##########
        # JUMP TO NEXT PAGE WHILE THE BOT IS STILL RUNNING
        ##########

        data_next_url = ''
        try:
            data_next_url = response.xpath( "//div[@class='job_results']" )
            data_next_url = data_next_url[0].root.attrib['data-next-url']
            if len(data_next_url)>0:
                url = JOB_SITE_LINKS['Ziprecruiter']['job_site_base'] + data_next_url
                bot = CommonFuncs.get_bot('Ziprecruiter_Bot')
                # CommonFuncs.log('finished parsing job page for ZiprecruiterWebcrawler: ' + this_url)
                if bot.is_running:  # verify that the bot is running before continuing to the next page
                    yield scrapy.Request(url=url, callback=self.parse)
                else:
                    return
        except:
            pass


# if __name__ == '__main__':
#     runner = CrawlerRunner()
#     runner.crawl(ZiprecruiterLoginWebcrawler(username='zimpetterson@gmail.com', password='scout555'))
#     d = runner.join()
#     d.addBoth(lambda _: reactor.stop())
#     reactor.run()