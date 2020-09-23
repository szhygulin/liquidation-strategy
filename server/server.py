import json
import logging
from aiohttp import web
import os
import random

PORT = 80
logging.basicConfig(level="INFO")
LOG = logging.getLogger(__name__)
LOG.setLevel('INFO')
counter = 0

async def do_get(request):
    #if random.randint(0,10) == 0:
    os.system('python3 retreive_data.py')
    #else:
    #    os.system('python3 retreive_data_cached.py')
    with open('result.json', 'r') as f:
        data = json.load(f)
    response = web.json_response(data)
    return response

async def do_post(request):
    result = await request.json()
    logging.info(str(result))
    with open('result.json', 'r') as f:
        data = json.load(f)
    response = {}
    # reformat output
    response = web.json_response(response)
    return response


async def mirror(request):
    request = await request.json()
    logging.info(str(request))
    result = request
    response = web.json_response(result)
    return response

async def web_app():
    app = web.Application()
    app.add_routes([web.post('/', do_post),
                    web.post('/ping', mirror)])
    return app


# this should be used for standalone mode
# in normal run prefer to use gunicorn setup
if __name__ == "__main__":
    #port = int(os.environ.get('PORT', 80))
    port = int(os.environ.get('PORT', 80))
    logging.info("serving at port " + str(port))
    app = web.Application()
    app.add_routes([web.post('/', do_post),
                    web.get('/', do_get),
                    web.post('/ping', mirror)])
    web.run_app(app, port=port)



