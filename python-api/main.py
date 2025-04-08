from flask import Flask, jsonify, render_template, request
from instagrapi import Client
import threading, random, time, os
from pymongo import MongoClient
from datetime import datetime, timedelta

app = Flask(__name__)
cl = Client()
logs = []

# MongoDB setup
mongo_client = MongoClient("mongodb://localhost:27017/")
db = mongo_client["insta_bot"]
accounts_col = db["accounts"]
posts_col = db["posts"]
dms_col = db["dm_logs"]
followers_col = db["followers"]

# Folder for images to post
IMAGE_FOLDER = r"C:\Users\User\Pictures\insta"

# Welcome messages for DM
WELCOME_MESSAGES = [
    "Hey there! 👋",
    "Hello and welcome!",
    "Hi! Hope you're doing great!",
    "Greetings!",
    "Welcome aboard!",
    "Howdy!",
    "Nice to meet you!",
    "Yo! What's up?",
    "Hey! Great to connect!",
    "Warm wishes to you!"
]

# DM timing constraints
DM_INTERVAL_MIN = 10 * 60  # 10 minutes
DM_INTERVAL_MAX = 20 * 60  # 20 minutes
DAILY_DM_LIMIT = 30
SAME_USER_INTERVAL = 4 * 60 * 60  # 4 hours

# Log helper
def log_event(msg):
    print(msg)
    logs.append(msg)

# Check DM limits
def can_send_dm(to_user):
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)

    # Daily DM count
    count_today = dms_col.count_documents({
        "from_user": cl.username,
        "sent_at": {"$gte": today_start}
    })
    if count_today >= DAILY_DM_LIMIT:
        return False, "🚫 Daily DM limit reached. Please try again later."

    # Recent DM to same user
    recent_dm = dms_col.find_one({
        "from_user": cl.username,
        "to_user": to_user
    }, sort=[("sent_at", -1)])

    if recent_dm:
        last_sent = recent_dm["sent_at"]
        if (now - last_sent).total_seconds() < SAME_USER_INTERVAL:
            return False, f"⏳ You already messaged @{to_user} recently. Try again later."

    return True, None

# Instagram login with challenge handling
def login_instagram(username, password):
    try:
        cl.load_settings("settings.json")
        cl.login(username, password)
        log_event("✅ Logged in using saved session.")
    except:
        try:
            cl.login(username, password)
            cl.dump_settings("settings.json")
            log_event("✅ Fresh login successful.")
        except Exception as e:
            log_event("⚠️ Challenge required. Trying to resolve...")
            cl.challenge_resolve(cl.last_json)
            code = input("Enter the 6-digit code sent by Instagram: ")
            try:
                cl.challenge_code(code)
                cl.dump_settings("settings.json")
                log_event("✅ Challenge passed! Login complete.")
            except Exception as e:
                log_event(f"❌ Login failed: {str(e)}")

# Image posting function
def post_images_from_folder():
    try:
        files = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if not files:
            log_event("⚠️ No images found in folder.")
            return

        img_path = os.path.join(IMAGE_FOLDER, files[0])
        time.sleep(random.uniform(5, 10))
        cl.photo_upload(
            path=img_path,
            caption="#bekolatechnical #internship #projecthelp #finalyearproject #webdevelopment #mernstack #nodejs #reactjs #expressjs #mongodb #flutter #androiddevelopment #liveproject #itstudents #bca #mca #btech #csstudents #collegeproject #codinglife #developers #programmerslife #softwareengineering #dubaiit #malayalamdeveloper #keraladeveloper #projectsupport #hiredeveloper #ittraining #techstartup #campusdrive"
        )
        log_event(f"📸 Posted image: {files[0]}")

        posts_col.insert_one({
            "username": cl.username,
            "image_name": files[0],
            "posted_at": datetime.now(),
            "status": "Success"
        })

        os.remove(img_path)
        log_event(f"🗑️ Deleted image: {files[0]}")
    except Exception as e:
        log_event(f"❌ Error while posting image: {str(e)}")

# DM sending function (static target)
def send_dms_only():
    try:
        username = "i.badhran"
        can_send, msg = can_send_dm(username)
        if not can_send:
            log_event(msg)
            return

        user_id = cl.user_id_from_username(username)
        time.sleep(random.uniform(3, 6))
        message = random.choice(WELCOME_MESSAGES)
        cl.direct_send(text=message, user_ids=[user_id])
        log_event(f"📨 Sent DM to @{username}: '{message}'")

        dms_col.insert_one({
            "from_user": cl.username,
            "to_user": username,
            "message": message,
            "sent_at": datetime.now(),
            "status": "Sent"
        })
    except Exception as e:
        log_event(f"❌ Error with @{username}: {str(e)}")

# DM sending function (custom target)
@app.route('/send-dm', methods=['POST'])
def send_custom_dm():
    try:
        data = request.get_json()
        username = data.get("username", "").strip()
        if not username:
            return jsonify({"message": "⚠️ Username not provided."}), 400

        can_send, msg = can_send_dm(username)
        if not can_send:
            return jsonify({"message": msg}), 429

        user_id = cl.user_id_from_username(username)
        message = random.choice(WELCOME_MESSAGES)
        cl.direct_send(text=message, user_ids=[user_id])
        log_event(f"📨 Sent DM to @{username}: '{message}'")

        dms_col.insert_one({
            "from_user": cl.username,
            "to_user": username,
            "message": message,
            "sent_at": datetime.now(),
            "status": "Sent"
        })

        return jsonify({"message": f"✅ DM sent to @{username}!"})
    except Exception as e:
        log_event(f"❌ Error sending DM to @{username}: {str(e)}")
        return jsonify({"message": f"❌ Error sending DM: {str(e)}"}), 500

# Random user follower function
def follow_random_user():
    try:
        hashtags = ["life", "coding", "travel", "music", "art", "fitness", "developer", "fun", "startup", "design"]
        tag = random.choice(hashtags)
        users = cl.hashtag_medias_recent(tag, amount=30)
        random.shuffle(users)

        for media in users:
            user = media.user
            if not cl.user_following(user.pk):
                delay = random.uniform(900, 1200)
                log_event(f"⏳ Waiting {int(delay)} seconds (~{int(delay/60)} min) before next follow...")
                time.sleep(delay)
                cl.user_follow(user.pk)
                log_event(f"➕ Followed random user: @{user.username} from #{tag}")

                followers_col.insert_one({
                    "bot_user": cl.username,
                    "target_user": user.username,
                    "source_tag": tag,
                    "followed_at": datetime.now(),
                    "status": "Followed"
                })
                return

        log_event("⚠️ No suitable user found to follow.")
    except Exception as e:
        log_event(f"❌ Error while following random user: {str(e)}")

# Routes
@app.route('/')
def index():
    return render_template("index.html")

@app.route('/start-image-posting', methods=['POST'])
def start_image_posting():
    threading.Thread(target=post_images_from_folder).start()
    return jsonify({"message": "✅ Image posting started!"})

@app.route('/start', methods=['POST'])
def start_dm():
    threading.Thread(target=send_dms_only).start()
    return jsonify({"message": "✅ DM automation started!"})

@app.route('/follow-user', methods=['POST'])
def follow_user():
    threading.Thread(target=follow_random_user).start()
    return jsonify({"message": "✅ Follow random user task started!"})

@app.route('/logs')
def get_logs():
    return jsonify(logs)

if __name__ == '__main__':
    log_event("🚀 Flask server starting...")
    login_instagram("devang8836", "m6cA7kG!CX$xkG,")
    app.run(debug=True)
