# # lims/queue.py
# """
# Single-worker *priority* queue for Word/COM jobs — console prints only (no files).
# priority: lower runs first (0 = high, e.g., normal Reports; 10 = low, decedent).
# """

# import importlib, uuid, heapq, itertools, threading
# from typing import Any, Dict, List, Tuple
# from concurrent.futures import ProcessPoolExecutor, Future

# try:
#     import pythoncom
# except Exception:
#     pythoncom = None

# # One worker → never touch Word concurrently
# _EXECUTOR: ProcessPoolExecutor = ProcessPoolExecutor(max_workers=1)

# # In-process priority heap + dispatcher
# # (priority, seq, callable_path, kwargs, client_future, job_id)
# _PENDING: List[Tuple[int, int, str, Dict[str, Any], Future, str]] = []
# _JOBS: Dict[str, Future] = {}  # job_id -> client Future
# _SEQ = itertools.count()
# _CV = threading.Condition()
# _RUNNING = False
# _DISPATCHER_STARTED = False


# def _run_callable(callable_path: str, kwargs: Dict[str, Any], job_id: str) -> Any:
#     print(f"[queue] START {job_id} {callable_path}")
#     if pythoncom:
#         try:
#             pythoncom.CoInitialize()
#         except Exception:
#             pass
#     try:
#         module_path, func_name = callable_path.split(":", 1)
#         fn = getattr(importlib.import_module(module_path), func_name)
#         result = fn(**kwargs)
#         print(f"[queue] DONE  {job_id}")
#         return result
#     except Exception as e:
#         print(f"[queue] FAIL  {job_id}: {e!r}")
#         raise
#     finally:
#         if pythoncom:
#             try:
#                 pythoncom.CoUninitialize()
#             except Exception:
#                 pass


# def _dispatch_loop() -> None:
#     global _RUNNING
#     print("[queue] dispatcher thread started")
#     while True:
#         with _CV:
#             while _RUNNING or not _PENDING:
#                 _CV.wait()
#             prio, _, path, kwargs, client_fut, job_id = heapq.heappop(_PENDING)
#             _RUNNING = True

#         pfut = _EXECUTOR.submit(_run_callable, path, kwargs, job_id)

#         def _relay(src: Future, dst: Future = client_fut) -> None:
#             global _RUNNING
#             try:
#                 dst.set_result(src.result())
#             except BaseException as e:
#                 dst.set_exception(e)
#             finally:
#                 with _CV:
#                     _RUNNING = False
#                     _CV.notify_all()
#                     print("[queue] idle; pending:", len(_PENDING))

#         pfut.add_done_callback(_relay)


# def _start_dispatcher_once() -> None:
#     global _DISPATCHER_STARTED
#     if not _DISPATCHER_STARTED:
#         t = threading.Thread(target=_dispatch_loop, name="queue-dispatcher", daemon=True)
#         t.start()
#         _DISPATCHER_STARTED = True


# # Start at import and also on submit (defensive vs. reloads)
# # _start_dispatcher_once()


# def submit(callable_path: str, *, priority: int = 10, **kwargs: Any) -> Future:
#     """
#     Enqueue <module>:<callable>(**kwargs).
#     Returns a Future; also exposes fut.job_id for convenience.
#     """
#     _start_dispatcher_once()
#     job_id = uuid.uuid4().hex[:8]
#     print(f"[queue] QUEUED {job_id} prio={priority} {callable_path}")
#     fut: Future = Future()
#     setattr(fut, "job_id", job_id)
#     with _CV:
#         heapq.heappush(_PENDING, (priority, next(_SEQ), callable_path, kwargs, fut, job_id))
#         _CV.notify()
#     _JOBS[job_id] = fut
#     return fut


# def get_status(job_id: str) -> str:
#     """
#     Return one of: 'unknown' | 'working' | 'ready' | 'error'
#     """
#     fut = _JOBS.get(job_id)
#     if fut is None:
#         return "unknown"
#     if fut.done():
#         try:
#             fut.result()
#             return "ready"
#         except BaseException:
#             return "error"
#     return "working"



import redis
import importlib
import sys
from rq import Queue
from rq.job import Job
from flask import current_app

# ---------------------------------------------------------
#  HELPER: The "Dispatcher" Function
#  This is the ACTUAL function that Redis runs.
#  It takes the string path, imports the function, and runs it.
# ---------------------------------------------------------
def _execute_task(callable_path, kwargs):
    """
    Dynamically imports and executes a function string.
    Run by the worker process.
    """
    try:
        # Split "module.path:func_name"
        module_path, func_name = callable_path.split(":", 1)
        
        # Import the file
        module = importlib.import_module(module_path)
        
        # Get the function
        func = getattr(module, func_name)
        
        # Run it with the arguments
        return func(**kwargs)
    except Exception as e:
        print(f"Task Execution Failed: {e}")
        raise e

# ---------------------------------------------------------
#  PUBLIC API
# ---------------------------------------------------------

def get_redis_conn():
    """Helper to get connection safely from Flask config"""
    try:
        host = current_app.config.get('CACHE_REDIS_HOST', 'localhost')
        port = current_app.config.get('CACHE_REDIS_PORT', 6379)
    except:
        # Fallback if called outside request context
        host, port = 'localhost', 6379
        
    return redis.Redis(host=host, port=port, db=0)

def submit(callable_path: str, *, priority: int = 10, **kwargs) -> Job:
    """
    Enqueues a task to Redis. 
    Maps priority integers to Queue names:
      0-4  -> 'high' (Reports, Printer)
      5+   -> 'low'  (Litigation Packets)
    """
    r = get_redis_conn()
    
    # 1. Map Integer Priority to Queue Name
    if priority < 5:
        queue_name = 'high'
    else:
        queue_name = 'low'
        
    q = Queue(queue_name, connection=r)

    # 2. Enqueue the generic dispatcher
    # We set a long timeout (1 hour) because generating large PDFs/Word docs is slow
    job = q.enqueue(
        _execute_task, 
        args=(callable_path, kwargs),
        job_timeout='1h',
        result_ttl=120, # Keep result for 2min        meta={'original_priority': priority}
    )
    
    # 3. Compatibility Patch
    # Your existing routes expect `job.job_id`, but RQ uses `job.id`
    job.job_id = job.id
    
    return job

def get_status(job_id: str) -> str:
    """
    Return one of: 'unknown' | 'working' | 'ready' | 'error'
    Used by your frontend polling.
    """
    try:
        r = get_redis_conn()
        job = Job.fetch(job_id, connection=r)
        status = job.get_status()
        
        if status == 'finished':
            return 'ready'
        elif status == 'failed':
            return 'error'
        elif status in ['queued', 'started', 'deferred']:
            return 'working'
        else:
            return 'unknown'
    except Exception:
        return 'unknown'