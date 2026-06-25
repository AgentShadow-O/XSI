DEFAULT_RULES = [
    {"name": "High risk external IP", "rule_type": "network", "min_score": 65, "action": "block_ip"},
    {"name": "Critical process behavior", "rule_type": "endpoint", "min_score": 80, "action": "stop_process"},
    {"name": "Critical file behavior", "rule_type": "endpoint", "min_score": 80, "action": "quarantine_file"},
]
