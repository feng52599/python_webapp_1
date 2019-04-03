import logging
# logging.basicConfig函数对日志的输出格式及方式做相关配置，
# 代码设置日志的输出等级是WARNING级别，意思是WARNING级别以上的日志才会输出
logging.basicConfig(level=logging.INFO)

import asyncio,os, json, time
from aiohttp import web
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from www.config import configs
from www.coreweb import add_routes, add_static
import www.orm


## handlers 时url处理模块， 当handles.py 在API章节里完全编辑完再取消注释
## from coreweb import cookie2user, COOKIE_NAME

## 初始化jinja2的函数
## 用来解析test.html
def init_jinja2(app, **kw):
    logging.info('init jinja2...')
    # 配置options参数，这些参数用来渲染jinja2模版
    options = dict(
        # 自动转义xml/html的特殊字符
        autoescape = kw.get('autosscape', True),
        # 代码块开始、结束的标志
        block_start_string = kw.get('block_start_string', '{%'),
        block_end_string = kw.get('block_end_string', '%}'),
        # 变量开始、结束的标志
        variable_start_string = kw.get('variable_start_string', '{{'),
        variable_end_string = kw.get('variable_end_string', '}}'),
        # 自动加载修改后的模版文件
        auto_reload = kw.get('auto_reload', True)
    )
    # 获取模版文件夹的路径
    path = kw.get('path', None)
    if path is None:
        # 在当前文件路径中查找template文件夹
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

    logging.info('set jinja2 template path: %s' % path)
    # 配置 Jinja2 为你的应用加载文档的最简单方式
    # Environment类是jinja2的核心类，用来保存配置、全局对象以及模板文件的路径
    # FileSystemLoader 用来加载path路径中的模板文件   options导入配置
    env = Environment(loader=FileSystemLoader(path), **options)
    # 获取过滤器集合
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            # 把filter的值，给Environment类的属性
            env.filters[name] = f
    # 所有的一切是为了给app添加__templating__字段
    # env存储了jinja2的环境配置，在这里存入app的dict中，这样app就知道如何找到模板，解析模板
    app['__templating__'] =env

## 以下时middleware，可以把通用的功能从每个URL处理函数中拿出来集中放到一个地方
## URL处理日志工厂

async def logger_factory(app, handler):
    async def logger(request):
        logging.info('Request: %s %s' % (request.method, request.path))
        return (await handler(request))
    return logger

## 认证处理工厂--把当前用户绑定request上， 并对URL/manage/ 进行拦截， 检查当前用户是否时管理员身份
## 需要handles.py 的支持

# async def auth_factory(app, handler):
#     async def auth(request):
#         logging.info('check user: %s %s' % (request.method, request.path))
#         request.__user__ = None
#         cookie_str = request.cookies.get(COOKIE_NAME)
#         if cookie_str:
#             user = await cookie2user(cookie_str)
#             if user:
#                 logging.info('set current user: %s' % user.email)
#                 request.__user__ = user
#         if request.path.startwith('/manage/') and (request.__user__ is None or not request.__user__.admin):
#             return web.HttpFound('/signin')
#         return (await handler(request))
#     return auth


## 数据处理工厂
## hanler是视图函数
async def data_factory(app, handler):
    async def parse_data(request):
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_type.startswith('applicion/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request from: %s' % str(request.__data__))
        return (await handler(request))
    return parse_data


# 处理视图函数返回值，制作response的middleware
# 请求对象request的处理工序：
#   data_factory => request_factory => RequestHandler().__call__ => handler
# 响应对象的response的处理工序：
# 1.由视图函数处理request后返回数据
# 2.@get@post装饰器在返回对象上附加'__method_'和我'__route__'属性， 使其附带URL信息
# 3.response_factory 对处理后的对象，进过一系列类型判断，构造出真正的web.Response对象
# 响应返回处理工厂
async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler...')
        r = await handler(request)
        # StreamResponse是所有Response对象的父类
        if isinstance(r, web.StreamResponse):
            # 无需构造， 直接返回
            return r
        if isinstance(r, bytes):
            # 继承自StreamResponse， 接收body参数，构造HTTP响应内容
            resp = web.Response(body=r)
            # 设置content_type 属性
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            # 若返回重定向字符串
            if r.startswith('redirct:'):
                # 重定向至目标URL
                return web.HTTPFound(r[9:])
            resp = web.Response(body = r.encode('utf-8'))
            resp.content_type = 'text/html; charset = utf-8'
        if isinstance(r, dict):
            # 在后续构造视图函数返回值时， 会加入__template__至，用以选择渲染的模板
            template = r.get('__template__', None)
            # 若不带模板信息，则返回json对象
            if template is None:
                # ensure_ascii : 默认True，仅能输出ascii格式数据，故设置为False
                # default：r对象会被defalut中的函数进行处理，然后被序列化为json对象
                # __dict__：以dict形式返回属性和值的映射
                resp = web.Response(body = json.dumps(r, ensure_ascii = False, default = lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json; charset = utf-8'
                return resp
            # 带模板信息，渲染模板
            else:
                # handler.py 完成后去掉下一行的注释
                # r['__user__'] = request.__user__
                #  app['__templating__']获取已初始化的Environment对象，调用get_template返回template对象
                # 调用Template对象的render()方法，传入r（handler(request)）渲染模板，返回unicode格式字符串，将其用utf-8编码
                resp = web.Response(body = app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html; charset = utf-8'
                return resp
        if isinstance(r, int) and r >=100 and r < 600:
            # 返回响应码
            return web.Response(r)
        # 返回了一组响应代码和原因，如：(200, 'OK'), (404, 'Not Found')
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(t, str(m))

        # default: 以上条件均不满足，默认返回
        resp = web.Response(body = str(r).encode('utf-8'))
        resp.content_type = 'text/plain; charset = utf-8'
        return resp
    return response

## 时间转换

def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta//60)
    if delta < 86400:
        return u'%s小时前' % (delta//3600)
    if delta < 604800:
        return u'%s天前' % (delta//86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%月%日' % (dt.year, dt.month, dt.day)

async def init(loop):
    await www.orm.create_pool(loop = loop, **configs.db)
    ## 在handles.py 完成后 ，在下面的middlewares的list中加入auto_factory
    app = web.Application(loop = loop, middlewares=[logger_factory, response_factory])
    init_jinja2(app, filters = dict(datetime = datetime_filter))
    add_routes(app, 'handlers')
    add_static(app)
    srv = await loop.create_server(app._make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()

















#
# #定义服务器响应请求的返回为"Awesome Website"
# async def index(request):
#     return web.Response(body=b'<h1>Awesome Website</h1>', content_type='text/html')
#
# #建立服务器应用，持续监听本地9000端口的http请求， 对首页的"/"进行响应
# def init():
#     ##函数需要（） 否则回监听失败
#     app = web.Application()
#     #发送get请求？
#     app.router.add_get('/', index)
#     web.run_app(app, host='127.0.0.1', port=9000)
#
# if __name__ == "__main__":
#     init()