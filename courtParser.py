import sys
from glob import glob
from bs4 import BeautifulSoup
from extractor import Extractor
import re
import dataModel as dm
from collections import OrderedDict
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

# ============================================
# About the logic flow
# ============================================
# The entry point is def parse(...)
# It runs a simple state machine, 
# depending on current state it calls different subfunctions:
#   find_header
#   find_metadata
#   read_row
#   etc.
#
# Depending on the court type, different state machine is used
# this is specified by transit_map

debug = False
def showParseErr(msg):
    if debug:
        raise ValueError(msg)
    else:
        print ("ParseError: ", msg)

# States
FIND_METADATA        = 0
FIND_METADATA_MAG    = 1
FIND_METADATA_FMC_SP = 2
FIND_HEADER          = 3
READ_ROW             = 4

# transit[currentState][retVal] = nextState
#2metadata + 4column
transit_2M_4C = {
    FIND_METADATA: { 0 : FIND_METADATA, 1 : FIND_HEADER   , },
    FIND_HEADER  : { 0 : FIND_HEADER  , 1 : READ_ROW      , },
    READ_ROW     : { 0 : READ_ROW     , 1 : FIND_METADATA , },
}

#7column
transit_7C = {
    FIND_HEADER  : { 0 : FIND_HEADER  , 1 : READ_ROW      , },
    READ_ROW     : { 0 : READ_ROW     , 1 : FIND_HEADER , },
}

#2metadata(MAGISTRATES'COURTS) + 5column
transit_2M_5C = {
    FIND_METADATA_MAG: { 0 : FIND_METADATA_MAG, 1 : FIND_HEADER       , },
    FIND_HEADER      : { 0 : FIND_HEADER      , 1 : READ_ROW          , },
    READ_ROW         : { 0 : READ_ROW         , 1 : FIND_METADATA_MAG , },
}

#FMC
transit_FMC = {
    FIND_HEADER          : { 0 : FIND_HEADER          , 1 : READ_ROW             , },
    READ_ROW             : { 0 : READ_ROW             , 1 : FIND_METADATA_FMC_SP , },
    FIND_METADATA_FMC_SP : { 0 : FIND_METADATA_FMC_SP , 1 : FIND_HEADER          , },
}

#The transit table and init action to use for each court type
transit_map = {
    "BP"    : (transit_2M_4C, FIND_METADATA),
    "CLCMC" : (transit_2M_4C, FIND_METADATA),
    "CRHPI" : (transit_2M_4C, FIND_METADATA),
    "CWUP"  : (transit_2M_4C, FIND_METADATA),
    "MIA"   : (transit_2M_4C, FIND_METADATA),
    "O14"   : (transit_2M_4C, FIND_METADATA),
    "OTD"   : (transit_2M_4C, FIND_METADATA),
    "CLPI"  : (transit_2M_4C, FIND_METADATA),
    "MCL"   : (transit_2M_4C, FIND_METADATA),

    "CACFI" : (transit_7C   , FIND_HEADER)  ,
    "CFA"   : (transit_7C   , FIND_HEADER)  ,
    "CT"    : (transit_7C   , FIND_HEADER)  ,
    "DC"    : (transit_7C   , FIND_HEADER)  ,
    "DCMC"  : (transit_7C   , FIND_HEADER)  ,
    "HCMC"  : (transit_7C   , FIND_HEADER)  ,
    "LANDS" : (transit_7C   , FIND_HEADER)  ,
    "DCMC"  : (transit_7C   , FIND_HEADER)  ,
    "FMC"   : (transit_FMC  , FIND_HEADER)  ,
    "ETNMAG": (transit_2M_5C   , FIND_METADATA_MAG)  ,
    "FLMAG" : (transit_2M_5C   , FIND_METADATA_MAG)  ,
    "KCMAG" : (transit_2M_5C   , FIND_METADATA_MAG)  ,
    "KTMAG" : (transit_2M_5C   , FIND_METADATA_MAG)  ,
    "STMAG" : (transit_2M_5C   , FIND_METADATA_MAG)  ,
    "TMMAG" : (transit_2M_5C   , FIND_METADATA_MAG)  ,
    "WKMAG" : (transit_2M_5C   , FIND_METADATA_MAG)  ,
}

