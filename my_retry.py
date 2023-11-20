import socket, httpx
from random import random
from socket import error as SocketError
from googleapiclient.errors import HttpError
from time import sleep
from functools import wraps
from logdef import *
import time
import datetime

def runtimer(func):
    @wraps(func)
    def timeit_wrapper(*args, **kwargs):
        runtime_start = time.time()
        result = func(*args, **kwargs)
        runtime = f"runtime: {datetime.timedelta(seconds=(time.time()-runtime_start))}"
        logger.info(f"Function {func.__name__}({args}) {runtime}")
        return result
    return timeit_wrapper

def my_retry(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        failures = 0
        max_tries = 11
        tries = 1
        sleep_time = 1
        max = 2048
        while (tries <= max_tries):
            try:
                tries += 1
                return fn(*args, **kwargs)
            except (MyRetryError, socket.timeout, SocketError, HttpError, TimeoutError, httpx.ReadTimeout, httpx.ConnectError, httpx.ReadError, httpx.ConnectTimeout) as e:
                logger.error(e)
                if isinstance(e, HttpError):
                    if e.status_code in [400, 404, 403]:
                        raise

                    # if "Precondition check failed" in str(e):
                    #     raise
                if sleep_time >= max:
                    logger.fatal("Max backoff exceeded; aborting")
                    # send_email('pbowman@acsamman.edu.jo', "Max backoff exceeded; aborting", str(e))
                    raise
                failures += 1
                sleep_time = 2 ** tries + random()
                logger.error(f"request failed {failures} times")
                
                logger.error(f"waiting {sleep_time} seconds")
                sleep(sleep_time)
                #sleep_time = tries * sleep_time + randint(1, 10)
    return wrapped

class MyRetryError(Exception):
    def __init__(self, Exception):
        pass
    def __str__(self):
        return "intentional error"

class Whoopsie:
    def __init__(self):
        self.whoopsie()
    @my_retry
    def whoopsie(self):
        raise MyRetryError("this is an intentional error")


