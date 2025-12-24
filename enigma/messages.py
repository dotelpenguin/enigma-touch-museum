#!/usr/bin/env python3
"""
Message loading utilities for Enigma Museum Controller
"""

import json
import os
from typing import List
from .constants import ENGLISH_MSG_FILE, GERMAN_MSG_FILE


def load_messages_from_file(filepath: str) -> List[str]:
    """Load messages from a JSON file"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                messages = json.load(f)
                if isinstance(messages, list):
                    return messages
    except Exception:
        pass
    return []


# Load museum messages from files
ENGLISH_MESSAGES = load_messages_from_file(ENGLISH_MSG_FILE)
GERMAN_MESSAGES = load_messages_from_file(GERMAN_MSG_FILE)

# Fallback messages if files are empty or missing
if not ENGLISH_MESSAGES:
    ENGLISH_MESSAGES = ["NO MESSAGES LOADED FROM english.msg FILE"]

if not GERMAN_MESSAGES:
    GERMAN_MESSAGES = ["NO MESSAGES LOADED FROM german.msg FILE"]

