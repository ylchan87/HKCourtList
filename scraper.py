# This is a template for a Python scraper on morph.io (https://morph.io)
# including some code snippets below that you should find helpful

# import scraperwiki
# import lxml.html
#
# # Read in a page
# html = scraperwiki.scrape("http://foo.com")
#
# # Find something on the page using css selectors
# root = lxml.html.fromstring(html)
# root.cssselect("div[align='left']")
#
# # Write out to the sqlite database using scraperwiki library
# scraperwiki.sqlite.save(unique_keys=['name'], data={"name": "susan", "occupation": "software developer"})
#
# # An arbitrary query against the database
# scraperwiki.sql.select("* from data where 'name'='peter'")

# You don't have to do things with the ScraperWiki and lxml libraries.
# You can use whatever libraries you want: https://morph.io/documentation/python
# All that matters is that your final data is written to an SQLite database
# called "data.sqlite" in the current working directory which has at least a table
# called "data".

import sys
import requests
from datetime import datetime
from datetime import timedelta
import pytz

import dataModel as dm
import courtParser as cp

#the court codes
codes = [
    "BP"    ,
    "CLCMC" ,
    "CRHPI" ,
    "CWUP"  ,
    "MIA"   ,
    "O14"   ,
    "OTD"   ,
    "CLPI"  ,
    "MCL"   ,
    "CACFI" ,
    "CFA"   ,
    "CT"    ,
    "DC"    ,
    "DCMC"  ,
    "HCMC"  ,
    "LANDS" ,
    "DCMC"  ,
    "FMC"   ,
    "ETNMAG",
    "FLMAG" ,
    "KCMAG" ,
    "KTMAG" ,
    "STMAG" ,
    "TMMAG" ,
    "WKMAG" ,
]

todo_codes = [
    "LT" ,
    "OAT",
    "SCT",
    "CRC",
]

ua = "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36"
header = {
    'User-Agent': ua
}

if len(sys.argv) == 3:
    #for debug
    code    = sys.argv[1]
    dateYMD = sys.argv[2]

    code = code.upper()
    if code not in codes:
        print ("Unknown court code, exit")
        sys.exit(1)

    dateObj = datetime.strptime(dateYMD, "%Y%m%d")
    dateDMY = datetime.strftime(dateObj, "%d%m%Y") # 01122018

    url = "https://e-services.judiciary.hk/dcl/view.jsp?lang=tc&date={}&court={}".format(dateDMY, code)
    print ("Parsing %s"% url)
    r = requests.get(url, headers = header)    
    text = r.text

    session = dm.init()
    cp.debug = True
    events = cp.parse(code, dateYMD, text)

if len(sys.argv) == 1: 
    hkt = pytz.timezone('Asia/Hong_Kong')
    dateObj = datetime.now().replace(tzinfo=hkt).date() - timedelta(days=1)
    dateDMY = datetime.strftime(dateObj, "%d%m%Y") # 01122018
    dateYMD = datetime.strftime(dateObj, "%Y%m%d")

    session = dm.init("sqlite:///data.sqlite")

    for code in codes:
        code = code.upper()

        url = "https://e-services.judiciary.hk/dcl/view.jsp?lang=tc&date={}&court={}".format(dateDMY, code)
        print ("Parsing %s"% url)
        r = requests.get(url, headers = header)
        
        text = r.text
        if len(text)==0: continue
        if "There is no hearing on this day" in text: continue    

        try:
            events = cp.parse(code, dateYMD, r.text, hide_parties=True)
            print ("Events parsed from %s %s: %d"%(code, dateYMD, len(events)))
        except Exception as e:
            print("Fail parsing %s %s"%(code, dateYMD))
            print(e)