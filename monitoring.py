#!/usr/bin/env python3
"""
Monitoring and Health Check System for Invoice Reconciliation Platform
Provides comprehensive health monitoring, metrics collection, and alerting
"""

import os
import time
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HealthMonitor:
    """Comprehensive health monitoring for the platform"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.metrics = {
            "requests": 0,
            "errors": 0,
            "response_times": [],
            "db_queries": 0,
            "db_errors": 0
        }
        
    def record_request(self, response_time: float, status_code: int = 200):
        """Record a request with response time and status"""
        self.metrics["requests"] += 1
        self.metrics["response_times"].append(response_time)
        
        if status_code >= 400:
            self.metrics["errors"] += 1
        
        # Keep only last 1000 response times for memory efficiency
        if len(self.metrics["response_times"]) > 1000:
            self.metrics["response_times"] = self.metrics["response_times"][-1000:]
    
    def record_db_query(self, success: bool = True):
        """Record database query statistics"""
        self.metrics["db_queries"] += 1
        if not success:
            self.metrics["db_errors"] += 1
    
    def get_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report"""
        uptime = datetime.now() - self.start_time
        response_times = self.metrics["response_times"]
        
        # Calculate statistics
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        error_rate = (self.metrics["errors"] / self.metrics["requests"]) * 100 if self.metrics["requests"] > 0 else 0
        db_error_rate = (self.metrics["db_errors"] / self.metrics["db_queries"]) * 100 if self.metrics["db_queries"] > 0 else 0
        
        # Determine health status
        health_status = "healthy"
        issues = []
        
        if error_rate > 5:
            health_status = "degraded"
            issues.append(f"High error rate: {error_rate:.1f}%")
        
        if avg_response_time > 5000:  # 5 seconds
            health_status = "degraded"
            issues.append(f"Slow responses: {avg_response_time:.0f}ms avg")
        
        if db_error_rate > 1:
            health_status = "degraded"
            issues.append(f"Database issues: {db_error_rate:.1f}% error rate")
        
        if error_rate > 20 or db_error_rate > 10:
            health_status = "unhealthy"
        
        return {
            "status": health_status,
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": int(uptime.total_seconds()),
            "uptime_human": str(uptime).split('.')[0],
            "metrics": {
                "total_requests": self.metrics["requests"],
                "total_errors": self.metrics["errors"],
                "error_rate_percent": round(error_rate, 2),
                "avg_response_time_ms": round(avg_response_time, 2),
                "db_queries": self.metrics["db_queries"],
                "db_errors": self.metrics["db_errors"],
                "db_error_rate_percent": round(db_error_rate, 2)
            },
            "issues": issues
        }
    
    def check_database_health(self) -> Dict[str, Any]:
        """Perform detailed database health check"""
        try:
            start_time = time.time()
            database = get_db()
            
            # Test basic connectivity
            stats = database.get_health_stats()
            query_time = (time.time() - start_time) * 1000  # Convert to ms
            
            self.record_db_query(success=True)
            
            return {
                "status": "healthy",
                "query_time_ms": round(query_time, 2),
                "stats": stats
            }
            
        except Exception as e:
            self.record_db_query(success=False)
            logger.error(f"Database health check failed: {e}")
            
            return {
                "status": "unhealthy",
                "error": str(e),
                "query_time_ms": None
            }
    
    def check_external_dependencies(self) -> Dict[str, Any]:
        """Check health of external dependencies"""
        dependencies = {}
        
        # Check if OpenAI API key is configured (for future AI features)
        openai_key = os.environ.get('OPENAI_API_KEY', '')
        dependencies['openai'] = {
            "configured": openai_key and not openai_key.startswith('your_') and openai_key != 'not-configured',
            "status": "optional"
        }
        
        # Check file system access
        try:
            upload_folder = os.environ.get('UPLOAD_FOLDER', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            test_file = os.path.join(upload_folder, '.health_check')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            
            dependencies['filesystem'] = {
                "status": "healthy",
                "upload_folder": upload_folder
            }
        except Exception as e:
            dependencies['filesystem'] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        return dependencies

# Global monitor instance
monitor = HealthMonitor()

def get_monitor() -> HealthMonitor:
    """Get the global monitor instance"""
    return monitor

class PerformanceProfiler:
    """Simple performance profiler for API endpoints"""
    
    def __init__(self):
        self.endpoint_stats = {}
    
    def record_endpoint(self, endpoint: str, method: str, response_time: float, status_code: int):
        """Record endpoint performance statistics"""
        key = f"{method} {endpoint}"
        
        if key not in self.endpoint_stats:
            self.endpoint_stats[key] = {
                "calls": 0,
                "total_time": 0,
                "errors": 0,
                "min_time": float('inf'),
                "max_time": 0
            }
        
        stats = self.endpoint_stats[key]
        stats["calls"] += 1
        stats["total_time"] += response_time
        stats["min_time"] = min(stats["min_time"], response_time)
        stats["max_time"] = max(stats["max_time"], response_time)
        
        if status_code >= 400:
            stats["errors"] += 1
    
    def get_endpoint_report(self) -> Dict[str, Any]:
        """Get performance report for all endpoints"""
        report = {}
        
        for endpoint, stats in self.endpoint_stats.items():
            avg_time = stats["total_time"] / stats["calls"] if stats["calls"] > 0 else 0
            error_rate = (stats["errors"] / stats["calls"]) * 100 if stats["calls"] > 0 else 0
            
            report[endpoint] = {
                "calls": stats["calls"],
                "avg_response_time_ms": round(avg_time, 2),
                "min_response_time_ms": round(stats["min_time"], 2),
                "max_response_time_ms": round(stats["max_time"], 2),
                "error_rate_percent": round(error_rate, 2),
                "total_errors": stats["errors"]
            }
        
        return report

# Global profiler instance
profiler = PerformanceProfiler()

def get_profiler() -> PerformanceProfiler:
    """Get the global profiler instance"""
    return profiler

def create_monitoring_middleware(app):
    """Create Flask middleware for automatic monitoring"""
    
    @app.before_request
    def before_request():
        """Record request start time"""
        import flask
        flask.g.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        """Record request completion and metrics"""
        import flask
        
        if hasattr(flask.g, 'start_time'):
            response_time = (time.time() - flask.g.start_time) * 1000  # Convert to ms
            
            # Record in monitor
            monitor.record_request(response_time, response.status_code)
            
            # Record in profiler
            profiler.record_endpoint(
                flask.request.endpoint or flask.request.path,
                flask.request.method,
                response_time,
                response.status_code
            )
            
            # Add performance headers
            response.headers['X-Response-Time'] = f"{response_time:.2f}ms"
            response.headers['X-Request-ID'] = str(int(time.time() * 1000000))
        
        return response
    
    return app

if __name__ == "__main__":
    # Test monitoring system
    monitor = get_monitor()
    
    # Simulate some requests
    for i in range(10):
        monitor.record_request(100 + i * 10, 200)
    
    monitor.record_request(5000, 500)  # Slow error
    
    # Generate report
    report = monitor.get_health_report()
    print("Health Report:")
    print(json.dumps(report, indent=2))
    
    # Test database health
    db_health = monitor.check_database_health()
    print("\\nDatabase Health:")
    print(json.dumps(db_health, indent=2))
    
    # Test dependencies
    deps = monitor.check_external_dependencies()
    print("\\nDependencies:")
    print(json.dumps(deps, indent=2))