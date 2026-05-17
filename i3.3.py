
import os
import time
import json
import logging
import re
import threading

import telebot
from telebot import types

#--- KONSTANTALAR ---

TOKEN = os.getenv("BOT_TOKEN")  # Bot tokenini env orqali bering
ADMIN_ID = 6130389200  # 🛑 ADMIN ID

DATA_FOLDER = "RASHSIZ"
os.makedirs(DATA_FOLDER, exist_ok=True)

USERS_FILE = os.path.join(DATA_FOLDER, "users.json")
EXAMS_FILE = os.path.join(DATA_FOLDER, "exams.json")
EXAM_RESULTS_FILE = os.path.join(DATA_FOLDER, "results.json")
PENDING_REVIEWS_FILE = os.path.join(DATA_FOLDER, "pending_reviews.json")

STAGE1_TOTAL_QUESTIONS = 40
STAGE2_QUESTION_KEYS = ["41", "42", "43"]
STAGE2_DEFAULT_BALL = 75.0

#--- LOGGING O'RNATISH ---

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
user_states: dict[int, dict] = {}
state_lock = threading.Lock()
