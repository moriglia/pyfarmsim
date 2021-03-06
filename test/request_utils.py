import random
import time
from pyfarmsim.utils import DebugPrint, pretty_time as t
from pyfarmsim.server import FullQueue
from pyfarmsim.webrequest import WebRequest

random.seed(time.time())
debug = DebugPrint()


def usage_ask(env, s, iterations, interval):
    for i in range(iterations):
        yield env.timeout(interval)
        u = s.usage_last_interval(0.5)
        debug(f"[T: {t()}] {s} CPU utilization: {u*100}%, sample {i} ")


def incoming_request(idn, env, server, processing_time):
    wr = WebRequest(env, processing_time, None)
    try:
        debug(f"[T: {t()}] Sending REQ {wr.id} to {server.name}")
        server.submit_request(wr)
        err = yield wr.wait_for_completion()
        if err == 0:
            debug(f"[T: {t()}] REQ {wr.id} successful")
        else:
            raise err
    except FullQueue as fq:
        debug(f"[T: {t()}] REQ {wr.id} rejected: {fq}")

    return


def capacity_setter(env, server):
    for i in range(5):
        yield env.timeout(0.5)
        debug(f"[T: {t()}] Updating capacity: {server}")
        server.set_capacity(5+i)
        debug(f"[T: {t()}] Updated  capacity: {server}")

    for i in range(5):
        yield env.timeout(0.5)
        debug(f"[T: {t()}] Updating capacity {server}")
        server.set_capacity(10-i)
        debug(f"[T: {t()}] Updated  capacity {server}")


class MockServer:
    def __init__(self):
        self._request_list = []
        self._usage = random.random()

    def usage_last_interval(self, interval):
        return self._usage

    def submit_request(self, req):
        self._request_list.append(req)
        req.succeed()


class MockLoadBalancer:
    def __init__(self, queue_length=0, usage_last_interval=0, count=0):
        self._queue_length = queue_length
        self._request_list = []
        self._usage_last_interval = usage_last_interval
        self._count = count

    @property
    def queue_length(self):
        return self._queue_length

    def submit_request(self, request):
        self._request_list.append(request)
        request.succeed()

    def usage_last_interval(self, interval):
        return self._usage_last_interval

    @property
    def count(self):
        return self._count
