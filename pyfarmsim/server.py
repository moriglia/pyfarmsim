import simpy as sp
from .utils import pretty_time as t
from .utils import DebugPrint
from .usagemanager import UsageManager as UM
from functools import wraps


debug = DebugPrint()


def get_queue_monitor(fnc, srv, env):
    @wraps(fnc)
    def monitor(*args, **kwargs):
        ret = fnc(*args, **kwargs)
        srv._queue_log.append((env.now, srv.queue_len))
        return ret

    return monitor


class FullQueue(Exception):
    def __init__(self, message):
        super().__init__(message)


class Server(sp.resources.resource.Resource, UM):
    """
    This class has been created to model a Virtualized Physical Machine.
    The capacity represents the number of Virtual Machines.
    """
    def __init__(self, env=None, capacity=4, length=10, name=None):
        # Set environment and capacity
        e = env if env else sp.Environment()
        sp.resources.resource.Resource.__init__(self, e, capacity)
        UM.__init__(self, capacity, e)

        # define a maximum length
        self._queue_len_max = length

        self._name = name

        # monitoring logs
        self._submission_log = []
        self._fail_log = []
        self._queue_log = []
        for name in ['put', 'get', 'request', 'release']:
            setattr(
                self,
                name,
                get_queue_monitor(getattr(self, name), self, self._env)
            )

    def __str__(self):
        return f"{self.name} usage: {self.count}/{self.capacity}VMs \
            {self.queue_len}/{self._queue_len_max}"

    def set_capacity(self, new_capacity):
        """
        Tune the number of VMs
        """
        old_capacity = self._capacity
        self._capacity = new_capacity

        if old_capacity >= new_capacity:
            """
            When the VM will be released, they will not be reallocated
            and the change will really take effect. But if there are free VMs
            the capacity takes immediately effect
            """
            if self.count < old_capacity:
                self._capacity_changes.appendleft(
                    (
                        # Time the change occurred
                        self._env.now,
                        # If the least is count, then the new capacity takes
                        # immediately effect
                        # If the least is the new capacity, then the
                        # capacity reduction takes effect from count
                        # progressively down to the new_capacity
                        max(new_capacity, self.count)
                    )
                )
        else:
            """
            If we increased the number of VMs, we must check the queue
            This function iterates over the queue and allocates the
            newly available VMs to the first requests in queue
            """
            self._capacity_changes.appendleft(
                    (
                        self._env.now,    # time the change occurred
                        new_capacity      # capacity after the change
                    )
                )
            self._trigger_put(None)

        return

    @property
    def name(self):
        return self._name

    @property
    def queue_len(self):
        return len(self.queue)

    def __request_process(self, webrequest):
        """
        The Request class has infinite queue. But real web servers
        have a finite queue. In this generator I implemented the
        limitedness of the queue
        """

        if (self.queue_len < self._queue_len_max):
            with self.request() as req:
                debug(f"[T: {t()}] {self}, alloc VM to {webrequest.id}.")
                yield req  # get a computational resource (VM or CPU)

                with self.CPU_record_usage(webrequest.id):
                    # While recording VM / CPU usage, serve the request
                    debug(f"[T: {t()}] {self}, \
                        alloc VM OK {webrequest.id} for {webrequest.time}.")
                    yield self._env.timeout(webrequest.time)
                    if not webrequest.triggered:
                        webrequest.succeed(0)

                if self.count > self.capacity:
                    self._capacity_changes.appendleft(
                        (
                            self._env.now,    # time the change occurred
                            self.count-1      # capacity after the change
                        )
                    )

            debug(f"[T: {t()}] {self}, freed VM fr {webrequest.id}.")
        else:
            fq = FullQueue(f"Server queue reached the maximum. {self}")
            self._fail_log.append((self._env.now, webrequest.id))
            webrequest.fail(fq)

        return

    def submit_request(self, webrequest):
        """
        This function creates the event of "acquired VM" and returns it.
        The caller can yield the returned event to sleep and to be woken up
        once the top of the queue is reached
        """

        # Record submission
        self._submission_log.append((self._env.now, webrequest.id))

        return self._env.process(self.__request_process(webrequest))

    @property
    def submission_log(self):
        return self._submission_log.copy()

    @property
    def fail_log(self):
        return self._fail_log.copy()

    @property
    def queue_log(self):
        return self._queue_log.copy()
