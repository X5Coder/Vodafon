from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import time
import os
import socket

app = Flask(__name__)
CORS(app)  # دي بتخلي أي موقع يتصل بيك

# إعدادات فودافون
TOKEN_URL = "https://mobile.vodafone.com.eg/auth/realms/vf-realm/protocol/openid-connect/token"
CLIENT_SECRET = "95fd95fb-7489-4958-8ae6-d31a525cd20a"
CLIENT_ID = "ana-vodafone-app"

def get_access_token(number, password):
    """الحصول على رمز الدخول"""
    payload = {
        'grant_type': "password",
        'username': number,
        'password': password,
        'client_secret': CLIENT_SECRET,
        'client_id': CLIENT_ID
    }
    headers = {
        'User-Agent': "okhttp/4.11.0",
        'clientId': "AnaVodafoneAndroid",
        'x-agent-version': "2025.11.1"
    }
    try:
        response = requests.post(TOKEN_URL, data=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json().get("access_token", "")
        else:
            return None
    except Exception as e:
        print(f"❌ Token error: {e}")
        return None

def get_promotions(number, access_token):
    """جلب العروض"""
    url = "https://web.vodafone.com.eg/services/dxl/ramadanpromo/promotion"
    params = {
        '@type': "RamadanHub",
        'channel': "website",
        'msisdn': number
    }
    headers = {
        'User-Agent': "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
        'Accept': "application/json",
        'Authorization': f"Bearer {access_token}",
        'msisdn': number,
        'clientId': "WebsiteConsumer",
        'api-host': "PromotionHost",
        'channel': "APP_PORTAL",
        'Content-Type': "application/json",
        'X-Requested-With': "com.emeint.android.myservices",
        'Referer': "https://web.vodafone.com.eg/portal/bf/hub"
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        return response.json()
    except Exception as e:
        print(f"❌ Promo error: {e}")
        return {}

@app.route('/scan', methods=['POST'])
def scan_cards():
    """نقطة النهاية الرئيسية للمسح"""
    data = request.get_json()
    
    # التحقق من المدخلات
    if not data:
        return jsonify({
            'success': False,
            'error': 'Please send JSON data'
        }), 400
    
    number = data.get('number')
    password = data.get('password')
    
    if not number or not password:
        return jsonify({
            'success': False,
            'error': 'Please provide both number and password'
        }), 400
    
    print(f"\n📱 Scanning for: {number}")
    print(f"⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # الحصول على التوكن
    token = get_access_token(number, password)
    if not token:
        return jsonify({
            'success': False,
            'error': 'خطأ في الرقم أو كلمة المرور'
        }), 401
    
    # جلب العروض
    response_data = get_promotions(number, token)
    cards = []
    
    # تحليل البيانات
    try:
        if isinstance(response_data, list) and len(response_data) > 1:
            patterns = response_data[1].get("pattern", [])
            print(f"📦 Found {len(patterns)} patterns")
            
            for item in patterns:
                try:
                    actions = item.get("action", [])
                    for action in actions:
                        chars = action.get("characteristics", [])
                        
                        char_dict = {}
                        for char in chars:
                            if isinstance(char, dict) and 'name' in char and 'value' in char:
                                char_dict[char['name']] = char['value']
                        
                        # استخراج البيانات
                        amount = char_dict.get('amount', 'N/A')
                        units = char_dict.get('GIFT_UNITS', 'N/A')
                        remaining = char_dict.get('REMAINING_DEDICATIONS', 'N/A')
                        card = char_dict.get('CARD_SERIAL', '')
                        
                        # إضافة الكارت لو موجود
                        if card and amount != 'N/A' and not card.startswith("015"):
                            try:
                                amount_value = float(amount) if amount != 'N/A' else 0
                                
                                # طباعة في التيرمنال
                                print(f"✅ Found card: {card} - {amount} EGP")
                                
                                # إضافة للنتيجة
                                cards.append({
                                    'card_number': card,
                                    'value': amount_value,
                                    'units': int(units) if units != 'N/A' and str(units).isdigit() else 0,
                                    'remaining_charges': int(remaining) if remaining != 'N/A' and str(remaining).isdigit() else 0,
                                    'code': f"*858*{card}#"
                                })
                            except (ValueError, TypeError):
                                continue
                except Exception as e:
                    continue
    except Exception as e:
        print(f"❌ Parse error: {e}")
    
    print(f"\n✨ Found {len(cards)} card(s)")
    print("-" * 50)
    
    return jsonify({
        'success': True,
        'account': number,
        'total_cards': len(cards),
        'cards': cards,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/', methods=['GET'])
def home():
    """الصفحة الرئيسية"""
    return jsonify({
        'name': 'Vodafone Card Scanner API',
        'version': '3.0',
        'status': 'running',
        'endpoints': {
            '/scan': 'POST - Scan for cards (send JSON with number and password)',
            '/': 'GET - This info'
        },
        'how_to_use': {
            'method': 'POST',
            'url': '/scan',
            'headers': {'Content-Type': 'application/json'},
            'body': {'number': '010xxxxxxxx', 'password': 'your_password'}
        }
    })

if __name__ == '__main__':
    # Render بيدخل PORT في متغيرات البيئة
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
