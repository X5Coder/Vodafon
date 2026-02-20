from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import time
import json
from threading import Thread
import uuid

app = Flask(__name__)
CORS(app)  # عشان يسمح للفرونت إند يتكلم معاه

# تخزين مؤقت للنتائج (في الذاكرة)
tasks = {}

# الكود الأصلي بتاعك (عدلته شوية)
def check_account_task(task_id, number, password):
    """الدالة اللي بتشغل الكود بتاعك"""
    
    token_url = "https://mobile.vodafone.com.eg/auth/realms/vf-realm/protocol/openid-connect/token"
    
    # 1. جلب التوكن
    payload = {
        'grant_type': "password",
        'username': number,
        'password': password,
        'client_secret': "95fd95fb-7489-4958-8ae6-d31a525cd20a",
        'client_id': "ana-vodafone-app"
    }
    
    headers_token = {
        'User-Agent': "okhttp/4.11.0",
        'clientId': "AnaVodafoneAndroid",
        'x-agent-version': "2025.11.1"
    }
    
    try:
        response = requests.post(token_url, data=payload, headers=headers_token)
        token = response.json().get("access_token", "")
        
        if not token:
            tasks[task_id] = {"status": "error", "message": "فشل تسجيل الدخول"}
            return
        
        # 2. جلب العروض
        promo_url = "https://web.vodafone.com.eg/services/dxl/ramadanpromo/promotion"
        params = {
            '@type': "RamadanHub",
            'channel': "website",
            'msisdn': number
        }
        
        headers_promo = {
            'User-Agent': "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
            'Authorization': f"Bearer {token}",
            'msisdn': number,
            'clientId': "WebsiteConsumer",
            'channel': "APP_PORTAL"
        }
        
        response = requests.get(promo_url, params=params, headers=headers_promo)
        data = response.json()
        
        # 3. استخراج الكروت
        cards = []
        if isinstance(data, list) and len(data) > 1:
            patterns = data[1].get("pattern", [])
            
            for item in patterns:
                actions = item.get("action", [])
                for action in actions:
                    chars = action.get("characteristics", [])
                    
                    char_dict = {}
                    for char in chars:
                        if isinstance(char, dict) and 'name' in char and 'value' in char:
                            char_dict[char['name']] = char['value']
                    
                    amount = char_dict.get('amount', 'N/A')
                    units = char_dict.get('GIFT_UNITS', 'N/A')
                    remaining = char_dict.get('REMAINING_DEDICATIONS', 'N/A')
                    card = char_dict.get('CARD_SERIAL', '')
                    
                    if card and amount != 'N/A' and not card.startswith("015"):
                        cards.append({
                            "code": f"*858*{card}#",
                            "amount": amount,
                            "units": units,
                            "remaining": remaining
                        })
                        time.sleep(0.1)
        
        tasks[task_id] = {
            "status": "completed",
            "cards": cards,
            "count": len(cards)
        }
        
    except Exception as e:
        tasks[task_id] = {"status": "error", "message": str(e)}

@app.route('/api/check', methods=['POST'])
def check_account():
    """الـ endpoint اللي بيستقبل الطلبات من المستخدم"""
    data = request.json
    number = data.get('number')
    password = data.get('password')
    
    if not number or not password:
        return jsonify({"error": "الرقم وكلمة السر مطلوبين"}), 400
    
    # إنشاء ID فريد للمهمة
    task_id = str(uuid.uuid4())
    
    # تخزين المهمة (حالتها: قيد التنفيذ)
    tasks[task_id] = {"status": "processing"}
    
    # تشغيل الفحص في Thread منفصل (عشان المستخدم ما ينتظرش)
    thread = Thread(target=check_account_task, args=(task_id, number, password))
    thread.daemon = True
    thread.start()
    
    # رجع للمستخدم الـ task_id عشان يسأل بالنتيجة بعدين
    return jsonify({"task_id": task_id, "status": "processing"})

@app.route('/api/result/<task_id>', methods=['GET'])
def get_result(task_id):
    """الـ endpoint اللي بيستعلم عن نتيجة المهمة"""
    task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "المهمة غير موجودة"}), 404
    
    return jsonify(task)

@app.route('/api/health', methods=['GET'])
def health():
    """للتحقق إن السيرفر شغال"""
    return jsonify({"status": "running"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
