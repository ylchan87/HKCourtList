This is a scraper that runs on [Morph](https://morph.io). To get started [see the documentation](https://morph.io/documentation)

# HK Court Lists Archive

## What the code do
This repo scrap HK court cases from
https://e-services.judiciary.hk/dcl/index.jsp?lang=en

This repositry is a prototype for the one of the projects pitched in the [first g0vhk.io Hackathon on 2018-06-23](https://beta.hackfoldr.org/g0vhk1st/) in Hong Kong. The main document written by project owner, Selina, listed the details in this [Hackpad](https://hackpad.tw/HK-Court-Lists-Archive-e6DAOVBLRoh). Please go and read.

The scraped data can be found at https://morph.io/ylchan87/HKCourtList

## Files
`scraper.py`

the scraper, get called by morph.io, makes http request and parse the reply with `courtParser.py`

`courtParser.py`

parse the html to get the fields and save to database, as defined by `dataModel.py`

`dataModel.py`

the sqlAlchemy data model for the court cases

`extractor.py`

util to explodes a html table to a python list of list (i.e. 2D array)

`testTableExtract.py`

test script to test extractor.py

## About the data model

### Event
a row in the court's timetable, the "main" table of the SQL DB

### Case
Case no. uniquely identifying a case
A case can have many events (when there's multiple hearings and trials)
An event can deal with multiple cases at the same time

many-to-many relationship with event

### Judge
many-to-many relationship with event

### Lawyer
many-to-many relationship with event

### Tag
Could be
Offence nature of the event (theft, robbery, etc)
Procedure type of the event (trail, hearing, mention, summon etc)

many-to-many relationship with event
