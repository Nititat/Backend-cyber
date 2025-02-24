from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
import requests
import json
import bcrypt
from datetime import datetime, timedelta
from collections import Counter
import psycopg2
from psycopg2.extras import RealDictCursor
app = Flask(__name__)
CORS(app)
from flask_jwt_extended import JWTManager, create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from google.auth.transport.requests import Request
from google.oauth2.id_token import verify_oauth2_token
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pyotp
import qrcode
import io
from flask import send_file
import random
import colorsys
# เวลาปัจจุบันใน UTC
now = datetime.utcnow()

# คำนวณเที่ยงคืนของวันก่อนหน้า ("now-1d/d")
yesterday_midnight = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Access environment variables
ES_URL = os.getenv("ES_URL")
ES_URL2 = os.getenv("ES_URL2")
ES_USERNAME = os.getenv("ES_USERNAME")
ES_PASSWORD = os.getenv("ES_PASSWORD")

# JWT Configuration
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "your_secret_key")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=6000)  # Access Token หมดอายุใน -- นาที
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=6000)

jwt = JWTManager(app)

# Database connection setup
def connect_to_db():
    return psycopg2.connect(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        host=os.getenv("DB_HOST")
    )



# ฟังก์ชันสุ่มสี
def generate_random_color():
    h, s, v = random.random(), 0.9, 0.9  # ใช้ HSV เพื่อให้สีไม่ซ้ำกัน
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return f"#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}"

@app.route("/api/attack_colors/<attack_type>", methods=["GET"])
def get_or_create_attack_color(attack_type):
    conn = connect_to_db()
    cursor = conn.cursor()

    # ค้นหาสีที่เคยถูกบันทึกไว้แล้ว
    cursor.execute("SELECT color FROM attack_colors WHERE attack_type = %s", (attack_type,))
    result = cursor.fetchone()

    if result:
        color = result[0]
    else:
        # สร้างสีใหม่แล้วบันทึกลงในฐานข้อมูล
        color = generate_random_color()
        cursor.execute("INSERT INTO attack_colors (attack_type, color) VALUES (%s, %s) RETURNING color", 
                       (attack_type, color))
        conn.commit()

    cursor.close()
    conn.close()
    return jsonify({"attack_type": attack_type, "color": color})



# Register endpoint
@app.route("/api/register", methods=["POST"])
def register():
    """
    ลงทะเบียนผู้ใช้ใหม่
    """
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")
        email = data.get("email")

        if not username or not password or not email:
            return jsonify({"msg": "Username, password, and email are required"}), 400

        conn = connect_to_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # ตรวจสอบว่าชื่อผู้ใช้ซ้ำหรือไม่
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        existing_user = cursor.fetchone()
        if existing_user:
            return jsonify({"msg": "Username already exists"}), 400

        # ตรวจสอบว่า email ซ้ำหรือไม่
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        existing_email = cursor.fetchone()
        if existing_email:
            return jsonify({"msg": "Email already exists"}), 400

        # เข้ารหัสรหัสผ่านด้วย bcrypt
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # บันทึกผู้ใช้ในฐานข้อมูล
        cursor.execute(
            'INSERT INTO users (username, password_hash, email) VALUES (%s, %s, %s)',
            (username, password_hash, email)
        )
        conn.commit()

        return jsonify({"msg": "User registered successfully"}), 201
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"msg": "Internal Server Error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()



# @app.route("/api/google-auth", methods=["POST"])
# def google_auth():
#     """
#     ยืนยันตัวตนผู้ใช้ด้วย Google OAuth2 และสร้าง JWT Token
#     """
#     try:
#         # รับ token จาก frontend
#         data = request.get_json()
#         token = data.get("token")
#         if not token:
#             return jsonify({"msg": "Token is required"}), 400

#         # ตรวจสอบ token กับ Google
#         CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
#         idinfo = verify_oauth2_token(token, Request(), CLIENT_ID)

#         # ดึงข้อมูลผู้ใช้จาก token
#         google_id = idinfo.get("sub")
#         email = idinfo.get("email")
#         name = idinfo.get("name")

#         # เชื่อมต่อฐานข้อมูล
#         conn = connect_to_db()
#         cursor = conn.cursor(cursor_factory=RealDictCursor)

#         # ตรวจสอบว่าผู้ใช้มีอยู่ในฐานข้อมูลหรือยัง
#         cursor.execute('SELECT * FROM users WHERE google_id = %s', (google_id,))
#         user = cursor.fetchone()

#         if not user:
#             # เพิ่มผู้ใช้ใหม่
#             placeholder_password = "GOOGLE_AUTH_USER"
#             cursor.execute(
#                 '''
#                 INSERT INTO users (username, email, google_id, password_hash)
#                 VALUES (%s, %s, %s, %s)
#                 ''',
#                 (name, email, google_id, placeholder_password)
#             )
#             conn.commit()

#             user = {
#                 "username": name,
#                 "email": email,
#                 "google_id": google_id
#             }

