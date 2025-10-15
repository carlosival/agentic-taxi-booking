from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class Dataset(BaseModel): 
    id: int
    input: Any
    ref_output: Any
    

class Result(BaseModel):  
    id: int
    id_dataset: Any
    output: Any


class Evaluation(BaseModel):
    id:int
    id_dataset:int
    id_result:int
    eval_by_ai: int
    eval_human: Optional[int]
    experiment_name: Optional[str] = "generic"

class Insight:

    def __init__(self, target, evaluator, dataset: List[Dataset], exp = "generic"):
        self.target = lambda input: input
        self.datasets = dataset
        self.results = []
        self.evaluations = []
        self.evaluator = lambda ref_out, out: ref_out == out
        self.num_repetitions = 1
        self.experiment = exp


    def run(self):
        for r in range(self.num_repetitions):
            for dataset in self.datasets:
               out = self.target(dataset.input)
               self.results.append(Result(len(self.results),dataset.id,out))

    def evaluate(self, refout, output): 
        for i, result in enumerate(self.results):
            result_eval = self.evaluator(self.datasets[result.id_dataset].ref_output, result.output)
            self.evaluations.append(Evaluation(i,result.id_dataset,result.id,result_eval))
    
    
    def metricTrueoFalse(self):
        if not self.evaluations:
            return 0
        return sum(1 for evaluation in self.evaluations if evaluation.eval_by_ai in {0, 1}) / len(self.evaluations) 

    def metricsAvg(self):

        if not self.evaluations:
            return 0
        
        return sum(evaluation.eval_by_ai for evaluation in self.evaluations) / len(self.evaluations)     