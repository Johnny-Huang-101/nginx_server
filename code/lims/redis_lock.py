import time
import uuid
import redis
from lims import app

class DistributedRedisLock:
    """
    A generic Redis-backed distributed lock context manager.
    
    Usage:
        # Lock for Printer (blocks other print jobs)
        with DistributedRedisLock("dymo_printer_lock"):
            ...

        # Lock for specific Case Narrative (blocks only this case, allows others)
        with DistributedRedisLock(f"narrative_lock_{case_id}"):
            ...
    """
    def __init__(self, lock_name, timeout=20, wait_time=0.5):
        """
        :param lock_name: The unique key for this specific lock. 
                          Different names create different parallel queues.
        :param timeout: Max time (seconds) to hold lock before auto-release.
        :param wait_time: Time (seconds) to sleep between retry attempts.
        """
        self.lock_name = lock_name
        self.timeout = timeout
        self.wait_time = wait_time
        self.identifier = str(uuid.uuid4()) # Unique ID for this specific attempt

        # Grab config safely from Flask
        try:
            self.redis_host = app.config.get('CACHE_REDIS_HOST', 'localhost')
            self.redis_port = app.config.get('CACHE_REDIS_PORT', 6379)
        except RuntimeError:
            self.redis_host = 'localhost'
            self.redis_port = 6379

        self.redis_client = redis.Redis(host=self.redis_host, port=self.redis_port, db=0)

    def __enter__(self):
        give_up_time = time.time() + 60 # Default global timeout of 60s
        
        while time.time() < give_up_time:
            # Try to acquire the lock for this specific 'lock_name'
            if self.redis_client.set(self.lock_name, self.identifier, nx=True, ex=self.timeout):
                return self
            
            # Lock is busy, wait
            time.sleep(self.wait_time)
            
        raise Exception(f"System Busy: Could not acquire lock '{self.lock_name}'")

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            current_value = self.redis_client.get(self.lock_name)
            if current_value and current_value.decode() == self.identifier:
                self.redis_client.delete(self.lock_name)
        except Exception as e:
            print(f"Error releasing lock {self.lock_name}: {e}")