#         # สร้าง JWT Token
#         access_token = create_access_token(identity=google_id)
#         refresh_token = create_refresh_token(identity=google_id)

#         return jsonify({
#             "msg": "Login successful",
#             "user": user,
#             "access_token": access_token,
#             "refresh_token": refresh_token
#         }), 200
#     except ValueError as e:
#         print(f"Invalid token: {e}")
#         return jsonify({"msg": "Invalid token"}), 401
#     except Exception as e:
#         print(f"Error: {e}")
#         return jsonify({"msg": "Internal Server Error"}), 500
#     finally:
#         if 'cursor' in locals():
#             cursor.close()
#         if 'conn' in locals():
#             conn.close()



@app.route("/api/login", methods=["POST"])
def login():
    """
    Login เพื่อรับ JWT Token และตรวจสอบการตั้งค่า 2FA
    """
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"msg": "Username and password are required"}), 400

        conn = connect_to_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # ตรวจสอบข้อมูลผู้ใช้
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()

        if user and bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
            # สร้าง JWT Token
            # access_token = create_access_token(identity=username)
            # refresh_token = create_refresh_token(identity=username)

            return jsonify({
                
                "user_info": {
                    "username": user["username"],
                    "role": user["role"]
                },
                "otp_configured": user["otp_configured"]  # ส่งสถานะ OTP
            }), 200

        return jsonify({"msg": "Invalid username or password"}), 401
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"msg": "Internal Server Error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()



@app.route("/api/2fa/verify", methods=["POST"])
def verify_2fa():
    """
    ยืนยัน OTP หลังจากสแกน QR Code
    """
    try:
        data = request.get_json()
        username = data.get("username")
        otp = data.get("otp")

        if not username or not otp:
            return jsonify({"msg": "Username and OTP are required"}), 400

        conn = connect_to_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # ตรวจสอบว่าผู้ใช้มีอยู่จริง
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"msg": "User not found"}), 404

        if not user["otp_secret"]:
            return jsonify({"msg": "2FA is not set up for this user"}), 400

        # ตรวจสอบ OTP
        totp = pyotp.TOTP(user["otp_secret"])
        if not totp.verify(otp):
            return jsonify({"msg": "Invalid OTP"}), 401

        # อัปเดตสถานะ otp_configured
        cursor.execute('UPDATE users SET otp_configured = TRUE WHERE username = %s', (username,))
        conn.commit()

        # สร้าง Access Token และ Refresh Token
        access_token = create_access_token(identity=username)
        refresh_token = create_refresh_token(identity=username)

        return jsonify({
            "msg": "OTP verified and 2FA is enabled",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_info": {
                "username": username,
                "role": user["role"],  # เพิ่ม role ใน response
                "roles": user.get("roles", [])
            }
        }), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"msg": "Internal Server Error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()






