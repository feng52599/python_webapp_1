
# -*- coding: utf-8 -*-

'''
Configuration
'''
from www import config_default, config_override

__author__ = 'feng'

import www.config_default

## 应用程序读取配置文件优先从config_override.py 读取
## 为简化读取配置文件， 可以把所有配置读取到config.py 中，然后将之转化为可读的字典

class Dict(dict):
    '''
    Simple dict but support access as x.y style.
    '''
    def __init__(self, names = (), values = (), **kw):
        super(Dict, self).__init__(**kw)
        for k,v in zip(names, values):
            self[k] = v

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value


def merge(defaults, override):
    r = {}
    for k, v in defaults.items():
        if k in override:
            if isinstance(v, dict):
                r[k] = merge(v, override[k])
            else:
                r[k] = override[k]
        else:
            r[k] = v
    return r

def toDict(d):
    D = Dict()
    for k, v in d.items():
        D[k] = toDict(v) if isinstance(v, dict) else v
    return D

configs = config_default.configs

# 使用本地测试时不需要，只有使用服务器测试需要
# try:
#     import www.config_override
#     configs = merge(configs, config_override.configs)
# except ImportError:
#     pass

configs = toDict(configs)