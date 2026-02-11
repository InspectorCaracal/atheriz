import asyncio
from asyncio import AbstractEventLoop
import os
from threading import Lock, Thread, RLock
import time
from typing import Optional
import traceback
import queue
from atheriz.logger import logger
from atheriz.settings import DEBUG


class AsyncThread(Thread):
    def __init__(self, loop: AbstractEventLoop, num: int):
        self.loop = loop
        self.stop_event = asyncio.Event()
        super().__init__(None, daemon=True)
        self.name = f"AsyncThread{num}"
        self.wait = False

    def run(self):
        self.loop.run_until_complete(self.stop_event.wait())
        # print(f"thread is stopping: {self.name}")
        if self.wait:
            pending = asyncio.all_tasks(self.loop)
            if pending:
                self.loop.run_until_complete(asyncio.gather(*pending))
        # self.loop.stop()
        # self.loop.close()

    async def do_stop(self):
        self.stop_event.set()  # gotta set this event from inside this thread

    def stop(self, wait):  # True = wait for shit to finish
        self.wait = wait
        asyncio.run_coroutine_threadsafe(self.do_stop(), self.loop)


class AsyncThreadPool:
    def __init__(self, max_threads: Optional[int] = None, default_timeout=None):
        if max_threads == None:
            max_threads = os.cpu_count() or 4
        self.max_threads = max_threads
        self.threads = []
        self.loop = asyncio.new_event_loop()
        self.threads.append(AsyncThread(self.loop, 0))
        self.threads[0].start()  # first thread is for async
        self.timeout = default_timeout
        self.task_queue = queue.Queue()
        for _ in range(max_threads - 1):  # rest of the threads for sync
            t = Thread(daemon=True, target=self._work_loop)
            t.start()
            self.threads.append(t)

    def _work_loop(self):
        async def do_async(func, *args, **kwargs):
            try:
                await func(*args, **kwargs)
            except Exception as e:
                tb = traceback.format_exc()
                if DEBUG:
                    try:
                        caller = args[0]
                        caller.msg(f"{tb}")
                    except Exception as e2:
                        logger.error(f"Exception while sending exception to caller: {e2}")
                logger.error(f"{tb}")

        while True:
            task = self.task_queue.get()
            if task is None:  # kill signal
                # print("worker thread stopping...")
                break
            func, args, kwargs = task
            if hasattr(func, "__code__") and func.__code__.co_flags & 128 == 128:
                # logger.info(f"async task: {func}")
                asyncio.run_coroutine_threadsafe(do_async(func, *args, **kwargs), self.loop)
            else:
                try:
                    # logger.info(f"sync task: {func}")
                    func(*args, **kwargs)
                except Exception as e:
                    tb = traceback.format_exc()
                    if DEBUG:
                        try:
                            caller = args[0]
                            caller.msg(f"{tb}")
                        except:
                            pass
                    logger.info(f"{tb}")

    def stop(self, wait=True):
        """
        Stop AsyncThreadPool. AsyncTicker should be stopped first.
        Args:
            wait (bool, optional): wait for async tasks to finish. Defaults to True.
        """
        print("at AsyncThreadPool.stop() ...")
        self.threads[0].stop(wait)
        for _ in range(self.max_threads):
            self.task_queue.put(None)

    def add_task(self, func, *args, **kwargs):
        """
        execute a function on the threadpool
        Args:
            func (callable): coroutine or function to execute
            args: func args
            kwargs: func kwargs
        """
        self.task_queue.put((func, args, kwargs))