@app.route("/api/2fa/setup", methods=["POST"])
def setup_2fa():
    """
    สร้าง secret และ QR Code สำหรับ 2FA
    """
    try:
        data = request.get_json()
        username = data.get("username")

        if not username:
            return jsonify({"msg": "Username is required"}), 400

        conn = connect_to_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # ตรวจสอบว่าผู้ใช้มีอยู่จริง
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"msg": "User not found"}), 404

        if user["otp_configured"]:
            return jsonify({"msg": "2FA is already configured"}), 400

        # สร้าง secret ใหม่
        otp_secret = pyotp.random_base32()
        cursor.execute('UPDATE users SET otp_secret = %s WHERE username = %s', (otp_secret, username))
        conn.commit()

        # สร้าง URL สำหรับ QR Code
        totp = pyotp.TOTP(otp_secret)
        qr_url = totp.provisioning_uri(name=username, issuer_name="Melon Cloud")

        # สร้าง QR Code
        qr = qrcode.QRCode(box_size=10, border=5)
        qr.add_data(qr_url)
        qr.make(fit=True)
        img = qr.make_image(fill="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        return send_file(buf, mimetype="image/png")
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"msg": "Internal Server Error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()



@app.route("/api/users/reset-otp/<int:user_id>", methods=["PUT"])
@jwt_required()
def reset_otp(user_id):
    """
    รีเซ็ต OTP สำหรับผู้ใช้ที่ระบุ (ล้าง otp_secret และตั้งค่า otp_configured = FALSE)
    """
    try:
        conn = connect_to_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # ตรวจสอบว่าผู้ใช้มีอยู่จริงหรือไม่
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"msg": "User not found"}), 404

        # รีเซ็ตค่า OTP (ลบ otp_secret และตั้งค่า otp_configured = FALSE)
        cursor.execute(
            "UPDATE users SET otp_secret = NULL, otp_configured = FALSE WHERE id = %s",
            (user_id,)
        )
        conn.commit()

        return jsonify({"msg": "OTP reset successfully"}), 200

    except Exception as e:
        print(f"Error resetting OTP: {e}")
        return jsonify({"msg": "Internal Server Error"}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()




@app.route("/api/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """
    ใช้ Refresh Token เพื่อรับ Access Token ใหม่ พร้อมข้อมูลผู้ใช้
    """
    try:
        current_user = get_jwt_identity()

        conn = connect_to_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # ดึงข้อมูลผู้ใช้จากฐานข้อมูล
        cursor.execute('SELECT username, role FROM users WHERE username = %s', (current_user,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"msg": "User not found"}), 404

        new_access_token = create_access_token(identity=current_user)

        return jsonify({
            "access_token": new_access_token,
            "user_info": {
                "username": user["username"],
                "role": user["role"]
            }
        }), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"msg": "Internal Server Error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()





# Get all users endpoint
@app.route("/api/users", methods=["GET"])
@jwt_required()
def get_users():
    """
    ดึงข้อมูลผู้ใช้ทั้งหมด
    """
    try:
        conn = connect_to_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Query ข้อมูลผู้ใช้ทั้งหมด
        cursor.execute('SELECT id, username, email, google_id, role, created_at FROM users')
        users = cursor.fetchall()

        return jsonify(users), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"msg": "Internal Server Error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()





# Update user endpoint
@app.route("/api/users/<int:user_id>", methods=["PUT"])
@jwt_required()
def update_user(user_id):
    """
    แก้ไขข้อมูลผู้ใช้
    """
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")  # รับ password จาก request
        email = data.get("email")
        role = data.get("role")

        if not username or not email:
            return jsonify({"msg": "Username and email are required"}), 400

        # แฮชรหัสผ่านใหม่หากมีการส่งมา
        password_hash = None
        if password:
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        conn = connect_to_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # ตรวจสอบว่า username ซ้ำ (ยกเว้น ID ของผู้ใช้ที่กำลังแก้ไข)
        cursor.execute("SELECT * FROM users WHERE username = %s AND id != %s", (username, user_id))
        if cursor.fetchone():
            return jsonify({"field": "username", "msg": "Username already exists"}), 409

        # ตรวจสอบว่า email ซ้ำ (ยกเว้น ID ของผู้ใช้ที่กำลังแก้ไข)
        cursor.execute("SELECT * FROM users WHERE email = %s AND id != %s", (email, user_id))
        if cursor.fetchone():
            return jsonify({"field": "email", "msg": "Email already exists"}), 410

        # ดำเนินการอัปเดตข้อมูล
        if password_hash:
            cursor.execute(
                """
                UPDATE users 
                SET username = %s, password_hash = %s, email = %s, role = %s 
                WHERE id = %s
                """,
                (username, password_hash, email, role, user_id)
            )
        else:
            cursor.execute(
                """
                UPDATE users 
                SET username = %s, email = %s, role = %s 
                WHERE id = %s
                """,
                (username, email, role, user_id)
            )

        conn.commit()

        return jsonify({"msg": "User updated successfully"}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"msg": "Internal Server Error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()




@app.route("/api/users", methods=["POST"])
@jwt_required()  # ต้องการ JWT Authorization
def add_user():
    """
    เพิ่มผู้ใช้ใหม่และส่งอีเมลแจ้งข้อมูลเข้าสู่ระบบ
    """
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")
        email = data.get("email")
        role = data.get("role", "user")  # ตั้งค่า role เป็น 'user' โดย default

        # ตรวจสอบค่าที่จำเป็น
        if not username or not password or not email:
            return jsonify({"msg": "Username, password, and email are required"}), 400

        # แฮชรหัสผ่านด้วย bcrypt
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # เชื่อมต่อฐานข้อมูล
        conn = connect_to_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # ตรวจสอบว่าชื่อผู้ใช้ซ้ำหรือไม่
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            return jsonify({"msg": "Username already exists"}), 401

        # ตรวจสอบว่า email ซ้ำหรือไม่
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"msg": "Email already exists"}), 402

        # เพิ่มผู้ใช้ใหม่ในฐานข้อมูล
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, email, role)
            VALUES (%s, %s, %s, %s)
            """,
            (username, password_hash, email, role)
        )
        conn.commit()

        # ส่งอีเมลแจ้งข้อมูลเข้าสู่ระบบ
        send_email_notification(email, username, password)

        return jsonify({"msg": "User added successfully"}), 201
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"msg": "Internal Server Error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def send_email_notification(to_email, username, password):
    """
    ส่งอีเมลแจ้งข้อมูลเข้าสู่ระบบ
    """
    try:
        sender_email = os.getenv("EMAIL_ADDRESS")
        sender_password = os.getenv("EMAIL_PASSWORD")
        smtp_server = "smtp.gmail.com"
        smtp_port = 587

        subject = "Your Account Details"
        body = f"""
        Dear User,

        Your account has been created successfully.
        Here are your login details:
        Username: {username}
        Password: {password}

        Please change your password after your first login.

        Best regards,
        Your Team
        """

        # สร้างอีเมล
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        # ส่งอีเมล
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())

        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")


