#!/usr/bin/env python
# -*- coding: utf-8 -*-
import base64
import json
import os
import time
import hashlib
from threading import Thread

import flask
import requests
import yaml
from flask import Blueprint, request

from .tools import safe_get, safe_value

path = os.path.dirname(os.path.abspath(__file__))
blueprint = Blueprint(os.path.basename(path), __name__)

config = None
data = None


@blueprint.route('/', methods=['GET'])
def index():
    pw = request.args.get('password', request.args.get('pw', None))
    conf = get_config()
    if not conf or 'password' not in conf:
        return flask.json.dumps({'code': -500, 'msg': 'no config'})
    if not pw or md5_updata(md5_updata(pw)) != conf['password']:
        print(pw)
        return flask.json.dumps({'code': -300, 'msg': 'password error'})
    d = get_data()
    if int(time.time() - d['last_time']) <= 60 * 5 and d['last'] and d['last'] != '':
        return d['last']
    ths = []
    for key, value in d['SSR'].items():
        ths.append(ResultThread(get, (value['url'],), name=key))
    for th in ths:
        th.start()
    for th in ths:
        th.join()
    urls_list = []
    for th in ths:
        urls = th.get_result()
        ip = th.get_name()
        if urls is None:
            if not d['SSR'][ip]['failed']:
                d['SSR'][ip]['failed'] = time.time()
            elif int(time.time() - d['SSR'][ip]['failed']) > 60 * 60 * 10:
                rm_ssr(ip)
            continue
        d['SSR'][ip]['failed'] = None
        urls_list.extend(urls)
    ret = '\n'.join(urls_list)
    set_time()
    d['last'] = base64.urlsafe_b64encode(ret.encode('utf-8')).decode().rstrip('=')
    save_data()
    return d['last']


@blueprint.route('/reg', methods=['POST'])
def reg():
    try:
        conf = get_config()
        if not conf:
            return flask.json.dumps({'code': -500, 'msg': 'no config'})
        args = flask.json.loads(request.json)
        if 'server' not in args or 'url' not in args:
            return flask.json.dumps({'code': -100, 'msg': 'Missing parameters'})
        if args.get('token', '') != conf.get('token', ''):
            return flask.json.dumps({'code': -101, 'msg': 'token error'})
        add_ssr(args['server'], args['url'])
        index()
        save_data()
        return flask.json.dumps({'code': 0, 'msg': ''})
    except Exception as e:
        return flask.json.dumps({'code': -500, 'msg': repr(e)})


@blueprint.route('/group')
def group():
    conf = get_config()
    if 'group' in conf:
        return flask.json.dumps({'code': 0, 'data': {'group': conf['group']}})
    else:
        return flask.json.dumps({'code': 0, 'data': {'group': 'default-group'}})


@blueprint.route('/server/<ip>', methods=['GET'])
def server(ip):
    pw = request.args.get('password', request.args.get('pw', None))
    conf = get_config()
    if not conf or 'password' not in conf:
        return flask.json.dumps({'code': -500, 'msg': 'no config'})
    if not pw or pw != conf['password']:
        return flask.json.dumps({'code': -300, 'msg': 'password error'})
    d = get_data()
    if ip in d['SSR'].keys():
        urls = get(d['SSR'][ip])
        if urls is None:
            if not d['SSR'][ip]['failed']:
                d['SSR'][ip]['failed'] = time.time()
            elif int(time.time() - d['SSR'][ip]['failed']) > 60 * 60 * 10:
                rm_ssr(ip)
            save_data()
            return ''
        d['SSR'][ip]['failed'] = None
        ret = '\n'.join(urls)
        save_data()
        return base64.urlsafe_b64encode(ret.encode('utf-8')).decode().rstrip('=')


def load_config():
    global config
    try:
        with open(path + '/config.yaml', 'r') as f:
            config = yaml.load(f)
        if config is None:
            return False
        if 'token' in config and 'password' in config and 'group' in config:
            return True
        return False
    except yaml.YAMLError:
        return False


def get_config():
    global config
    if config is None:
        if not load_config():
            return None
    return config


def get_data():
    global data
    if data is None or type(data) is not dict:
        data = {
            'last_time': 0,
            'last': '',
            'SSR': {}
        }
    if 'last_time' not in data or data['last_time']:
        data['last_time'] = 0
    if 'last' not in data:
            data['last'] = ''
    if 'SSR' not in data or type(data['SSR']) is not dict:
        data['SSR'] = {}
    return data


def set_data(d):
    global data
    data = d
    return get_data()


def set_time():
    t = time.time()
    d = get_data()
    d['last_time'] = t
    return True


def add_ssr(server, url):
    d = get_data()
    d['SSR'][server] = {'url': url, 'failed': None}
    return True


def rm_ssr(server):
    d = get_data()
    if server in d['SSR'].keys():
        d['SSR'].pop(server)
        return True
    return False


def save_data():
    global data
    try:
        json.dump(data, open(path + '/data.json', 'w'))
        return True
    except TypeError:
        return False


def get(url):
    conf = get_config()
    if conf is None:
        return None
    url += '?token=%s' % (conf.get('token', ''),)
    req = requests.get(url)
    if not req:
        return None
    try:
        j = req.json()
    except json.JSONDecodeError:
        return None
    if 'code' not in j or j['code'] != 0 or 'data' not in j or 'urls' not in j['data']:
        return None
    return j['data']['urls']


def md5_updata(a):
    m = hashlib.md5()
    m.update(a.encode('utf-8'))
    return m.hexdigest()


def init():
    conf = get_config()
    if conf is None:
        raise ValueError('not find config')
    if os.path.exists(path + '/data.json'):
        try:
            d = json.load(open(path + '/data.json', 'r'))
            set_data(d)
        except json.JSONDecodeError:
            get_data()
            save_data()


class ResultThread(Thread):

    def __init__(self, func, args, name=''):
        Thread.__init__(self)
        self.name = name
        self.func = func
        self.args = args
        self.result = None

    def run(self):
        self.result = self.func(*self.args)

    def get_result(self):
        return self.result

    def get_name(self):
        return self.name


init()
