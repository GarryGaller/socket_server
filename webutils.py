#--------------------------------------
"""
Script      : webutils.py
Desсription : Библиотека функций для web
Author      : Gary Galler
Copyright(C): Gary Galler, 2017.  All rights reserved
Version     : 1.0.0.0
Date        : 24.10.2017
"""
#--------------------------------------
__version__ = '1.0.0.0'
__date__    = '24.10.2017'

import os
import hashlib
import re
import time
from datetime import datetime


#---------------------------------
# форматирвание времени в web формат
#---------------------------------
def time_web_format(timetuple=None):
    if timetuple is None: 
        timetuple = time.gmtime()
    return time.strftime("%A, %d %b %Y %H:%M:%S GMT",timetuple)

#---------------------------------
# время последней модификации файла 
#---------------------------------
def time_last_modified_source(filepath,utc=True):
    
    if utc:
        dt = datetime.utcfromtimestamp(os.stat(filepath).st_mtime)
    else:
        dt = datetime.fromtimestamp(os.stat(filepath).st_mtime)
    dt = datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second,0)
    return dt

#---------------------------------
# валидация If-Modified-Since
#---------------------------------
def is_modified_since(header_if_modified_since,filepath):
    modified_since = datetime.strptime(
                header_if_modified_since,
                "%A, %d %b %Y %H:%M:%S GMT")
    return time_last_modified_source(filepath) > modified_since

#---------------------------------
# валидация If-None-Match
#---------------------------------
def is_none_match(header_if_none_match,filepath):
    return header_if_none_match != etag(filepath)

#-------------------------------------- 
# получение параметров http заголовков
#--------------------------------------
def get_params_from_header(value_header,param,delim=";"):
    result = {};
    for val in value_header.split(delim):
        values = val.split('=')
        if len(values) == 1:
            values.append(None) 
        v = values[1]
        if v:
            values[1] = v.strip()
            values[1] = int(v) if v.isdigit() else v
        result[values[0].strip()] = v
    
    res = result.get(param) or result.get(param + '*')
    return res

#---------------------------------
# вычисление md5 для содержимого файла
#---------------------------------
def md5sum(filepath):
    with open(filepath, 'rb') as fh:
        m = hashlib.md5()
        while True:
            data = fh.read(8192)
            if not data:
                break
            m.update(data)
        return m.hexdigest()

def md5sum2(fname):
    m = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            m.update(chunk)
    return m.hexdigest()

#---------------------------------
# генерация значения ETag
#---------------------------------
def etag(filepath):
    result = str(os.stat(filepath).st_mtime) + filepath
    m = hashlib.md5()
    m.update(bytes(result,encoding='utf-8'))
    return '"' + m.hexdigest() + '"'
    
#--------------------------------------    
# парсинг аргумента date в формате 1w1d1h1m1s
#--------------------------------------
def parse_time(s):
    match = re.findall(r"(-?\d+)([a-z])?",s)
    match = dict([tuple(reversed(t)) for t in match])
    if "" in match.keys():
       match["d"] = match[""] 
       del match[""]
    delta = dict(days=0, hours=0,minutes=0,seconds=0, weeks=0)
    
        
    for k in delta:
        if k[0] in match:
            delta[k]=int(match[k[0]])
    return delta 
    
#--------------------------------------    
# добавление начального слеша, если отсутствует
#--------------------------------------
def add_start_slash(s):
    return s if s.startswith('/')  else "/" + s       
    
