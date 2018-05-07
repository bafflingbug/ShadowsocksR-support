#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os

from flask import Flask

from service.core import load_plugins

app = Flask(__name__)

app.logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(os.path.dirname(os.path.abspath(__file__)) + '/flask.log')
fh.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
fh.setFormatter(formatter)
app.logger.addHandler(fh)

load_plugins(app)

if __name__ == '__main__':
    from werkzeug.contrib.fixers import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.run(debug=False, host='0.0.0.0', port=80)
