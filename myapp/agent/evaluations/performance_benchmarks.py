"""
Performance Benchmarking Tools for Agent Evaluation

This module provides tools for measuring agent performance under various conditions
including load testing, memory usage, and response time analysis.
"""

import time
import threading
import concurrent.futures
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import psutil
import json
from datetime import datetime
import uuid

from ..agent import Agent, AgentConfig


@dataclass
class PerformanceMetrics:
    """Performance metrics for a single test run"""
    response_time: float
    memory_usage_mb: float
    cpu_usage_percent: float
    success: bool
    error_message: Optional[str] = None


@dataclass 
class LoadTestResult:
    """Results from load testing"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    max_response_time: float
    min_response_time: float
    p95_response_time: float
    p99_response_time: float
    throughput_rps: float
    avg_memory_usage: float
    peak_memory_usage: float
    avg_cpu_usage: float
    peak_cpu_usage: float


class PerformanceBenchmark:
    """Agent performance benchmarking suite"""
    
    def __init__(self, agent_config: Optional[AgentConfig] = None):
        self.config = agent_config or AgentConfig()
        self.results = []
        
    def measure_single_request(self, user_input: str, session_id: str) -> PerformanceMetrics:
        """Measure performance metrics for a single request"""
        # Get initial system metrics
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        start_time = time.time()
        start_cpu = process.cpu_percent()
        
        try:
            # Create agent and process input
            agent = Agent(session_id=session_id, config=self.config)
            response = agent.process_input(user_input, session_id)
            
            # Calculate metrics
            end_time = time.time()
            response_time = end_time - start_time
            
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_usage = final_memory - initial_memory
            
            # CPU usage (approximate)
            cpu_usage = process.cpu_percent()
            
            return PerformanceMetrics(
                response_time=response_time,
                memory_usage_mb=max(0, memory_usage),  # Ensure non-negative
                cpu_usage_percent=cpu_usage,
                success=bool(response and len(response) > 0)
            )
            
        except Exception as e:
            return PerformanceMetrics(
                response_time=time.time() - start_time,
                memory_usage_mb=0,
                cpu_usage_percent=0,
                success=False,
                error_message=str(e)
            )
    
    def run_load_test(self, concurrent_users: int = 10, requests_per_user: int = 5) -> LoadTestResult:
        """Run load test with multiple concurrent users"""
        print(f"🚀 Starting load test: {concurrent_users} users, {requests_per_user} requests each")
        
        # Test scenarios
        test_inputs = [
            "I need a taxi from downtown to airport",
            "Book me a ride for tomorrow at 3 PM",
            "Necesito un taxi del centro al aeropuerto",
            "2 passengers, pickup at mall",
            "Yes, confirm the booking"
        ]
        
        all_results = []
        
        def user_simulation(user_id: int) -> List[PerformanceMetrics]:
            """Simulate a single user making multiple requests"""
            user_results = []
            session_id = f"load-test-user-{user_id}-{uuid.uuid4().hex[:8]}"
            
            for req_num in range(requests_per_user):
                test_input = test_inputs[req_num % len(test_inputs)]
                metrics = self.measure_single_request(test_input, session_id)
                user_results.append(metrics)
                
                # Small delay between requests from same user
                time.sleep(0.1)
            
            return user_results
        
        # Run concurrent users
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            future_to_user = {
                executor.submit(user_simulation, user_id): user_id 
                for user_id in range(concurrent_users)
            }
            
            for future in concurrent.futures.as_completed(future_to_user):
                user_results = future.result()
                all_results.extend(user_results)
        
        total_time = time.time() - start_time
        
        # Calculate metrics
        successful_results = [r for r in all_results if r.success]
        failed_results = [r for r in all_results if not r.success]
        
        if successful_results:
            response_times = [r.response_time for r in successful_results]
            response_times.sort()
            
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            min_response_time = min(response_times)
            
            # Percentiles
            p95_index = int(0.95 * len(response_times))
            p99_index = int(0.99 * len(response_times))
            p95_response_time = response_times[p95_index] if p95_index < len(response_times) else max_response_time
            p99_response_time = response_times[p99_index] if p99_index < len(response_times) else max_response_time
            
            # Memory metrics
            memory_usages = [r.memory_usage_mb for r in successful_results]
            avg_memory = sum(memory_usages) / len(memory_usages)
            peak_memory = max(memory_usages)
            
            # CPU metrics
            cpu_usages = [r.cpu_usage_percent for r in successful_results]
            avg_cpu = sum(cpu_usages) / len(cpu_usages)
            peak_cpu = max(cpu_usages)
            
        else:
            avg_response_time = max_response_time = min_response_time = 0
            p95_response_time = p99_response_time = 0
            avg_memory = peak_memory = avg_cpu = peak_cpu = 0
        
        throughput = len(successful_results) / total_time if total_time > 0 else 0
        
        return LoadTestResult(
            total_requests=len(all_results),
            successful_requests=len(successful_results),
            failed_requests=len(failed_results),
            avg_response_time=avg_response_time,
            max_response_time=max_response_time,
            min_response_time=min_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            throughput_rps=throughput,
            avg_memory_usage=avg_memory,
            peak_memory_usage=peak_memory,
            avg_cpu_usage=avg_cpu,
            peak_cpu_usage=peak_cpu
        )
    
    def run_memory_stress_test(self, num_sessions: int = 100) -> Dict[str, Any]:
        """Test memory usage with multiple concurrent sessions"""
        print(f"🧠 Running memory stress test with {num_sessions} sessions")
        
        agents = []
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        try:
            # Create multiple agent sessions
            for i in range(num_sessions):
                session_id = f"memory-test-{i}"
                agent = Agent(session_id=session_id, config=self.config)
                agents.append(agent)
                
                # Process a simple request in each session
                agent.process_input("I need a taxi", session_id)
                
                if i % 10 == 0:  # Log progress
                    current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                    print(f"Created {i+1} sessions, Memory: {current_memory:.1f} MB")
            
            final_memory = psutil.Process().memory_info().rss / 1024 / 1024
            memory_per_session = (final_memory - initial_memory) / num_sessions
            
            return {
                "num_sessions": num_sessions,
                "initial_memory_mb": initial_memory,
                "final_memory_mb": final_memory,
                "total_memory_increase_mb": final_memory - initial_memory,
                "memory_per_session_mb": memory_per_session,
                "test_passed": memory_per_session < 10  # Reasonable threshold
            }
            
        except Exception as e:
            return {
                "num_sessions": len(agents),
                "error": str(e),
                "test_passed": False
            }
    
    def run_response_time_analysis(self, test_scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze response times for different conversation lengths"""
        print("⏱️ Running response time analysis")
        
        results = defaultdict(list)
        
        for scenario in test_scenarios:
            scenario_name = scenario.get("name", "unnamed")
            conversation = scenario.get("conversation", [])
            
            session_id = f"timing-test-{uuid.uuid4().hex[:8]}"
            agent = Agent(session_id=session_id, config=self.config)
            
            turn_times = []
            
            for i, user_input in enumerate(conversation):
                start_time = time.time()
                try:
                    response = agent.process_input(user_input, session_id)
                    response_time = time.time() - start_time
                    turn_times.append(response_time)
                    
                    results[scenario_name].append({
                        "turn": i + 1,
                        "response_time": response_time,
                        "success": True
                    })
                    
                except Exception as e:
                    response_time = time.time() - start_time
                    results[scenario_name].append({
                        "turn": i + 1,
                        "response_time": response_time,
                        "success": False,
                        "error": str(e)
                    })
        
        # Calculate summary statistics
        summary = {}
        for scenario_name, scenario_results in results.items():
            response_times = [r["response_time"] for r in scenario_results if r["success"]]
            if response_times:
                summary[scenario_name] = {
                    "total_turns": len(scenario_results),
                    "successful_turns": len(response_times),
                    "avg_response_time": sum(response_times) / len(response_times),
                    "max_response_time": max(response_times),
                    "min_response_time": min(response_times),
                    "total_conversation_time": sum(response_times)
                }
        
        return {
            "detailed_results": dict(results),
            "summary": summary
        }
    
    def generate_performance_report(self, load_result: LoadTestResult, 
                                   memory_result: Dict[str, Any],
                                   timing_result: Dict[str, Any]) -> str:
        """Generate comprehensive performance report"""
        
        report = f"""
# Agent Performance Benchmark Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Load Test Results
- **Total Requests**: {load_result.total_requests}
- **Success Rate**: {load_result.successful_requests / load_result.total_requests:.2%}
- **Throughput**: {load_result.throughput_rps:.2f} requests/second
- **Average Response Time**: {load_result.avg_response_time:.3f}s
- **95th Percentile**: {load_result.p95_response_time:.3f}s
- **99th Percentile**: {load_result.p99_response_time:.3f}s
- **Max Response Time**: {load_result.max_response_time:.3f}s

## Resource Usage
- **Average Memory Usage**: {load_result.avg_memory_usage:.2f} MB
- **Peak Memory Usage**: {load_result.peak_memory_usage:.2f} MB  
- **Average CPU Usage**: {load_result.avg_cpu_usage:.2f}%
- **Peak CPU Usage**: {load_result.peak_cpu_usage:.2f}%

## Memory Stress Test
- **Sessions Created**: {memory_result.get('num_sessions', 0)}
- **Memory per Session**: {memory_result.get('memory_per_session_mb', 0):.2f} MB
- **Total Memory Increase**: {memory_result.get('total_memory_increase_mb', 0):.2f} MB
- **Test Passed**: {'✅' if memory_result.get('test_passed', False) else '❌'}

## Response Time Analysis
"""
        
        for scenario, stats in timing_result.get('summary', {}).items():
            report += f"""
### {scenario}
- **Total Turns**: {stats['total_turns']}
- **Average Response Time**: {stats['avg_response_time']:.3f}s
- **Total Conversation Time**: {stats['total_conversation_time']:.3f}s
"""
        
        return report