# ============================================
# Utils func
# ============================================
def rmAllSpace(s):
    """
    remove all space
    """
    s = s.strip()
    s = re.sub("[\s]+","", s)
    return s

def rmDupSpace(s):
    """
    duplicate space to single space
    """
    s = s.strip()
    s = re.sub("[\s]+"," ", s)
    return s

def rmPS(s):
    """
    remove * #, i.e. marks used for P.S.
    """
    s = re.sub("[*#]+","", s)
    return s

def rmEn(s):
    """
    remove all Eng
    """
    s = re.sub('[A-Za-z]', '', s)
    return s

def rmDupElems(l):
    """
    See https://stackoverflow.com/questions/7961363/removing-duplicates-in-lists
    """
    return list(OrderedDict.fromkeys(l))

def rmNeighborDupElems(l):
    """
    [1,1,2,3,1] -> [1,2,3,1]
    """
    l = l.copy()
    idx = 1
    while idx<len(l):
        if l[idx]==l[idx-1]:
            l.pop(idx)
        else:
            idx+=1
    return l

def detectLang(s):
    s = s.strip()
    if s=="": return "nil"

    nonNumerical = re.sub('[][/()\-.0-9IV\"\'〔〕《》（）’ˇＩ\s]', '', s)
    if len(nonNumerical)==0: return "num"

    # 27(a) 104A 8A(1) 16CA(1)etc.
    if re.fullmatch("[0-9]{1,3}[A-Z]{0,2}[\s(]?[0-9A-Za-z]{1,2}[)\s]?", s): return "num"

    # 25mm 10km etc.
    if re.fullmatch("[0-9]{1,4}[\s(]*(mm|cm|m|km)?[)\s]*", s): return "num"

    nonEnChar = re.sub('[][!@#$%^&*/()\+-.\'\"〔〕《》（）’ˇ:,A-Za-z0-9\s]', '', s)
    if len(nonEnChar)==0: 
        if len(s)<=3 and s.upper() not in ["THE","AND","BUT","AN","CRB"]:
            return "num"  ## "P" in "P"牌, DVD, OK, etc    
        else:
            return "en"
    return "zh"
    
def getLangPairs(inList, mergeSameLang = False):
    """
    inList is a list of string
    returns list of ("中","en") tuple

    eg.
    In [23]: getLangPair( ["呂羅律師", "事務所", "Lui & Law", "貝克.麥堅時律師事務所","Baker & McKenzie"], mergeSameLang=True)
    Out[23]: [('呂羅律師事務所', 'Lui & Law'), ('貝克.麥堅時律師事務所', 'Baker & McKenzie')]
    
    In [24]: getLangPair( ["Lui & Law", "Baker & McKenzie"])
    Out[24]: [(None, 'Lui & Law'), (None, 'Baker & McKenzie')]
    """
    l = inList.copy()
    l = [s.strip() for s in l]
    
    # merge nearby same lang tokens
    pos = 1
    while pos<len(l):
        if l[pos]=="":
            pos += 2
            continue
        langA = detectLang(l[pos])
        langB = detectLang(l[pos-1])
        if langA=="num" or langB=="num":
            l[pos-1] += l[pos]
            del l[pos]
            continue
        if mergeSameLang and (langA == langB == 'zh'):
            l[pos-1] += l[pos]
            del l[pos]
            continue
        if mergeSameLang and (langA == langB == 'en'):
            l[pos-1] += " " + l[pos] #if eng add space between merge
            del l[pos]
            continue
        pos +=1
    
    # search zh,en pairs
    output = []
    while l:
        if (l[0]==""):
            l.pop(0)
            continue

        lang0 = detectLang(l[0])
        if lang0=='en':
            output.append( (None, l[0]) )
            l.pop(0)
        elif lang0=='zh':
            if len(l)>=2 and detectLang(l[1])=='en':
                output.append( (l[0], l[1]) )
                l.pop(0)
                l.pop(0)
            else:
                output.append( (l[0], None) )
                l.pop(0)
        else:
            #Should not reach here
            # showParseErr("getLangPairs error: %s" % l)
            l.pop(0)
    if debug: 
        print ("form pair")
        print (inList)
        print (output)
    return output

