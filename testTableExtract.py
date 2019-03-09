import sys
from glob import glob
from bs4 import BeautifulSoup
from extractor import Extractor

print (sys.argv)


FIND_METADATA = 0
FIND_HEADER   = 1
READ_ROW      = 2

if len(sys.argv) == 2:
    f = open(sys.argv[1],'r')
    text = f.read()

    soup = BeautifulSoup( text, 'html.parser')
    tables = soup.find_all('table')
    
    contents = []
    for table in tables:
        extractor = Extractor( table )
        extractor.parse()
        content = extractor.return_list()
        
        if content != []:
            contents.append(content)


if len(sys.argv) == 1:
    codes = ["cfa","cacfi","hcmc","mcl","bp","clpi","clcmc","crhpi","cwup","mia","otd","o14","ct","lands","dc","dcmc","etnmag","kcmag","ktmag","wkmag","stmag","flmag","tmmag","crc","lt","smt","oat"]
    special_codes = ['fmc'] # TODO handle this

    # codes = codes + special_codes

    variations = {}

    for code in codes:
        print(code)
        files = glob("../data/%s/*.HTML"%code.upper())
        files.sort()
        files = files[:100]
        for afile in files:
            f = open(afile,'r')
            text = f.read()

            soup = BeautifulSoup( text, 'html.parser')
            tables = soup.find_all('table')

            for table in tables:
                if "案件編號" in str(table) or "案件號碼" in str(table):
                    extractor = Extractor( table )
                    extractor.parse()
                    headerTable = extractor.return_list()
                    
                    for i in range(0,len(headerTable)):
                        if (''.join(headerTable[i])).find(u'案件號碼') != -1 or (''.join(headerTable[i])).find(u'案件編號') != -1:
                            headers = headerTable[i]
                    headersStr = str(headers)
                    try:
                        variations[headersStr] += 1
                    except KeyError as e:
                        variations[headersStr] = 1
                        print(afile)
                        print(headers)



    
            

