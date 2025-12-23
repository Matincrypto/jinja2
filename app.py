from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
from jinja2 import Template
import json
import re
import os

app = Flask(__name__)
CORS(app)  # برای جلوگیری از خطای دسترسی مرورگر

# --- تنظیمات Gemini ---
# کلید خود را اینجا بگذارید
MY_API_KEY = "AIzaSyBvI3LZ8k49IuIcy27FmvackzejW3-WHDA".strip()
genai.configure(api_key=MY_API_KEY, transport='rest')
model = genai.GenerativeModel('gemini-flash-latest')

# کلمات کلیدی برای آنالیز اولیه
KEYWORDS = {
    "gratitude": [r"ممنون", r"تشکر", r"سپاس", r"لطف کردید", r"مرسی"],
    "greeting": [r"سلام", r"وقت بخیر", r"روز بخیر", r"خسته نباشید", r"ارادت"],
}


def analyze_chat_structure(chat_text):
    lines = chat_text.split('\n')
    context = {
        "raw_chat": chat_text,
        "has_user_gratitude": False,
        "has_user_greeting": False,
        "agent_started_first": False,
    }

    # تشخیص شروع کننده
    first_line = lines[0] if lines else ""
    if any(x in first_line for x in ["پشتیبان", "کارشناس", "AGENT", "Admin"]):
        context["agent_started_first"] = True

    # تشخیص کلمات کلیدی
    for pattern in KEYWORDS["gratitude"]:
        if re.search(pattern, chat_text):
            context["has_user_gratitude"] = True
            break

    for pattern in KEYWORDS["greeting"]:
        if re.search(pattern, chat_text):
            context["has_user_greeting"] = True
            break

    return context


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
def analyze_chat():
    data = request.json
    chat_text = data.get('chat_text', '')

    if not chat_text:
        return jsonify({"error": "متن چت خالی است"}), 400

    # 1. آنالیز اولیه با پایتون
    context = analyze_chat_structure(chat_text)

    # 2. ساخت پرامپت داینامیک با Jinja2
    prompt_template = """
    تو کارشناس کنترل کیفیت هستی.
    وظیفه: بررسی رعایت "تصدیق مناسب" در مکالمه.

    متن چت:
    {{ raw_chat }}

    دستورالعمل ارزیابی:
    {% if has_user_gratitude %}
    - کاربر تشکر کرده است. کارشناس **باید** پاسخ محبت‌آمیز داده باشد. (الزامی)
    {% endif %}

    {% if has_user_greeting %}
    - کاربر احوال‌پرسی کرده است. کارشناس باید پاسخ دهد.
    {% endif %}

    {% if agent_started_first %}
    - نکته: مکالمه توسط کارشناس شروع شده. اگر کاربر فقط جواب سلام داده، نیاز به تصدیق نیست.
    {% endif %}

    {% if not has_user_gratitude and not has_user_greeting %}
    - کاربر عبارت محبت‌آمیز خاصی نگفته است. فقط چک کن برخورد کارشناس محترمانه باشد.
    {% endif %}

    خروجی JSON:
    {
        "value": boolean,
        "reasoning": "توضیح کوتاه فارسی",
        "detected_items": ["لیست مواردی که در چت پیدا کردی"]
    }
    """

    jinja_tmpl = Template(prompt_template)
    final_prompt = jinja_tmpl.render(**context)

    # 3. ارسال به هوش مصنوعی
    try:
        response = model.generate_content(final_prompt)
        text_resp = response.text.replace('```json', '').replace('```', '').strip()

        match = re.search(r'\{.*\}', text_resp, re.DOTALL)
        if match:
            ai_result = json.loads(match.group())

            # ترکیب نتیجه هوش مصنوعی با نتیجه آنالیز پایتون برای نمایش در فرانت
            final_response = {
                "ai_result": ai_result,
                "python_analysis": context  # برای نمایش اینکه چه فلگ‌هایی فعال شدند
            }
            return jsonify(final_response)
        else:
            return jsonify({"error": "فرمت پاسخ AI صحیح نیست"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5090)
