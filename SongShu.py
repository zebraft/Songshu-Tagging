from Book2 import Book 
from collections import defaultdict
from bs4 import BeautifulSoup, NavigableString
import bs4
from urllib import request
import urllib
import time, os, glob
import random
import re
import logging
import hashlib
from zhon import hanzi
from copy import deepcopy
from Surname import Surname

### Some "global variables" defined outside the class
#CJK_DIGIT  = r'元一二三四五六七八九十'
ONE_TO_99 = r'(?:[二三四五六七八九]?十[一二三四五六七八九]|[元一二三四五六七八九十])年' # expression to match era years 1-99
MONTH_EXPR = r'閏?(?:十[一二]?|[元一二三四五六七八九])月'
DAY_EXPR   = r'(?:三十|二?十[一二三四五六七八九]|[一二三四五六七八九十])日'
SEASON     = r'[春夏秋冬]'
GANZHI     = r'甲子|乙丑|丙寅|丁卯|戊辰|己巳|庚午|辛未|壬申|癸酉|甲戌|乙亥|丙子|丁丑|戊寅|己卯|庚辰|辛巳|壬午|癸未|甲申|乙酉|丙戌|丁亥|戊子|己丑|庚寅|辛卯|壬辰|癸巳|甲午|乙未|丙申|丁酉|戊戌|己亥|庚子|辛丑|壬寅|癸卯|甲辰|乙巳|丙午|丁未|戊申|己酉|庚戌|辛亥|壬子|癸丑|甲寅|乙卯|丙辰|丁巳|戊午|己未|庚申|辛酉|壬戌|癸亥'
# Eastern Jin and Liu Song era names:  東漢（漢獻帝）, 魏, 吳, 蜀, 西晉, 東晉, 劉宋
ERA_NAME   = '永漢|中平|初平|興平|建安|延康|' + \
            '黃初|太和|青龍|景初|正始|嘉平|正元|甘露|景元|咸熙|' + \
            '黃武|黃龍|嘉禾|赤烏|太元|神鳳|建興|五鳳|太平|永安|元興|甘露|寶鼎|建衡|鳳凰|天鍹|天璽|天紀|' + \
            '章武|建興|延熙|景耀|炎興|' + \
            '泰始|咸寧|太康|太熙|永熙|永平|元康|永康|永寧|太安|永安|建武|永安|永興|光熙|永嘉|建興|' + \
            '建武|太興|永昌|太寧|咸和|咸康|建元|永和|昇平|隆和|興寧|太和|咸安|寧康|太元|隆安|元興|義熙|元熙|' + \
            '永初|景平|元嘉|太初|孝建|大明|永光|景和|泰始|泰豫|元徽|昇明' # 劉宋

re_yy      = fr"(?:(?:{ERA_NAME})?{ONE_TO_99}{SEASON}?)"
re_mm      = fr"{re_yy}?(?:{MONTH_EXPR})(?:{GANZHI})?"
re_dd      = fr"{re_mm}?(?:{DAY_EXPR})"
regex_date = re.compile(fr"(?P<date>{re_dd}|{re_mm}|{re_yy})")

## If one of these family relationships is present as 'b' in the triple (a, b, c),
## then a and c should have the same surname
## used in normalizeName1()
FAMILY_SAME_SURNAME = (r'從父弟|從祖弟|長子|中子|少子|兄子|族弟|次弟|嗣孫|' + \
                       r'從弟|長兄|嗣子|嗣孫|從兄|從叔|伯父|子|父|兄|弟|祖|孫').split('|')

# These are the non-prince biographical entries (列傳) in Songshu
VALID_BIO_FILENOS = list(range(597,654)) + list(range(664,714)) + list(range(722,751)) + \
                    list(range(755,761)) + list(range(755,761)) + list(range(774, 798))

# regex for a MD5-hashed expression
regex_md5hashed = re.compile(r"[0-9a-f]{32}")

# Initialize a global variable sur to provide the function split_name()
sur = Surname()
#split_name = sur.split_name

