from eval_framework import Insight, Dataset
from myapp.agent.agent import Agent
from typing import List
from python_datasets import all_conversations
from myapp.agent.memory import RedisMemory
from myapp.agent.state import BookingModel, BookingState
import os
import time

OLLAMA_HOST = os.getenv("OLLAMA_HOST")
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")

datasets = []

def load_dataset(convest:List):
    pass



session_exp_1 = f"exp_1_{time.time()}"
redis_memory = RedisMemory(host=REDIS_HOST,port=REDIS_PORT)
state_model = BookingModel()

agent = Agent()
agent.set_booking(state_model)
agent.set_memory(redis_memory)

datasets = load_dataset(all_conversations)

def evaluator():
    pass