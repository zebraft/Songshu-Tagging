# Songshu-Tagging
Songshu tagging project

Digital Songshu 2019/11 - towards stage one wrap-up

https://hackmd.io/@DZR/rJF0y0M2r

## Updates
2019-12-14

Songshu.py

(1) Set <time> tags to <time id="UNKNOWN"> if unable to identify era name or year.

(2) For leap month (e.g. 閏十二月), the month field of "id" attribute has an extra "0.5".
    For example 閏十二月四日 (元徽四年) is tagged <time id="476-12.5-04">

(3) For seasons that appear immediately after a year (e.g., 五年春 in fileno=601), the rule for defining the month isas follows:

    春 = 02, 夏 = 05, 秋 = 08, 冬 = 10
    
    