def getDefaultTags(cat):
    cat = cat.upper()
    d = {
        'OTD'   : dm.Tag.get_or_create_zh_or_en(name_zh=u"反對自動解除破產"     , name_en="Objections to discharge"),
        'MIA'   : dm.Tag.get_or_create_zh_or_en(name_zh=u"有關無力償還的雜項申請", name_en="Miscellaneous Insolvency Application"),
        'O14'   : dm.Tag.get_or_create_zh_or_en(name_zh=u"簡易判決"     , name_en="O.14 List"),
        'BP'    : dm.Tag.get_or_create_zh_or_en(name_zh=u"破產呈請"     , name_en="Bankruptcy Petition"),
        'CLCMC' : dm.Tag.get_or_create_zh_or_en(name_zh=u"核對列表聆訊/案件管理會議"     , name_en="Check List/Case Management Conference"),
        'CRHPI' : dm.Tag.get_or_create_zh_or_en(name_zh=u"核對列表審核聆訊 (人身傷亡案件)"     , name_en="Checklist Review Hearing(PI Cases)"),
        'CWUP'  : dm.Tag.get_or_create_zh_or_en(name_zh=u"公司清盤呈請"     , name_en="Companies Winding-Up Petition"),
        'LB'    : dm.Tag.get_or_create_zh_or_en(name_zh=u"勞資審裁處"     , name_en="Labour Tribunal"),
    }
    if cat in d: return [d[cat]]
    return []

