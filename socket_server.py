#!/usr/bin/env python3

#https://andreymal.org/socket3/
#http://ftpn.ru/redirect-external-link/
#http://jdevelop.info/articles/html-css-js/200-perekhod-na-druguyu-stranitsu-s-pomoshchyu-javascript

#--------------------------------------
"""
Script      : socket_server.py
Desсription : Сокет сервер для листинга директорий
Author      : Gary Galler
Copyright(C): Gary Galler, 2017.  All rights reserved
Version     : 1.0.0.0
Date        : 24.10.2017
"""
#--------------------------------------
__version__ = '1.0.0.0'
__date__    = '24.10.2017'


import time,os,sys
import traceback 
import socket
import mimetypes,cgi
import re
import hashlib
import queue
import threading
import locale
from datetime import datetime
from string import Template
from urllib.parse import quote,unquote
from subprocess import Popen
#для автоопределения кодировки файлов
from chardet.universaldetector import UniversalDetector
from webutils import (
                    etag, 
                    is_none_match, 
                    is_modified_since, 
                    get_params_from_header,
                    time_last_modified_source,
                    time_to_rfc2616)

if os.name == "nt" and sys.version_info[:2] < (3,6):
    import win_unicode_console
    win_unicode_console.enable()


#---------------------------------
# базовый шаблон html
#---------------------------------

BASE_HTML = """
<!DOCTYPE html>
<html>
    <head>
        <meta charset=$charset">
        <title>$title</title>
        <style> a:hover {
            color: white;
            padding: 1px;
            background-color: gray;
            border-color: #ccc;
            border-width: 4px;
            border-style:outset;}
        </style>
    </head>
<body>
    $body
</body>
</html>
"""
#---------------------------------
# дебаговый вывод информации
#---------------------------------
def debug_response_headers(response):
    print("-"*10)
    print("RESPONSE:")
    print(response.version,response.status)
    
    for name,val in response.headers:
        print(name,val,sep=': ')


def debug_request_headers(request):
    print("-"*10)
    print("CONNECTED:",request.host)
    print(
        request.method, 
        unquote(request.address),
        request.version
    )
    
    for name,val in request.headers:
        print(name,val,sep=': ')


#---------------------------------
# чтение файла
#---------------------------------
def read_file(filepath):
    data = open(filepath,"rb").read()
    return data,int(len(data))

#---------------------------------
# определение кодировки файла
#---------------------------------
def detect_encoding(filepath):
    #default_enc = sys.getfilesystemencoding()
    default_enc = locale.getpreferredencoding()
    result = None
    detector = UniversalDetector()
    detector.reset()
    
    for line in open(filepath, 'rb'):
        detector.feed(line)
        if detector.done: break
    detector.close()
    encoding = detector.result.get('encoding') or default_enc
    
    return encoding

#---------------------------------
# листинг каталогов
#---------------------------------
def list_directory(root):
    
    dirs  = []
    files = []
    
    cache_dirs = CASCHE_DIRS.get(root)
    if cache_dirs:
        return cache_dirs
    
    for name in os.listdir(root):
        if os.path.isdir(os.path.join(root,name)):
            dirs.append(name.upper() + "/")
        else:
            files.append(name)
    
    dirs.sort()
    files.sort()
    dirs.extend(files)
    CASCHE_DIRS[root] = dirs
    return dirs

#---------------------------------
# генерация страницы ошибки
#---------------------------------
def render_error(**kwargs):
    html = BASE_HTML
    
    body = """
    <h2>$title</h2>
    <p>Error code: $status_code</p>
    <p>Description: $message</p>
    <p>$traceback</p>
    """
    html = Template(html.replace('$body',body))
    
    return html.safe_substitute(kwargs)
    
