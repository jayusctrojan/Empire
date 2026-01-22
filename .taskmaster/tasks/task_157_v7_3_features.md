# Task ID: 157

**Title:** B2 Storage Error Handling

**Status:** done

**Dependencies:** 137 ✓, 153 ✓

**Priority:** medium

**Description:** Implement robust error handling for B2 storage operations including retry logic for uploads/downloads, checksum verification, dead letter handling for failed operations, and storage metrics collection.

**Details:**

Enhance the B2 storage service with comprehensive error handling mechanisms:

1. Implement retry logic with exponential backoff for upload/download operations:
   ```python
   from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
   from b2sdk.exception import B2ConnectionError, B2RequestTimeout
   
   @retry(
       stop=stop_after_attempt(5),
       wait=wait_exponential(multiplier=1, min=2, max=60),
       retry=retry_if_exception_type((B2ConnectionError, B2RequestTimeout))
   )
   async def resilient_b2_upload(file_path, destination_path):
       try:
           return await b2_client.upload_file(file_path, destination_path)
       except Exception as e:
           logger.error(f"B2 upload error: {str(e)}")
           raise
   ```

2. Implement checksum verification for data integrity:
   ```python
   import hashlib
   
   def calculate_sha1(file_path):
       sha1 = hashlib.sha1()
       with open(file_path, 'rb') as f:
           while chunk := f.read(8192):
               sha1.update(chunk)
       return sha1.hexdigest()
   
   async def verify_upload_integrity(local_file_path, b2_file_info):
       local_checksum = calculate_sha1(local_file_path)
       remote_checksum = b2_file_info.content_sha1
       
       if local_checksum != remote_checksum:
           logger.error(f"Checksum mismatch for {local_file_path}")
           raise IntegrityError(f"Upload verification failed: checksums don't match")
       
       return True
   ```

3. Implement dead letter queue for failed uploads:
   ```python
   class B2DeadLetterQueue:
       def __init__(self, redis_client, queue_name="b2_dead_letter_queue"):
           self.redis = redis_client
           self.queue_name = queue_name
       
       async def add_failed_operation(self, operation_type, file_path, error_details, retry_count):
           entry = {
               "operation_type": operation_type,
               "file_path": file_path,
               "error_details": str(error_details),
               "retry_count": retry_count,
               "timestamp": datetime.utcnow().isoformat()
           }
           await self.redis.lpush(self.queue_name, json.dumps(entry))
       
       async def get_failed_operations(self, limit=100):
           entries = await self.redis.lrange(self.queue_name, 0, limit-1)
           return [json.loads(entry) for entry in entries]
       
       async def retry_operation(self, entry_index):
           entry = json.loads(await self.redis.lindex(self.queue_name, entry_index))
           # Logic to retry the operation
           # If successful, remove from queue
           await self.redis.lrem(self.queue_name, 1, json.dumps(entry))
           return True
   ```

4. Implement storage metrics collection:
   ```python
   from prometheus_client import Counter, Histogram, Gauge
   
   # Define metrics
   b2_operation_counter = Counter(
       'b2_operations_total',
       'Total number of B2 operations',
       ['operation_type', 'status']
   )
   
   b2_operation_latency = Histogram(
       'b2_operation_latency_seconds',
       'Latency of B2 operations in seconds',
       ['operation_type']
   )
   
   b2_storage_usage = Gauge(
       'b2_storage_usage_bytes',
       'Current B2 storage usage in bytes'
   )
   
   # Usage in code
   async def track_b2_operation(operation_type, start_time, status):
       duration = time.time() - start_time
       b2_operation_counter.labels(operation_type=operation_type, status=status).inc()
       b2_operation_latency.labels(operation_type=operation_type).observe(duration)
   
   async def update_storage_metrics():
       usage = await b2_client.get_bucket_usage()
       b2_storage_usage.set(usage)
   ```

5. Create a B2StorageService class that integrates all these components:
   ```python
   class B2StorageService:
       def __init__(self, b2_client, redis_client):
           self.b2_client = b2_client
           self.dead_letter_queue = B2DeadLetterQueue(redis_client)
       
       async def upload_file(self, local_path, remote_path, retry_count=0):
           start_time = time.time()
           try:
               result = await resilient_b2_upload(local_path, remote_path)
               await verify_upload_integrity(local_path, result)
               await track_b2_operation('upload', start_time, 'success')
               return result
           except Exception as e:
               await track_b2_operation('upload', start_time, 'failure')
               if retry_count >= 5:
                   await self.dead_letter_queue.add_failed_operation(
                       'upload', local_path, str(e), retry_count
                   )
               raise
       
       async def download_file(self, remote_path, local_path, retry_count=0):
           start_time = time.time()
           try:
               result = await resilient_b2_download(remote_path, local_path)
               await track_b2_operation('download', start_time, 'success')
               return result
           except Exception as e:
               await track_b2_operation('download', start_time, 'failure')
               if retry_count >= 5:
                   await self.dead_letter_queue.add_failed_operation(
                       'download', remote_path, str(e), retry_count
                   )
               raise
       
       async def process_dead_letter_queue(self, batch_size=10):
           failed_operations = await self.dead_letter_queue.get_failed_operations(batch_size)
           for i, operation in enumerate(failed_operations):
               try:
                   if operation['operation_type'] == 'upload':
                       await self.upload_file(
                           operation['file_path'],
                           operation['destination_path'],
                           retry_count=operation['retry_count'] + 1
                       )
                   elif operation['operation_type'] == 'download':
                       await self.download_file(
                           operation['remote_path'],
                           operation['local_path'],
                           retry_count=operation['retry_count'] + 1
                       )
                   await self.dead_letter_queue.retry_operation(i)
               except Exception as e:
                   logger.error(f"Failed to process dead letter queue item: {str(e)}")
   ```

6. Create a scheduled task to periodically process the dead letter queue and update metrics:
   ```python
   @shared_task
   async def process_b2_maintenance():
       storage_service = B2StorageService(get_b2_client(), get_redis_client())
       await storage_service.process_dead_letter_queue()
       await update_storage_metrics()
   ```

**Test Strategy:**

1. Unit tests for retry logic:
   - Test successful upload/download after temporary failures
   - Test that retry count respects maximum attempts
   - Verify exponential backoff timing between retries
   - Test behavior when max retries are exhausted

2. Unit tests for checksum verification:
   - Test successful verification with matching checksums
   - Test failure detection with mismatched checksums
   - Test handling of corrupted files
   - Test with various file sizes (small, medium, large)

3. Unit tests for dead letter queue:
   - Test adding failed operations to the queue
   - Test retrieving operations from the queue
   - Test retrying operations from the queue
   - Test queue persistence across service restarts

4. Unit tests for metrics collection:
   - Test counter increments for successful operations
   - Test counter increments for failed operations
   - Test latency histogram recording
   - Test storage usage gauge updates

5. Integration tests:
   - Test end-to-end upload with simulated network failures
   - Test end-to-end download with simulated network failures
   - Test dead letter queue processing with real Redis instance
   - Test metrics reporting to Prometheus endpoint

6. Performance tests:
   - Benchmark upload/download speeds with retry logic enabled
   - Test system under high concurrency
   - Measure impact of checksum verification on throughput
   - Test dead letter queue processing with large backlogs

7. Chaos testing:
   - Test behavior during B2 service outages
   - Test behavior during Redis outages
   - Test behavior with network packet loss and latency
   - Test recovery after system restarts
