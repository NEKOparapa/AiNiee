"""Bounded file workers with acknowledged callbacks on the calling thread."""
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from queue import Empty, Queue

from Backend.domain.models.cache_project import CacheProject
from Backend.domain.models.cache_file import CacheFile


def isolated_file_project(project, file):
    # Round-trip public fields, avoiding cache locks and copies of other assets.
    return CacheProject.from_dict(
        replace(project, files={file.storage_path: file}, stats_data=None).to_dict())


def copy_file(file):
    return CacheFile.from_dict(file.to_dict())


def run_file_workers(files, worker, *, workers, context, on_event, on_result, prefix):
    """Each worker owns one file; only this thread may commit shared state.

    emit() waits for the callback to finish, so a worker cannot send a paid
    request before its prepared checkpoint has been durably acknowledged.
    Keep pumping events after cancellation until every active worker drains.
    """
    events = Queue()
    pending = {}
    next_index = 0
    failure = None

    def execute(index, file):
        def emit(payload):
            acknowledgement = Future()
            events.put((index, payload, acknowledgement))
            return acknowledgement.result()
        return worker(index, file, emit)

    with ThreadPoolExecutor(max_workers=min(workers, len(files)), thread_name_prefix=prefix) as pool:
        while pending or (next_index < len(files) and not context.is_cancelled()):
            while len(pending) < workers and next_index < len(files) and not context.is_cancelled():
                index = next_index
                next_index += 1
                pending[pool.submit(execute, index, files[index])] = index
            if not pending:
                break
            try:
                index, payload, acknowledgement = events.get(timeout=0.02)
            except Empty:
                pass
            else:
                try:
                    acknowledgement.set_result(on_event(index, payload))
                except Exception as error:
                    context.cancel()
                    acknowledgement.set_exception(error)
            for future in sorted((f for f in pending if f.done()), key=pending.get):
                index = pending.pop(future)
                try:
                    on_result(index, future.result())
                except Exception as error:
                    context.cancel()
                    failure = failure or error
    if failure is not None:
        raise failure