# Delete user endpoint
@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id):
    """
    ลบผู้ใช้
    """
    try:
        conn = connect_to_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # ลบผู้ใช้จากฐานข้อมูล
        cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
        conn.commit()

        return jsonify({"msg": "User deleted successfully"}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"msg": "Internal Server Error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()





@app.route("/api/change-password", methods=["PUT"])
@jwt_required()
def change_password():
    try:
        # Get user ID from JWT
        user_id = get_jwt_identity()
        
        # Get request data
        data = request.get_json()
        current_password = data.get("currentPassword")
        new_password = data.get("newPassword")
        
        if not current_password or not new_password:
            return jsonify({"msg": "Both current and new passwords are required"}), 400
            
        conn = connect_to_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get user with username instead of ID
        cursor.execute("SELECT * FROM users WHERE username = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({"msg": "User not found"}), 404
        
        # Verify current password
        if not bcrypt.checkpw(current_password.encode('utf-8'), user["password_hash"].encode('utf-8')):
            return jsonify({"msg": "Current password is incorrect"}), 401
            
        # Hash new password
        new_password_hash = bcrypt.hashpw(
            new_password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')
        
        # Update password
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (new_password_hash, user["id"])
        )
        conn.commit()
        
        return jsonify({"msg": "Password updated successfully"}), 200
        
    except Exception as e:
        print(f"Error changing password: {str(e)}")
        return jsonify({"msg": "Internal Server Error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()







@app.route("/api/alerts", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_alerts():
    """
    ดึงข้อมูล Alerts จาก Elasticsearch
    """
    try:
        # ดึงข้อมูล User จาก JWT
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")

        # Elasticsearch Query
        query = {
            "query": {
                "term": {
                    "rule.groups": "attack"
                }
            }
        }

        # ส่งคำขอไปยัง Elasticsearch
        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False
        )

        # ตรวจสอบสถานะ HTTP
        response.raise_for_status()

        # ดึงข้อมูล JSON จาก Elasticsearch
        data = response.json()
        hits = data.get("hits", {}).get("hits", [])

        # ส่งข้อมูลกลับในรูปแบบ JSON
        return jsonify(hits), 200

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching alerts: {e}"}), 500





@app.route("/api/top-mitre-techniques", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_top_mitre_techniques():
    """
    Fetch Top 10 MITRE ATT&CK Techniques
    """
    try:
        # ดึงข้อมูล User จาก JWT
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")
        
        # รับค่าจาก Query Parameter (ค่าเริ่มต้น 200 วัน)
        days = request.args.get("days", default=200, type=int)  
        if days not in [1, 30, 90, 200]:  # ตรวจสอบค่าที่รับมา
            return jsonify({"error": "Invalid days parameter"}), 400

        query = {
            "aggs": {
                "2": {
                    "terms": {
                        "field": "rule.mitre.technique",
                        "order": {
                            "_count": "desc"
                        },
                        "size": 10
                    }
                }
            },
            "size": 0,
            "stored_fields": ["*"],
            "script_fields": {},
            "docvalue_fields": [
                {"field": "data.aws.createdAt", "format": "date_time"},
                {"field": "data.aws.end", "format": "date_time"},
                {"field": "data.aws.resource.instanceDetails.launchTime", "format": "date_time"},
                {"field": "data.aws.service.eventFirstSeen", "format": "date_time"},
                {"field": "data.aws.service.eventLastSeen", "format": "date_time"},
                {"field": "data.aws.start", "format": "date_time"},
                {"field": "data.aws.updatedAt", "format": "date_time"},
                {"field": "data.ms-graph.createdDateTime", "format": "date_time"},
                {"field": "data.ms-graph.firstActivityDateTime", "format": "date_time"},
                {"field": "data.ms-graph.lastActivityDateTime", "format": "date_time"},
                {"field": "data.ms-graph.lastUpdateDateTime", "format": "date_time"},
                {"field": "data.ms-graph.resolvedDateTime", "format": "date_time"},
                {"field": "data.timestamp", "format": "date_time"},
                {"field": "data.vulnerability.published", "format": "date_time"},
                {"field": "data.vulnerability.updated", "format": "date_time"},
                {"field": "syscheck.mtime_after", "format": "date_time"},
                {"field": "syscheck.mtime_before", "format": "date_time"},
                {"field": "timestamp", "format": "date_time"}
            ],
            "_source": {"excludes": ["@timestamp"]},
            "query": {
                "bool": {
                    "must": [],
                    "filter": [
                        {"match_all": {}},
                        {"match_phrase": {"cluster.name": {"query": "wazuh"}}},
                        {
                            "range": {
                                "timestamp": {
                                    "gte": f"now-{days}d/d",  # ใช้ค่าจาก Query Parameter
                                    "lte": "now",   #ถึงเวลาปัจจุบัน
                                    "format": "strict_date_optional_time"
                                }
                            }
                        }
                    ],
                    "should": [],
                    "must_not": []
                }
            }
        }

        # Send Elasticsearch request
        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False  # Disable SSL verification (for development only)
        )

        # Raise an exception if the request fails
        response.raise_for_status()

        # Extract the response data
        data = response.json()
        buckets = data.get("aggregations", {}).get("2", {}).get("buckets", [])

        # Format the results
        results = [{"technique": bucket["key"], "count": bucket["doc_count"]} for bucket in buckets]

        return jsonify(results)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching data from Elasticsearch: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route("/api/top-agents", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_top_agents():
    """
    ดึงข้อมูล Top 5 Agent Names ที่มีการโจมตีมากที่สุด
    """
    try:
        # ดึงข้อมูล User จาก JWT
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")

        # รับค่าจาก Query Parameter (ค่าเริ่มต้น 200 วัน)
        days = request.args.get("days", default=200, type=int)  
        if days not in [1, 30, 90, 200]:  # ตรวจสอบค่าที่รับมา
            return jsonify({"error": "Invalid days parameter"}), 400

        # Elasticsearch Query
        query = {
            "aggs": {
                "2": {
                    "terms": {
                        "field": "agent.name",
                        "order": {
                            "_count": "desc"
                        },
                        "size": 5
                    }
                }
            },
            "size": 0,
            "stored_fields": ["*"],
            "docvalue_fields": [
                {"field": "data.aws.createdAt", "format": "date_time"},
                {"field": "data.aws.end", "format": "date_time"},
                {"field": "data.aws.resource.instanceDetails.launchTime", "format": "date_time"},
                {"field": "data.aws.service.eventFirstSeen", "format": "date_time"},
                {"field": "data.aws.service.eventLastSeen", "format": "date_time"},
                {"field": "data.aws.start", "format": "date_time"},
                {"field": "data.aws.updatedAt", "format": "date_time"},
                {"field": "data.ms-graph.createdDateTime", "format": "date_time"},
                {"field": "data.ms-graph.firstActivityDateTime", "format": "date_time"},
                {"field": "data.ms-graph.lastActivityDateTime", "format": "date_time"},
                {"field": "data.ms-graph.lastUpdateDateTime", "format": "date_time"},
                {"field": "data.ms-graph.resolvedDateTime", "format": "date_time"},
                {"field": "data.timestamp", "format": "date_time"},
                {"field": "data.vulnerability.published", "format": "date_time"},
                {"field": "data.vulnerability.updated", "format": "date_time"},
                {"field": "syscheck.mtime_after", "format": "date_time"},
                {"field": "syscheck.mtime_before", "format": "date_time"},
                {"field": "timestamp", "format": "date_time"}
            ],
            "_source": {"excludes": ["@timestamp"]},
            "query": {
                "bool": {
                    "must": [],
                    "filter": [
                        {"match_all": {}},
                        {"match_phrase": {"cluster.name": {"query": "wazuh"}}},
                        {
                            "range": {
                                "timestamp": {
                                    "gte": f"now-{days}d/d",  # ใช้ค่าจาก Query Parameter
                                    "lte": "now",
                                    "format": "strict_date_optional_time"
                                }
                            }
                        }
                    ],
                    "should": [],
                    "must_not": []
                }
            }
        }

        # ส่งคำขอไปยัง Elasticsearch
        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False
        )

        # ตรวจสอบสถานะ HTTP
        response.raise_for_status()

        # ดึงข้อมูล JSON จาก Elasticsearch
        data = response.json()
        buckets = data.get("aggregations", {}).get("2", {}).get("buckets", [])

        # แปลงข้อมูลสำหรับการตอบกลับ
        results = [{"agent_name": bucket["key"], "count": bucket["doc_count"]} for bucket in buckets]

        return jsonify(results)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching top agents: {e}"}), 500






@app.route("/api/top-countries", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_top_countries():
    """
    ดึงข้อมูล 10 ประเทศที่มีการโจมตีมากที่สุด
    """
    try:
        # ดึงข้อมูล User จาก JWT
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")


        # รับค่าจาก Query Parameter (ค่าเริ่มต้น 200 วัน)
        days = request.args.get("days", default=200, type=int)  
        if days not in [1, 30, 90, 200]:  # ตรวจสอบค่าที่รับมา
            return jsonify({"error": "Invalid days parameter"}), 400


        # Elasticsearch Query
        query = {
            "aggs": {
                "2": {
                    "terms": {
                        "field": "GeoLocation.country_name",
                        "order": {
                            "_count": "desc"
                        },
                        "size": 10
                    }
                }
            },
            "size": 0,
            "stored_fields": ["*"],
            "script_fields": {},
            "docvalue_fields": [
                {"field": "data.aws.createdAt", "format": "date_time"},
                {"field": "data.aws.end", "format": "date_time"},
                {"field": "data.aws.resource.instanceDetails.launchTime", "format": "date_time"},
                {"field": "data.aws.service.eventFirstSeen", "format": "date_time"},
                {"field": "data.aws.service.eventLastSeen", "format": "date_time"},
                {"field": "data.aws.start", "format": "date_time"},
                {"field": "data.aws.updatedAt", "format": "date_time"},
                {"field": "data.ms-graph.createdDateTime", "format": "date_time"},
                {"field": "data.ms-graph.firstActivityDateTime", "format": "date_time"},
                {"field": "data.ms-graph.lastActivityDateTime", "format": "date_time"},
                {"field": "data.ms-graph.lastUpdateDateTime", "format": "date_time"},
                {"field": "data.ms-graph.resolvedDateTime", "format": "date_time"},
                {"field": "data.timestamp", "format": "date_time"},
                {"field": "data.vulnerability.published", "format": "date_time"},
                {"field": "data.vulnerability.updated", "format": "date_time"},
                {"field": "syscheck.mtime_after", "format": "date_time"},
                {"field": "syscheck.mtime_before", "format": "date_time"},
                {"field": "timestamp", "format": "date_time"}
            ],
            "_source": {"excludes": ["@timestamp"]},
            "query": {
                "bool": {
                    "must": [],
                    "filter": [
                        {"match_all": {}},
                        {
                            "range": {
                                "timestamp": {
                                    "gte": f"now-{days}d/d",  # ใช้ค่าจาก Query Parameter
                                    "lte": "now",
                                    "format": "strict_date_optional_time"
                                }
                            }
                        }
                    ]
                }
            }
        }

        # ส่งคำขอไปยัง Elasticsearch
        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False
        )

        # ตรวจสอบสถานะ HTTP
        response.raise_for_status()

        # ดึงข้อมูล JSON จาก Elasticsearch
        data = response.json()
        buckets = data.get("aggregations", {}).get("2", {}).get("buckets", [])

        # แปลงข้อมูลสำหรับการตอบกลับ
        results = [{"country": bucket["key"], "count": bucket["doc_count"]} for bucket in buckets]

        return jsonify(results)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching top countries: {e}"}), 500




@app.route("/api/top-techniques", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_top_techniques():
    """
    Fetches the top MITRE techniques with historical attack data broken down by 30-minute intervals.
    """
    try:
        # ดึงข้อมูล User จาก JWT
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")
        # Elasticsearch Query for top MITRE techniques within a specific date range
        
        days = request.args.get("days", default=200, type=int)  
        if days not in [1, 30, 90, 200]:  # ตรวจสอบค่าที่รับมา
            return jsonify({"error": "Invalid days parameter"}), 400
        query = {
            "aggs": {
                "3": {
                    "terms": {
                        "field": "rule.mitre.technique",
                        "order": {
                            "_count": "desc"
                        },
                        "size": 5
                    },
                    "aggs": {
                        "2": {
                            "date_histogram": {
                                "field": "timestamp",
                                "fixed_interval": "30m",  # 30-minute intervals
                                "time_zone": "Asia/Bangkok",  # Adjust to local timezone
                                "min_doc_count": 1
                            }
                        }
                    }
                }
            },
            "size": 0,  # We only want aggregation results, no hits
            "query": {
                "bool": {
                    "filter": [
                        {"match_all": {}},
                        {"match_phrase": {"cluster.name": {"query": "wazuh"}}},  # Only data from 'wazuh' cluster
                        {"exists": {"field": "rule.mitre.id"}},  # Only documents with a MITRE ID
                        {
                            "range": {
                                "timestamp": {
                                    "gte": f"now-{days}d/d",  # ใช้ค่าจาก Query Parameter
                                    "lte": "now",
                                    "format": "strict_date_optional_time"
                                }
                            }
                        }
                    ]
                }
            }
        }

        # Send the request to Elasticsearch
        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False  # Disable SSL verification if using self-signed certificates
        )

        # Check if the request was successful
        response.raise_for_status()

        # Parse the response JSON
        data = response.json()
        techniques_buckets = data.get("aggregations", {}).get("3", {}).get("buckets", [])

        # Prepare results for the response
        results = []
        for technique_bucket in techniques_buckets:
            technique_name = technique_bucket["key"]
            technique_data = {
                "technique": technique_name,
                "histogram": []
            }

            # For each 30-minute interval, get the count of events for the technique
            for interval_bucket in technique_bucket.get("2", {}).get("buckets", []):
                technique_data["histogram"].append({
                    "timestamp": interval_bucket["key_as_string"],  # Timestamp of the 30-minute interval
                    "count": interval_bucket["doc_count"]  # Number of events in this interval
                })

            results.append(technique_data)

        return jsonify(results)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching top techniques: {e}"}), 500






@app.route("/api/peak-attack-periods", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_peak_attack_periods():
    """
    ดึงข้อมูลช่วงเวลาที่มีการโจมตีมากที่สุดใน 7 วัน
    """
    try:
        # Elasticsearch Query
        # ดึงข้อมูล User จาก JWT
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")

        
        query = {
            "aggs": {
                "2": {
                    "date_histogram": {
                        "field": "timestamp",
                        "fixed_interval": "1h",  # แบ่งข้อมูลตามช่วงเวลา 1 ชั่วโมง
                        "time_zone": "Asia/Bangkok",  # ใช้ timezone ของประเทศไทย
                        "min_doc_count": 1
                    }
                }
            },
            "size": 0,  # ไม่ดึงข้อมูล hits, ดึงเฉพาะ aggregation
            "query": {
                "bool": {
                    "filter": [
                        {"match_all": {}},
                        {
                            "range": {
                                "timestamp": {
                                    "gte": "now/d-7h",
                                    "lte": "now",
                                    "format": "strict_date_optional_time"
                                }
                            }
                        }
                    ]
                }
            }
        }

        # ส่งคำขอไปยัง Elasticsearch
        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False  # ปิด SSL verification (หากใช้ self-signed certificate)
        )

        # ตรวจสอบสถานะ HTTP
        response.raise_for_status()

        # ดึงข้อมูล JSON จาก Elasticsearch
        data = response.json()
        buckets = data.get("aggregations", {}).get("2", {}).get("buckets", [])

        # แปลงข้อมูลเพื่อเตรียมการตอบกลับ
        results = [{"timestamp": bucket["key_as_string"], "count": bucket["doc_count"]} for bucket in buckets]

        return jsonify(results)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching peak attack periods: {e}"}), 500




@app.route('/api/vulnerabilities', methods=['GET'])
@jwt_required()  # Require JWT authentication
def get_vulnerabilities():
    current_user = get_jwt_identity()
    print(f"Request made by: {current_user}")
    """
    ดึงข้อมูล vulnerability severity จาก Elasticsearch โดยใช้โครงสร้าง JSON Query ที่ระบุ
    """
    
    # Elasticsearch Query
    query = {
        "aggs": {
            "2": {
                "filters": {
                    "filters": {
                        "Critical": {
                            "bool": {
                                "must": [],
                                "filter": [
                                    {
                                        "bool": {
                                            "should": [
                                                {
                                                    "match_phrase": {
                                                        "vulnerability.severity": "Critical"
                                                    }
                                                }
                                            ],
                                            "minimum_should_match": 1
                                        }
                                    }
                                ],
                                "should": [],
                                "must_not": []
                            }
                        },
                        "High": {
                            "bool": {
                                "must": [],
                                "filter": [
                                    {
                                        "bool": {
                                            "should": [
                                                {
                                                    "match_phrase": {
                                                        "vulnerability.severity": "High"
                                                    }
                                                }
                                            ],
                                            "minimum_should_match": 1
                                        }
                                    }
                                ],
                                "should": [],
                                "must_not": []
                            }
                        },
                        "Medium": {
                            "bool": {
                                "must": [],
                                "filter": [
                                    {
                                        "bool": {
                                            "should": [
                                                {
                                                    "match_phrase": {
                                                        "vulnerability.severity": "Medium"
                                                    }
                                                }
                                            ],
                                            "minimum_should_match": 1
                                        }
                                    }
                                ],
                                "should": [],
                                "must_not": []
                            }
                        },
                        "Low": {
                            "bool": {
                                "must": [],
                                "filter": [
                                    {
                                        "bool": {
                                            "should": [
                                                {
                                                    "match_phrase": {
                                                        "vulnerability.severity": "Low"
                                                    }
                                                }
                                            ],
                                            "minimum_should_match": 1
                                        }
                                    }
                                ],
                                "should": [],
                                "must_not": []
                            }
                        }
                    }
                }
            }
        },
        "size": 0,
        "stored_fields": ["*"],
        "script_fields": {},
        "docvalue_fields": [
            {"field": "package.installed", "format": "date_time"},
            {"field": "vulnerability.detected_at", "format": "date_time"},
            {"field": "vulnerability.published_at", "format": "date_time"}
        ],
        "_source": {"excludes": []},
        "query": {
            "bool": {
                "must": [],
                "filter": [
                    {"match_all": {}},
                    {
                        "match_phrase": {
                            "wazuh.cluster.name": {"query": "wazuh"}
                        }
                    }
                ],
                "should": [],
                "must_not": []
            }
        }
    }

    try:
        # ส่งคำขอไปยัง Elasticsearch
        response = requests.post(
            ES_URL2,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False  # ปิดการตรวจสอบ SSL หากใช้ self-signed certificates
        )

        # ตรวจสอบสถานะ HTTP
        response.raise_for_status()

        # แปลงผลลัพธ์จาก Elasticsearch
        data = response.json()
        buckets = data.get("aggregations", {}).get("2", {}).get("buckets", {})

        # สร้างผลลัพธ์ที่ตอบกลับ
        results = [{"severity": key, "count": value["doc_count"]} for key, value in buckets.items()]
        return jsonify(results), 200

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error querying Elasticsearch: {e}"}), 500


@app.route("/api/latest_alert", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_latest_alert():
    try:
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")
        query = {
            "size": 1,
            "sort": [
                {
                    "@timestamp": {
                        "order": "desc"
                    }
                }
            ]
        }

        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False
        )

        response.raise_for_status()

        data = response.json()
        hits = data.get("hits", {}).get("hits", [])

        return jsonify(hits)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching latest alert: {e}"}), 500


@app.route("/api/mitre_alert", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_mitre_alert():
    try:
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")
        query = {
            "size": 1,
            "query": {
                "bool": {
                    "must": [
                        {
                            "exists": {
                                "field": "rule.mitre.id"
                            }
                        }
                    ]
                }
            },
            "sort": [
                {
                    "@timestamp": {
                        "order": "desc"
                    }
                }
            ]
        }

        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False
        )

        response.raise_for_status()

        data = response.json()
        hits = data.get("hits", {}).get("hits", [])

        return jsonify(hits)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching MITRE alert: {e}"}), 500

# Count log
@app.route("/api/mitre_techniques", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_mitre_techniques():
    try:
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")
        query = {
            "size": 0,
            "aggs": {
                "mitre_techniques": {
                    "terms": {
                        "field": "rule.mitre.technique",
                        "size": 20
                    }
                }
            }
        }

        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False
        )

        response.raise_for_status()

        data = response.json()
        aggregations = data.get("aggregations", {}).get("mitre_techniques", {}).get("buckets", [])

        # Return the aggregated data
        return jsonify(aggregations)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching MITRE techniques: {e}"}), 500




@app.route("/api/today-attacks", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_today_attacks():
    """
    ดึงข้อมูลการโจมตีของทุกประเทศที่เกิดขึ้นในวันนี้
    """
    try:
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")
        # Elasticsearch Query
        query = {
            "aggs": {
                "2": {
                    "terms": {
                        "field": "GeoLocation.country_name",
                        "order": {
                            "_count": "desc"
                        },
                        "size": 100  # ขยายขนาดเพื่อรวมทุกประเทศ
                    }
                }
            },
            "size": 0,
            "stored_fields": ["*"],
            "script_fields": {},
            "docvalue_fields": [
                {"field": "timestamp", "format": "date_time"}
            ],
            "_source": {"excludes": ["@timestamp"]},
            "query": {
                "bool": {
                    "must": [],
                    "filter": [
                        {"match_all": {}},
                        {
                            "range": {
                                "timestamp": {
                                    "gte": "now/d",  # เริ่มต้นวันนี้
                                    "lte": "now",   # จนถึงตอนนี้
                                    "format": "strict_date_optional_time"
                                }
                            }
                        }
                    ]
                }
            }
        }

        # ส่งคำขอไปยัง Elasticsearch
        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False
        )

        # ตรวจสอบสถานะ HTTP
        response.raise_for_status()

        # ดึงข้อมูล JSON จาก Elasticsearch
        data = response.json()
        buckets = data.get("aggregations", {}).get("2", {}).get("buckets", [])

        # แปลงข้อมูลสำหรับการตอบกลับ
        results = [{"country": bucket["key"], "count": bucket["doc_count"]} for bucket in buckets]

        return jsonify(results)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching today attacks: {e}"}), 500





@app.route("/api/today_mitre_techniques", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_mitre_techniques_today():
    try:
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")
        

        # Elasticsearch query with date range
        query = {
            "size": 0,
            "query": {
                "range": {
                    "@timestamp": {  # ปรับฟิลด์ให้ตรงกับที่ใช้ใน Elasticsearch
                        "gte": "now/d",  # เริ่มต้นวันนี้
                        "lte": "now", 
                        "format": "strict_date_optional_time"
                    }
                }
            },
            "aggs": {
                "mitre_techniques": {
                    "terms": {
                        "field": "rule.mitre.technique",
                        "size": 100
                    }
                }
            }
        }

        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False
        )

        response.raise_for_status()

        data = response.json()
        aggregations = data.get("aggregations", {}).get("mitre_techniques", {}).get("buckets", [])

        # Return the aggregated data
        return jsonify(aggregations)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching MITRE techniques: {e}"}), 500




@app.route("/api/top_rule_descriptions", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_top_rule_descriptions():
    try:
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")

        # Elasticsearch Query
        query = {
            "aggs": {
                "2": {
                    "terms": {
                        "field": "rule.description",
                        "order": {
                            "_count": "desc"
                        },
                        "size": 100  # ดึง 5 อันดับแรก
                    }
                }
            },
            "size": 0,
            "stored_fields": ["*"],
            "docvalue_fields": [
                {"field": "timestamp", "format": "date_time"}
            ],
            "_source": {
                "excludes": ["@timestamp"]
            },
            "query": {
                "bool": {
                    "filter": [
                        {"match_all": {}},
                        {
                            "range": {
                                "timestamp": {
                                    "gte": "now/d",  # เริ่มต้นวันนี้
                                    "lte": "now", 
                                    "format": "strict_date_optional_time"
                                }
                            }
                        }
                    ]
                }
            }
        }

        # ส่งคำขอไปยัง Elasticsearch
        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False  # ปิด SSL Verification หากจำเป็น
        )

        response.raise_for_status()

        # แยกผลลัพธ์จาก Elasticsearch
        data = response.json()
        buckets = data.get("aggregations", {}).get("2", {}).get("buckets", [])

        # จัดข้อมูลสำหรับการส่งกลับ
        top_descriptions = [
            {"rule_description": bucket["key"], "count": bucket["doc_count"]}
            for bucket in buckets
        ]

        return jsonify(top_descriptions)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching top rule descriptions: {e}"}), 500




if __name__ == "__main__":
    app.run(debug=True)
