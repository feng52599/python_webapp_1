# -*- coding: utf-8 -*-

'''
Default
'''

# 网站运行需要读取配置文件， 包括数据库用户名， 口令，
# 默认的配置文件

configs = {
    'debug': True,
    'db':{
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'root',
        'password': 'lsh525',
        'db': 'awesome'
    },
    'session':{
        'secret': 'Awesome'
    }
}