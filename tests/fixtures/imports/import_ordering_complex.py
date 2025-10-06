"""Example with complex import ordering issue."""
import json
import os
import sys
from pathlib import Path
from typing import Dict, List
import asyncio
from dataclasses import dataclass
import re
from collections import defaultdict

# Third-party imports mixed with stdlib
import requests
import pytest
from pydantic import BaseModel

@dataclass
class Config:
    """Configuration class."""
    api_key: str
    timeout: int