#---------------------------------
# генерация страницы листинга файлов
#---------------------------------    
def render_html(root,charset=None):
    
    if charset is None:
        charset = "utf-8"
    root = unquote(root)
    root = root if root != ROOT else '/'
    
    html = BASE_HTML
   
    body = """<h1>Index of %s </h1>\n<hr>\n<ul>\n""" % root
    li = """<li><a  href="{name}" title={title}>{name}</a></li>\n"""
    #добавляем в самый верх относительную ссылку на родительский каталог
    body += li.format(name="../",title="")
    
    # сортировка файлов и директорий - первыми идут каталоги
    filepath = os.path.normpath(os.path.join(ROOT,root.strip('/')))
    listing = list_directory(filepath)
    
    for name in listing: 
        path = os.path.join(filepath,name)
        if not os.path.isdir(path):
            size = os.path.getsize(path)
            if size > 1024: 
                size = str(round(size/1024)) + " kb" 
            else: 
                size = str(round(size)) + " byte"
            size = "Size: {}".format(size)
        else:
            size = '""'
        body+= li.format(name=name,
                        title='"' + size + '"')
    
    body+= "</ul>\n<hr>\n"
    html = Template(html)
    return html.safe_substitute(title=root,
                                charset=charset,
                                body=body)
    

#---------------------------------
# отправка ответа клиенту
#---------------------------------

def send_answer(conn, 
                protocol = "HTTP/1.1", 
                status="200 OK", 
                typ="text/plain",
                charset=None, 
                data="",
                binary=False,
                headers=None):
    
    if not binary and data:
        if charset is None:
            charset = 'utf-8'
        data = data.encode(charset)
    
    charset = '; charset=' + charset if charset else ""
    start_line = "{} {}".format(protocol, status)
    default_headers = [
            ("Server", "simplehttp"),
            ("Date", time_to_rfc2616()),
            ("Connection", "close"),
            ("Content-Type", typ + charset),
            ("Content-Length", len(data)),
        ]
    
    _headers = []
    if headers is None:
        headers = []
    elif headers == -1:
        headers = []
        default_headers = []
    
    _headers.extend(default_headers)
    _headers.extend(headers)
    # динамически создаем простой объект для передачи данных ответа
    response = type("Response",(object,), {
        'version':protocol,
        'status':status,
        'headers':_headers
        }
    )
    
    debug_response_headers(response)
    conn.send(start_line.encode(DEFAULT_CHARSET) + b"\r\n") 
    
    if _headers:
        for header in _headers:
            conn.send(": ".join(map(str,header)).encode(DEFAULT_CHARSET) + b"\r\n")     
        
    if data:
        conn.send(b"\r\n") # после пустой строки в HTTP начинаются данные
        conn.send(data)
    
#---------------------------------
# чтение данных из сокета  
#---------------------------------
def read_data(conn, addr):
    data = b""
    
    while not b"\r\n" in data: # ждём первую строку
        time.sleep(0.1)
        try:
            tmp = conn.recv(65535)
            if not tmp:   # сокет закрыли, пустой объект
                break
        except socket.error:
            continue
        except KeyboardInterrupt:
            #(typ, val, tb) = sys.exc_info()
            print("Route: Exit by Ctrl+C")
            conn.close()
            sys.exit(0)
        else:
            data += tmp
    
    return data

#---------------------------------
# парсинг данных  
#---------------------------------
def parse_request(conn,data):    
    udata = data.decode(DEFAULT_CHARSET)
    
    # отделяем запрос и заголовки от данных
    udata = udata.split("\r\n\r\n", 1)[0]
    # разделяем запрос и заголовки на список
    udata = udata.split('\r\n')
    # берем первую строку содержащую запрос и делим ее на составляющие части
    method, address, protocol = udata[0].split(" ", 2)
    raw_headers = udata[1:] # получаем список заголовков
    headers = []
    for header in raw_headers:
        name,value = header.split(":",1)
        headers.append((name.strip(),value.strip()))
    
    host = dict(headers).get('Host',HOST)
    # динамически создаем простой объект для передачи данных запроса
    request = type("Request",(object,), {
        "host":host,
        'method':method,
        'address':address,
        'version':protocol,
        'headers':headers
        }
    )
    
    debug_request_headers(request)
    route(conn,request)
    

#---------------------------------
# маршрутизация url и обработка соединений  
#---------------------------------

