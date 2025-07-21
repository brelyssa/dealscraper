import sys
import configparser
import dataclasses
from argparse import ArgumentParser
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.proxy import Proxy, ProxyType
import time
from random import choice
import requests
import bs4
import asyncio
import re
from email.message import EmailMessage
from typing import Collection, List, Tuple, Union
import aiosmtplib

driver = webdriver.Firefox()
prCount = 0

HOST = "smtp.gmail.com"
CARRIER_MAP = {
    "verizon": "vtext.com",
    "tmobile": "tmomail.net",
    "sprint": "messaging.sprintpcs.com",
    "at&t": "txt.att.net",
    "boost": "smsmyboostmobile.com",
    "cricket": "sms.cricketwireless.net",
    "uscellular": "email.uscc.net",
}

@dataclasses.dataclass
class EmailSMSConfig:
    num: str = ""
    carrier: str = "verizon"
    email: str = ""
    pword: str = ""
    msg: str = "start bidding now!"
    subj: str = "ALERT"

@dataclasses.dataclass
class ProductConfig:
    productId: str = ""
    update_interval: int = 10  # seconds

@dataclasses.dataclass
class DealScraperConfig:
    email_sms: EmailSMSConfig = dataclasses.field(default_factory=EmailSMSConfig)
    product: ProductConfig = dataclasses.field(default_factory=ProductConfig)


def get_config():
    config = configparser.ConfigParser()
    config.read('config.ini')

    scraper_config = DealScraperConfig()

    if config.has_section('Email SMS Settings'):
        scraper_config.email_sms.carrier = config.get('Email SMS Settings', 'PhoneCarrier', fallback='verizon')
        scraper_config.email_sms.num = config.get('Email SMS Settings', 'PhoneNumber')
        scraper_config.email_sms.email = config.get('Email SMS Settings', 'EmailAddress')
        scraper_config.email_sms.email = config.get('Email SMS Settings', 'Password')
        scraper_config.email_sms.email = config.get('Email SMS Settings', 'Message', fallback='start bidding now!')
        scraper_config.email_sms.email = config.get('Email SMS Settings', 'Subject', fallback='ALERT')

    if config.has_section('Product Settings'):
        scraper_config.product.productId = config.get('Product Settings', 'ProductId')
        scraper_config.product.update_interval = config.getint('ProductSettings', 'Update Interval', fallback=10)

    return scraper_config

async def send_txt(cur_bid: str, config: EmailSMSConfig) -> Tuple[dict, str]:
    num = str(num)
    to_email = CARRIER_MAP[config.carrier]

    # build message
    message = EmailMessage()
    message["From"] = config.email
    message["To"] = f"{num}@{to_email}"
    message["Subject"] = config.subj
    message.set_content("Current bid price: "+cur_bid +", "+ config.msg)

    #send
    send_kws = dict(username=config.email, password=config.pword, hostname=HOST, port=587, start_tls=True)
    res = await aiosmtplib.send(message, **send_kws)
    if not re.search(r"\sOK\s", res[1]):
        print("Sending text message failed.")
    else:
        print("Sending text message succeeded.")
    return res

def checkProxy(proxy):
    #check for letters after 'http://'
    proxyNum = str(proxy).split("http://",1)[1]
    for x in proxyNum:
        if x.isalpha():
            return False
        #check for any non-alpha,non-digit,not period, special character
    size=len(proxyNum)
    proxyNum = proxyNum[:size-2]
    return True

def get_proxy_list():
    response = requests.get("https://sslproxies.org/") 
    soup = bs4.BeautifulSoup(response.content, 'html.parser') 
    proxies_found = soup.select('tr')
    proxy_list = []
    i=0
    for proxy in proxies_found:
        proxy = {'http': 'http://'+choice(list(map(lambda x:x[0]+':'+x[1], list(zip(map(lambda x:x.text, soup.findAll('td')[::8]), map(lambda x:x.text, soup.findAll('td')[1::8]))))))}
        if i>=20:
            break
        if checkProxy(proxy) == True:
            proxy_list.append(proxy)
            i+=1
    return proxy_list

proxy_list = get_proxy_list()

def get_proxy():
    global proxy_list
    global prCount

    #rotate through proxy list
    while True:
        if prCount>=20:
            prCount=0
        proxy=proxy_list[prCount]
        #use current proxy if validated
        if checkProxy(proxy):
            prCount+=1
            return proxy


firefox_options = Options()
proxy=get_proxy()
print(proxy)
firefox_options.add_argument(f"--proxy-server={proxy}")


def main():
    scraper_config = get_config()

    driver.get(f"https://www.dealdash.com/auction/{scraper_config.product.productId}") # Open a web page
    while(True):
        
        time.sleep(10) # Allow the page to load

        currentBid = driver.find_elements(By.CLASS_NAME, "css-146c3p1.r-gfo7p.r-jwli3a.r-1ra0lkn.r-vw2c0b")
        print("Current bid price: "+currentBid[0].text)
        
        users_list = driver.find_elements(By.CLASS_NAME, "css-146c3p1.r-dnmrzs.r-1udh08x.r-1udbk01.r-3s2u2q.r-1iln25a.r-gfo7p.r-m2pi6t.r-1enofrn")
        
        #for user in users_list:
        #    print("Last couple user bids: "+user.text)

        distinct_users_list = []
        count = 0
        for user in users_list: #getting all recent distinct users
            if(user.text not in distinct_users_list):
                count += 1
                distinct_users_list.append(user.text)

        #print("# distinct users: "+str(len(distinct_users_list)))
        #print("List of distinct users: ")
        #for distinct_user in distinct_users_list: #getting all recent distinct users
        #    print(distinct_user)


        if(len(distinct_users_list)<=2):
            #want to send an alert
            print("<=2 users left. Attempting to send an SMS alert...")
            coro = send_txt(currentBid[0].text, scraper_config.email_sms)
            asyncio.run(coro)
        elif (len(distinct_users_list)==3):
            print("3 users bidding. Close to bidding time!")
        else:
            print(str(len(distinct_users_list))+" bidders currently, not time yet.")

    driver.quit() # Close the browser



if __name__ == "__main__":
    main()