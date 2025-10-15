"""
Comprehensive Agent Evaluation System

This module provides evaluation tools for the taxi booking agent,
including dataset generation, performance metrics, and conversation analysis.
"""

import json
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import uuid

from ..agent import Agent, AgentConfig
from .eval_framework import Dataset, Result, Evaluation, Insight


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ConversationResult:
    """Result of a single conversation evaluation"""
    session_id: str
    success: bool
    turns: int
    completion_time: float
    booking_completed: bool
    booking_state: Dict[str, Any]
    errors: List[str]
    conversation_flow: List[Dict[str, str]]


@dataclass
class EvaluationMetrics:
    """Comprehensive evaluation metrics"""
    success_rate: float
    avg_turns: float
    avg_completion_time: float
    booking_completion_rate: float
    error_rate: float
    language_consistency: float
    information_extraction_accuracy: float


class AgentEvaluator:
    """Comprehensive agent evaluation system"""
    
    def __init__(self, agent_config: Optional[AgentConfig] = None):
        self.config = agent_config or AgentConfig()
        self.test_datasets = []
        self.results = []
        
    def create_test_datasets(self) -> List[Dataset]:
        """Create comprehensive test datasets for agent evaluation"""
        
        # Basic booking scenarios
        basic_scenarios = [
            {
                "id": 1,
                "input": ["I need a taxi from downtown to the airport", "Tomorrow at 3 PM", "2 passengers", "No special requests", "Yes, confirm"],
                "ref_output": {
                    "pickup_location": "downtown",
                    "destination": "airport", 
                    "pickup_time": "Tomorrow at 3 PM",
                    "passengers": 2,
                    "special_requests": "N/A",
                    "confirmed": True
                }
            },
            {
                "id": 2,
                "input": ["Necesito un taxi del centro al aeropuerto", "Mañana a las 3 PM", "2 pasajeros", "Sin solicitudes especiales", "Sí, confirmar"],
                "ref_output": {
                    "pickup_location": "centro",
                    "destination": "aeropuerto",
                    "pickup_time": "Mañana a las 3 PM", 
                    "passengers": 2,
                    "special_requests": "N/A",
                    "confirmed": True
                }
            }
        ]
        
        # Edge cases
        edge_cases = [
            {
                "id": 3,
                "input": ["Book taxi", "123 Main St", "456 Oak Ave", "ASAP", "1", "Child seat needed", "yes"],
                "ref_output": {
                    "pickup_location": "123 Main St",
                    "destination": "456 Oak Ave",
                    "pickup_time": "ASAP",
                    "passengers": 1,
                    "special_requests": "Child seat needed",
                    "confirmed": True
                }
            },
            {
                "id": 4,
                "input": ["I need a ride", "Actually, let me change that", "From the mall to home", "5 PM today", "3 people", "No", "Confirm please"],
                "ref_output": {
                    "pickup_location": "mall",
                    "destination": "home",
                    "pickup_time": "5 PM today",
                    "passengers": 3,
                    "special_requests": "N/A",
                    "confirmed": True
                }
            }
        ]
        
        # Error handling scenarios
        error_scenarios = [
            {
                "id": 5,
                "input": ["", "invalid location @#$%", "tomorrow at 25:00", "-5 passengers", "maybe", "not sure"],
                "ref_output": {
                    "pickup_location": None,
                    "destination": None,
                    "pickup_time": None,
                    "passengers": None,
                    "special_requests": None,
                    "confirmed": False
                }
            }
        ]
        
        all_scenarios = basic_scenarios + edge_cases + error_scenarios
        datasets = []
        
        for scenario in all_scenarios:
            dataset = Dataset(
                id=scenario["id"],
                input=scenario["input"],
                ref_output=scenario["ref_output"]
            )
            datasets.append(dataset)
            
        self.test_datasets = datasets
        return datasets
    
    def evaluate_single_conversation(self, conversation_inputs: List[str], expected_output: Dict[str, Any]) -> ConversationResult:
        """Evaluate a single conversation scenario"""
        session_id = f"eval-{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        errors = []
        conversation_flow = []
        
        try:
            # Initialize agent for this test
            agent = Agent(session_id=session_id, config=self.config)
            
            # Simulate conversation
            for i, user_input in enumerate(conversation_inputs):
                if not user_input.strip():  # Skip empty inputs
                    continue
                    
                try:
                    response = agent.process_input(user_input, session_id)
                    conversation_flow.append({
                        "turn": i + 1,
                        "user": user_input,
                        "agent": response
                    })
                    
                    # Check if booking is complete
                    if agent.is_confirm() and agent.is_complete():
                        break
                        
                except Exception as e:
                    errors.append(f"Turn {i+1}: {str(e)}")
                    logger.error(f"Error in turn {i+1}: {e}")
            
            # Get final booking state
            final_state = agent.booking_state.get_state()
            booking_completed = agent.is_confirm() and agent.is_complete()
            
            completion_time = time.time() - start_time
            
            return ConversationResult(
                session_id=session_id,
                success=len(errors) == 0,
                turns=len(conversation_flow),
                completion_time=completion_time,
                booking_completed=booking_completed,
                booking_state=final_state.model_dump() if final_state else {},
                errors=errors,
                conversation_flow=conversation_flow
            )
            
        except Exception as e:
            logger.error(f"Fatal error in conversation evaluation: {e}")
            return ConversationResult(
                session_id=session_id,
                success=False,
                turns=0,
                completion_time=time.time() - start_time,
                booking_completed=False,
                booking_state={},
                errors=[f"Fatal error: {str(e)}"],
                conversation_flow=[]
            )
    
    def evaluate_information_extraction(self, result: ConversationResult, expected: Dict[str, Any]) -> float:
        """Evaluate accuracy of information extraction"""
        if not result.booking_state:
            return 0.0
        
        total_fields = len(expected)
        correct_fields = 0
        
        for key, expected_value in expected.items():
            actual_value = result.booking_state.get(key)
            
            # Handle different value types
            if expected_value is None:
                if actual_value is None:
                    correct_fields += 1
            elif isinstance(expected_value, bool):
                if actual_value == expected_value:
                    correct_fields += 1
            elif isinstance(expected_value, (int, float)):
                if actual_value == expected_value:
                    correct_fields += 1
            elif isinstance(expected_value, str):
                if actual_value and str(actual_value).lower() in str(expected_value).lower():
                    correct_fields += 1
        
        return correct_fields / total_fields if total_fields > 0 else 0.0
    
    def evaluate_language_consistency(self, conversation_flow: List[Dict[str, str]]) -> float:
        """Evaluate if agent maintains consistent language with user"""
        if not conversation_flow:
            return 0.0
        
        # Simple heuristic: check if agent responses contain similar language patterns
        consistent_responses = 0
        total_responses = len(conversation_flow)
        
        for turn in conversation_flow:
            user_msg = turn.get("user", "").lower()
            agent_msg = turn.get("agent", "").lower()
            
            # Check for Spanish language consistency
            spanish_indicators = ["necesito", "del", "al", "mañana", "sí", "no", "por favor"]
            user_spanish = any(word in user_msg for word in spanish_indicators)
            agent_spanish = any(word in agent_msg for word in spanish_indicators)
            
            if user_spanish == agent_spanish or not user_spanish:
                consistent_responses += 1
        
        return consistent_responses / total_responses if total_responses > 0 else 0.0
    
    def run_comprehensive_evaluation(self) -> EvaluationMetrics:
        """Run comprehensive evaluation on all test datasets"""
        if not self.test_datasets:
            self.create_test_datasets()
        
        results = []
        
        logger.info(f"Starting evaluation with {len(self.test_datasets)} test cases")
        
        for dataset in self.test_datasets:
            logger.info(f"Evaluating dataset {dataset.id}")
            
            result = self.evaluate_single_conversation(
                dataset.input,
                dataset.ref_output
            )
            results.append(result)
        
        # Calculate metrics
        total_tests = len(results)
        successful_tests = sum(1 for r in results if r.success)
        completed_bookings = sum(1 for r in results if r.booking_completed)
        total_errors = sum(len(r.errors) for r in results)
        total_turns = sum(r.turns for r in results)
        total_time = sum(r.completion_time for r in results)
        
        # Information extraction accuracy
        extraction_scores = []
        for i, result in enumerate(results):
            if i < len(self.test_datasets):
                score = self.evaluate_information_extraction(result, self.test_datasets[i].ref_output)
                extraction_scores.append(score)
        
        # Language consistency
        language_scores = []
        for result in results:
            score = self.evaluate_language_consistency(result.conversation_flow)
            language_scores.append(score)
        
        metrics = EvaluationMetrics(
            success_rate=successful_tests / total_tests if total_tests > 0 else 0.0,
            avg_turns=total_turns / total_tests if total_tests > 0 else 0.0,
            avg_completion_time=total_time / total_tests if total_tests > 0 else 0.0,
            booking_completion_rate=completed_bookings / total_tests if total_tests > 0 else 0.0,
            error_rate=total_errors / total_tests if total_tests > 0 else 0.0,
            language_consistency=sum(language_scores) / len(language_scores) if language_scores else 0.0,
            information_extraction_accuracy=sum(extraction_scores) / len(extraction_scores) if extraction_scores else 0.0
        )
        
        self.results = results
        return metrics
    
    def generate_detailed_report(self, metrics: EvaluationMetrics) -> str:
        """Generate detailed evaluation report"""
        report = f"""
# Agent Evaluation Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Overall Performance Metrics
- **Success Rate**: {metrics.success_rate:.2%}
- **Booking Completion Rate**: {metrics.booking_completion_rate:.2%}
- **Average Turns per Conversation**: {metrics.avg_turns:.1f}
- **Average Completion Time**: {metrics.avg_completion_time:.2f}s
- **Error Rate**: {metrics.error_rate:.2f} errors per test
- **Language Consistency**: {metrics.language_consistency:.2%}
- **Information Extraction Accuracy**: {metrics.information_extraction_accuracy:.2%}

## Detailed Test Results
"""
        
        for i, result in enumerate(self.results):
            report += f"""
### Test Case {i+1}
- **Session ID**: {result.session_id}
- **Success**: {'✅' if result.success else '❌'}
- **Booking Completed**: {'✅' if result.booking_completed else '❌'}
- **Turns**: {result.turns}
- **Time**: {result.completion_time:.2f}s
- **Errors**: {len(result.errors)}
"""
            
            if result.errors:
                report += "- **Error Details**:\n"
                for error in result.errors:
                    report += f"  - {error}\n"
            
            if result.booking_state:
                report += f"- **Final State**: {json.dumps(result.booking_state, indent=2)}\n"
        
        return report
    
    def save_results(self, filename: str = None) -> str:
        """Save evaluation results to file"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"/root/app_agent/myapp/agent/evaluations/eval_results_{timestamp}.json"
        
        results_data = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "model_name": self.config.model_name,
                "temperature": self.config.temperature,
                "max_memory": self.config.max_memory
            },
            "results": [
                {
                    "session_id": r.session_id,
                    "success": r.success,
                    "turns": r.turns,
                    "completion_time": r.completion_time,
                    "booking_completed": r.booking_completed,
                    "booking_state": r.booking_state,
                    "errors": r.errors,
                    "conversation_flow": r.conversation_flow
                }
                for r in self.results
            ]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        
        return filename


def run_evaluation_suite():
    """Run the complete evaluation suite"""
    print("🤖 Starting Agent Evaluation Suite...")
    
    # Initialize evaluator
    evaluator = AgentEvaluator()
    
    # Create test datasets
    print("📊 Creating test datasets...")
    datasets = evaluator.create_test_datasets()
    print(f"✅ Created {len(datasets)} test scenarios")
    
    # Run evaluation
    print("🧪 Running comprehensive evaluation...")
    metrics = evaluator.run_comprehensive_evaluation()
    
    # Generate and display report
    print("📈 Generating evaluation report...")
    report = evaluator.generate_detailed_report(metrics)
    print(report)
    
    # Save results
    results_file = evaluator.save_results()
    print(f"💾 Results saved to: {results_file}")
    
    return metrics, evaluator.results


if __name__ == "__main__":
    run_evaluation_suite()