#===========================================
# The entry point of courtParser
# For 1st read, I recommend
# read the main body first then the subfunctions
#===========================================
def parse(cat, date, text, hide_parties=True):
    """
    cat: FMC CFA etc
    date: yyyymmdd
    text: html text to parse
    hide_parties: to hide suer/defendent names or not
    """

    #"Global vars", their values can be updated in the subfunctions of def parse(...)

    #cat = None
    court = None
    judges = []
    cases = []
    #date = None
    time = None
    parties = None
    parties_atk = None
    parties_def = None
    tags = []
    lawyers = []
    lawyers_atk = []
    lawyers_def = []

    headers = []
    caseColIdx = 0
    rowsRead = 0

    #===========================================
    # sub functions to be called in the state machine loop
    #===========================================
    def find_metadata():
        nonlocal it
        nonlocal ir
        nonlocal court
        nonlocal judges

        row = tables[it][ir]
        
        found = False
        for cell in row:
            if cell.get_text().strip()[:2] == u"法庭":
                found = True
                break        
        if not found: return 0

        for cell in row:
            s = cell.get_text().strip()

            #match court
            match = re.findall("Court No.[\s]*:[\s]*(?P<target>[A-Za-z0-9.\s]+)", s)
            if len(match)>0:
                court = rmAllSpace(match[0])
                continue

            #match lawyer
            match = re.findall("聆案官[\s]*:[\s]*(?P<name_zh>[\u4e00-\u9fff.\s]+)Master[\s]*:[\s]*(?P<name_en>[A-Za-z0-9.\s]+)", s)
            if len(match)>0:
                name_zh = rmAllSpace(match[0][0])
                name_en = rmDupSpace(match[0][1])
                judge = dm.Judge.get_or_create_zh_or_en(name_zh=name_zh, name_en=name_en)
                judges = [judge] 
                continue
        if debug: print (court, judge)
        return 1 # metadata found and parsed

    def find_metadata_mag():
        nonlocal it
        nonlocal ir
        nonlocal court
        nonlocal judges

        row = tables[it][ir]
        
        found = False
        ic = 0
        for ic,cell in enumerate(row):
            if rmAllSpace(cell.get_text())[:2] == u"法庭":
                found = True
                break        
        if not found: return 0
        
        cell = tables[it][ir][ic+2]
        s = cell.get_text().strip()

        #match court
        match = re.findall("(?P<target>No[A-Za-z0-9.\s]+)", s)
        if len(match)>0:
            court = rmAllSpace(match[0])
        else:
            showParseErr("Parse court failed: %s"%s)

        cell = tables[it][ir+1][ic+2]
        s = cell.get_text().strip()

        #match lawyer
        match = re.findall("(?P<name_zh>[\u4e00-\u9fff.,\s]+)(?P<name_en>[A-Za-z0-9.,\-\s]+)", s)
        if len(match)>0:
            name_zh = rmAllSpace(match[0][0])
            name_en = rmDupSpace(match[0][1])
            judge = dm.Judge.get_or_create_zh_or_en(name_zh=name_zh, name_en=name_en)
            judges = [judge] 
        elif s.strip("*")=="":
            # On ETNMAG_20180816.HTML, there is 
            # 裁判官 Magistrate : ********  
            judge = None
            judges = []
        else:
            showParseErr("Parse judge failed: %s"%s)
        if debug: print (court, judge)
        return 1 # metadata found and parsed

    def find_metadata_fmc_sp():
        nonlocal it
        nonlocal ir
        nonlocal court
        nonlocal judges

        row = tables[it][ir]
        
        found = False
        ic = 0
        for ic,cell in enumerate(row):
            if rmAllSpace(cell.get_text())[:2] == u"法庭":
                found = True
                break        
        if not found: return 0
        
        cell = tables[it][ir][ic]
        s = cell.get_text().strip()

        #match court
        match = re.findall("(?P<target>No[A-Za-z0-9.\s]+)", s)
        if len(match)>0:
            court = rmAllSpace(match[0])
        else:
            showParseErr("Parse court failed: %s"%s)

        #match lawyer
        pattern = "法官[\s]*:[\s]*(?P<name_zh>[\u4e00-\u9fff.,\s]+)" + \
                  "Judge[\s]*:[\s]*(?P<name_en>[A-Za-z0-9.,\-\s]+)"
        match = re.findall(pattern, s)
        if len(match)>0:
            name_zh = rmAllSpace(match[0][0])
            name_en = rmDupSpace(match[0][1])
            judge = dm.Judge.get_or_create_zh_or_en(name_zh=name_zh, name_en=name_en)
            judges = [judge] 
        else:
            showParseErr("Parse judge failed: %s"%s)
        if debug: print (court, judge)
        return 1 # metadata found and parsed

    def find_header():
        nonlocal it
        nonlocal ir
        nonlocal headers
        nonlocal rowsRead

        row = tables[it][ir]

        found = False
        for idx,cell in enumerate(row):
            tmp = cell.get_text().strip()
            if u"案件編號" in tmp or u"案件號碼" in tmp:
                found = True
                break        
        if not found: return 0
         
        headers = []
        for cell in row:
            headers.append( rmAllSpace( rmEn( cell.get_text() )))
        if debug: print(headers)
        rowsRead = 0 #reset no. of rows read
        return 1 
    
    def read_row():
        nonlocal it
        nonlocal ir
        nonlocal rowsRead
        nonlocal events

        #for court, time, judge, we reuse global val if this row don't provide them
        #and update global val if row do provide them
        nonlocal court
        nonlocal time
        nonlocal judges
        local_court  = None
        local_time   = None
        local_judges = []

        cases = []
        parties = []
        parties_atk = []
        parties_def = []
        tags = []
        lawyers = []
        lawyers_atk = []
        lawyers_def = []

        row = tables[it][ir]

        # find the mapping between this row's cell and the header
        # header_map[cellIdx] = the header for that cell
        header_map = [] 
        if len(row)==len(headers):
            #simple 1 to 1 map
            header_map = headers
        elif len(row)==len(rmNeighborDupElems(headers)):
            #probably some colspan=2 appeared at the header
            header_map = rmNeighborDupElems(headers)
        elif len(rmNeighborDupElems(row))==len(headers):
            #probably some colspan=2 appeared at the row
            tmp=-1 
            for i in range(0, len(row)):
                if i==0 or row[i]!=row[i-1]: tmp+=1
                header_map.append( headers[tmp] )

        if debug:
            print ("len", len(headers), len(row))
            print ("hm", header_map)
        
        caseColIdx = 0
        for idx,h in enumerate(header_map):
            if u"案件編號" in h or u"案件號碼" in h:
                caseColIdx = idx
                break        

        #check if row valid, valid row should have caseNo like: XXXX 1234/2017
        cell = row[caseColIdx]
        cell = cell.get_text().strip()
        caseNos = re.findall("(?P<caseNo>[A-Z]{2,4}[\s]*[0-9]*/[0-9]{4})", cell)
        if not caseNos and ((u"首次約見" in cell)  or (u"特别程序表" in cell )): caseNos = ["FCMC0000/0000"] # hack for FMC
        if debug: print (it,ir, caseNos, cell)
        if not caseNos: 
            if ir>=(nr-1) and rowsRead>0:
                return 1 #last row, job done
            else:
                return 0 #title row or empty row or row without caseNo, continue
        
        
        # the current row extends till we reach a row with nonempty caseNo
        # or a all empty row
        end_ir = ir+1
        for end_ir in range(ir+1, nr):
            row = tables[it][end_ir]
            cell = row[caseColIdx]
            cell = cell.get_text().strip()
            if len(cell)>0: 
                caseNosNext = re.findall("(?P<caseNo>[A-Z]{2,4}[\s]*[0-9]*/[0-9]{4})", cell)
                if debug: print("caseNos/next", caseNos, caseNosNext, caseNosNext!=caseNos)
                if caseNosNext!= caseNos: break
            if all([ cell.get_text().strip()=="" for cell in row]): break
            if end_ir+1==nr: end_ir=nr # ugly...  
            
        if debug: print("ir endir nr", ir, end_ir, nr)

        for ir in range(ir,end_ir):
            row = tables[it][ir]
            for idx,cell in enumerate(row):    
                header = header_map[idx]
                s = cell.get_text().strip() 
                if s=="": continue
                if s=="─": continue
                if s.strip("_")=="": continue
                # if debug: print (ir, header)

                if header==u"法庭":
                    match = []
                    if not match: match = ["The Court"] if "The Court" in s else []
                    if not match: match = ["Court of Final Appeal"] if "Court of Final Appeal" in s else []    
                    if not match: match = re.findall("Court[\s]*(?P<target>[A-Za-z0-9.\s]+)", s)
                    if not match: 
                        showParseErr('Error parsing court: %s'%s)
                        continue
                    court = rmAllSpace(match[0])

                elif header==u"法官" or header==u"法官/審裁處成員" or header==u"聆案官":
                    ps = [rmDupSpace(p.get_text()) for p in cell.find_all("p")]
                    langPairs = getLangPairs(ps, mergeSameLang=True)
                    
                    for pair in langPairs:
                        name_zh = rmPS(rmAllSpace(pair[0])) if pair[0] else None
                        name_en = rmPS(rmDupSpace(pair[1])) if pair[1] else None
                        judge = dm.Judge.get_or_create_zh_or_en(name_zh=name_zh, name_en=name_en)
                        local_judges.append(judge)

                elif header==u"時間":
                    match = re.findall("(?P<hh>[0-9]{1,2})[\s]*:[\s]*(?P<mm>[0-9]{1,2})[\s]*(?P<apm>[am|AM|pm|PM]*)",s)
                    if not match: 
                        showParseErr('Error parsing time: %s'%s)
                        continue
                    hh,mm,apm = match[0]
                    hh = int(hh)
                    mm = int(mm)
                    if 'pm' in apm.lower() and hh<12: hh+=12
                    time = "%02d%02d"%(hh,mm)
                
                elif header==u"案件編號" or header==u"案件號碼" or header==u"案件號碼/.":
                    caseNos = []
                    if not caseNos: caseNos = re.findall("(?P<caseNo>[A-Z]{2,4}[\s]*[0-9]*/[0-9]{4})", s)
                    if not caseNos: caseNos = ["FCMC0000/0000"] if (u"首次約見" in s) or (u"特别程序表" in s ) else []
                    if not caseNos: 
                        showParseErr('Error parsing caseNo: %s'%s)
                        continue

                    caseNos = [rmAllSpace(c) for c in caseNos]
                    
                    #chinese desciption of the caseNo, if avaialable
                    desc = re.findall("(?P<desc>[\u4e00-\u9fff.\s]+)", s)
                    desc = rmDupSpace(desc[0]) if desc else None
                    
                    for caseNo in caseNos:
                        case = dm.Case.get_or_create(caseNo=caseNo)
                        if desc and case.description==None: case.description = desc
                        cases.append(case)
                
                elif header==u"訴訟各方":
                    ps = [rmDupSpace(p.get_text()) for p in cell.find_all("p")]
                    
                    splitPos = None

                    # we can separate the parties to atk and def when...
                    # If just 1 'And' appear
                    andPos = [i for i,p in enumerate(ps) if (p=="AND" or p=="And")]
                    if len(andPos)==1 : splitPos = andPos[0] 

                    # If its a Criminal case where atk is gov
                    if rmAllSpace(ps[0])==u"HKSAR(香港特別行政區)v.": splitPos = 0

                    for i,p in enumerate(ps):
                        if (p=="AND" or p=="And"): continue
                        party = rmDupSpace( p.strip("RE:").strip("Re:").strip("v.") )
                        if splitPos is not None:
                            if i<=splitPos: 
                                parties_atk.append(party)
                            else: 
                                parties_def.append(party)
                        else:
                            parties.append(party)
                
                elif header==u"被告/答辯人/":
                    ps = [rmDupSpace(p.get_text()) for p in cell.find_all("p")]
                    for p in ps:
                        party = rmDupSpace(p)
                        parties_def.append(party)

                elif header==u"性質" or header==u"控罪/性質" or header==u"控罪/性質/" or header==u"聆訊":
                    ps = cell.find_all("p")
                    if len(ps)==1:
                        #sometimes they use <\br> instead of multiple <p> 
                        ps = ps[0].get_text("\n",True).split("\n") 
                    else:
                        ps = [p.get_text() for p in ps]
                    ps = [rmDupSpace(p) for p in ps]
                    if debug: print("ps@性質", ps)
                    langPairs = getLangPairs(ps, mergeSameLang=True)
                    
                    for pair in langPairs:
                        #removes (1) (2) 1. 2. etc. at start and end
                        tmp1 = "\([0-9]{1,2}\)"
                        tmp2 = "[0-9]{1,2}\."
                        pattern = "(^{0}|^{1}|{0}$|{1}$)".format(tmp1,tmp2)
                        name_zh = rmAllSpace(re.sub(pattern,"", pair[0])) if pair[0] else None
                        name_en = rmDupSpace(re.sub(pattern,"", pair[1])) if pair[1] else None

                        tag = dm.Tag.get_or_create_zh_or_en(name_zh=name_zh, name_en=name_en)
                        tags.append(tag)

                elif header==u"應訊代表":
                    ps = [rmDupSpace(p.get_text()) for p in cell.find_all("p")]

                    #strip away all text after "parties in person"
                    endPos = [i for i,p in enumerate(ps) if "parties in person" in p.lower()]
                    if len(endPos)>0 : ps = ps[0:endPos[0]]

                    # if debug: print("ps@應訊代表", ps)
                    langPairs = getLangPairs(ps)
                    
                    for pair in langPairs:
                        name_zh = pair[0] if pair[0] else None
                        name_en = pair[1] if pair[1] else None
                        lawyer = dm.Lawyer.get_or_create_zh_or_en(name_zh=name_zh, name_en=name_en)
                        lawyers.append(lawyer)

                elif header=="":
                    pass

                else:
                    showParseErr("Unknown header: %s" % header)

        # duplicates could occur if colspan=2 in table
        local_judges = rmDupElems(local_judges)
        cases        = rmDupElems(cases       )
        parties      = rmDupElems(parties     )
        parties_atk  = rmDupElems(parties_atk )
        parties_def  = rmDupElems(parties_def )
        tags         = rmDupElems(tags        )
        lawyers      = rmDupElems(lawyers     )
        lawyers_atk  = rmDupElems(lawyers_atk )
        lawyers_def  = rmDupElems(lawyers_def )

        if local_court : court  = local_court
        if local_time  : time   = local_time
        if local_judges: judges = local_judges
        
        # try to classify lawyer to atk / def side
        if parties_atk and parties_def and len(lawyers)==2:
            lawyers_atk = [ lawyers[0] ]
            lawyers_def = [ lawyers[1] ]
            lawyers = []
        elif parties_atk and not parties_def:
            lawyers_atk = lawyers
            lawyers = []
        elif not parties_atk and parties_def:
            lawyers_def = lawyers
            lawyers = []


        e = dm.Event()
        e.category = cat
        e.court = court
        e.judges = judges
        e.datetime = datetime.strptime(date+time, "%Y%m%d%H%M")
        e.cases = cases
        e.parties = "/".join(parties)
        e.parties_atk = "/".join(parties_atk)
        e.parties_def = "/".join(parties_def)
        e.tags = tags + getDefaultTags(cat)
        e.lawyers = lawyers
        e.lawyers_atk = lawyers_atk
        e.lawyers_def = lawyers_def

        if debug: 
            print("=====================")
            e.fullDesc()
            print("=====================")

        if hide_parties:
            if e.parties    : e.parties    ="hidden"
            if e.parties_atk: e.parties_atk="hidden"
            if e.parties_def: e.parties_def="hidden"

        try:
            dm.session.add(e)
            dm.session.commit()
        except SQLAlchemyError as err:
            print (err)
            dm.session.rollback()
            if debug: raise err

        events.append(e)

        rowsRead +=1
        if ir>=(nr-1) and rowsRead>0: 
            return 1 #last row in table, job done
        else:
            return 0 #continue read_row

    #===========================================
    # Main body of def parse(...)
    #===========================================
    soup = BeautifulSoup( text, 'html.parser')
    tables = soup.find_all('table')

    def explodeTable(t):
        extractor = Extractor( t )
        extractor.parse()
        return extractor.return_list()
    tables = [ explodeTable(t) for t in tables]

    transit, state = transit_map[cat.upper()]

    it = 0           #current table
    nt = len(tables) #total tables
    ir = 0           #current row
    nr = 0           #total rows

    events = []

    while it < nt:
        ir = 0
        nr = len(tables[it])
        while ir < nr:
            # print (state, ir , nr)
            if   state==FIND_METADATA       : ret = find_metadata()
            elif state==FIND_METADATA_MAG   : ret = find_metadata_mag()
            elif state==FIND_METADATA_FMC_SP: ret = find_metadata_fmc_sp()
            elif state==FIND_HEADER         : ret = find_header()
            elif state==READ_ROW            : ret = read_row() #would fill events
            state = transit[state][ret]
            ir+=1
        it+=1
    
    return events

