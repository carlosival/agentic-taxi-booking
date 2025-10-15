#!/usr/bin/env python3
"""
Agent Evaluation Runner

Run this script to evaluate the taxi booking agent's performance.
Includes functionality evaluation, performance benchmarks, and detailed reporting.
"""

import sys
import os
import argparse
from datetime import datetime

# Add the agent module to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'myapp'))

from agent.evaluations.agent_evaluator import AgentEvaluator, run_evaluation_suite
from agent.evaluations.performance_benchmarks import PerformanceBenchmark, run_performance_benchmarks
from agent.agent import AgentConfig


def run_functional_evaluation():
    """Run functional evaluation tests"""
    print("=" * 60)
    print("🧪 FUNCTIONAL EVALUATION")
    print("=" * 60)
    
    return run_evaluation_suite()


def run_performance_evaluation():
    """Run performance evaluation tests"""
    print("=" * 60)
    print("🚀 PERFORMANCE EVALUATION") 
    print("=" * 60)
    
    return run_performance_benchmarks()


def run_custom_evaluation(test_cases):
    """Run evaluation with custom test cases"""
    print("=" * 60)
    print("🔧 CUSTOM EVALUATION")
    print("=" * 60)
    
    evaluator = AgentEvaluator()
    
    # Create custom datasets
    from agent.evaluations.eval_framework import Dataset
    custom_datasets = []
    
    for i, test_case in enumerate(test_cases):
        dataset = Dataset(
            id=i + 1000,  # Offset to avoid conflicts
            input=test_case.get("input", []),
            ref_output=test_case.get("expected", {})
        )
        custom_datasets.append(dataset)
    
    evaluator.test_datasets = custom_datasets
    
    # Run evaluation
    metrics = evaluator.run_comprehensive_evaluation()
    report = evaluator.generate_detailed_report(metrics)
    
    print(report)
    
    # Save results
    results_file = evaluator.save_results()
    print(f"💾 Custom evaluation results saved to: {results_file}")
    
    return metrics, evaluator.results


def main():
    parser = argparse.ArgumentParser(description='Evaluate the taxi booking agent')
    parser.add_argument('--type', choices=['functional', 'performance', 'both', 'custom'], 
                       default='both', help='Type of evaluation to run')
    parser.add_argument('--model', default='llama3', help='Model name to use for evaluation')  
    parser.add_argument('--temperature', type=float, default=0.0, help='Model temperature')
    parser.add_argument('--concurrent-users', type=int, default=5, help='Number of concurrent users for load test')
    parser.add_argument('--requests-per-user', type=int, default=3, help='Requests per user in load test')
    
    args = parser.parse_args()
    
    # Configure agent
    config = AgentConfig()
    config.model_name = args.model
    config.temperature = args.temperature
    
    print(f"🤖 Agent Evaluation Suite")
    print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔧 Model: {config.model_name}")
    print(f"🌡️  Temperature: {config.temperature}")
    print()
    
    results = {}
    
    if args.type in ['functional', 'both']:
        try:
            functional_metrics, functional_results = run_functional_evaluation()
            results['functional'] = {
                'metrics': functional_metrics,
                'results': functional_results
            }
        except Exception as e:
            print(f"❌ Functional evaluation failed: {e}")
            results['functional'] = {'error': str(e)}
    
    if args.type in ['performance', 'both']:
        try:
            performance_results = run_performance_evaluation()
            results['performance'] = performance_results
        except Exception as e:
            print(f"❌ Performance evaluation failed: {e}")
            results['performance'] = {'error': str(e)}
    
    if args.type == 'custom':
        # Example custom test cases
        custom_test_cases = [
            {
                "input": ["Book a taxi", "From hotel to restaurant", "Tonight at 8 PM", "4 people", "yes"],
                "expected": {
                    "pickup_location": "hotel",
                    "destination": "restaurant", 
                    "pickup_time": "Tonight at 8 PM",
                    "passengers": 4,
                    "confirmed": True
                }
            }
        ]
        
        try:
            custom_metrics, custom_results = run_custom_evaluation(custom_test_cases)
            results['custom'] = {
                'metrics': custom_metrics,
                'results': custom_results
            }
        except Exception as e:
            print(f"❌ Custom evaluation failed: {e}")
            results['custom'] = {'error': str(e)}
    
    # Summary
    print("=" * 60)
    print("📊 EVALUATION SUMMARY")
    print("=" * 60)
    
    if 'functional' in results and 'metrics' in results['functional']:
        metrics = results['functional']['metrics']
        print(f"✅ Functional Tests:")
        print(f"   - Success Rate: {metrics.success_rate:.2%}")
        print(f"   - Booking Completion: {metrics.booking_completion_rate:.2%}")
        print(f"   - Information Accuracy: {metrics.information_extraction_accuracy:.2%}")
        print(f"   - Language Consistency: {metrics.language_consistency:.2%}")
    
    if 'performance' in results and not isinstance(results['performance'], dict) or 'error' not in results['performance']:
        print(f"🚀 Performance Tests: Completed (check detailed logs above)")
    
    print(f"\n🏁 Evaluation completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()