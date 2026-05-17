
import os
import time
import json
import logging
import re
import threading

import telebot
from telebot import types

#--- KONSTANTALAR ---

TOKEN = os.getenv("BOT_TOKEN", "8571268456:AAEgetqSss5gFN-HvzGPyEqvGatoPUO8Xpg")  # Bot tokenini env orqali bering
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


def send_typing(chat_id: int):
    """Telegramda typing animatsiyasini ko'rsatadi."""
    try:
        bot.send_chat_action(chat_id, "typing")
    except Exception:
        pass


def build_reply_keyboard(button_rows, one_time=False):
    """Telebot uchun ReplyKeyboardMarkup yaratadi."""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=one_time)
    for row in button_rows:
        normalized = []
        for btn in row:
            if isinstance(btn, types.KeyboardButton):
                normalized.append(btn)
            else:
                normalized.append(types.KeyboardButton(str(btn)))
        markup.row(*normalized)
    return markup


#--- ASOSIY YORDAMCHI FUNKSIYALAR ---

def read_json(filename):
    """JSON faylidan ma'lumotni o'qiydi."""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {} if filename in [USERS_FILE, EXAMS_FILE] else []


def write_json(filename, data):
    """JSON fayliga ma'lumotni yozadi."""
    if filename == USERS_FILE:
        logger.warning(f"USERS_FILE ({filename}) ga yozish bekor qilindi.")
        return
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def format_time(seconds):
    """Sekundlarni MM:SS formatiga o'tkazadi."""
    if seconds <= 0:
        return "00:00"
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes:02}:{seconds:02}"


def get_state(user_id: int) -> dict:
    with state_lock:
        return user_states.setdefault(user_id, {})


def set_state(user_id: int, data: dict):
    with state_lock:
        user_states[user_id] = data


def clear_state(user_id: int):
    with state_lock:
        user_states.pop(user_id, None)





def is_not_modified_error(exc: Exception) -> bool:
    return "message is not modified" in str(exc).lower()


def sanitize_plain(text):
    return "" if text is None else str(text)


TIME_REFRESH_SECONDS = 1


def build_timer_text(stage: int, time_left: float) -> str:
    time_display = format_time(time_left)
    return (
        f"⏳ Qolgan vaqt: {time_display}\n"
        f"📘 Bosqich: {stage}"
    )


def update_timer_message(chat_id: int, user_id: int, current_time: float | None = None):
    state = get_state(user_id)
    exam_state = state.get("in_exam")
    if not exam_state:
        return

    timer_message_id = exam_state.get("timer_message_id")
    if not timer_message_id:
        return

    now = current_time if current_time is not None else time.time()
    time_left = max(0, exam_state["end_time"] - now)
    timer_text = build_timer_text(exam_state["stage"], time_left)

    try:
        bot.edit_message_text(
            timer_text,
            chat_id=chat_id,
            message_id=timer_message_id,
            parse_mode=None,
        )
        exam_state["message_text"] = timer_text
        state["in_exam"] = exam_state
        set_state(user_id, state)
    except Exception as e:
        if not is_not_modified_error(e):
            logger.debug(f"timer message yangilash xatosi: {e}")



def safe_answer_callback_query(call_id, text: str | None = None, show_alert: bool = False, cache_time: int = 1) -> bool:
    """Callback query xatolarini botni yiqitmasdan yutadi."""
    try:
        bot.answer_callback_query(
            call_id,
            text=text,
            show_alert=show_alert,
            cache_time=cache_time,
        )
        return True
    except Exception as exc:
        msg = str(exc).lower()
        if "query is too old" in msg or "callback query is too old" in msg or "query id is invalid" in msg:
            return False
        logger.debug(f"answer_callback_query xatosi: {exc}")
        return False


def delete_message_safely(chat_id: int, message_id: int | None) -> None:
    if not message_id:
        return
    try:
        bot.delete_message(chat_id, message_id)
    except Exception:
        pass


def build_teacher_review_keyboard(pending_message_id: int | str):
    """O'qituvchi uchun tezkor baholash tugmalari."""
    pid = str(pending_message_id)
    rows = [
        [types.InlineKeyboardButton("75", callback_data=f"REVIEW|{pid}|75|75"),
         types.InlineKeyboardButton("67", callback_data=f"REVIEW|{pid}|67|75"),
         types.InlineKeyboardButton("58", callback_data=f"REVIEW|{pid}|58|75"),
         types.InlineKeyboardButton("55", callback_data=f"REVIEW|{pid}|55|75"),
         types.InlineKeyboardButton("54", callback_data=f"REVIEW|{pid}|54|75")],
        [types.InlineKeyboardButton("50", callback_data=f"REVIEW|{pid}|50|75"),
         types.InlineKeyboardButton("47", callback_data=f"REVIEW|{pid}|47|75"),
         types.InlineKeyboardButton("46", callback_data=f"REVIEW|{pid}|46|75"),
         types.InlineKeyboardButton("45", callback_data=f"REVIEW|{pid}|45|75"),
         types.InlineKeyboardButton("35", callback_data=f"REVIEW|{pid}|35|75")],
        [types.InlineKeyboardButton("0", callback_data=f"REVIEW|{pid}|0|75")],
    ]
    return types.InlineKeyboardMarkup(rows)


def build_answer_sheet_header(stage: int, current_page: int, total_pages: int, time_left: float | None):
    time_text = f"⏳ {format_time(time_left or 0)}" if time_left is not None else "⏳ --:--"
    stage_text = f"📘 Bosqich {stage}"
    page_text = f"📄 Sahifa {current_page}/{total_pages}"
    return [
        types.InlineKeyboardButton(time_text, callback_data="IGNORE"),
        types.InlineKeyboardButton(stage_text, callback_data="IGNORE"),
        types.InlineKeyboardButton(page_text, callback_data="IGNORE"),
    ]


def get_answer_sheet_caption(stage: int, current_page: int) -> str:
    if stage == 1:
        return f"**JAVOB VARAG'I**\n\n**Bosqich:** 1"
    return f"**JAVOB VARAG'I**\n\n**Bosqich:** 2"


def is_optional_skip(text: str) -> bool:
    value = sanitize_plain(text).strip().lower()
    return value in {"", "-", "yo'q", "yoq", "none", "null", "skip", "o'tkazib yuborish", "otkazib yuborish"}


def get_question_note(q_data: dict) -> str:
    if not isinstance(q_data, dict):
        return ""
    note = q_data.get("description") or q_data.get("tavsif") or q_data.get("note") or ""
    return sanitize_plain(note).strip()



def extract_labeled_parts(text: str) -> dict:
    raw = sanitize_plain(text).strip()
    if not raw:
        return {}

    # A)javob, B)javob, C)javob  yoki qatorbo'yicha kirishni qo'llaydi.
    pattern = re.compile(
        r'(?:^|[\n,;])\s*([A-Za-zА-Яа-я0-9]+)\s*[\)\.\:\-]\s*(.*?)\s*(?=(?:[\n,;]\s*[A-Za-zА-Яа-я0-9]+\s*[\)\.\:\-])|$)',
        re.S,
    )
    matches = pattern.findall(raw)
    if not matches:
        return {}

    parts = {}
    for key, value in matches:
        key = key.strip().upper()
        value = value.strip()
        if not key or not value:
            return {}
        parts[key] = value
    return parts

def get_question_creation_menu():
    return build_reply_keyboard([
        [types.KeyboardButton("4 Variantli (1-32)"), types.KeyboardButton("6 Variantli (33-35)")],
        [types.KeyboardButton("Ochiq Savol (36-40)")],
        [types.KeyboardButton("Test Savollari Tugadi")],
    ], one_time=True)



def get_question_prompt(q_num: int, q_data: dict, include_note: bool = True) -> str:
    note = get_question_note(q_data) if include_note else ""
    q_type = q_data.get("type")

    if q_type == "OPEN":
        text = f"📝 Savol #{q_num} javobini yuboring."
        if note:
            text += f"\n💡 Tavsif: {note}"
        return text

    if q_type == "COMPLEX_SUB":
        sub_questions = q_data.get("sub_questions", {})
        total_parts = len(sub_questions)

        if total_parts <= 1:
            text = f"📝 Savol #{q_num} javobini yuboring."
            if note:
                text += f"\n💡 Tavsif: {note}"
            return text

        part_labels = ", ".join(f"{chr(65 + i)})" for i in range(total_parts))
        text = (
            f"📝 Savol #{q_num} uchun qismli javob yuboring. "
            f"Format: {part_labels} javob"
        )
        if note:
            text += f"\n💡 Tavsif: {note}"
        return text

    return f"📝 Savol #{q_num} javobini yuboring."


