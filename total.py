#!/usr/bin/python
#-*-coding:utf-8

from urllib import request
import json
import time
import csv

import configparser
from cloudify_rest_client import CloudifyClient

import pandas as pd
from statsmodels.tsa.stattools import adfuller
import statsmodels.tsa.stattools as st
import numpy as np
import pyflux as pf

def parse_args(filename):
    cf=configparser.ConfigParser()
    cf.read(filename)

    hostip=cf.get('host','ip')
    return  hostip


def get_DashboardId():
    host=parse_args('/Users/wecash/PycharmProjects/datasort/setting.conf')  #读取配置文件
    client=CloudifyClient(host)
    blueprints=client.blueprints.list()
    blueprints_list=[]
    for blueprint in blueprints:
        blueprints_list.append(blueprint.id)
    return blueprints_list


def urlhandle():
    base_url='http://10.10.1.6/backend/grafana/series?'
    dicts={
        'dashboardId' :get_DashboardId()[0],
        'q':'select++mean(value)+from+%2Fnodecellar%5C..*%3F%5C.cpu_total_system%2F+where++time+%3E+now()+-+15m+++++group+by+time(10)++order+asc',
        'time_precision':'s'

    }
    item=dicts.items()
    url_joint=''
    for i in item:
        (key,value)=i
        temp_st=key+'='+value
        url_joint=url_joint+temp_st+'&'
    url_joint = url_joint[:len(url_joint) - 1]
    url=base_url+url_joint
    return url


def getdata():
    url=urlhandle()
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


def test_stationarity(timeseries):
    dftest = adfuller(timeseries, autolag='AIC')
    return dftest[1]


def best_diff(df, maxdiff = 8):
    p_set = {}
    for i in range(0, maxdiff):
        temp = df.copy() #每次循环前，重置
        if i == 0:
            temp['diff'] = temp[temp.columns[1]]
        else:
            temp['diff'] = temp[temp.columns[1]].diff(i)
            temp = temp.drop(temp.iloc[:i].index) #差分后，前几行的数据会变成nan，所以删掉
        pvalue = test_stationarity(temp['diff'])
        p_set[i] = pvalue
        p_df = pd.DataFrame.from_dict(p_set, orient="index")
        p_df.columns = ['p_value']
    i = 0
    while i < len(p_df):
        if p_df['p_value'][i]<0.01:
            bestdiff = i
            break
        i += 1
    return bestdiff


def produce_diffed_timeseries(df, diffn):
    if diffn != 0:
        df['diff'] = df[df.columns[1]].apply(lambda x:float(x)).diff(diffn)
    else:
        df['diff'] = df[df.columns[1]].apply(lambda x:float(x))
    df.dropna(inplace=True) #差分之后的nan去掉
    return df


def choose_order(ts, maxar, maxma):
    order = st.arma_order_select_ic(ts, maxar, maxma, ic=['aic', 'bic', 'hqic'])
    return order.bic_min_order


def predict_recover(ts, df, diffn):
    if diffn != 0:
        ts.iloc[0] = ts.iloc[0]+df['log'][-diffn]
        ts = ts.cumsum()
    ts = np.exp(ts)
#    ts.dropna(inplace=True)
    print('还原完成')
    return ts


def run_aram(df, maxar, maxma, test_size = 14):

    data = pd.DataFrame(df.dropna())
    data['log'] = np.log(data[data.columns[0]])
    #    test_size = int(len(data) * 0.33)
    train_size = len(data)-int(test_size)
    train, test = data[:train_size], data[train_size:]
    #print(test)
    if test_stationarity(train[train.columns[1]]) < 0.01:
        print('平稳，不需要差分')
    else:
        diffn = best_diff(train, maxdiff = 8)
        train = produce_diffed_timeseries(train, diffn)
        print('差分阶数为'+str(diffn)+'，已完成差分')
    print('开始进行ARMA拟合')
    order = choose_order(train[train.columns[2]], maxar, maxma)
    print('模型的阶数为：'+str(order))
    _ar = order[0]
    _ma = order[1]
    model = pf.ARIMA(data=train, ar=_ar, ma=_ma, target='diff', family=pf.Normal())
    model.fit("MLE")
    test = test['data']

    test_predict = model.predict(int(test_size))
    test_predict = predict_recover(test_predict, train, diffn)


    #print(np.sqrt((sum((np.array(test_predict['diff'])-np.array(test))**2))/test_size))
    RMSE = np.sqrt((np.mean(np.array(test_predict['diff'])-np.array(test))**2))
    print("测试集的RMSE为："+str(RMSE))


daily_payment = pd.read_csv('/Users/wecash/Documents/rawdata.csv',parse_dates=[0], index_col=0)
run_aram(daily_payment,5,5)