def route(conn,request):    
    
    charset = DEFAULT_CHARSET
    headers = []
    
    filepath = os.path.normpath(
                    os.path.join(ROOT,request.address.strip('/'))
                    )
    typ,enc = mimetypes.guess_type(filepath)
    if typ is None:
        typ = 'application/octet-stream'
    
    filepath = unquote(filepath)
    print('-'* 10)
    print(filepath,typ)
    
    if request.address == "/":
        answer = render_html(ROOT)
        return send_answer(conn, 
                            typ="text/html",
                            charset=charset,
                            data=answer)
    else:                        
        # если запрашиваемый ресурс - директория, выводим листинг
        if os.path.exists(filepath):
            # если путь - директория
            if os.path.isdir(filepath):
                # генерируем html для рендеринга листинга файлов
                answer = render_html(request.address,charset=DEFAULT_CHARSET) 
                # отправляем данные клиенту (браузеру)
                send_answer(conn, 
                            typ="text/html", 
                            charset=DEFAULT_CHARSET,
                            data=answer,
                            headers=[("Cache-Control", "no-cache")]
                            )
            # иначе - отображаем ресурс в браузере     
            else:
                modified = True
                headers = dict(request.headers)
                if 'If-Modified-Since' in headers:
                    if not is_modified_since(headers['If-Modified-Since'],filepath):
                        modified = False
                        
                if 'If-None-Match' in headers:
                    if not is_none_match(headers['If-None-Match'],filepath):
                        modified = False 
                     
                if 'Cache-Control' in headers:
                    max_age = get_params_from_header(headers['Cache-Control'],
                                                    "max-age",
                                                    delim=',')
                    if max_age == 0:
                        pass # ??   
                
                if not modified:
                    # если ресурс не изменился - отправляем клиенту (браузеру) код 304,
                    # чтобы он взял закэшированный ресурс
                    gmdate = time_to_rfc2616()
                    timetuple = time_last_modified_source(filepath).timetuple()
                    last_modified = time_to_rfc2616(timetuple)
                    headers = [
                                ("Date", gmdate),
                                ("ETag",etag(filepath)),
                                ("Last-Modified",last_modified)
                            ]
                    return send_answer(conn, 
                                    status="304 Not Modified",
                                    headers=-1
                                    )
                
                # если файл текстовый - определяем кодировку для того, 
                # чтобы браузер мог его правильно отобразить
                if text_types.match(typ):
                   charset =  detect_encoding(filepath)
                # или выводим диалог сохранения файла   
                else:
                    # добавляем заголовки для показа браузером диалога сохранения файла
                    if not browser_types.match(typ):
                        headers = [
                            ('Content-Description', 'File Transfer'),
                            ('Content-Transfer-Encoding','binary'),
                            ('Content-Disposition', 'attachment;filename=%s' % quote(
                                    os.path.basename(filepath)
                                    ))
                        ]
                        charset = None
                #------------------------------------    
                data,size = read_file(filepath)
                timetuple = time_last_modified_source(filepath).timetuple()
                #print(timetuple)
                last_modified = time_to_rfc2616(timetuple)
                # добавляем заголовки клиентского кэширования
                headers = []
                headers.append(("ETag",etag(filepath)))
                headers.append(("Last-Modified",last_modified))
                headers.append(("Cache-Control", 
                    # "max-age=%s" % MAX_AGE))
                    "max-age=%s, must-revalidate" % MAX_AGE))
                    #"max-age=%s, must-revalidate, private, no-cache" % 600)) # c no-cache не кэширует
                send_answer(conn, 
                            typ=typ,
                            charset=charset,
                            data=data,
                            binary=True,
                            headers=headers
                            )
        #-------------------------------------
        # если файла не существует           
        else:
            # генерируем html для рендеринга ошибки
            answer = render_error(
                            charset=charset,
                            title='Ой! Ошибочка вышла...',
                            status_code=404,
                            message='Page Not Found',
                            traceback=filepath)
            # отправляем данные клиенту (браузеру)
            send_answer(conn, 
                        typ="text/html",
                        status="404 Not Found",
                        charset=charset,
                        data=answer) 
                        
 
#---------------------------------
# многопоточная обработка
#---------------------------------  

class Worker(threading.Thread):
    
    def __init__(self, queue):
        """Инициализация потока"""
        super().__init__()
        self.queue = queue
     
    def run(self):
        """Запуск потока"""
        while True:
            try:
                item = self.queue.get()
                if item is None:
                    break
                conn, addr = item
                #print(conn, addr)
                self.work(conn, addr)
            except Exception as err:
                print(err)
            else:
                if conn:
                    conn.close() 
            finally:
                self.queue.task_done() 
     
    def work(self, conn, addr):
        data = read_data(conn, addr)
        # данные пришли - обрабатываем
        if data:
            parse_request(conn,data) 
    
    