def hashstr(txt, hash_func=hashlib.md5):
    '''
    Generate a hash hex string from string 'txt' using the hash function 'hash_func'
    '''
    return hash_func(txt.encode()).hexdigest()



class SongShu(Book):
    """SongShu Dataset
    
    Attributes:
        flat_meta : a list of bookmarks in SonShu extracted from Han-Ji
        flat_passages : a list of ``passages`` in SongShu. 
            Each ``passages`` contain a list of passage in a piece of work.
            i.e., flat_passages = [passages1(list, passages2(list), ...]
                  passages1 = [passage1(str), passage2(str), ...]    
                  
    Args: same as Book class
    
    Methods:
        extract_meta(): Extract meta data from self.paths. Index 3 in path for scroll, 4 for category, 5 for author name, after 5 for the title. The method would check the author name using author_bag automatically.    
        extract_passages(): Extract passages based on indent==2 & padding==0. 
                            If there's no passage in this page, merge all texts into one string.
    """




    
    def __init__(self, date, creator):
        Book.__init__(self, 'SongShu', date, creator)
        self.BOOKSIZE = 0
        self.paths_cleaned = []
        self.RSTR2NE = {}
        self.RSTR2CAT = {}
        self.NE_SORTED = []
        self.NE = {}
        self.fullnames = []
        self.BOOKMARK_PERSONS = []
        self.TE2HASH = {}  # dict to store all time expressions: key=time expr; val=MD5 hash
        self.HASH2TE = {}  # dict to store all time expressions: key=MD5 hash; val=time expr
    
    def load_htmls(self, path):
        super().load_htmls(path=path)
        BOOKSIZE = len(self.flat_bodies) # no. of HTML files in the book
        self.BOOKSIZE = BOOKSIZE
        self.fullnames = [set() for j in range(BOOKSIZE)]
        # Create a list to hold all person names extracted from the bookmarks
        self.BOOKMARK_PERSONS = [[] for k in range(BOOKSIZE)]
        # Create a clean list of bookmarks (without the page numbers and sources)
        self.paths_cleaned = [None for k in range(BOOKSIZE)]

    def extract_all(self, DEBUG=False):
        self.update_rare_chars()
        self.strip_all_irrelevant_tags()

        # preprocessing the songshu data to get metadata and bookmarks
        # and separate the passages in every pages
        self.extract_paths()
        self.extract_meta()
        self.extract_passages()
        self.__repr__()
        print('Removing bookmarks from main text...')
        self.removeBookmarks()
        if DEBUG: return # skip the following
        print('Extracting full person names based on Global NE List...')
        self.extractFullNamesAll()
        print('Getting all person names from bookmarks...')
        self.getBookmarkNamesAll()
        print('Normalizing all person names bookmarks...')
        self.normalizeBookmarkNamesAll()
        print('Combining all person names (global list and bookmarks)...')
        self.collectPersonNamesAll()

    def extract_meta(self):
        self.flat_meta = []
        for path in self.paths:
            meta = {}
            bookmark_split = path.split('／')

            # Navie implementation
            category = bookmark_split[3].split('\u3000')[0] # 本紀、志、列傳
            scroll   = bookmark_split[4].split('\u3000')[0] # 卷 N 
            categrory_number   = bookmark_split[4].split('\u3000')[1] # 本紀第 N 
            title = '/'.join(bookmark_split[5:]).replace('..[底本：宋元明三朝遞修本]', '')
            meta['category'] = category
            meta['category_number'] = categrory_number
            meta['scroll'] = scroll
            meta['title']  = title
            self.flat_meta.append(meta)

    def extract_passages(self):
        '''Extract passages from SongShu, which divided by the ( indent == 2 & padding == 0 )'''
        self.flat_passages = []

        for body,path in zip(self.flat_bodies, self.paths):
            texts  = body.find_all('div', attrs={'style': True})
            try:
                self.flat_passages.append(
                    self._passage2paragraphs(texts)
                )
            except IndexError as e:
                logging.warning("Not the right indent.{}".format(path))
                self.flat_passages.append(
                    ''.join([text.text for text in texts])
                )


    def _passage2paragraphs(self, texts):
        '''Organize a passage with its paragraph, which is defined using ( indent == 2& padding == 0 )
        '''
        # concatenent the paragraphs with indents not equal to 2 to the previous paragraph
        new_texts = []
        
        # get the pairs of indents and paddings 
        indent_padding_list = self._indent_and_padding(texts)
        
        for text, (indent, padding) in zip(texts, indent_padding_list):
            if indent == 2 and padding == 0:
                # only save the text, without tags
                new_texts.append(
                    ''.join([s for s in text if isinstance(s, bs4.NavigableString)])
                )
            else:
                new_texts[-1] += ''.join([s for s in text if isinstance(s, bs4.NavigableString)])
            
        return new_texts   


    def test(self, txt):
        return None
        
    def buildDictionaries(self, dictSource):
    
        self.NE_SORTED = []
        with open(dictSource, 'r', encoding='utf-8') as fi:
            for line in fi:
                (s, category, rstr) = (None, None, None) # NE, category, random string
                try:
                    (s, category, rstr) = line.strip().split()
                    self.NE_SORTED.append((s, rstr))
                except:
                    print(f"problem: {s}")
                    pass
                if rstr in self.RSTR2NE:
                    print(f"repeated: {rstr}")
                else:
                    self.RSTR2NE[rstr]  = s
                    self.RSTR2CAT[rstr] = category
                    self.NE[s] = category
                    
                        
    def tagEncode(self, txt): # encode text with random string
        '''
        Tag txt with  
        '''
        for (s, rstr) in self.NE_SORTED:
            if s in txt:
                txt = txt.replace(s, rstr)
        return txt    
    
    def tagDecode(self, txt): # encode text with random string
        '''
        Turn random string back into original NE,
        but tagged with appropriate XML tag
        '''
        for k in self.RSTR2NE.keys():
            if k in txt:
                txt = txt.replace(k, f"<{self.RSTR2CAT[k]}>{self.RSTR2NE[k]}</{self.RSTR2CAT[k]}>")
        return txt
        
        
    def tagFamilyMembersFromBookmark(self, txt, bookmark):
        '''
        This module attempts to tag 'txt' using info from 'bookmark'
        '''
        return txt

    def extractFullNamesFromBookmark(self, fileno):
        '''
        Extract full names from the bookmarks based on Global List
        '''
        FullNames = set()
        regex_clean_bookmark1 = re.compile(r"\(P\.\d+\)\.\.\[底本.+?\]$")  # (P.nnnn)..[底本：宋元明三朝遞修本]
        txt = regex_clean_bookmark1.sub('', self.paths[fileno])
        self.paths_cleaned[fileno] = txt  # save 'cleaned' bookmarks (for later use)
        for (s, rstr) in self.NE_SORTED:
            if s in txt:
                txt = txt.replace(s, rstr)
                FullNames.add(s)
        return FullNames

    def extractFullNamesFromMainText(self, fileno):
        '''
        Extract full names from the main texts based on Global List
        '''
        FullNames = set()
        txt = self.flat_bodies[fileno].text
        for (s, rstr) in self.NE_SORTED:
            if s in txt:
                txt = txt.replace(s, rstr)
                if self.RSTR2CAT[rstr]=='person':
                    FullNames.add(s)
        return FullNames

    def extractFullNames(self, fileno):
        '''
        Combines the results from the above two methods
        '''
        self.fullnames[fileno] = self.extractFullNamesFromMainText(fileno).union( \
                                 self.extractFullNamesFromBookmark(fileno))


    def extractFullNamesAll(self):
        for fileno in range(self.BOOKSIZE):
            self.extractFullNames(fileno)

    ## This function attempts to tag persons that appear only as given names
    ##   in the text, based on information from self.fullnames[]
    def tagGivenNames(self, fileno, txt, DEBUG=False):
        tagged2 = txt
        for entry in self.fullnames[fileno]:
            if DEBUG: print(f"DEBUG: entry = {entry}")
            try:
                (sur0, giv0) = sur.split_name(entry)
                #if DEBUG: print(f"DEBUG2: sur0 = {sur0}, giv0 = {giv0}")
                if giv0 in txt:
                    if DEBUG: print(f"DEBUG2: entry = {entry}, sur0 = {sur0}, giv0 = {giv0}")
                    tagged2 = tagged2.replace(giv0, f"<person id='{entry}'>{giv0}</person>")
            except:
                print(f"Unable to split this name: {entry}")
            
        return tagged2
        #return self.tagDecode(tagged2)


    def removeBookmarks(self):
        '''
        Remove bookmark from the main text of each HTML (to prevent the bookmark from being tagged)
        '''
        for soup in self.flat_bodies:
            # extract "gobookmark" class
            path  = soup.find('a', attrs={'class', 'gobookmark'})
            if path: path.extract()


    ## Functions to extract all person names (some full names, 
    ## same given names only) and turn them all into full names

    def getProtagonists(self, bookmark, START_COLUMN=7, DEBUG=False):
        '''
        Extract names from bookmark - used by getBookmarkNames() below
        '''
        regex_delim = re.compile(r'[／\u3000]')
        family = r"(從父弟|從祖弟|長子|中子|少子|女婿|兄子|族弟|次弟|嗣孫|從弟|長兄|嗣子|嗣孫|從兄|從叔|伯父|子|父|兄|弟|祖|孫|妻)"
        regex_family = re.compile(f"(伯子|荀伯子|[^嗣從長中少兄弟子伯次族]+)?{family}([^族弟]+)")
        M = START_COLUMN ## this is the index where the first peron name appears

        if DEBUG: print(fr"Input bookmark = [{bookmark}]")

        CANDIDATES = []
        # Step (1) parse bookmark to get a list of "persons"
        fields = regex_delim.split(bookmark)
        if DEBUG: print(f"DEBUG: fields={fields[M:]}")  
        if len(fields) == M+1:  # there's only one person name in bookmark
            CANDIDATES.append(fields[M])
        else:
            for f in fields[M:]:
                stuff = regex_family.findall(f) # parse family relationship and name(s)
                if stuff: # if there's a match (we'll assume there's at most one match)
                    CANDIDATES.append(list(stuff[0]))  # add the triple to CANDIDATES as a list
                else:
                    CANDIDATES.append(f) # if there's no such family-relationship match, it's just a name
            
        return CANDIDATES

    def getBookmarkNames(self, fileno, DEBUG=False):
        '''
        Example -
        Input:   史／正史／宋書／列傳\u3000凡六十卷／卷四十二\u3000列傳第二／劉穆之／長子慮之\u3000慮之子邕
        Output:  ['劉穆之', ['', '長子', '慮之'], ['慮之', '子', '邕']]
        '''
        if DEBUG: print(fileno)
        self.BOOKMARK_PERSONS[fileno] = []
        res = self.getProtagonists(self.paths_cleaned[fileno], DEBUG=DEBUG)
        if len(res)>1:
            if DEBUG: print(self.paths_cleaned[fileno])
            if DEBUG: print(res)
        self.BOOKMARK_PERSONS[fileno].extend(res)
        if DEBUG: print('-'*20)


    def getBookmarkNamesAll(self, DEBUG=False):
        '''
        Run getBookmarkNames() above for entire book
        '''
        for fileno in range(self.BOOKSIZE):
            self.getBookmarkNames(fileno)


    def FillMissingRelatives(self, fileno, DEBUG=False):
        '''
        For each triple [a, b, c], where b is a family relationship,
        if a is '' (empty string), find an appropriate value for it.
        
        Input:  ['朱齡石', ['', '父', '綽'], ['', '弟', '超石']]
        Output: ['朱齡石', ['朱齡石', '父', '綽'], ['朱齡石', '弟', '超石']]
        '''
        names_list = deepcopy(self.BOOKMARK_PERSONS[fileno])  # create a copy
        refPerson = names_list[0]  # this is the first named (reference) person in the bookmark
        # now process the remaining entries in the list
        for idx, entry in enumerate(names_list): # check the rest
            if DEBUG: print(f"[{idx}] {entry}")
            if idx == 0: continue # skip the first entry (always a leaf node)
            if type(entry) is list: # an [a,b,c] triple
                if entry[0] == '': # missing relative
                    entry[0] = refPerson
            else: # leaf 
                refPerson = names_list[idx]  # change of reference person!
                pass

        self.BOOKMARK_PERSONS[fileno] = names_list  # remove comment when debugged
        return names_list

    def normalizeName1(self, fileno, DEBUG=False):
        '''
        For each triple [a, b, c], where 'b' is a family relationship,
        if 'a' is '' (empty string), find an appropriate value for it
        Example 1 -
        Input:  ['垣護之', ['垣護之', '伯父', '遵'], ['垣護之', '父', '苗'], ['垣護之', '弟', '詢之']]
        Output: ['垣護之', ['垣護之', '伯父', '垣遵'], ['垣護之', '父', '垣苗'], ['垣護之', '弟', '垣詢之']]
        Example 2 -
        Input:  ['張邵', ['張邵', '兄子', '暢'], ['暢', '弟', '悅'], ['暢', '子', '淹']]
        Output: ['張邵', ['張邵', '兄子', '張暢'], ['張暢', '弟', '張悅'], ['張暢', '子', '張淹']]
        Exmple 3 (Songshu HTML 794 onwards)
            [0] ['蕭思話', ['', '父', '源之'], '甄法護', ['', '子', '惠明']]
            [1] ['蕭思話', ['蕭思話', '父', '源之'], '甄法護', ['蕭思話', '子', '惠明']]  <=== WRONG!!!
            [2] ['蕭思話', ['蕭思話', '父', '蕭源之'], '甄法護', ['蕭思話', '子', '蕭惠明']]
            [3] ['蕭思話', ['蕭思話', '父', '蕭源之'], '甄法護', ['蕭思話', '子', '蕭惠明']]
            [4] ['蕭思話', ['蕭思話', '父', '蕭源之'], '甄法護', ['蕭思話', '子', '蕭惠明']]
        Algorithm:
        (1) Starting with first triple (a1, b1, c2)
        (2) if 'b' qualifies as same-surname:
                add surname of 'a' to 'c'
        (3a) for (a2, b2, c2), 
            if a2 == c2's given name:
                add surname of 'c2' to 'a2'
        (3b) Repeat (2) for (a2, b2, c2)
        (4) Repeat for (a3, b3, c3), etc. 
        Example: 
            (1) ['張邵', '兄子', '暢'], ['暢', '弟', '悅']]  
            (2) ['張邵', '兄子', '張暢'], ['暢', '弟', '悅']] 
            (3a) ['張邵', '兄子', '張暢'], ['張暢', '弟', '悅']] 
            (3b) ['張邵', '兄子', '張暢'], ['張暢', '弟', '張悅']] 
        '''

        names_list = deepcopy(self.BOOKMARK_PERSONS[fileno])  # create a copy
        refPerson = names_list[0]  # this is the first named (reference) person in the bookmark

        # now process the remaining entries in the list
        for idx, entry in enumerate(names_list): # check the rest
            if DEBUG: print(f"[{idx}] current_entry {entry}")
            if idx == 0: continue # skip the first entry (always a leaf node)
            previous_entry = names_list[idx-1]
            if DEBUG: print(f"[DEBUG] previous_entry = {previous_entry}")

            if type(entry) is list:
                # Step (3a)
                # First check if book.fullnames already has a full name that contains this given name
                surname_found = False
                # Check the 'c' of previous entry 
                if type(previous_entry) is list: # an [a,b,c] triple
                    if entry[0] == sur.split_name(previous_entry[2])[1]:  # equal to given name of previous entry
                        entry[0] = sur.split_name(previous_entry[2])[0] + entry[0]
                        surname_found = True
                        if DEBUG: print(f'[DEBUG] [updated entry[0]] = {entry[0]}')
                else: # previous_entry is a leaf node
                    if entry[0] == sur.split_name(previous_entry)[1]:  # equal to given name of previous entry
                        entry[0] = sur.split_name(previous_entry)[0] + entry[0]
                        surname_found = True
                        if DEBUG: print(f'[DEBUG] [updated entry[0]] = {entry[0]}')
                # 倒回去找 nearest full name 'a' in (a, b, c) (or just 'a') with this given name
                if not surname_found: # search book.fullnames
                    for j in range(idx, 0, -1): 
                        if type(names_list[j]) is list:
                            ref = names_list[j][0]
                        else:
                            ref = names_list[j]
                        if sur.split_name(ref)[1] == entry[0]:
                            entry[0] = sur.split_name(ref)[0] + entry[0]
                            surname_found = True
                            break
                if not surname_found: # search book.fullnames
                    for fullname in self.fullnames[fileno]:
                        (sur1, giv1) = sur.split_name(fullname)
                        if giv1 == entry[0]:
                            entry[0] = sur1 + entry[0]
                            surname_found = True
                #if not surname_found:
                #   print(f"[Error] Surname for {entry[0]} cannot be found!")
                # step (2)
                if entry[1] in FAMILY_SAME_SURNAME: # family relationship
                    try:
                        if sur.split_name(entry[0])[0] != sur.split_name(entry[2])[0]:
                            entry[2] = sur.split_name(entry[0])[0] + entry[2] # add surname to it
                    except:
                        if DEBUG: print(f"[DEBUG] {entry[0]} can't be split?")
                    if DEBUG: print(f'[DEBUG] [updated entry[2]] = {entry[2]}')
            else: # lead node
                #refPerson = names_list[idx]
                pass
                
        self.BOOKMARK_PERSONS[fileno] = names_list  # remove comment when debugged
        return names_list


    def normalizeName2(self, fileno, DEBUG=False):
        # Takes care of these cases
        # 649
        #['劉康祖', ['劉康祖', '伯父', '簡之'], '謙之', ['劉康祖', '父', '虔之']]
        # ['劉康祖', ['劉康祖', '伯父', '劉簡之'], '謙之', ['劉康祖', '父', '劉虔之']]
        # 682
        # ['孔季恭', ['孔季恭', '子', '山士'], '靈符', ['靈符', '子', '淵之']]
        # ['孔季恭', ['孔季恭', '子', '孔山士'], '靈符', ['靈符', '子', '淵之']]
        # 702
        # ['殷淳', ['殷淳', '弟', '沖'], '淡']
        # ['殷淳', ['殷淳', '弟', '殷沖'], '淡']
        # 731
        # ['沈演之', ['沈演之', '父', '叔任'], ['沈演之', '子', '睦'], '勃', '統']
        # ['沈演之', ['沈演之', '父', '沈叔任'], ['沈演之', '子', '沈睦'], '勃', '統']
        # 776
        # ['顏延之', ['顏延之', '子', '測'], '㚟']
        # ['顏延之', ['顏延之', '子', '顏測'], '㚟']

        names_list = deepcopy(self.BOOKMARK_PERSONS[fileno])  # create a copy
        SPREAD_ORIGIN = r'子|弟|伯父'.split('|')
        Potential_Spread = {} # key - idx, val - list of leaf indexes
        Potential_Spread_family = {}
        for idx, entry in enumerate(names_list):
            if idx==0: continue
            if type(entry) is list:
                if entry[1] in SPREAD_ORIGIN:
                    # find leaf nodes later in the list
                    for j in range(idx+1, len(names_list)):
                        if type(names_list[j]) is list: # we don't want this
                            break
                        else: # leaf node!
                            # check if it's already in book.fullnames[fileno] or in book.NE
                            pot = names_list[j]  # potential SPREAD candidates
                            if len(pot) > 2 or pot in self.fullnames[fileno] or pot in self.NE:
                                pass # treat it as a full name, not a given name
                                break
                            else:
                                if idx in Potential_Spread:
                                    Potential_Spread[idx].append(j)
                                else:
                                    Potential_Spread[idx] = [j]
                                    Potential_Spread_family[idx] = entry[1]

            else: # left node
                pass # nothing to do
        if Potential_Spread != dict(): # empty dictionary
            if DEBUG: print(f"Potential_Spread: {Potential_Spread}")
            for k in Potential_Spread.keys():
                ref = names_list[k][0]  # this is the 'a' of the (a,b,c) triple at idx=k
                (sur2, giv2) = sur.split_name(ref)
                for p in Potential_Spread[k]:
                    #names_list[p] = sur2 + names_list[p] # a leaf
                    names_list[p] = [ref, Potential_Spread_family[k], sur2 + names_list[p]] # a leaf

        self.BOOKMARK_PERSONS[fileno] = names_list  # remove comment when debugged
        return names_list


    ## Perform normalizations for all
    def normalizeBookmarkNamesAll(self):
        for fileno in VALID_BIO_FILENOS:
            self.FillMissingRelatives(fileno)
            self.normalizeName1(fileno)
            self.normalizeName2(fileno)
            self.normalizeName1(fileno) # check inline documentation to see why a second time is necessary


    # Collect all names from book.BOOKMARK_PERSONS and place them in book.fullnames for each fileno¶
    def collectPersonNamesAll(self, DEBUG=False):
        for fileno in VALID_BIO_FILENOS:
            for entry in self.BOOKMARK_PERSONS[fileno]:
                if DEBUG: print(fr"fileno: <{entry}>")
                if type(entry) is list:
                    self.fullnames[fileno].add(entry[0]) # 'a' of the triple [a, b, c]
                    self.fullnames[fileno].add(entry[2]) # 'c' of the triple [a, b, c]
                else:
                    self.fullnames[fileno].add(entry)

    ### Time expressions

    def encodeTime(self):
        for fileno in range(len(self.flat_bodies)):
            res = regex_date.findall(self.flat_bodies[fileno].text)
            if res:
                for te in res: # te=time expression
                    #self.TIME_EXPR[hashstr(te)] = te
                    hashed = hashstr(te)
                    self.TE2HASH[te] = hashed
                    self.HASH2TE[hashed] = te
        # Now sort self.TE2HASH by length of key (needed when tagging/encoding TEs)
        self.TE2HASH = { k: self.TE2HASH[k] for k in sorted(self.TE2HASH, key=len, reverse=True) }

    def tagTimeEncode(self, fileno): # encode TEs in txt with the hashed version
        '''
        Tag TEs in txt with their hashed versions
        '''
        txt = self.flat_bodies[fileno].text.strip()
        for te in self.TE2HASH.keys():
            if te in txt:
                txt = txt.replace(te, self.TE2HASH[te])
        return txt   

    def tagTimeDecode(self, txt):
        '''
        Replaces hashed TEs with the original TEs
        '''
        for k in self.HASH2TE.keys():
                if k in txt:
                    txt = txt.replace(k, f"<time>{self.HASH2TE[k]}</time>")
        return txt


    def tag(self, fileno):
        txt1 = self.tagTimeEncode(fileno) # flat_bodies[fileno] encoded with TE hashes
        txt2 = self.tagEncode(txt1)
        txt3 = self.tagGivenNames(fileno, txt2)
        txt4 = self.tagTimeDecode(txt3)
        txt5 = self.tagDecode(txt4)
        return txt5




    ### Some diagnostic functions to discover problems such as
    ### missing surnames, important characters or office titles 
    ### missing from the Global NE List

    def findUnsplittableNames(self):
        for fileno in range(self.BOOKSIZE):
            for name in self.fullnames[fileno]:
                try:
                    (sur0, giv0) = sur.split_name(name)
                    if sur0 is None or giv0 is None:
                        print(f"{fileno}: unable to split this name: {name}")
                except:
                    print(f"{fileno}: unable to split this name: {name}")



