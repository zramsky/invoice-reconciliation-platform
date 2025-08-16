"""
Batch Processing Engine for Unspend - Handle multiple documents efficiently
"""
import asyncio
import threading
import time
import logging
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import uuid

class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass
class BatchJob:
    """Individual job in a batch"""
    id: str
    job_type: str  # 'extract_contract', 'extract_invoice', 'reconcile'
    input_data: Dict[str, Any]
    priority: JobPriority = JobPriority.NORMAL
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)  # Job IDs this job depends on

    def duration(self) -> Optional[float]:
        """Get processing duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

@dataclass
class BatchRequest:
    """Batch processing request"""
    id: str
    name: str
    jobs: List[BatchJob]
    created_at: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None
    callback_url: Optional[str] = None

class JobQueue:
    """Priority queue for batch jobs"""
    
    def __init__(self):
        self.queue = queue.PriorityQueue()
        self.active_jobs: Dict[str, BatchJob] = {}
        self.completed_jobs: Dict[str, BatchJob] = {}
        self.lock = threading.RLock()
    
    def enqueue(self, job: BatchJob):
        """Add job to queue"""
        with self.lock:
            # Priority queue uses (priority, item) tuples
            # Lower numbers = higher priority, so we invert the enum values
            priority_value = 5 - job.priority.value
            self.queue.put((priority_value, job.created_at.timestamp(), job))
    
    def dequeue(self, timeout: float = 1.0) -> Optional[BatchJob]:
        """Get next job from queue"""
        try:
            _, _, job = self.queue.get(timeout=timeout)
            with self.lock:
                self.active_jobs[job.id] = job
            return job
        except queue.Empty:
            return None
    
    def complete_job(self, job_id: str, result: Dict[str, Any] = None, error: str = None):
        """Mark job as completed"""
        with self.lock:
            if job_id in self.active_jobs:
                job = self.active_jobs.pop(job_id)
                job.completed_at = datetime.now()
                
                if error:
                    job.status = JobStatus.FAILED
                    job.error = error
                else:
                    job.status = JobStatus.COMPLETED
                    job.result = result
                
                self.completed_jobs[job_id] = job
                return job
        return None
    
    def get_job_status(self, job_id: str) -> Optional[Tuple[JobStatus, Dict[str, Any]]]:
        """Get job status and result"""
        with self.lock:
            # Check active jobs
            if job_id in self.active_jobs:
                job = self.active_jobs[job_id]
                return job.status, {"started_at": job.started_at}
            
            # Check completed jobs
            if job_id in self.completed_jobs:
                job = self.completed_jobs[job_id]
                return job.status, {
                    "result": job.result,
                    "error": job.error,
                    "duration": job.duration(),
                    "completed_at": job.completed_at
                }
        
        return None

class BatchProcessor:
    """Main batch processing engine"""
    
    def __init__(self, max_workers: int = 4, max_concurrent_jobs: int = 10):
        self.max_workers = max_workers
        self.max_concurrent_jobs = max_concurrent_jobs
        self.job_queue = JobQueue()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running = False
        self.worker_threads = []
        self.logger = logging.getLogger(__name__)
        
        # Job processors
        self.job_processors: Dict[str, Callable] = {}
        
        # Statistics
        self.stats = {
            'total_jobs_processed': 0,
            'jobs_completed': 0,
            'jobs_failed': 0,
            'avg_processing_time': 0.0,
            'started_at': datetime.now()
        }
        
        # LLM client reference (will be set externally)
        self.llm_client = None
        self.ocr_processor = None
        self.reconciliation_engine = None
    
    def register_processor(self, job_type: str, processor_func: Callable):
        """Register a job processor function"""
        self.job_processors[job_type] = processor_func
        self.logger.info(f"Registered processor for job type: {job_type}")
    
    def set_dependencies(self, llm_client, ocr_processor, reconciliation_engine):
        """Set external dependencies"""
        self.llm_client = llm_client
        self.ocr_processor = ocr_processor
        self.reconciliation_engine = reconciliation_engine
    
    def start(self):
        """Start the batch processor"""
        if self.running:
            return
        
        self.running = True
        self.logger.info(f"Starting batch processor with {self.max_workers} workers")
        
        # Start worker threads
        for i in range(self.max_workers):
            thread = threading.Thread(target=self._worker_loop, name=f"BatchWorker-{i}")
            thread.daemon = True
            thread.start()
            self.worker_threads.append(thread)
    
    def stop(self, timeout: float = 30.0):
        """Stop the batch processor"""
        if not self.running:
            return
        
        self.running = False
        self.logger.info("Stopping batch processor...")
        
        # Wait for workers to finish
        start_time = time.time()
        for thread in self.worker_threads:
            remaining_time = max(0, timeout - (time.time() - start_time))
            thread.join(timeout=remaining_time)
        
        self.executor.shutdown(wait=True)
        self.logger.info("Batch processor stopped")
    
    def submit_batch(self, batch_request: BatchRequest) -> str:
        """Submit a batch of jobs for processing"""
        self.logger.info(f"Submitting batch '{batch_request.name}' with {len(batch_request.jobs)} jobs")
        
        # Enqueue all jobs
        for job in batch_request.jobs:
            self.job_queue.enqueue(job)
        
        return batch_request.id
    
    def submit_job(self, job_type: str, input_data: Dict[str, Any], 
                   priority: JobPriority = JobPriority.NORMAL) -> str:
        """Submit a single job"""
        job_id = str(uuid.uuid4())
        job = BatchJob(
            id=job_id,
            job_type=job_type,
            input_data=input_data,
            priority=priority
        )
        
        self.job_queue.enqueue(job)
        self.logger.debug(f"Submitted job {job_id} of type {job_type}")
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific job"""
        status_info = self.job_queue.get_job_status(job_id)
        if status_info:
            status, details = status_info
            return {
                "job_id": job_id,
                "status": status.value,
                **details
            }
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics"""
        uptime = (datetime.now() - self.stats['started_at']).total_seconds()
        
        return {
            **self.stats,
            'uptime_seconds': uptime,
            'jobs_per_minute': (self.stats['total_jobs_processed'] / max(uptime / 60, 1)),
            'active_jobs': len(self.job_queue.active_jobs),
            'queue_size': self.job_queue.queue.qsize(),
            'worker_threads': len(self.worker_threads),
            'is_running': self.running
        }
    
    def _worker_loop(self):
        """Main worker loop"""
        while self.running:
            try:
                # Get next job
                job = self.job_queue.dequeue(timeout=1.0)
                if not job:
                    continue
                
                # Check dependencies
                if not self._check_dependencies(job):
                    # Re-queue job if dependencies not met
                    self.job_queue.enqueue(job)
                    time.sleep(0.1)
                    continue
                
                # Process the job
                self._process_job(job)
                
            except Exception as e:
                self.logger.error(f"Worker error: {e}", exc_info=True)
    
    def _check_dependencies(self, job: BatchJob) -> bool:
        """Check if job dependencies are satisfied"""
        for dep_id in job.dependencies:
            dep_status = self.job_queue.get_job_status(dep_id)
            if not dep_status or dep_status[0] != JobStatus.COMPLETED:
                return False
        return True
    
    def _process_job(self, job: BatchJob):
        """Process a single job"""
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now()
        
        try:
            self.logger.debug(f"Processing job {job.id} of type {job.job_type}")
            
            # Get processor function
            processor = self.job_processors.get(job.job_type)
            if not processor:
                raise ValueError(f"No processor registered for job type: {job.job_type}")
            
            # Execute the job
            result = processor(job.input_data)
            
            # Complete the job
            completed_job = self.job_queue.complete_job(job.id, result)
            if completed_job:
                self._update_stats(completed_job)
            
            self.logger.debug(f"Completed job {job.id} successfully")
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Job {job.id} failed: {error_msg}")
            
            # Check if we should retry
            if job.retry_count < job.max_retries:
                job.retry_count += 1
                job.status = JobStatus.PENDING
                self.job_queue.enqueue(job)
                self.logger.info(f"Retrying job {job.id} (attempt {job.retry_count}/{job.max_retries})")
            else:
                # Mark as failed
                completed_job = self.job_queue.complete_job(job.id, error=error_msg)
                if completed_job:
                    self._update_stats(completed_job)
    
    def _update_stats(self, job: BatchJob):
        """Update processing statistics"""
        self.stats['total_jobs_processed'] += 1
        
        if job.status == JobStatus.COMPLETED:
            self.stats['jobs_completed'] += 1
        elif job.status == JobStatus.FAILED:
            self.stats['jobs_failed'] += 1
        
        # Update average processing time
        if job.duration():
            current_avg = self.stats['avg_processing_time']
            total_jobs = self.stats['total_jobs_processed']
            self.stats['avg_processing_time'] = (
                (current_avg * (total_jobs - 1) + job.duration()) / total_jobs
            )

def create_document_processors(batch_processor: BatchProcessor, 
                             llm_client, ocr_processor, reconciliation_engine):
    """Create and register document processing functions"""
    
    async def process_contract_extraction(input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process contract extraction job"""
        file_path = input_data['file_path']
        
        # Extract text
        contract_text = ocr_processor.process_document(file_path)
        
        # Extract with LLM
        if hasattr(llm_client, 'call_async'):
            from llm_client import LLMRequest
            request = LLMRequest(
                model=llm_client.small_model,
                system="You are an extraction engine for contracts...",
                user=f"Extract contract details from: {contract_text[:6000]}",
                json_schema={}  # Would include actual schema
            )
            contract_details, success = await llm_client.call_async(request)
        else:
            # Fallback to sync call
            contract_details, success = llm_client.extract_contract(contract_text)
        
        return {
            'success': success,
            'contract_details': contract_details,
            'text_length': len(contract_text)
        }
    
    def sync_contract_processor(input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous wrapper for contract processing"""
        try:
            # For now, use synchronous processing
            file_path = input_data['file_path']
            contract_text = ocr_processor.process_document(file_path)
            contract_details, success = llm_client.extract_contract(contract_text)
            
            return {
                'success': success,
                'contract_details': contract_details,
                'text_length': len(contract_text)
            }
        except Exception as e:
            raise Exception(f"Contract processing failed: {str(e)}")
    
    def sync_invoice_processor(input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous invoice processing"""
        try:
            file_path = input_data['file_path']
            invoice_text = ocr_processor.process_document(file_path)
            invoice_details, success = llm_client.extract_invoice(invoice_text)
            
            return {
                'success': success,
                'invoice_details': invoice_details,
                'text_length': len(invoice_text)
            }
        except Exception as e:
            raise Exception(f"Invoice processing failed: {str(e)}")
    
    def reconciliation_processor(input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process reconciliation job"""
        try:
            contract_data = input_data['contract']
            invoice_data = input_data['invoice']
            
            result = reconciliation_engine.reconcile(contract_data, invoice_data)
            
            return {
                'success': True,
                'reconciliation_result': result.dict(),
                'matches_count': len(result.matches),
                'flags_count': len(result.flags)
            }
        except Exception as e:
            raise Exception(f"Reconciliation failed: {str(e)}")
    
    # Register processors
    batch_processor.register_processor('extract_contract', sync_contract_processor)
    batch_processor.register_processor('extract_invoice', sync_invoice_processor)
    batch_processor.register_processor('reconcile', reconciliation_processor)
    
    # Set dependencies
    batch_processor.set_dependencies(llm_client, ocr_processor, reconciliation_engine)
    
    return batch_processor