# -*- coding: utf-8 -*-
import os
import io
import json
from flask import Flask, request, jsonify, send_file
from requests import get
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone

# تحميل مفاتيح API 
load_dotenv()

app = Flask(__name__, static_folder='frontend', static_url_path='')

# --- الثوابت والمقاييس ---
BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
API_URL = "https://api.twitter.com/2"

# الكلمات المفتاحية للمشروع (يمكنك تغييرها وتوسيعها)
TARGET_KEYWORDS = ["مشروعنا", "اسم_مشروعك_الفريد", "أفضل_تطبيق"]

# الأوزان في معادلة السكور
WEIGHTS = {
    "keyword_mentions": 0.60, # الوزن الأعلى للكلمات المفتاحية
    "followers_count": 0.25,
    "tweet_count": 0.10,
    "account_age": 0.05
}

# يجب تحميل خط يدعم اللغة العربية لتجنب ظهور رموز غير مفهومة
# إذا لم يكن لديك خط على جهازك، يمكن استخدام خط افتراضي، لكن يفضل تحميل خط عربي
# على سبيل المثال: 'arial.ttf' أو مسار لخط عربي 
try:
    FONT_AR = ImageFont.truetype("arial.ttf", 35)
    FONT_AR_SMALL = ImageFont.truetype("arial.ttf", 25)
except IOError:
    FONT_AR = ImageFont.load_default()
    FONT_AR_SMALL = ImageFont.load_default()

# ------------------------- دوال المساعدة -------------------------

def fetch_image_as_bytes(url):
    """تجلب الصورة من الرابط وتحولها إلى كائن بايت"""
    try:
        response = get(url, stream=True)
        response.raise_for_status()
        return io.BytesIO(response.content)
    except Exception as e:
        print(f"Error fetching image: {e}")
        return None

def calculate_score(user_data, mentions_count):
    """تحسب السكور النهائي للمستخدم"""
    followers = user_data.get("followers_count", 0)
    total_tweets = user_data.get("tweet_count", 0)
    
    # حساب عمر الحساب بالأيام
    created_at_str = user_data.get("created_at")
    if created_at_str:
        # تنسيق تاريخ تويتر هو ISO 8601
        creation_date = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        account_age_days = (datetime.now(timezone.utc) - creation_date).days
    else:
        account_age_days = 1

    # توحيد المقاييس (Normalization) من 0.0 إلى 1.0 
    
    # القيم القصوى المستخدمة للتوحيد: 100 إشارة، 10 آلاف متابع، 5 آلاف تغريدة، 3 سنوات (1095 يوم)
    normalized_mentions = min(mentions_count / 100.0, 1.0)
    normalized_followers = min(followers / 10000.0, 1.0) 
    normalized_tweets = min(total_tweets / 5000.0, 1.0)
    normalized_age = min(account_age_days / 1095.0, 1.0)
    
    # حساب السكور
    final_score = (
        WEIGHTS["keyword_mentions"] * normalized_mentions +
        WEIGHTS["followers_count"] * normalized_followers +
        WEIGHTS["tweet_count"] * normalized_tweets +
        WEIGHTS["account_age"] * normalized_age
    )
    
    # تحويل السكور إلى رقم من 1000 نقطة
    final_score_1000 = int(final_score * 1000)

    return {
        "score": final_score_1000,
        "mentions_count": mentions_count,
        "followers": followers
    }

