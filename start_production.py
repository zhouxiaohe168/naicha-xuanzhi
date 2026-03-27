import os
import sys
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')

print(f"[PROD] Titan V17.0 Omni-Vision starting...", flush=True)
print(f"[PROD] Working directory: {BASE_DIR}", flush=True)

import uvicorn
uvicorn.run("server.api:app", host="0.0.0.0", port=5000, log_level="info")