def format_stage2_review_text(q_key: str, payload: dict) -> str:
    q_key = sanitize_plain(q_key)
    if not isinstance(payload, dict):
        return f"O'quvchi javobi ({q_key}):\n(bo'sh)"

    if payload.get("mode") == "file":
        content_type = payload.get("content_type", "file")
        return (
            f"O'quvchi javobi ({q_key}):\n"
            f"Tur: {content_type}\n"
            f"Fayl ID: {payload.get('file_id', '')}"
        )

    raw_text = sanitize_plain(payload.get("text", "")).strip() or "(bo'sh)"
    parts = payload.get("parts") or {}
    if parts:
        lines = [f"O'quvchi javobi ({q_key}):", f"Matn: {raw_text}", "Qismlar:"]
        for key in sorted(parts.keys()):
            lines.append(f"{key}) {parts[key]}")
        return "\n".join(lines)

    return f"O'quvchi javobi ({q_key}):\n{raw_text}"


def build_stage2_submission_payload(mode: str, text: str | None = None, file_id: str | None = None, content_type: str | None = None) -> dict:
    payload = {
        "mode": mode,
        "submitted_at": time.time(),
        "review_status": "pending",
        "max_ball": STAGE2_DEFAULT_BALL,
    }
    if mode == "text":
        raw_text = sanitize_plain(text).strip()
        payload["text"] = raw_text
        parts = extract_labeled_parts(raw_text)
        if parts:
            payload["parts"] = parts
    elif mode == "file":
        payload["file_id"] = file_id
        payload["content_type"] = content_type or "document"
    return payload

