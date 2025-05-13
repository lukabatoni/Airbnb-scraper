import yaml
import random
import time
from pathlib import Path

def load_config(config_path="config/config.yaml"):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def get_random_user_agent(user_agents_file="config/user_agents.txt"):
    with open(user_agents_file, 'r') as f:
        agents = [line.strip() for line in f.readlines() if line.strip()]
    return random.choice(agents)

def random_delay(min_delay, max_delay):
    time.sleep(random.uniform(min_delay, max_delay))

def ensure_dir_exists(dir_path):
    Path(dir_path).mkdir(parents=True, exist_ok=True)