def run_performance_benchmarks():
    """Run complete performance benchmark suite"""
    print("🔥 Starting Performance Benchmark Suite...")
    
    benchmark = PerformanceBenchmark()
    
    # Load test
    load_result = benchmark.run_load_test(concurrent_users=5, requests_per_user=3)
    
    # Memory test  
    memory_result = benchmark.run_memory_stress_test(num_sessions=20)
    
    # Timing analysis
    test_scenarios = [
        {
            "name": "Quick Booking",
            "conversation": [
                "I need a taxi",
                "From downtown to airport", 
                "Tomorrow at 3 PM",
                "2 passengers",
                "Yes confirm"
            ]
        },
        {
            "name": "Complex Booking",
            "conversation": [
                "Hi, I need transportation",
                "Actually, let me change that",
                "I need a ride from the mall",
                "Going to the train station",
                "Can you pick me up at 5 PM?",
                "Make that 4 people",
                "We need a child seat",
                "Yes, that's correct, confirm please"
            ]
        }
    ]
    
    timing_result = benchmark.run_response_time_analysis(test_scenarios)
    
    # Generate report
    report = benchmark.generate_performance_report(load_result, memory_result, timing_result)
    print(report)
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = f"/root/app_agent/myapp/agent/evaluations/performance_results_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "load_test": load_result.__dict__,
            "memory_test": memory_result,
            "timing_analysis": timing_result
        }, f, indent=2)
    
    print(f"💾 Performance results saved to: {results_file}")


if __name__ == "__main__":
    run_performance_benchmarks()