if __name__=="__main__":
    print (sys.argv)
    debug = True
    # debug = False
    if len(sys.argv) == 3:
        code = sys.argv[1]
        date = sys.argv[2]
        filePath = "../data/{code}/{code}_{date}.HTML".format(code=code.upper(), date=date)

        f = open(filePath,'r')
        text = f.read()

        session = dm.init()
        events = parse(code, date, text)
    
    if len(sys.argv) == 1:
        from glob import glob

        debug = False

        session = dm.init("sqlite:///data_test9.sqlite")

        codes = transit_map.keys()
        for code in codes:
            code = code.upper()
            files = glob("../data/{code}/{code}_*.HTML".format(code=code.upper()))
            files.sort()
            # files = files[:1]
            for filePath in files:
                print(filePath)
                dateYMD = re.findall("[0-9]{8}",filePath)[0]
                f = open(filePath,'r')
                text = f.read()
                if len(text)==0: continue
                if "There is no hearing on this day" in text: continue    
                
                events = parse(code, dateYMD, text)

                whiteList = [
                    "../data/BP/BP_20180912.HTML", #Judge name hidden in title
                    "../data/FLMAG/FLMAG_20181103.HTML", #really have no cases
                ]
                print ("Events parsed from %s : %d"%(filePath, len(events)))

                if not events and filePath not in whiteList and "MAG" not in code: 
                    showParseErr("No event parsed")
