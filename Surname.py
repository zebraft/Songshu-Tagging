# -*- coding: utf-8 -*-
"""
Created on Tue Mar 12 08:54:13 2019
Updated (test) on Nov 24, 2019

@author: ruben
"""

import re

fin_surname_list = 'china_surnames.txt'

class Surname:
    '''
    Input:  full name, e.g. '愛新覺羅福臨'
    Output: A tuple (surname, given_name), e.g. ('愛新覺羅', '福臨')
    '''
    def __init__(self):
        with open(fin_surname_list, "r", encoding="utf-8") as fi:
            surnames = fi.read().split()
        #sort list by string length, descending order
        surnames.sort(key = lambda s: len(s), reverse=True)
        self.surname_list = surnames

    def split_name(self, fullname):
        for idx, sn in enumerate(self.surname_list):
            m = re.search(fr"^{sn}", fullname)
            if m:
                return fullname[:m.end()], fullname[m.end():]
        return None, None