def retry_plain_if_markdown_fails(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if "can't parse entities" in str(e).lower():
            kwargs.pop("parse_mode", None)
            return func(*args, **kwargs)
        raise

def load_pending_reviews() -> dict:
    data = read_json(PENDING_REVIEWS_FILE)
    return data if isinstance(data, dict) else {}


def save_pending_reviews(data: dict):
    write_json(PENDING_REVIEWS_FILE, data)


def stage2_question_keys() -> list[str]:
    return list(STAGE2_QUESTION_KEYS)


def first_pending_stage2_question(exam_state: dict) -> str | None:
    answers = exam_state.get("answers", {})
    for q_key in STAGE2_QUESTION_KEYS:
        payload = answers.get(q_key)
        if not isinstance(payload, dict):
            return q_key
        if payload.get("review_status") != "reviewed":
            return q_key
    return None


def parse_teacher_score(text: str) -> tuple[float | None, float | None, str]:
    raw = (text or "").strip()
    if not raw:
        return None, None, ""

    match = re.match(r"^([0-9]+(?:[.,][0-9]+)?)(?:\s*/\s*([0-9]+(?:[.,][0-9]+)?))?(?:\s*[-:]\s*(.*))?$", raw)
    if not match:
        return None, None, raw

    score = float(match.group(1).replace(",", "."))
    max_score = match.group(2)
    comment = (match.group(3) or "").strip()
    return score, (float(max_score.replace(",", ".")) if max_score else None), comment


def update_latest_result_record(user_id: int, exam_code: str, answers: dict, total_ball, max_ball):
    results = read_json(EXAM_RESULTS_FILE)
    if not isinstance(results, list):
        return
    for item in reversed(results):
        if str(item.get("user_id")) == str(user_id) and item.get("exam_code") == exam_code:
            item["score"] = total_ball
            item["total"] = max_ball
            item["answers"] = answers
            item["updated_at"] = time.time()
            write_json(EXAM_RESULTS_FILE, results)
            return


def stage2_payload_text(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    if payload.get("mode") == "text":
        return str(payload.get("text", "")).strip()
    return ""



def stage2_status_text(payload: dict) -> str:
    if not isinstance(payload, dict):
        return "🔴"
    if payload.get("review_status") == "reviewed":
        score = payload.get("score")
        return f"✅ ({score})" if score is not None else "✅"
    if payload.get("review_status") == "pending":
        if payload.get("mode") == "file":
            return "⏳📎"
        if payload.get("parts"):
            return "⏳🧩"
        return "⏳📝"
    if payload.get("mode") == "file":
        return "📎"
    if payload.get("parts"):
        return "🧩"
    if payload.get("mode") == "text":
        return "📝"
    return "🔴"


def send_stage2_to_teacher(student_message, user_id: int, exam_state: dict, q_key: str, payload: dict, file_type: str | None = None):
    exam_code = sanitize_plain(exam_state.get("exam_code", ""))
    student_name = sanitize_plain(
        student_message.from_user.full_name or student_message.from_user.first_name or "Noma'lum"
    )
    q_key = sanitize_plain(q_key)
    mode = payload.get("mode", "text")
    review_type = sanitize_plain(file_type or mode)

    caption = (
        "Tekshiruv uchun javob\n"
        f"Imtihon: {exam_code}\n"
        f"O'quvchi: {student_name} ({user_id})\n"
        f"Savol: {q_key}\n"
        f"Tur: {review_type}\n\n"
        "Tez baholash tugmalaridan foydalaning yoki reply qilib ball yozing.\n"
        "Namuna: 48 yoki 48/75 - izoh bolsin yoki yoq"
    )

    pending = load_pending_reviews()
    pending_message = None

    try:
        if mode == "file":
            file_id = payload.get("file_id")
            if payload.get("content_type") == "photo":
                pending_message = bot.send_photo(ADMIN_ID, file_id, caption=caption)
            else:
                pending_message = bot.send_document(ADMIN_ID, file_id, caption=caption)
        else:
            body = format_stage2_review_text(q_key, payload)
            review_text = f"{caption}\n\n{body}"
            pending_message = bot.send_message(ADMIN_ID, review_text)
    except Exception as e:
        logger.error(f"Admin chatga yuborishda xato: {e}")
        bot.reply_to(student_message, "❌ Javobni tekshiruvga yuborishda xato yuz berdi. yoki etiborsiz qilmoqdasiz")
        return False

    pending[str(pending_message.message_id)] = {
        "student_id": int(user_id),
        "student_chat_id": student_message.chat.id,
        "exam_code": exam_code,
        "q_key": q_key,
        "teacher_message_id": pending_message.message_id,
        "student_message_id": student_message.message_id,
        "mode": mode,
        "file_type": file_type,
        "submitted_at": time.time(),
        "text": payload.get("text"),
        "parts": payload.get("parts", {}),
    }
    save_pending_reviews(pending)

    try:
        bot.edit_message_reply_markup(
            chat_id=ADMIN_ID,
            message_id=pending_message.message_id,
            reply_markup=build_teacher_review_keyboard(pending_message.message_id),
        )
    except Exception:
        pass

    return True

def save_stage2_answer_to_state(user_id: int, q_key: str, payload: dict):

    state = get_state(user_id)
    exam_state = state.get("in_exam")
    if not exam_state:
        return None
    answers = exam_state.setdefault("answers", {})
    answers[q_key] = payload
    exam_state["answers"] = answers
    state["in_exam"] = exam_state
    set_state(user_id, state)
    return exam_state


def get_main_keyboard(is_admin=False):
    """Asosiy menyu tugmalarini yaratadi."""
    keyboard = [
        ["🔑 Imtihon boshlash", "📊 Natijalarim"]
    ]
    if is_admin:
        keyboard.append(["📝 Imtihon yaratish", "📋 Imtihonlar ro'yxati"])
    return build_reply_keyboard(keyboard)



def get_score(answers: dict, exam_data: dict):
    """Javoblarni tekshirib, ball va umumiy ballni qaytaradi."""
    total_ball = 0.0
    max_ball = 0.0
    questions = exam_data.get("questions", {})

    for q_key, q_data in questions.items():
        q_type = q_data.get("type")

        if q_type in ["MCQ_4", "MCQ_6"]:
            q_ball = float(q_data.get("ball", 1))
            max_ball += q_ball
            user_answer = answers.get(q_key)
            correct_answer = q_data.get("answer")
            if user_answer and user_answer == correct_answer:
                total_ball += q_ball

        elif q_type == "OPEN":
            q_ball = float(q_data.get("ball", 1))
            max_ball += q_ball
            user_answer = answers.get(q_key)
            correct_answers = [str(a).strip().lower() for a in q_data.get("answer", [])]
            if user_answer:
                processed_user_answer = str(user_answer).strip().lower()
                if processed_user_answer in correct_answers:
                    total_ball += q_ball

        elif q_type == "COMPLEX_SUB":
            sub_questions = q_data.get("sub_questions", {})
            for sub_key, sub_data in sub_questions.items():
                sub_ball = float(sub_data.get("ball", 1))
                max_ball += sub_ball
                full_key = f"{q_key}-{sub_key}"
                user_sub_answer = answers.get(full_key)

                if sub_data.get("type") == "OPEN":
                    correct_answers = [str(a).strip().lower() for a in sub_data.get("answer", [])]
                    if user_sub_answer:
                        processed_user_answer = str(user_sub_answer).strip().lower()
                        if processed_user_answer in correct_answers:
                            total_ball += sub_ball

    if float(total_ball).is_integer():
        total_ball = int(total_ball)
    if float(max_ball).is_integer():
        max_ball = int(max_ball)

    return total_ball, max_ball


def create_answer_sheet_keyboard(answers: dict, stage: int, exam_data: dict, current_page: int = 1, time_left: float | None = None):
    """Javob varag'i tugmalarini yaratadi."""
    questions = exam_data.get("questions", {})

    if stage == 1:
        all_q_keys = [str(i) for i in range(1, STAGE1_TOTAL_QUESTIONS + 1)]
        items_per_page = 25
    elif stage == 2:
        all_q_keys = stage2_question_keys()
        items_per_page = 3
    else:
        return types.InlineKeyboardMarkup()

    start_index = (current_page - 1) * items_per_page
    end_index = start_index + items_per_page
    page_q_keys = all_q_keys[start_index:end_index]
    total_pages = max(1, (len(all_q_keys) + items_per_page - 1) // items_per_page)

    keyboard_layout = []
    row = []

    for q_key in page_q_keys:
        q_num = int(q_key)
        q_data = questions.get(q_key, {})
        q_type = q_data.get("type")

        button_text = f"🔴 S{q_num}"
        callback_data = "IGNORE"

        if stage == 1:
            if 1 <= q_num <= 35:
                answered = answers.get(q_key)
                if answered:
                    button_text = f"✅ S{q_num} ({answered})"
                callback_data = f"EXAM|{q_key}|SHOW_OPTIONS|{current_page}"

            elif 36 <= q_num <= STAGE1_TOTAL_QUESTIONS:
                if q_type == "OPEN":
                    answered = answers.get(q_key)
                    button_text = f"{'✅' if answered else '📝'} S{q_num}"
                    callback_data = f"EXAM|{q_key}|TEXT_INPUT|{current_page}"

                elif q_type == "COMPLEX_SUB":
                    sub_questions = q_data.get("sub_questions", {})
                    answered_parts = sum(1 for sub_key in sub_questions if f"{q_key}-{sub_key}" in answers)
                    total_parts = len(sub_questions)
                    if total_parts <= 0:
                        continue
                    status_emoji = "✅" if answered_parts == total_parts else ("🟡" if answered_parts > 0 else "🧩")
                    button_text = f"{status_emoji} S{q_num} ({answered_parts}/{total_parts})"
                    callback_data = f"EXAM|{q_key}|TEXT_INPUT|{current_page}"
                else:
                    continue
            else:
                continue

        else:
            payload = answers.get(q_key)
            status = stage2_status_text(payload)
            button_text = f"{status} S{q_num}"
            if isinstance(payload, dict) and payload.get("review_status") == "reviewed":
                score = payload.get("score")
                if score is not None:
                    button_text = f"✅ S{q_num} ({score})"
            callback_data = f"EXAM|{q_key}|STAGE2_INPUT|{current_page}"

        row.append(types.InlineKeyboardButton(button_text, callback_data=callback_data))
        if len(row) == (3 if stage == 2 else 4):
            keyboard_layout.append(row)
            row = []

    if row:
        keyboard_layout.append(row)

    navigation_row = []
    if total_pages > 1:
        if current_page > 1:
            navigation_row.append(types.InlineKeyboardButton("⬅️ Oldingi", callback_data=f"PAGE|{current_page - 1}"))
        navigation_row.append(types.InlineKeyboardButton(f"Sahifa {current_page}/{total_pages}", callback_data="IGNORE"))
        if current_page < total_pages:
            navigation_row.append(types.InlineKeyboardButton("Keyingi ➡️", callback_data=f"PAGE|{current_page + 1}"))

    if navigation_row:
        keyboard_layout.append(navigation_row)

    keyboard_layout.append([types.InlineKeyboardButton("🏁 Imtihonni yakunlash", callback_data="EXAM|FINISH|0")])
    return types.InlineKeyboardMarkup(keyboard_layout)


def finish_exam(chat_id, user_id: int):
    """Imtihonni yakunlaydi, natijalarni hisoblaydi va saqlaydi."""
    state = get_state(user_id)
    if not state.get("in_exam"):
        return

    exam_state = state["in_exam"]
    exam_code = exam_state["exam_code"]
    answers = exam_state["answers"]

    exams = read_json(EXAMS_FILE)
    exam_data = exams.get(exam_code, {})

    total_ball, max_ball = get_score(answers, exam_data)

    results = read_json(EXAM_RESULTS_FILE)
    new_result = {
        "user_id": str(user_id),
        "exam_code": exam_code,
        "score": total_ball,
        "total": max_ball,
        "timestamp": time.time(),
        "answers": answers,
    }
    if not isinstance(results, list):
        results = []
    results.append(new_result)
    write_json(EXAM_RESULTS_FILE, results)

    response = f"🎉 **Imtihon yakunlandi!**\n\n"
    response += f"**Imtihon kodi:** `{exam_code}`\n"
    response += f"**Yig'ilgan ball:** **{total_ball}** / **{max_ball}**\n\n"
    response += "Natijalarim panelidan o'zingizning to'liq 40 ta savolni. natijalaringizni tekshirishingiz mumkin. yozma ish javobi kuting."

    delete_message_safely(chat_id, exam_state.get("timer_message_id"))
    delete_message_safely(chat_id, exam_state.get("answer_sheet_id"))
    delete_message_safely(chat_id, exam_state.get("awaiting_open_prompt_id"))
    delete_message_safely(chat_id, exam_state.get("awaiting_stage2_prompt_id"))

    try:
        bot.send_message(
            chat_id,
            response,
            reply_markup=get_main_keyboard(chat_id == ADMIN_ID),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Yakunlashda xato (send): {e}")
        bot.send_message(chat_id, response, reply_markup=get_main_keyboard(chat_id == ADMIN_ID), parse_mode="Markdown")

    state.pop("in_exam", None)
    state.pop("mode", None)
    state.pop("awaiting_stage2_q", None)
    state.pop("awaiting_open_q", None)
    state.pop("awaiting_open_prompt_id", None)
    state.pop("awaiting_stage2_prompt_id", None)
    state.pop("timer_message_id", None)
    set_state(user_id, state)


def move_to_stage_2(chat_id: int, user_id: int, exam_state: dict, exam_data: dict) -> bool:
    """1-bosqichdan 2-bosqichga o'tkazadi."""
    state = get_state(user_id)
    current_time = time.time()
    stage_2_time_min = exam_data.get("stage_2_time_min", 95)

    exam_state["stage"] = 2
    exam_state["start_time"] = current_time
    exam_state["end_time"] = current_time + (stage_2_time_min * 60)
    exam_state["current_page"] = 1
    exam_state["awaiting_stage2_q"] = None
    exam_state.pop("awaiting_open_q", None)
    exam_state.pop("awaiting_open_prompt_id", None)
    exam_state.pop("awaiting_stage2_prompt_id", None)
    state["in_exam"] = exam_state
    set_state(user_id, state)

    timer_text = build_timer_text(2, stage_2_time_min * 60)
    msg_text = f"**JAVOB VARAG'I (Sahifa 1)**"
    new_keyboard = create_answer_sheet_keyboard(exam_state["answers"], 2, exam_data, 1)

    try:
        delete_message_safely(chat_id, exam_state.get("answer_sheet_id"))
        delete_message_safely(chat_id, exam_state.get("awaiting_open_prompt_id"))
        delete_message_safely(chat_id, exam_state.get("awaiting_stage2_prompt_id"))

        stage_2_file = exam_data.get("stage_2_file_url")
        if stage_2_file:
            bot.send_document(chat_id, stage_2_file, caption="Savol varag'i 2-bosqich (41-43 savollar)")
            time.sleep(0.5)

        timer_message_id = exam_state.get("timer_message_id")
        if timer_message_id:
            try:
                bot.edit_message_text(timer_text, chat_id=chat_id, message_id=timer_message_id, parse_mode=None)
            except Exception:
                timer_sent = bot.send_message(chat_id, timer_text, parse_mode=None)
                exam_state["timer_message_id"] = timer_sent.message_id
        else:
            timer_sent = bot.send_message(chat_id, timer_text, parse_mode=None)
            exam_state["timer_message_id"] = timer_sent.message_id

        sent_message = bot.send_message(chat_id, msg_text, reply_markup=new_keyboard, parse_mode="Markdown")
        exam_state["answer_sheet_id"] = sent_message.message_id
        exam_state["message_text"] = msg_text
        state["in_exam"] = exam_state
        set_state(user_id, state)
        return True
    except Exception as e:
        logger.error(f"Bosqich 2 ga o'tishda xato: {e}")
        bot.send_message(chat_id, "❌ Bosqich 2 ga o'tishda xato yuz berdi. Iltimos, /start bosing.")
        return False


def update_answer_sheet(chat_id: int, user_id: int, current_time: float | None = None):
    update_timer_message(chat_id, user_id, current_time=current_time)


def exam_timer_check_loop():
    """Har 1 sekundda imtihon vaqtini tekshiradi."""
    while True:
        try:
            current_time = time.time()
            items = list(user_states.items())
            if not items:
                time.sleep(TIME_REFRESH_SECONDS)
                continue

            exams = read_json(EXAMS_FILE)

            for user_id, state in items:
                exam_state = state.get("in_exam")
                if not exam_state:
                    continue

                chat_id = exam_state["user_id"]
                exam_code = exam_state["exam_code"]
                stage = exam_state["stage"]
                exam_data = exams.get(exam_code, {})

                time_left = exam_state["end_time"] - current_time

                if time_left <= 0:
                    if stage == 1:
                        move_to_stage_2(chat_id, user_id, exam_state, exam_data)
                        continue
                    elif stage == 2:
                        finish_exam(chat_id, user_id)
                        continue

                last_tick = exam_state.get("last_tick")
                displayed_tick = int(time_left)
                if last_tick == displayed_tick:
                    continue

                exam_state["last_tick"] = displayed_tick
                state["in_exam"] = exam_state
                set_state(user_id, state)
                update_answer_sheet(chat_id, user_id, current_time=current_time)
        except Exception as e:
            logger.error(f"Timer loop xatosi: {e}")

        time.sleep(TIME_REFRESH_SECONDS)

def handle_create_exam_step(message, text, mode):
    """Adminning imtihon yaratish qadamlarini to'liq boshqaradi."""
    user_id = message.from_user.id
    state = get_state(user_id)
    exam_state = state.setdefault("create_exam", {})
    exam_state.setdefault("questions", {})

    if text.lower() == "bekor qilish":
        clear_state(user_id)
        bot.reply_to(message, "✅ Imtihon yaratish jarayoni bekor qilindi.", reply_markup=get_main_keyboard(True))
        return True

    # --- Qadam 1 ---
    if mode == "create_exam_code":
        exam_code = text.strip().upper()
        exams = read_json(EXAMS_FILE)
        if exam_code in exams:
            bot.reply_to(message, "❌ Bunday kod allaqachon mavjud. Boshqa kod kiriting.")
        else:
            exam_state["code"] = exam_code
            state["mode"] = "create_exam_name"
            set_state(user_id, state)
            bot.reply_to(message, "📝 Imtihon nomi/mavzusini kiriting (Masalan: Matematika blok 2024):")
        return True

    if mode == "create_exam_name":
        exam_state["name"] = text.strip()
        state["mode"] = "create_exam_file_1"
        set_state(user_id, state)
        bot.reply_to(message, "📝 1-Bosqich (1-40) savollar faylini **Telegram File ID** yoki **URL** orqali kiriting:")
        return True

    if mode == "create_exam_file_1":
        exam_state["stage_1_file_url"] = text.strip()
        state["mode"] = "create_exam_time_1"
        set_state(user_id, state)
        bot.reply_to(message, "📝 1-Bosqich (1-40) uchun vaqtni **minutda** kiriting (Masalan: 120):")
        return True

    if mode == "create_exam_time_1":
        try:
            time_min = int(text.strip())
            exam_state["stage_1_time_min"] = time_min
            state["mode"] = "create_exam_file_2"
            set_state(user_id, state)
            bot.reply_to(message, "📝 2-Bosqich (41-43) savollar faylini **Telegram File ID** yoki **URL** orqali kiriting:")
        except ValueError:
            bot.reply_to(message, "❌ Noto'g'ri format. Vaqtni faqat **raqamda (minut)** kiriting.")
        return True

    if mode == "create_exam_file_2":
        exam_state["stage_2_file_url"] = text.strip()
        state["mode"] = "create_exam_time_2"
        set_state(user_id, state)
        bot.reply_to(message, "📝 2-Bosqich (41-43) uchun vaqtni **minutda** kiriting (Masalan: 95):")
        return True

    if mode == "create_exam_time_2":
        try:
            time_min = int(text.strip())
            exam_state["stage_2_time_min"] = time_min
            exam_state["next_q_num"] = exam_state.get("next_q_num", 1)
            state["mode"] = "create_exam_q_type"
            set_state(user_id, state)
            bot.reply_to(
                message,
                f"✅ Barcha asosiy sozlamalar saqlandi.\n\nSavol #{exam_state['next_q_num']} uchun turini tanlang:",
                reply_markup=get_question_creation_menu(),
            )
        except ValueError:
            bot.reply_to(message, "❌ Noto'g'ri format. Vaqtni faqat **raqamda (minut)** kiriting.")
        return True

    # --- Savol turi tanlash ---
    if mode == "create_exam_q_type":
        q_num = exam_state.get("next_q_num", 1)

        if 1 <= q_num <= 32 and text == "4 Variantli (1-32)":
            exam_state["current_q_type"] = "MCQ_4"
            exam_state["current_q_opts"] = ["A", "B", "C", "D"]
            state["mode"] = "create_exam_correct_ans"
            set_state(user_id, state)
            bot.reply_to(
                message,
                f"✅ Savol #{q_num} uchun to'g'ri javob variantini tanlang (A, B, C yoki D):",
                reply_markup=build_reply_keyboard([[o for o in exam_state["current_q_opts"]]], one_time=True),
            )

        elif 33 <= q_num <= 35 and text == "6 Variantli (33-35)":
            exam_state["current_q_type"] = "MCQ_6"
            exam_state["current_q_opts"] = ["A", "B", "C", "D", "E", "F"]
            state["mode"] = "create_exam_correct_ans"
            set_state(user_id, state)
            bot.reply_to(
                message,
                f"✅ Savol #{q_num} uchun to'g'ri javob variantini tanlang (A, B, C, D, E, F):",
                reply_markup=build_reply_keyboard([[o for o in exam_state["current_q_opts"]]], one_time=True),
            )

        elif 36 <= q_num <= 40 and text == "Ochiq Savol (36-40)":
            state["mode"] = "create_exam_open_count"
            set_state(user_id, state)
            bot.reply_to(
                message,
                f"📝 Savol #{q_num} nechta qismdan iborat?\n1 bo'lsa oddiy javob, 2 va undan ko'p bo'lsa qismli javob ishlatiladi.",
                parse_mode="Markdown",
            )

        elif text == "Test Savollari Tugadi":
            if exam_state.get("questions"):
                state["mode"] = "create_exam_save"
                set_state(user_id, state)
                bot.reply_to(message, "✅ Savollar kiritish tugadi. Imtihonni saqlash uchun **SAQLASH** deb yozing.")
            else:
                bot.reply_to(message, "❌ Avval kamida bittasavol kiritishingiz kerak.")
        else:
            bot.reply_to(message, "❌ Noto'g'ri tur tanlandi yoki savol raqami chegaradan chiqdi.")

        state["create_exam"] = exam_state
        set_state(user_id, state)
        return True

    # --- Yopiq Savollar Javobini Saqlash (1-35) ---
    if mode == "create_exam_correct_ans":
        q_num = exam_state.get("next_q_num", 1)
        if text.upper().strip() in exam_state.get("current_q_opts", []):
            exam_state["temp_answer"] = text.upper().strip()
            state["mode"] = "create_exam_ball"
            set_state(user_id, state)
            bot.reply_to(message, f"📝 Savol #{q_num} uchun ball kiriting (masalan: 1, 2, 0.5):")
        else:
            bot.reply_to(message, "❌ Noto'g'ri javob variantini tanlash.")
        state["create_exam"] = exam_state
        set_state(user_id, state)
        return True

    if mode == "create_exam_ball":
        q_num = exam_state.get("next_q_num", 1)
        try:
            ball = float(text.strip())
            if ball <= 0:
                raise ValueError

            exam_state["questions"][str(q_num)] = {
                "type": exam_state["current_q_type"],
                "answer": exam_state["temp_answer"],
                "ball": ball,
            }
            exam_state["next_q_num"] = q_num + 1
            exam_state.pop("temp_answer", None)

            state["mode"] = "create_exam_q_type"
            set_state(user_id, state)

            bot.reply_to(
                message,
                f"✅ Savol #{q_num} saqlandi.\n\nSavol #{exam_state['next_q_num']} uchun turini tanlang:",
                reply_markup=get_question_creation_menu(),
            )
        except ValueError:
            bot.reply_to(message, "❌ Ballni faqat musbat raqam ko'rinishida kiriting.")
        state["create_exam"] = exam_state
        set_state(user_id, state)
        return True

    # --- Ochiq Savollar (36-40) ---
    if mode == "create_exam_open_count":
        q_num = exam_state.get("next_q_num", 1)
        try:
            count = int(text.strip())
            if not (1 <= count <= 10):
                bot.reply_to(message, "❌ Qismlar soni 1 dan 10 gacha bo'lishi kerak.")
                return True

            exam_state["current_sub_count"] = count
            exam_state["current_sub_index"] = 0
            exam_state["current_q_type"] = "OPEN" if count == 1 else "COMPLEX_SUB"
            state["create_exam"] = exam_state
            set_state(user_id, state)

            if count == 1:
                state["mode"] = "create_exam_open_ans"
                set_state(user_id, state)
                bot.reply_to(
                    message,
                    f"📝 Savol #{q_num} javobini kiriting. Agar bir nechta to'g'ri javob bo'lsa, vergul bilan ajrating.",
                    parse_mode="Markdown",
                )
            else:
                state["mode"] = "create_exam_complex_ans_open"
                set_state(user_id, state)
                sub_key = chr(ord("A") + exam_state["current_sub_index"])
                bot.reply_to(
                    message,
                    f"📝 Savol #{q_num}-{sub_key} uchun javobni kiriting. Agar bir nechta to'g'ri javob bo'lsa, vergul bilan ajrating.",
                    parse_mode="Markdown",
                )
        except ValueError:
            bot.reply_to(message, "❌ Faqat musbat son kiriting (qismlar soni uchun).")
        return True

    if mode == "create_exam_open_ans":
        q_num = exam_state.get("next_q_num", 1)
        correct_answers_raw = [ans.strip() for ans in text.split(",") if ans.strip()]
        if not correct_answers_raw:
            bot.reply_to(message, "❌ Kamida bitta to'g'ri javob kiriting.")
            return True

        exam_state["temp_answer"] = correct_answers_raw
        state["mode"] = "create_exam_open_ball"
        set_state(user_id, state)
        bot.reply_to(message, f"📝 Savol #{q_num} uchun ball kiriting (masalan: 1, 0.5):")
        return True

    if mode == "create_exam_open_ball":
        q_num = exam_state.get("next_q_num", 1)
        try:
            ball = float(text.strip())
            if ball <= 0:
                raise ValueError

            exam_state["questions"][str(q_num)] = {
                "type": "OPEN",
                "answer": exam_state["temp_answer"],
                "ball": ball,
            }

            exam_state.pop("temp_answer", None)
            state["mode"] = "create_exam_open_desc"
            set_state(user_id, state)
            bot.reply_to(
                message,
                f"📝 Savol #{q_num} uchun tavsif yoki eslatma kiriting. Kerak bo'lmasa `-` yozing:",
                parse_mode="Markdown",
            )
        except ValueError:
            bot.reply_to(message, "❌ Ballni faqat musbat raqam ko'rinishida kiriting.")
        state["create_exam"] = exam_state
        set_state(user_id, state)
        return True

    if mode == "create_exam_open_desc":
        q_num = exam_state.get("next_q_num", 1)
        if not is_optional_skip(text):
            exam_state["questions"][str(q_num)]["description"] = text.strip()

        exam_state["next_q_num"] = q_num + 1
        exam_state.pop("current_sub_count", None)
        exam_state.pop("current_sub_index", None)
        exam_state.pop("current_q_type", None)

        state["mode"] = "create_exam_q_type"
        set_state(user_id, state)

        bot.reply_to(
            message,
            f"✅ Savol #{q_num} saqlandi.\n\nSavol #{exam_state['next_q_num']} uchun turini tanlang:",
            reply_markup=get_question_creation_menu(),
        )
        state["create_exam"] = exam_state
        set_state(user_id, state)
        return True

    if mode == "create_exam_complex_ans_open":
        q_num = exam_state.get("next_q_num", 1)
        sub_key = chr(ord("A") + exam_state["current_sub_index"])
        correct_answers_raw = [ans.strip() for ans in text.split(",") if ans.strip()]
        if not correct_answers_raw:
            bot.reply_to(message, "❌ Kamida bitta to'g'ri javob kiriting.")
            return True

        exam_state["questions"].setdefault(str(q_num), {"type": "COMPLEX_SUB", "sub_questions": {}})
        exam_state["questions"][str(q_num)]["sub_questions"][sub_key] = {
            "type": "OPEN",
            "answer": correct_answers_raw,
        }

        state["mode"] = "create_exam_complex_ball"
        set_state(user_id, state)
        bot.reply_to(message, f"📝 Savol #{q_num}-{sub_key} uchun ball kiriting (masalan: 1, 0.5):", parse_mode="Markdown")
        return True

    if mode == "create_exam_complex_ball":
        q_num = exam_state.get("next_q_num", 1)
        sub_key = chr(ord("A") + exam_state["current_sub_index"])
        try:
            ball = float(text.strip())
            if ball <= 0:
                raise ValueError

            exam_state["questions"][str(q_num)]["sub_questions"][sub_key]["ball"] = ball
            state["mode"] = "create_exam_complex_desc"
            set_state(user_id, state)
            bot.reply_to(
                message,
                f"📝 Savol #{q_num}-{sub_key} uchun tavsif yoki eslatma kiriting. Kerak bo'lmasa `-` yozing:",
                parse_mode="Markdown",
            )
        except ValueError:
            bot.reply_to(message, "❌ Ballni faqat musbat raqam ko'rinishida kiriting.")
        state["create_exam"] = exam_state
        set_state(user_id, state)
        return True

    if mode == "create_exam_complex_desc":
        q_num = exam_state.get("next_q_num", 1)
        sub_key = chr(ord("A") + exam_state["current_sub_index"])
        if not is_optional_skip(text):
            exam_state["questions"][str(q_num)]["sub_questions"][sub_key]["description"] = text.strip()

        exam_state["current_sub_index"] += 1

        if exam_state["current_sub_index"] < exam_state.get("current_sub_count", 0):
            state["mode"] = "create_exam_complex_ans_open"
            set_state(user_id, state)
            next_sub_key = chr(ord("A") + exam_state["current_sub_index"])
            bot.reply_to(
                message,
                f"📝 Savol #{q_num}-{next_sub_key} uchun javobni kiriting. Agar bir nechta to'g'ri javob bo'lsa, vergul bilan ajrating.",
                parse_mode="Markdown",
            )
        else:
            exam_state["next_q_num"] = q_num + 1
            exam_state.pop("current_sub_count", None)
            exam_state.pop("current_sub_index", None)
            exam_state.pop("current_q_type", None)

            state["mode"] = "create_exam_q_type"
            set_state(user_id, state)

            bot.reply_to(
                message,
                f"✅ Savol #{q_num} va uning barcha qismlari saqlandi.\n\nSavol #{exam_state['next_q_num']} uchun turini tanlang:",
                reply_markup=get_question_creation_menu(),
            )
        state["create_exam"] = exam_state
        set_state(user_id, state)
        return True

    # --- Yakuniy saqlash ---
    if mode == "create_exam_save" and text.lower() == "saqlash":
        exam_code = exam_state.get("code")
        exams = read_json(EXAMS_FILE)

        if not exam_state.get("questions"):
            bot.reply_to(message, "❌ Savollar kiritilmagan. Saqlash bekor qilindi.")
            clear_state(user_id)
            return True

        exams[exam_code] = {
            "name": exam_state.get("name", exam_code),
            "stage_1_file_url": exam_state.get("stage_1_file_url"),
            "stage_1_time_min": exam_state.get("stage_1_time_min"),
            "stage_2_file_url": exam_state.get("stage_2_file_url"),
            "stage_2_time_min": exam_state.get("stage_2_time_min"),
            "questions": exam_state["questions"],
        }
        write_json(EXAMS_FILE, exams)
        clear_state(user_id)
        bot.reply_to(message, f"✅ **'{exam_code}'** imtihoni muvaffaqiyatli saqlandi!", reply_markup=get_main_keyboard(True), parse_mode="Markdown")
        return True

    return False


def user_functions(message, text, uid):
    """Foydalanuvchi tomonidan yuborilgan matnli xabarlarni boshqaradi."""
    user_id = int(uid)
    state = get_state(user_id)
    exam_state = state.get("in_exam", {})

    # --- Stage 2 javoblari: matn yuborish ---
    if exam_state and str(exam_state.get("user_id")) == uid and exam_state.get("stage") == 2:
        if text not in {"🔑 Imtihon boshlash", "📊 Natijalarim"} and not text.startswith("/"):
            awaiting_q = exam_state.get("awaiting_stage2_q") or first_pending_stage2_question(exam_state)
            if awaiting_q:
                payload = build_stage2_submission_payload("text", text=text)
                save_stage2_answer_to_state(user_id, awaiting_q, payload)
                delete_message_safely(message.chat.id, exam_state.get("awaiting_stage2_prompt_id"))
                exam_state["awaiting_stage2_q"] = None
                exam_state.pop("awaiting_stage2_prompt_id", None)
                state["in_exam"] = exam_state
                set_state(user_id, state)
                send_stage2_to_teacher(message, user_id, exam_state, awaiting_q, payload, file_type="text")
                bot.reply_to(message, f"✅ Savol `{awaiting_q}` javobi qabul qilindi va tekshiruvga yuborildi.", parse_mode="Markdown")
                return True

    # --- Ochiq / qismli savollarga javob berish (imtihon ichida) ---
    if exam_state and str(exam_state.get("user_id")) == uid:
        last_open_q = exam_state.get("awaiting_open_q")

        if last_open_q:
            q_num = last_open_q
            q_data = read_json(EXAMS_FILE).get(exam_state["exam_code"], {}).get("questions", {}).get(q_num, {})
            q_type = q_data.get("type")

            if q_type == "OPEN":
                user_answer = text.strip()
                if not user_answer:
                    bot.reply_to(message, "❌ Javob bo'sh bo'lishi mumkin emas.")
                    return True

                exam_state["answers"][q_num] = user_answer
                delete_message_safely(message.chat.id, exam_state.get("awaiting_open_prompt_id"))
                exam_state["awaiting_open_q"] = None
                exam_state.pop("awaiting_open_prompt_id", None)
                state["in_exam"] = exam_state
                set_state(user_id, state)

                current_page = exam_state.get("current_page", 1)
                exams = read_json(EXAMS_FILE)
                exam_data = exams.get(exam_state["exam_code"])
                time_left = exam_state["end_time"] - time.time()
                new_keyboard = create_answer_sheet_keyboard(
                    exam_state["answers"],
                    exam_state["stage"],
                    exam_data,
                    current_page,
                    time_left,
                )

                try:
                    bot.edit_message_reply_markup(
                        chat_id=message.chat.id,
                        message_id=exam_state["answer_sheet_id"],
                        reply_markup=new_keyboard,
                    )
                except Exception as e:
                    if not is_not_modified_error(e):
                        logger.error(f"Ochiq savol javobidan keyin panel yangilash xatosi: {e}")
                bot.reply_to(message, f"✅ Savol #{q_num} javobi qabul qilindi.")
                return True

            if q_type == "COMPLEX_SUB":
                parts = extract_labeled_parts(text)
                if not parts:
                    bot.reply_to(message, "❌ Javob formatini to'g'ri kiriting. Misol: `A)5.5, B)To'g'ri`")
                    return True

                for sub_key, user_answer in parts.items():
                    if sub_key in q_data.get("sub_questions", {}):
                        full_key = f"{q_num}-{sub_key}"
                        exam_state["answers"][full_key] = user_answer

                delete_message_safely(message.chat.id, exam_state.get("awaiting_open_prompt_id"))
                exam_state["awaiting_open_q"] = None
                exam_state.pop("awaiting_open_prompt_id", None)
                state["in_exam"] = exam_state
                set_state(user_id, state)

                current_page = exam_state.get("current_page", 1)
                exams = read_json(EXAMS_FILE)
                exam_data = exams.get(exam_state["exam_code"])
                time_left = exam_state["end_time"] - time.time()
                new_keyboard = create_answer_sheet_keyboard(
                    exam_state["answers"],
                    exam_state["stage"],
                    exam_data,
                    current_page,
                    time_left,
                )

                try:
                    bot.edit_message_reply_markup(
                        chat_id=message.chat.id,
                        message_id=exam_state["answer_sheet_id"],
                        reply_markup=new_keyboard,
                    )
                except Exception as e:
                    if not is_not_modified_error(e):
                        logger.error(f"Ochiq savol javobidan keyin panel yangilash xatosi: {e}")
                bot.reply_to(message, f"✅ Savol #{q_num} qismlari uchun javoblar qabul qilindi.")
                return True

    # --- Asosiy Menyu Xabarlari ---
    if text == "🔑 Imtihon boshlash":
        exams = read_json(EXAMS_FILE)
        if not exams:
            bot.reply_to(message, "❌ Hozirda faol imtihonlar yo'q. Adminni kuting.")
        else:
            state["mode"] = "exam_start_code"
            set_state(user_id, state)
            codes = "\n".join(exams.keys())
            bot.reply_to(
                message,
                f"🔑 Imtihon kodini kiriting:\n\n**Mavjud Kodlar:**\n{codes}",
                parse_mode="Markdown",
            )
        return True

    if state.get("mode") == "exam_start_code":
        exam_code = text.strip().upper()
        exams = read_json(EXAMS_FILE)

        if exam_code in exams:
            exam_data = exams[exam_code]
            stage_1_time = exam_data.get("stage_1_time_min", 120)

            start_time = time.time()
            end_time = start_time + (stage_1_time * 60)

            exam_state = {
                "user_id": int(uid),
                "exam_code": exam_code,
                "start_time": start_time,
                "end_time": end_time,
                "answers": {},
                "stage": 1,
                "message_text": "",
                "current_page": 1,
                "last_tick": None,
            }
            state["in_exam"] = exam_state
            state.pop("mode", None)
            set_state(user_id, state)

            stage_1_file = exam_data.get("stage_1_file_url")
            if stage_1_file:
                bot.send_document(message.chat.id, stage_1_file, caption="Savol varag'i 1-bosqich (1-40 savollar)")
                time.sleep(0.5)

            timer_message = bot.send_message(
                message.chat.id,
                build_timer_text(1, end_time - start_time),
                parse_mode=None,
            )

            msg_text = f"**JAVOB VARAG'I (Sahifa 1)**"
            new_keyboard = create_answer_sheet_keyboard(exam_state["answers"], 1, exam_data, 1)

            sent_message = bot.reply_to(message, msg_text, reply_markup=new_keyboard, parse_mode="Markdown")

            exam_state["timer_message_id"] = timer_message.message_id
            exam_state["answer_sheet_id"] = sent_message.message_id
            exam_state["message_text"] = msg_text
            state["in_exam"] = exam_state
            set_state(user_id, state)
        else:
            bot.reply_to(message, f"❌ '{exam_code}' kodli imtihon topilmadi. Qayta kiriting.")
        return True

    if text == "📊 Natijalarim":
        results = read_json(EXAM_RESULTS_FILE)
        user_results = [r for r in results if str(r.get("user_id")) == uid]

        if not user_results:
            bot.reply_to(message, "Siz hali imtihon topshirmadingiz.")
        else:
            response = "📝 **Sizning Natijalaringiz:**\n\n"

            for i, res in enumerate(user_results):
                dt_object = time.ctime(res["timestamp"])
                response += f"{i+1}. **{res['exam_code']}**: {res['score']}/{res['total']} (_{dt_object}_)\n"
            bot.reply_to(message, response, parse_mode="Markdown")
        return True

    return False

@bot.message_handler(commands=["start"])
def start(message):
    if not message:
        return

    send_typing(message.chat.id)
    user = message.from_user
    state = get_state(user.id)

    if state.get("in_exam"):
        bot.reply_to(message, "❌ Imtihonni yakunlamaguningizcha boshqa buyruq bera olmaysiz.")
        return

    clear_state(user.id)
    is_admin = user.id == ADMIN_ID
    reply = get_main_keyboard(is_admin)
    bot.reply_to(message, "👋 Xush kelibsiz! Asosiy menyu:", reply_markup=reply)


@bot.message_handler(content_types=["text"])
def message_handler(message):
    if not message or not message.text:
        return

    send_typing(message.chat.id)
    user = message.from_user
    uid = str(user.id)
    text = (message.text or "").strip()

    state = get_state(user.id)
    mode = state.get("mode")

    if user.id == ADMIN_ID:
        if process_teacher_review_reply(message):
            return

        if mode and mode.startswith("create_exam_"):
            handled = handle_create_exam_step(message, text, mode)
            if handled:
                return

        if text == "📝 Imtihon yaratish":
            clear_state(user.id)
            state = {"mode": "create_exam_code"}
            set_state(user.id, state)
            bot.reply_to(
                message,
                "📝 Yangi imtihon uchun **Kod** kiriting (Masalan: SERTIFIKAT-1):",
                reply_markup=build_reply_keyboard([["Bekor qilish"]], one_time=True),
            )
            return

        if text == "📋 Imtihonlar ro'yxati":
            exams = read_json(EXAMS_FILE)
            if not exams:
                bot.reply_to(message, "Hozirda ro'yxatda imtihonlar yo'q.")
            else:
                response = "📋 **Mavjud Imtihonlar:**\n"
                for code, data in exams.items():
                    response += f"\n**Kod:** `{code}`\n"
                    response += f"**Nomi:** {data.get('name', 'Nomsiz')}\n"
                    response += f"**Savol soni:** {len(data.get('questions', {}))}\n"
                bot.reply_to(message, response, parse_mode="Markdown")
            return

    user_functions(message, text, uid)



@bot.message_handler(content_types=["document", "photo"])

def get_file_id(message):
    """Admin fayl ID sini qaytaradi yoki o'quvchining 2-bosqich faylini tekshiruvga yuboradi."""
    user_id = message.from_user.id
    state = get_state(user_id)
    exam_state = state.get("in_exam", {})

    file_id = None
    file_type = None

    if message.document:
        file_id = message.document.file_id
        file_type = "document"
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"

    if not file_id:
        return

    if user_id != ADMIN_ID and exam_state and str(exam_state.get("user_id")) == str(user_id) and exam_state.get("stage") == 2:
        q_key = exam_state.get("awaiting_stage2_q") or first_pending_stage2_question(exam_state)
        if not q_key:
            bot.reply_to(message, "❌ 2-bosqich savollari uchun tekshiruvga yuboriladigan joy qolmadi.")
            return

        payload = build_stage2_submission_payload("file", file_id=file_id, content_type=file_type)
        save_stage2_answer_to_state(user_id, q_key, payload)
        delete_message_safely(message.chat.id, exam_state.get("awaiting_stage2_prompt_id"))
        exam_state["awaiting_stage2_q"] = None
        exam_state.pop("awaiting_stage2_prompt_id", None)
        state["in_exam"] = exam_state
        set_state(user_id, state)
        if send_stage2_to_teacher(message, user_id, exam_state, q_key, payload, file_type=file_type):
            bot.reply_to(message, f"✅ Savol {q_key} fayli qabul qilindi va o'qituvchiga yuborildi.")
        return

    if user_id != ADMIN_ID:
        return

    text = (
        f"Fayl ID ({'Hujjat/PDF' if message.document else 'Rasm'}):\n\n"
        f"{file_id}\n\n"
        "Eslatma: Savol varag'ini yaratishda shu ID ni ishlating. Yani shu id ni nusxlab olib chatga qayta tashlang. Shunda fileingizni yuborgan boladsiz!!!"
    )
    try:
        bot.reply_to(message, text)
    except Exception as e:
        logger.error(f"Admin fayl ID qaytarishda xato: {e}")
    logger.info(f"Admin uchun File ID yuborildi: {file_id}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("PAGE|"))
def page_callback_handler(call):
    safe_answer_callback_query(call.id)

    data = call.data.split("|")
    if data[0] != "PAGE":
        return

    new_page = int(data[1])
    user_id = call.from_user.id
    state = get_state(user_id)
    exam_state = state.get("in_exam", {})
    if not exam_state:
        return

    exam_code = exam_state["exam_code"]
    exams = read_json(EXAMS_FILE)
    exam_data = exams.get(exam_code)
    stage = exam_state["stage"]

    time_left = max(0, exam_state["end_time"] - time.time())
    new_keyboard = create_answer_sheet_keyboard(
        exam_state["answers"],
        stage,
        exam_data,
        new_page,
        time_left,
    )

    try:
        bot.edit_message_text(
            f"**JAVOB VARAG'I (Sahifa {new_page if stage == 1 else 1})**",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=new_keyboard,
            parse_mode="Markdown",
        )
        exam_state["current_page"] = new_page
        exam_state["last_tick"] = int(time_left)
        state["in_exam"] = exam_state
        set_state(user_id, state)
    except Exception as e:
        logger.error(f"PAGE callbackda xato: {e}")
        safe_answer_callback_query(call.id, "❌ Sahifa yangilanishida xato yuz berdi.", show_alert=False)


@bot.callback_query_handler(func=lambda call: call.data == "IGNORE")
def ignore_callback_handler(call):
    safe_answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("REVIEW|"))
def review_callback_handler(call):
    safe_answer_callback_query(call.id)

    parts = call.data.split("|")
    if len(parts) < 4:
        return

    pending_id = parts[1]
    try:
        score = float(parts[2])
        max_score = float(parts[3])
    except ValueError:
        safe_answer_callback_query(call.id, "❌ Noto'g'ri ball.", show_alert=False)
        return

    pending = load_pending_reviews()
    review = pending.get(str(pending_id))
    if not review:
        safe_answer_callback_query(call.id, "❌ Tekshiruv topilmadi.", show_alert=False)
        return

    apply_teacher_review(
        review,
        score,
        max_score,
        "",
        admin_chat_id=call.message.chat.id,
        admin_message_id=call.message.message_id,
        pending_id=str(pending_id),
    )
    safe_answer_callback_query(call.id, f"✅ {score}/{max_score} baholandi.", show_alert=False)


@bot.callback_query_handler(func=lambda call: call.data.startswith("EXAM|"))
def exam_callback_handler(call):
    safe_answer_callback_query(call.id)

    data = call.data.split("|")
    if data[0] != "EXAM":
        return

    uid = str(call.from_user.id)
    user_id = call.from_user.id
    state = get_state(user_id)
    exam_state = state.get("in_exam", {})

    if not exam_state or uid != str(exam_state.get("user_id")):
        safe_answer_callback_query(call.id, "❌ Imtihon holati topilmadi yoki tugagan.", show_alert=False)
        return

    exam_code = exam_state["exam_code"]
    exams = read_json(EXAMS_FILE)
    exam_data = exams.get(exam_code)
    stage = exam_state["stage"]
    time_left = exam_state["end_time"] - time.time()

    if time_left <= 0:
        if stage == 1:
            move_to_stage_2(call.message.chat.id, user_id, exam_state, exam_data)
        else:
            finish_exam(call.message.chat.id, user_id)
        return

    if len(data) > 2 and data[2] == "CANCEL":
        current_page = exam_state.get("current_page", 1)
        new_keyboard = create_answer_sheet_keyboard(
            exam_state["answers"],
            stage,
            exam_data,
            current_page,
            time_left,
        )
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=new_keyboard,
            )
        except Exception:
            pass
        return

    if data[1] == "FINISH":
        if stage == 1:
            buttons = [
                [types.InlineKeyboardButton("🏁 HA, 2-BOSQICHGA o'taman", callback_data="EXAM|NEXT_STAGE|0")],
                [types.InlineKeyboardButton("🛑 YO'Q, Imtihonni TUGATAMAN", callback_data="EXAM|CONFIRM_FINISH|0")],
                [types.InlineKeyboardButton("⬅️ Orqaga", callback_data="EXAM|FINISH|CANCEL|0")],
            ]
            time_display = format_time(time_left)
            bot.edit_message_text(
                f"❓ Qolgan vaqt: **{time_display}**.\n\nSiz:\n1. Vaqtni kutmasdan **2-Bosqichga** o'tmoqchimisiz?\n2. Yoki imtihonni **to'liq yakunlamoqchimisiz**?",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=types.InlineKeyboardMarkup(buttons),
                parse_mode="Markdown",
            )
            return

        elif stage == 2:
            buttons = [
                [types.InlineKeyboardButton("✅ HA, Yakunlayman", callback_data="EXAM|CONFIRM_FINISH|0")],
                [types.InlineKeyboardButton("❌ YO'Q, Davom etaman", callback_data="EXAM|FINISH|CANCEL|0")],
            ]
            time_display = format_time(time_left)
            bot.edit_message_text(
                f"❓ Imtihonni yakunlashga ishonchingiz komilmi? Qolgan vaqt: **{time_display}**",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=types.InlineKeyboardMarkup(buttons),
                parse_mode="Markdown",
            )
            return

    if data[1] == "NEXT_STAGE" and stage == 1:
        move_to_stage_2(call.message.chat.id, user_id, exam_state, exam_data)
        return

    if data[1] == "CONFIRM_FINISH":
        finish_exam(call.message.chat.id, user_id)
        return

    q_key = data[1]
    action = data[2]
    current_page = int(data[3]) if len(data) > 3 and data[3].isdigit() else exam_state.get("current_page", 1)

    if action == "SHOW_OPTIONS" and 1 <= int(q_key) <= 35:
        q_data = exam_data.get("questions", {}).get(q_key, {})
        q_type = q_data.get("type")

        if q_type == "MCQ_4":
            options = ["A", "B", "C", "D"]
        elif q_type == "MCQ_6":
            options = ["A", "B", "C", "D", "E", "F"]
        else:
            safe_answer_callback_query(call.id, "Savol turini aniqlab bo'lmadi.", show_alert=False)
            return

        buttons = [types.InlineKeyboardButton(opt, callback_data=f"EXAM|{q_key}|{opt}|{current_page}") for opt in options]
        options_keyboard = [buttons]
        options_keyboard.append([types.InlineKeyboardButton("⬅️ Orqaga (Panelni yopish)", callback_data=f"EXAM|{q_key}|CLOSE_OPTIONS|{current_page}")])
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=types.InlineKeyboardMarkup(options_keyboard))
        return

    if action == "CLOSE_OPTIONS":
        new_keyboard = create_answer_sheet_keyboard(
            exam_state["answers"],
            stage,
            exam_data,
            current_page,
            time_left,
        )
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=new_keyboard)
        return

    if q_key.isdigit() and 1 <= int(q_key) <= 35 and action in ["A", "B", "C", "D", "E", "F"]:
        old_answer = exam_state["answers"].get(q_key)
        exam_state["answers"][q_key] = action
        exam_state["current_page"] = current_page
        state["in_exam"] = exam_state
        set_state(user_id, state)

        new_keyboard = create_answer_sheet_keyboard(
            exam_state["answers"],
            stage,
            exam_data,
            current_page,
            time_left,
        )

        try:
            bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=new_keyboard)
            if old_answer == action:
                safe_answer_callback_query(call.id, "Javobingiz allaqachon belgilangan.", show_alert=False)
            else:
                safe_answer_callback_query(call.id, f"✅ Savol {q_key} - {action} javobi saqlandi.", show_alert=False)
        except Exception:
            safe_answer_callback_query(call.id, "Javob saqlandi, panel yangilanishida xato.", show_alert=False)
        return

    if q_key.isdigit() and int(q_key) >= 36 and action == "TEXT_INPUT":
        q_data = exam_data.get("questions", {}).get(q_key, {})
        q_type = q_data.get("type")

        if q_type in {"OPEN", "COMPLEX_SUB"}:
            prompt = get_question_prompt(int(q_key), q_data)
            sent = bot.send_message(
                call.message.chat.id,
                prompt,
                parse_mode="Markdown",
            )
            exam_state["awaiting_open_q"] = q_key
            exam_state["awaiting_open_prompt_id"] = sent.message_id
            exam_state["current_page"] = current_page
            state["in_exam"] = exam_state
            set_state(user_id, state)
        return

    if q_key.isdigit() and int(q_key) >= 41 and action == "STAGE2_INPUT":
        sent = bot.send_message(
            call.message.chat.id,
            f"📎 Savol #{q_key} uchun javobni matn yoki fayl ko'rinishida yuboring. Matn bo'lsa qismli yozish ham mumkin.",
            parse_mode=None,
        )
        exam_state["awaiting_stage2_q"] = q_key
        exam_state["awaiting_stage2_prompt_id"] = sent.message_id
        state["in_exam"] = exam_state
        set_state(user_id, state)
        return