def generate_score_image(username, score, profile_image_url):
    """تنشئ صورة تحتوي على السكور ومعلومات المستخدم"""
    try:
        # --- 1. إعداد القالب ---
        W, H = 800, 450
        img = Image.new("RGB", (W, H), color="#1DA1F2") # خلفية زرقاء لتويتر
        draw = ImageDraw.Draw(img)

        # --- 2. إضافة صورة البروفايل ---
        profile_img_stream = fetch_image_as_bytes(profile_image_url.replace('_normal', '_400x400'))
        if profile_img_stream:
            profile_img = Image.open(profile_img_stream).convert("RGBA").resize((180, 180))
            
            # وضع صورة البروفايل في الأعلى والمنتصف
            img.paste(profile_img, (W // 2 - 90, 50), profile_img)
        
        # --- 3. إضافة النصوص ---
        
        # عنوان السكور
        title_text = "سكور تأثير المشروع"
        draw.text((W // 2, 250), title_text, fill="white", font=FONT_AR_SMALL, anchor="ms")

        # السكور الرئيسي
        score_text = str(score)
        draw.text((W // 2, 300), score_text, fill="yellow", font=FONT_AR, anchor="ms")
        
        # اسم المستخدم
        username_text = f"@{username}"
        draw.text((W // 2, 360), username_text, fill="#CCCCCC", font=FONT_AR_SMALL, anchor="ms")
        
        # --- 4. إرجاع الصورة ---
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        print(f"Error generating image: {e}")
        # إرجاع صورة فارغة أو افتراضية عند الفشل
        return None

# ------------------------- نقطة النهاية (API Endpoint) -------------------------

@app.route("/api/score/<username>", methods=["GET"])
def get_user_score(username):
    """نقطة النهاية الرئيسية لحساب السكور وجلب البيانات"""
    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    
    # الخطوة 1: جلب بيانات المستخدم
    user_lookup_url = f"{API_URL}/users/by/username/{username}"
    params = {"user.fields": "public_metrics,created_at,profile_image_url"}
    
    user_response = get(user_lookup_url, headers=headers, params=params)
    
    if user_response.status_code != 200:
        try:
            error_data = user_response.json().get('errors', [{}])[0].get('detail', 'لا يمكن العثور على المستخدم أو مشكلة في الـ API')
        except json.JSONDecodeError:
            error_data = f"خطأ في الاتصال بالـ API: {user_response.status_code}"
        return jsonify({"error": error_data}), user_response.status_code
        
    user_data = user_response.json()["data"]
    user_id = user_data["id"]
    public_metrics = user_data["public_metrics"]

    # الخطوة 2: البحث عن التغريدات التي تذكر الكلمات المفتاحية
    keywords_query = " OR ".join(TARGET_KEYWORDS)
    search_query = f"({keywords_query}) from:{username}"
    
    # نقطة نهاية البحث
    search_url = f"{API_URL}/tweets/search/recent"
    search_params = {
        "query": search_query,
        "max_results": 100, # الحد الأقصى للجلب في المرة الواحدة
    }
    
    search_response = get(search_url, headers=headers, params=search_params)
    
    if search_response.status_code != 200:
        return jsonify({"error": "فشل في البحث عن التغريدات (قد تكون حدود الاستخدام)"}), 500

    mentions_count = search_response.json().get("meta", {}).get("result_count", 0)

    # الخطوة 3: حساب السكور
    score_result = calculate_score(
        user_data={**public_metrics, "created_at": user_data["created_at"]},
        mentions_count=mentions_count
    )
    
    score_result["profile_image_url"] = user_data.get("profile_image_url")
    score_result["username"] = username
    
    return jsonify(score_result), 200

@app.route("/api/score/image/<username>/<int:score>", methods=["GET"])
def get_score_image(username, score):
    """نقطة نهاية منفصلة لتوليد وعرض الصورة"""
    # هذا يتطلب جلب رابط الصورة مرة أخرى أو تمريره من الأمامية
    # لتبسيط الأمر، سنتجاهل الصورة الافتراضية هنا ونستخدم مسار جلب الصورة
    
    # NOTE: في تطبيق حقيقي، يجب جلب رابط صورة البروفايل من قاعدة بيانات بعد حساب السكور
    # هنا، نفترض أن لدينا رابط صورة بروفايل افتراضي مؤقتًا.
    DUMMY_PROFILE_URL = "https://abs.twimg.com/sticky/default_profile_images/default_profile.png"
    
    image_buffer = generate_score_image(username, score, DUMMY_PROFILE_URL)
    
    if image_buffer:
        return send_file(image_buffer, mimetype='image/png')
    else:
        return "فشل في توليد الصورة", 500

# ------------------------- خدمة ملفات الواجهة الأمامية -------------------------

@app.route("/")
def serve_index():
    """خدمة الملف الرئيسي index.html عند زيارة الموقع"""
    return app.send_static_file('index.html')

# --- تشغيل التطبيق ---
if __name__ == "__main__":
    # تشغيل Flask على 127.0.0.1:5000
    app.run(debug=True)