def create_workers(max_workers=10):
    global q, threads
    q = queue.Queue()
    threads = []
    
    for i in range(max_workers):
        t = Worker(q)
        t.start()
        threads.append(t)

def stop_workers(max_workers):
    # останавливаем воркеры
    for _ in range(max_workers):
        q.put(None)
        
    for t in threads:
        t.join() # дожидаемся завершения потоков
        print('{:<10}|Closed:{}'.format(
            t.name, 
            not t.is_alive())
        )

#---------------------------------
# запуск сервера
#---------------------------------   
def serve_forever(server,port,charset):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(0) # включаем неблокирующий режим для accept
    sock.bind((server, port))
    sock.listen(DEPTH_QUEUE_CONNECTIONS)
    
    create_workers(max_workers=MAX_WORKERS)
    
    try:
        while 1: 
            #time.sleep(0.01)
            try:
                conn, addr = sock.accept()
                print('-' * 10)
                print("Connected: " + addr[0])
            
            except socket.error: # данных нет
               continue
            
            except KeyboardInterrupt:
                print("Connected: Exit by Ctrl+C")
                stop_workers(MAX_WORKERS)
                
                if conn:
                    conn.close()
                sys.exit(0)
            
            else:    
                try:
                    # включаем неблокирующий режим для recv
                    conn.setblocking(0)
                    #work(conn,addr)
                    q.put((conn,addr)) 
                    
                # перехватываем внутренние ошибки сервера
                except Exception as err:
                    trace = traceback.format_exc()
                    print("[Internal Error]:",trace)
                    # генерируем html для рендеринга ошибки
                    answer = render_error(
                                    charset=DEFAULT_CHARSET,
                                    title='Ой! Ошибочка вышла...',
                                    status_code=500,
                                    message='Internal Server Error',
                                    traceback=err)
                    # отправляем данные клиенту (браузеру)
                    send_answer(conn, 
                                typ="text/html",
                                status="500 Internal Server Error",
                                charset=DEFAULT_CHARSET,
                                data=answer)   
                finally: 
                    pass
                
    except KeyboardInterrupt:
        print("Main: Exit by Ctrl+C")        
        stop_workers(MAX_WORKERS) 
        
    finally: 
        sock.close()

    
#--------------------------------------------------
if __name__ == "__main__":
    CASCHE_DIRS = {}
    HOST = SERVER,PORT = "0.0.0.0",8080
    HOST = ":".join(map(str,HOST))
    # корневая директория, которая будет доступна по адресу http://localhost:8080
    ROOT = os.path.dirname(__file__)
    DEFAULT_CHARSET = "utf-8"
    MAX_AGE = 0
    MAX_WORKERS = 100
    DEPTH_QUEUE_CONNECTIONS = 10
    
    if not mimetypes.inited:
        mimetypes.init() 
    
    # добавляем и переопределяем некоторые mime типы
    mimetypes.types_map.update(
        {
        ""     :'application/octet-stream', # файлам без расширения дадим дефолтный тип неизвестного двоичного содержимого 
        ".json":"application/json", # отсутствует
        ".vbs" :"text/plain",       # отсутствует, определяем для открытия в браузере
        ".csv" :"text/plain",       # переопределяем для открытия в браузере
        ".djvu":"application/djvu", # отсутствует
        ".js"  :"text/plain",       # переопределяем для открытия в браузере
        }
        )
    
    # типы, которые нужно открывать текстовом режиме и декодировать
    text_types = re.compile("|".join(
        ["text/.*","application/json"]
        ))
    
    # типы, которые мы хотим, чтобы браузер открывал сам
    # любые текстовые файлы, картинки, видео (если,получится)
    browser_types = re.compile("|".join(
        [
        "application/json",
        "application/pdf",
        "image/.*",
        "video/.*"
        ]
        ))
    
    # xlsx:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
    # exe: application/x-msdownload
    print('START LISTEN SERVER:{}'.format(HOST))
    serve_forever(SERVER,PORT,DEFAULT_CHARSET)
 