def apply_teacher_review(
    review: dict,
    score: float,
    max_score: float | None,
    comment: str,
    admin_chat_id: int | None = None,
    admin_message_id: int | None = None,
    pending_id: str | None = None,
):
    student_id = int(review["student_id"])
    exam_code = review["exam_code"]
    q_key = str(review["q_key"])

    state = get_state(student_id)
    exam_state = state.get("in_exam")
    if not exam_state or exam_state.get("exam_code") != exam_code:
        exam_state = None

    if exam_state:
        answers = exam_state.setdefault("answers", {})
        payload = answers.get(q_key, {})
        if not isinstance(payload, dict):
            payload = {"mode": review.get("mode", "text")}

        payload["review_status"] = "reviewed"
        payload["score"] = score
        if max_score is not None:
            payload["max_ball"] = max_score
        else:
            payload.setdefault("max_ball", STAGE2_DEFAULT_BALL)
        if comment:
            payload["teacher_comment"] = comment
        payload["reviewed_at"] = time.time()
        answers[q_key] = payload
        exam_state["answers"] = answers
        state["in_exam"] = exam_state
        set_state(student_id, state)

        total_ball, max_ball = get_score(answers, read_json(EXAMS_FILE).get(exam_code, {}))
        update_latest_result_record(student_id, exam_code, answers, total_ball, max_ball)

    pending = load_pending_reviews()
    pending_key = str(pending_id or admin_message_id or review.get("teacher_message_id") or "")
    if pending_key:
        pending.pop(pending_key, None)
        save_pending_reviews(pending)

    if admin_chat_id is not None and admin_message_id is not None:
        delete_message_safely(admin_chat_id, admin_message_id)

    summary = "\n".join([
        "Tekshiruv yakunlandi",
        f"O'quvchi: {student_id}",
        f"Imtihon: {exam_code}",
        f"Savol: {q_key}",
        f"Ball: {score}",
    ])
    if max_score is not None:
        summary += f"/{max_score}"
    if comment:
        summary += f"\nIzoh: {comment}"

    try:
        if admin_chat_id is not None:
            bot.send_message(admin_chat_id, summary)
    except Exception:
        pass

    student_text = f"Sizning {exam_code} imtihonidagi {q_key} savolingiz tekshirildi. Ball: {score}"
    if max_score is not None:
        student_text += f"/{max_score}"
    if comment:
        student_text += f"\nIzoh: {comment}"
    try:
        bot.send_message(student_id, student_text)
    except Exception as e:
        logger.error(f"Studentga xabar yuborishda xato: {e}")

    return True


def process_teacher_review_reply(message):
    if message.from_user.id != ADMIN_ID or not message.reply_to_message:
        return False

    pending = load_pending_reviews()
    reply_to_id = str(message.reply_to_message.message_id)
    review = pending.get(reply_to_id)
    if not review:
        return False

    score, max_score, comment = parse_teacher_score(message.text or "")
    if score is None:
        bot.reply_to(message, "❌ Ballni son bilan yozing. Misol: `56` yoki `56/75 - izoh bolsa yozing - qoyib `", parse_mode="Markdown")
        return True

    return apply_teacher_review(
        review,
        score,
        max_score,
        comment,
        admin_chat_id=message.chat.id,
        admin_message_id=message.reply_to_message.message_id,
        pending_id=reply_to_id,
    )


def main():
    timer_thread = threading.Thread(target=exam_timer_check_loop, daemon=True)
    timer_thread.start()
    print("✅ Bot ishga tushdi...")

    try:
        while True:
            try:
                bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
            except Exception as e:
                logger.error(f"Polling xatosi: {e}")
                time.sleep(5)
    except KeyboardInterrupt:
        print("🛑 Bot qo'lda to'xtatildi.")



if __name__ == "__main__":
    main()
