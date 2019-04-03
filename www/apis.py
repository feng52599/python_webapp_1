import json, logging, inspect, functools

#建立Page类来处理分页， 可以在page_size更改每页项目的个数

class Page(object):

    def __init__(self, item_count, page_index = 1, page_size = 8):
        # 记录总数
        self.item_count = item_count
        # 每页记录数
        self.page_size = page_size
        # 页数 = 总数/每页记录数 加1 是因为如果数据较多，后一页数据未满
        # 例：如果有18条数据， 每页5条，item_count//page_size = 3 ，存不下要加一页
        self.page_count = item_count//page_size + (1 if item_count % page_size >0 else 0)
        # 页面索引 > 页面数
        if (item_count == 0) or (page_index > self.page_count):
            self.offset = 0
            self.limit =0
            self.page_index = 1
        else:
            self.page_index = page_index
            # 页面偏移？？？
            self.offset = self.page_size * (page_index - 1)
            # 页面限制？
            self.limit = self.page_size
        self.has_next = self.page_index < self.page_count
        self.has_previous = self.page_index > 1

    def __str__(self):
        return 'item_count: %s, page_count: %s, page_index: %s, page_index: %s, offset:%s, limit: %s' % (
            self.item_count, self.page_count, self.page_index, self.page_size, self.offset, self.limit
        )

    __repr__ = __str__

class APIError(Exception):
    #  基础的APIError，包含错误类型(必要)，数据(可选)，信息(可选)
    def __init__(self, error, data = '', message =''):
        super(APIError, self).__init__(message)
        self.error = error
        self.data = data
        self.message = message
# 输入数据有问题
class APIValueError(APIError):
    def __init__(self, field, message = ''):
        super(APIValueError, self).__init__('value:invalid', field, message)

class APIResourceNotFoundError(APIError):
    def __init__(self, message = ''):
        super(APIResourceNotFoundError, self).__init__('permission:forbidden', 'permission', message)

class APIPermisssionError(APIError):
    def __init__(self, message = ''):
        super(APIResourceNotFoundError, self).__init__('permission:forbidden', 'permission', message)

if __name__ == '__main__':
    import doctest
    doctest.testmod()


