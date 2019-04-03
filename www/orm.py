import asyncio, logging, aiomysql

#使用aiomysql的原因时网站是基于异步编程，系统的每一层都必须是异步

#log
def log(sql, args = ()):
    logging.info('SQL:%s'%sql)

#创建全局的线程池，使每个http请求都可以从连接池获取数据库连接, 传入loop？
async def create_pool(loop, **kw):
    logging.info('create database connection pool...')
    #定义一个全局的进程池
    global  __pool
    #连接池由__pool存储， 使用await aiomysql.create_pool创建
    __pool = await aiomysql.create_pool(
        #获取目标ip
        host = kw.get('host', 'localhost'),
        port = kw.get('port', 3306),
        user = kw['user'],
        password = kw['password'],
        # 不能忘记db否则会造成不能连接数据库错误
        db = kw['db'],
        charset = kw.get('charset', 'utf8'),
        #实现事务自动提交功能，数据库中表类型必须是InnoDB,在客户端输入SQL语句， 每次都会自动执行一次commit
        autocommit = kw.get('autocommit', True),
        #设置最大空闲连接数（大于的话就关闭空闲连接）和最小连接数（大于于的话就创建一个连接）
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
    )

#执行select语句, size 决定了可以取得几条
#此时由fetchall（）返回一个结果集， 结果集是一个list， 每一个元素都是tuple，对应一条记录
async def select(sql, args, size = None):
    log(sql, args)
    global __pool
    with (await __pool) as conn:
        #aiomysql.DictCursor的作用使生成结果是一个dict
        cur = await conn.cursor(aiomysql.DictCursor)
        #执行前面的用%s替换？的sql.replace('?', '%s')
        #传入的args or ()是替换？的参数
        await cur.execute(sql.replace('?', '%s'), args or ())
        #如果传入的参数不为零，获取size个数据，为0的话则获取下一个数据
        if size:
            rs = await cur.fetchmany(size)
        else:
            rs = await cur.fetchall()
        #关闭游标
        await cur.close()
        logging.info('rows returned %s' % len(rs))
        ##rs是一个结果集
        return rs



#封装execute（）函数，执行insert update delete 语句可以使用通用的execute()函数
async def execute(sql, args):
    log(sql)
    with (await __pool) as conn:
        try:
            cur = await conn.cursor()
            # 执行前面的用%s替换？的sql.replace('?', '%s')
            # 传入的args or ()是替换？的参数
            await cur.execute(sql.replace('?', '%s'), args)
            #执行结果由rowcount返回影响的行数
            affected = cur.rowcount
            await cur.close()
        except BaseException as e:
            raise
        ##affect返回的是结果数，这就是两个函数的区别
        return affected

#建立Field（字段）类
class Field(object):
    def __init__(self, name, column_type, primary_key, default):
        #字段名
        self.name = name
        #字段数据类型
        self.column_type = column_type
        #是否为主键
        self.primary_key = primary_key
        #是否有默认值
        self.default = default
    #设置输出格式
    def __str__(self):
        return '<%s, %s:%s>' %(self.__class__.__name__, self.column_type, self.name)
#以下几个field类都继承了父类的初始化方法以及输出方法
#super()作为父类的构造函数，
class StringField(Field):
    def __init__(self, name = None, primary_key = False, default = None, ddl = 'varchar(100)'):
        super().__init__(name, ddl, primary_key, default)

class BooleanField(Field):
    def __init__(self, name = None, default = False):
        super().__init__(name, 'boolean', False, default)

class IntegerField(Field):
    def __init__(self, name = None, primary_key = False, default = 0):
        super().__init__(name, 'bigint', primary_key, default)

class FloatField(Field):
    def __init__(self, name = None, primary_key = False, default =  0):
        super().__init__(name, 'real', primary_key, default)

class TextField(Field):
    def __init__(self, name = None, default = None):
        super().__init__(name, 'text', False, default)

##用于输出元类中创建sql_insert语句中的占位符

def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ', '.join(L)