class AsyncTicker:
    class TimeSlot:
        def __init__(self, interval: float) -> None:
            self.lock = RLock()
            self.interval = interval
            self.coros = set()
            self.running = False
            self.task = None

        def add_coro(self, coro):
            with self.lock:
                self.coros.add(coro)

        def remove_coro(self, coro):
            with self.lock:
                try:
                    self.coros.remove(coro)
                except:
                    pass

        def stop(self):
            with self.lock:
                self.running = False
                if self.task:
                    self.task.cancel()

        async def timer(self):
            while True:
                with self.lock:
                    if not self.running:
                        return
                    self.task = asyncio.create_task(asyncio.sleep(self.interval))
                await self.task
                with self.lock:
                    for c in self.coros:
                        AsyncTicker.atp.add_task(c)

        def start(self):
            if not self.running:
                self.running = True
                AsyncTicker.atp.add_task(self.timer)

    def __init__(self, atp: AsyncThreadPool) -> None:
        AsyncTicker.atp = atp
        self.lock = RLock()
        self.slots: dict[float, AsyncTicker.TimeSlot] = {}

    def add_coro(self, coro, interval: float):
        with self.lock:
            slot = self.slots.get(interval)
            if not slot:
                slot = AsyncTicker.TimeSlot(interval)
                slot.add_coro(coro)
                self.slots[interval] = slot
                slot.start()
                return
        slot.add_coro(coro)
        slot.start()

    def remove_coro(self, coro, interval: float):
        with self.lock:
            slot = self.slots.get(interval)
        if slot:
            slot.remove_coro(coro)
            if len(slot.coros) == 0:
                slot.stop()

    def stop(self):
        """
        stop all running tickers
        """
        print("at AsyncTicker.stop() ...")
        with self.lock:
            try:
                for v in self.slots.values():
                    v.stop()
            except:
                pass


# class TestAddCoros:
#     def __init__(self, count, threads) -> None:
#         self.finished = False
#         self.count = count
#         self.counter = 0
#         self.lock = Lock()
#         self.atp = AsyncThreadPool(threads)

#     def start(self):
#         coros = []
#         for x in range(self.count):
#             coros.append(self.test(x))
#         start = time.time()
#         self.atp.add_coroutines(coros)
#         while not self.finished:
#             time.sleep(0.01)
#         elapsed = time.time() - start
#         print(f"elapsed = {elapsed}")
#         self.atp.stop(True)

#     async def test(self, x: int):
#         with self.lock:
#             self.counter += 1
#             if self.counter == self.count - 1:
#                 self.finished = True
#         print(x)
#         await asyncio.sleep(5)


# class TestAddCorosThreaded:
#     def __init__(self, count, threads) -> None:
#         self.finished = False
#         self.count = count
#         self.counter = 0
#         self.threads = threads
#         self.lock = Lock()
#         self.atp = AsyncThreadPool(threads)

#     def do_thread(self):
#         for x in range(self.count):
#             self.atp.add_task(self.test, x)

#     def start(self):
#         for _ in range(self.threads):
#             t = Thread(None, self.do_thread)
#             t.start()
#         start = time.time()
#         while not self.finished:
#             time.sleep(0.01)
#         elapsed = time.time() - start
#         print(f"elapsed = {elapsed}")
#         self.atp.stop()

#     async def test(self, x: int):
#         with self.lock:
#             self.counter += 1
#             if self.counter == self.count * self.threads - 1:
#                 self.finished = True
#         print(x)
#         await asyncio.sleep(5)

# def test():
#     print('test!')
# test.__await__ = test
# asyncio.run(test())
# print('done!')


# async def test1():
#     print("1 second!")


# async def test2():
#     print("2 seconds!")


# atp = AsyncThreadPool(6)
# at = AsyncTicker(atp)
# at.add_coro(test1, 1)
# at.add_coro(test2, 666666)
# time.sleep(5)
# print("sending stop...")
# at.stop()
# atp.stop()
# print("done!")

# 12 threads will each add 5,000 coroutines at the same time to execute on a threadpool of another 12 threads
# test = TestAddCorosThreaded(5000, 12)
# test.start()
# # this thread will add one list of 10,000 coroutines to be executed on a threadpool of 12 threads
# # test = TestAddCoros(10000, 12)
# # test.start()
# print('done!')
