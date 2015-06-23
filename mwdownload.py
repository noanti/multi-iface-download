import threading
import httplib
import time
import logging
import socket
from Queue import Queue
import sys

logging.basicConfig(level=logging.INFO)

def parseUrl(URL):
    url = str(URL)
    url.rstrip('/')
    if url[0:7] == "http://": url = url[7:]
    if url[0:8] == "https://": url = url[8:]
    index = url.find('/')
    if(index == -1):
        host = url
        path = "/"
    else:
        host = url[0:index]
        path = url[index:]
    return host, path

if sys.platform == "win32":
    ipList = socket.gethostbyname_ex(socket.gethostname())
    src_addr = [(i, 0) for i in ipList[2]]
if sys.platform.startswith("linux"):
    import fcntl
    import struct

    def get_ip_address(ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,
            struct.pack('256s', ifname[:15])
        )[20:24])
    src_addr = []
    src_addr.append((get_ip_address('eth0'),0))
    src_addr.append((get_ip_address('wlan0'),0))

print src_addr
tasks = Queue()

def getFileSize(host,path):
    try:
        conn = httplib.HTTPConnection(host)
        conn.request('GET', path)
        resp = conn.getresponse()
        logging.info("getfilesize's resp:%d" % resp.status)
        filesum = int(resp.getheader('Content-Length'))
    except httplib.HTTPException as e:
        print "http connect error", e
    finally:
        resp.close()
        return filesum

class downloadthread(threading.Thread):
    def __init__(self,url,source_address):
        threading.Thread.__init__(self)
        self.url = url
        self.source_address = source_address
        self.speed = 0

    def run(self):
        global tasks
        host, path = parseUrl(self.url)
        conn = httplib.HTTPConnection(host,source_address=self.source_address)
        while not tasks.empty():
            start, end = tasks.get()
            print "start:",start,"end:",end
            heads = {"Range":"bytes=%d-%d"%(start,end)}
            conn.request('GET',path,headers=heads)
            resp = conn.getresponse()
            try_num = 3
            while (resp.status != 206) and (try_num > 0):
                logging.warning("get response error,code:%d" % resp.status)
                time.sleep(1)
                resp = conn.getresponse()
                try_num -= 1
            if resp.status != 206:
                logging.error("can not get response,thread EXIT")
                return
            starttime = time.time()
            #count = 0
            while not resp.isclosed():
                resp.read(1024 * 512)
                #count += 1
                #self.speed = 512.0 * count / (time.time() - starttime)
                #logging.info("source:%s speed:%f" % (self.source_address[0],self.speed))
            resp.close()
            endtime = time.time()
            self.speed = (end-start) / 1024.0 / (endtime-starttime)
            logging.info("source:%s speed:%f" % (self.source_address[0],self.speed))
            tasks.task_done()
        print "source:%s"%self.source_address[0],"EXIT!!!!!!!!"

if __name__ == "__main__":
    testurl = "http://mirrors.ustc.edu.cn/ubuntu-releases/vivid/ubuntu-15.04-desktop-amd64.iso"
    h,p = parseUrl(testurl)
    try:
        filesize = getFileSize(h,p)
    except Exception as e:
        logging.error('Can not connect to host,%s' % e)
    logging.info("filesize:%d" % filesize)
    task_num = 300
    partsize = filesize / task_num + 1
    cur_addr = 0
    for i in range(task_num):
        if cur_addr + partsize > filesize:
            tasks.put((cur_addr,filesize))
        else:
            tasks.put((cur_addr,cur_addr+partsize))
        cur_addr += partsize
    oldtime = time.time()
    t1 = downloadthread(testurl, src_addr[2]);t1.start()
    t2 = downloadthread(testurl, src_addr[1]);t2.start()
    logging.info("main thread is waiting...")
    tasks.join()
    logging.info("all time:%f" % (time.time() - oldtime))