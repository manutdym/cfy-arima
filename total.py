#!/usr/bin/python
#-*-coding:utf-8

from urllib import request
import json
import time
import csv

def urlhandle():
    url='http://10.10.1.6/backend/grafana/series?dashboardId=nodecellar&q=select++mean(value)+from+%2Fnodecellar%5C..*%3F%5C.cpu_total_system%2F+where++time+%3E+now()+-+15m+++++group+by+time(10)++order+asc&time_precision=s'
    return url

def getdata(url):
    r=request.urlopen(url)
    hjson=json.loads(r.read())
    rawdata=hjson[0]['points']
    l=len(rawdata)
    with open('/Users/wecash/Documents/try.csv','w') as csvfile:
     writer=csv.writer(csvfile)
     writer.writerow(['time','data'])
     for i in range(l):
         time_local = time.localtime(rawdata[i][0])
         dt = time.strftime("%Y-%m-%d %H:%M:%S", time_local)
         writer.writerows([[dt,rawdata[i][1]]])
