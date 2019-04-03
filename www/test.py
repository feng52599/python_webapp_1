import www.orm
import asyncio
from www.models import User, Blog, Comment

async def test(loop):
    await www.orm.create_pool(loop = loop, user = 'root', password = 'lsh525', db = 'awesome')
    u = User(name = 'Test', email = '12345@qq.com', passwd = '12345', image = 'about:blank')
    await u.save()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test(loop))
    loop.close()