###ORM
####Model只是一个基类，如何将具体的子类如User的映射信息读取出来呢？答案就是通过metaclass：ModelMetaclass
class ModelMetaclass(type):
    #cls 表示即将创建的类的对象
    # name表示类名，创建User类，则name便是User
    # bases表示类继承的父类集合, 创建User类，则base便是Model
    # attrs表示类的属性/方法集合如id等属性，创建User类，则attrs便是一个包含User类属性的dict
    ### 元类必须实现__new__方法，当一个类指定通过某元类来创建，那么就会调用该元类的__new__方法
    def __new__(cls, name, bases, attrs):
        #排除Model类本身
        # 因为Model类是基类，所以排除掉，如果你print(name)的话，会依次打印出Model,User,Blog，即
        # 所有的Model子类，因为这些子类通过Model间接继承元类
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        #获取table名称：默认与类名相同
        tableName = attrs.get('__table__', None) or name
        #获取到表名后输出日志，如果表名不正确，则可以从日志中找出
        logging.info('found model:%s(table:%s)' % (name, tableName))
        #获取所有的Field和主键名：
        ### 用于存储所有的字段，以及字段值
        mappings = dict()
        # 仅用来存储非主键意外的其它字段，而且只存key
        fields = []
        primaryKey = None
        ###v的值为id,name,email,password
        ###k的值为IntegerField,StringField,StringField,StringField
        ###迭代查找主键和非主键
        # 注意这里attrs的key是字段名，value是字段实例，不是字段的具体值
        # 比如User类的id=StringField(...) 这个value就是这个StringField的一个实例，而不是实例化
        # 的时候传进去的具体id值
        for k, v in attrs.items():
            # attrs同时还会拿到一些其它系统提供的类属性，我们只处理自定义的类属性，所以判断一下
            # isinstance 方法用于判断v是否是一个Field
            if isinstance(v, Field):
                ###所以输出例子类似：Found mapping:  <StringField:email> ==>email
                logging.info('  found mapping: %s ==> %s' % (k,v))
                ###之所以在此处使用k是为了找到主键，找到之后就可以删除了
                mappings[k] = v
                ###如果v中有主键属性
                if v.primary_key:
                    # 找到主键
                    if primaryKey:
                        raise  RuntimeError('Duplicate primary key for field:%s' % k)
                    #保存主键
                    primaryKey = k
                else:
                    # 保存除主键外的属性
                    fields.append(k)
        if not primaryKey:
            raise RuntimeError('Primary key not found.')
        #从类属性中删除field属性，否则，容易造成运行时错误（实例的属性会遮盖类的同名属性）
        # 这里的目的是去除类属性，为什么要去除呢，因为我想知道的信息已经记录下来了。
        # 去除之后，就访问不到类属性了，如图
        # 记录到了mappings,fields，等变量里，而我们实例化的时候，如
        # user=User(id='10001') ，为了防止这个实例变量与类属性冲突，所以将其去掉
        for k in mappings.keys():
            attrs.pop(k)
        #转换为sql语法
        escaped_fields = list(map(lambda f:'`%s`' % f, fields))
        # 以下都是要返回的东西了，刚刚记录下的东西，如果不返回给这个类，又谈得上什么动态创建呢？
        # 到此，动态创建便比较清晰了，各个子类根据自己的字段名不同，动态创建了自己
        # 下面通过attrs返回的东西，在子类里都能通过实例拿到，如self
        #保存属性和列的映射关系
        attrs['__mappings__'] = mappings
        #表名
        attrs['__table__'] = tableName
        #主键属性名
        attrs['__primary_key__'] = primaryKey
        #除主键外的属性名
        attrs['__fields__'] = fields
        #构造默认的select， insert， update和update语句：
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields),tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ','.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields)+1))
        attrs['__update__'] = 'update `%s` set %s  where `%s` = ?' % (tableName, ','.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s` = ?' % (tableName, primaryKey)
        return type.__new__(cls,name, bases, attrs)


#基类
#让model继承dict，主要是为了具备dict所有的功能，如get方法
#metaclass指定元类为ModelMetaclass
class Model(dict, metaclass=ModelMetaclass):
    # 构造函数
    def __init__(self, **kw):
        #调用父类构造函数
        super(Model,self).__init__(**kw)
    #xxxxx实现__getattr__方法和__setattr__方法可以像引用普通字段一样，如print（model（'key'））model（'可以'）
    ####如果取不到值报错，这是一个魔术方法，使用时直接gettattr（obj，key）
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attributr '%s'" % key)
    ####同魔术方法， 设置一个值，使用时setattr（obj， key， val）
    def __setattr__(self, key, value):
        self[key] = value
    ####类方法，获取一个值
    def getValue(self, key):
        return getattr(self, key, None)
    ####类方法，获取一个值或者其默认值，字段类中的默认值属性，也可以是函数
    ####__mappings__，里面是一个属性名到列的映射。
    #### 所以 getValueOrDefault 就好理解了，
    #### 就是获取某个属性的值，如果该对象的该属性还没有赋值，就去获取它对应的列的默认值
    def getValueOrDefault(self, key):
        #赋值，用getattr获取self[key] 赋给 value
        #第三个参数None，可以在没有返回数值时，返回None，调用于save
        value = getattr(self, key, None)
        if value is None:
            #__mappings__可以通过属性名对列的映射
            #__mappings__这个方法在modelmetaclass中被定义，可以获取属性对应列的一个对象
            field = self.__mappings__[key]
            #如果该列有默认值
            if field.default is not None:
                #### 此处要考虑field是否是个方法
                #### 如果field是个方法value就是field被调用后返回的值， 否者value就是default本身
                value  = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s:%s' % (key, str(value)))
                setattr(self, key, value)
        return value
    #添加class方法，以便让所有子类调用
    #where值字段名， args是属性值
    # User.findAll('email=?', [email])
    @classmethod
    async def findAll(cls, where = None, args = None, **kw):
        ## find objects by where clause（字段）
        ## cls 表示即将创建的类的对象
        ## 调用select映射到 modelmetaclass 中的select语句
        sql = [cls.__select__]
        ##如果字段有值的话，就缇娜家
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        # args 如果不等于None，就会直接传入sql语句中，之后孩子 i 选哪个
        ##kw中存储着排列方法和limit方法，如果不能获取到值的话， 就返None
        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            # 如果limit是个tuple的话 并且长度等于2
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?, ?')
                # tuple融入list
                args.extend(limit)
            # 仅运行limit有两个限制，否则报错
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        #select（） 是之前定义的方法，sql是语句，后面的args是值，这样就模拟了手动输入select name from table where id = '1'
        #例子中1存在args中，其他存在sql中
        rs = await select(' '.join(sql), args)
        return [cls(**r) for r in rs]   #return rs一样

    @classmethod
    async def findNumber(cls, selectField, where = None, args = None):
        ## find number by select and where
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        #执行查找num字段，select 对象名 _num_ from 表名 where
        rs = await select(' '.join(sql), args, 1)
        #如果找不到，返回null
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    @classmethod
    async def find(cls, pk):
        ## find object by primary key
        ##'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields,tableName))
        ##cls.__select__ where cls.__primary_key__ = ?
        ##此处直接进行了sql语句集成，前面是sql语句，后面[pk]是where 的映射，返回一行
        rs = await select('%s where `%s` = ?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    #下面的save ,self.__mappings__,self__insert__等变量都是根据对应表的字段不同而动态映射的
    #调用时注意，看清是不是协程，注意使用yield from
    #save时必须要有主键的值
    async def save(self):
        #默认值和其列对应，用map保存
        args = list(map(self.getValueOrDefault, self.__fields__))
        #获取与主键的映射
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = await execute(self.__insert__, args)
        if rows != 1:
            logging.warn('failed to update by primary key: affected rows:%s' % rows)

    async def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warn('failed to update by primary key:affected rows: %s' % rows)

    async def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.warn('failed to remove by primary key:affect rows:%s' %rows)





