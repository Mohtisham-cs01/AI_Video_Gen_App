import threading
import queue
import asyncio

class AsyncTaskManager:
    def __init__(self):
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def _worker(self):
        while self.is_running:
            try:
                task_func, args, kwargs, callback = self.task_queue.get(timeout=1)
                try:
                    result = task_func(*args, **kwargs)
                    if callback:
                        self.result_queue.put((callback, result, None))
                except Exception as e:
                    if callback:
                        self.result_queue.put((callback, None, e))
                finally:
                    self.task_queue.task_done()
            except queue.Empty:
                continue

    def submit_task(self, task_func, callback=None, *args, **kwargs):
        """
        Submits a task to be run in the background.
        task_func: The function to run.
        callback: Function to call with the result (result, error).
        """
        self.task_queue.put((task_func, args, kwargs, callback))

    def check_results(self):
        """
        Call this periodically from the main UI thread to process callbacks.
        """
        while not self.result_queue.empty():
            callback, result, error = self.result_queue.get()
            if callback:
                callback(result, error)

    def stop(self):
        self.is_running = False
        if self.worker_thread.is_alive():
            self.worker_thread.join()
