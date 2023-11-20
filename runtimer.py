from functools import wraps
from logdef import *
import time, datetime


def runtimer(func):
    @wraps(func)
    def timeit_wrapper(*args, **kwargs):
        runtime_start = time.time()
        result = func(*args, **kwargs)
        runtime = f"runtime: {datetime.timedelta(seconds=(time.time()-runtime_start))}"
        logger.info(f"Function {func.__name__}({[str(a)[:5] + '...' if len(str(a)) > 5 else str(a) for a in args]}) {runtime}")
        return result
    return timeit_wrapper