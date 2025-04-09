from flask import Flask, render_template, request, redirect, url_for
from instagrapi import Client
import threading, random, time, os, requests
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()
USERNAME = os.getenv("INSTA_USER")
PASSWORD = os.getenv("INSTA_PASS")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# Logging setup
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Globals
app = Flask(__name__)
cl = Client()
logs = []
next_story_info = ""
last_story_url = ""

# MongoDB setup
mongo_client = MongoClient("mongodb://localhost:27017/")
db = mongo_client["insta_bot"]
accounts_col = db["accounts"]
posts_col = db["posts"]
dms_col = db["dm_logs"]
followers_col = db["followers"]

# Folder for images
IMAGE_FOLDER = r"C:\\Users\\User\\Pictures\\insta"
os.makedirs('static', exist_ok=True)

# DM messages
WELCOME_MESSAGES = [
    "Hey there! 👋", "Hello and welcome!", "Hi! Hope you're doing great!",
    "Greetings!", "Welcome aboard!", "Howdy!", "Nice to meet you!",
    "Yo! What's up?", "Hey! Great to connect!", "Warm wishes to you!"
]

# Timing rules
DM_INTERVAL_MIN = 10 * 60
DM_INTERVAL_MAX = 20 * 60
DAILY_DM_LIMIT = 30
SAME_USER_INTERVAL = 4 * 60 * 60
POST_INTERVAL = 30 * 60
FOLLOW_INTERVAL = 15 * 60

ACCOUNT_CREATED_AT = datetime(2025, 4, 8)

# Utils
def log_event(msg):
    logging.info(msg)
    print(msg)
    logs.append(f"{datetime.now().strftime('%H:%M:%S')} - {msg}")

def humanize_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return ' '.join([f"{hrs}h" if hrs else "", f"{mins}m" if mins else "", f"{secs}s" if secs else ""]).strip()

def get_account_age_days():
    return (datetime.now() - ACCOUNT_CREATED_AT).days

def get_story_interval_seconds():
    age_days = get_account_age_days()
    if age_days <= 7:
        return random.randint(4 * 3600, 6 * 3600)
    elif age_days <= 30:
        return random.randint(2 * 3600, 4 * 3600)
    else:
        return random.randint(1 * 3600, 3 * 3600)

# Condition checkers
def can_send_dm(to_user):
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)
    count_today = dms_col.count_documents({"from_user": cl.username, "sent_at": {"$gte": today_start}})
    if count_today >= DAILY_DM_LIMIT:
        next_time = today_start + timedelta(days=1)
        return False, f"🚫 Daily limit reached. Try again after {next_time.strftime('%H:%M:%S')}"
    recent_dm = dms_col.find_one({"from_user": cl.username, "to_user": to_user}, sort=[("sent_at", -1)])
    if recent_dm:
        last_sent = recent_dm["sent_at"]
        next_time = last_sent + timedelta(seconds=SAME_USER_INTERVAL)
        if datetime.now() < next_time:
            wait_seconds = (next_time - datetime.now()).total_seconds()
            return False, f"⏳ Wait {humanize_time(wait_seconds)} to DM @{to_user} again."
    return True, None

def can_post_image():
    last_post = posts_col.find_one({"username": cl.username}, sort=[("posted_at", -1)])
    if last_post:
        next_time = last_post["posted_at"] + timedelta(seconds=POST_INTERVAL)
        if datetime.now() < next_time:
            wait = next_time - datetime.now()
            return False, f"⏳ Wait {humanize_time(wait.total_seconds())}. Next post at {next_time.strftime('%H:%M:%S')}"
    return True, None

def can_post_story():
    last_story = posts_col.find_one({"username": cl.username, "story": True}, sort=[("posted_at", -1)])
    interval = get_story_interval_seconds()
    if last_story:
        next_time = last_story["posted_at"] + timedelta(seconds=interval)
        if datetime.now() < next_time:
            wait = next_time - datetime.now()
            global next_story_info
            next_story_info = f"⏳ Wait {humanize_time(wait.total_seconds())}. Next story at {next_time.strftime('%H:%M:%S')}"
            return False, next_story_info
    return True, None

def can_follow_user():
    last_follow = followers_col.find_one({"bot_user": cl.username}, sort=[("followed_at", -1)])
    if last_follow:
        next_time = last_follow["followed_at"] + timedelta(seconds=FOLLOW_INTERVAL)
        if datetime.now() < next_time:
            wait = next_time - datetime.now()
            return False, f"⏳ Wait {humanize_time(wait.total_seconds())}. Next follow at {next_time.strftime('%H:%M:%S')}"
    return True, None

# Instagram Actions
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
            caption="#bekolatechnical ..."
        )
        log_event(f"📸 Posted image: {files[0]}")
        posts_col.insert_one({"username": cl.username, "image_name": files[0], "posted_at": datetime.now(), "status": "Success"})
        os.remove(img_path)
        log_event(f"🗑️ Deleted image: {files[0]}")
    except Exception as e:
        log_event(f"❌ Error while posting image: {str(e)}")

def download_random_image_under_1mb():
    global last_story_url
    try:
        headers = {"Authorization": PEXELS_API_KEY}
        search_query = random.choice([
            "nature", "technology", "city", "travel", "mountains", "food", "fitness", 
            "sunset", "abstract", "cars", "flowers", "fashion", "interior", 
            "wildlife", "people", "startup", "coffee", "motivation", "sky", "music"
        ])
        response = requests.get(f"https://api.pexels.com/v1/search?query={search_query}&per_page=15", headers=headers)
        if response.status_code != 200:
            log_event("❌ Failed to fetch from Pexels API")
            return None
        photos = response.json().get("photos", [])
        for photo in photos:
            img_url = photo['src']['medium']
            if img_url == last_story_url:
                continue
            img_data = requests.get(img_url).content
            if len(img_data) <= 1_000_000:
                filename = os.path.join('static', f'story_{int(time.time())}.jpg')
                with open(filename, 'wb') as f:
                    f.write(img_data)
                last_story_url = img_url
                log_event(f"✅ Image downloaded: {img_url}")
                return filename
        log_event("⚠️ No image under 1MB found.")
        return None
    except Exception as e:
        log_event(f"❌ Error downloading image: {str(e)}")
        return None


def post_story_from_pexels():
    allowed, msg = can_post_story()
    if not allowed:
        log_event(msg)
        return
    image_path = download_random_image_under_1mb()
    if not image_path:
        log_event("⚠️ No suitable image found.")
        return
    time.sleep(random.randint(5, 15))
    try:
        cl.photo_upload_to_story(path=image_path, caption="#bekolatechnical ...")
        log_event("📤 Story posted successfully!")
        posts_col.insert_one({"username": cl.username, "story": True, "posted_at": datetime.now()})
    except Exception as e:
        log_event(f"❌ Failed to post story: {str(e)}")

# Flask Routes
@app.route('/')
def index():
    try:
        files = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if files:
            src = os.path.join(IMAGE_FOLDER, files[0])
            dst = os.path.join('static', 'next.jpg')
            with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
                fdst.write(fsrc.read())
            log_event(f"🔍 Next image preview: {files[0]}")
            can_post_story()
            logs.append(next_story_info)
        else:
            log_event("⚠️ No image available for preview.")
    except Exception as e:
        log_event(f"⚠️ Could not copy image for preview: {e}")

    filtered_logs = []
    for log in reversed(logs):
        filtered_logs.append(log)
        if "Next story at" in log:
            break
    filtered_logs = list(reversed(filtered_logs))
    return render_template('index.html', logs=filtered_logs)

@app.route('/post-image', methods=['POST'])
def trigger_post():
    allowed, msg = can_post_image()
    if not allowed:
        log_event(msg)
        return redirect(url_for('index'))
    threading.Thread(target=post_images_from_folder).start()
    return redirect(url_for('index'))

@app.route('/post-story', methods=['POST'])
def trigger_story():
    threading.Thread(target=post_story_from_pexels).start()
    return redirect(url_for('index'))

@app.route('/send-dm', methods=['POST'])
def send_dm():
    username = request.form.get('username')
    allowed, msg = can_send_dm(username)
    if not allowed:
        log_event(msg)
        return redirect(url_for('index'))
    try:
        user_id = cl.user_id_from_username(username)
        message = random.choice(WELCOME_MESSAGES)
        cl.direct_send(message, [user_id])
        dms_col.insert_one({"from_user": cl.username, "to_user": username, "message": message, "sent_at": datetime.now()})
        log_event(f"✉️ Sent DM to @{username}")
    except Exception as e:
        log_event(f"❌ Failed to send DM to @{username}: {str(e)}")
    return redirect(url_for('index'))

@app.route('/follow-user', methods=['POST'])
def follow_user():
    username = request.form.get('username')
    allowed, msg = can_follow_user()
    if not allowed:
        log_event(msg)
        return redirect(url_for('index'))
    try:
        user_id = cl.user_id_from_username(username)
        cl.user_follow(user_id)
        followers_col.insert_one({"bot_user": cl.username, "target_user": username, "followed_at": datetime.now()})
        log_event(f"➕ Followed @{username}")
    except Exception as e:
        if "feedback_required" in str(e).lower() or "action_blocked" in str(e).lower():
            log_event(f"🚫 Instagram blocked follow action for @{username}: {e}")
        else:
            log_event(f"❌ Failed to follow @{username}: {e}")
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = 5000
    log_event(f"🚀 Flask server starting on http://localhost:{port}")
    login_instagram(USERNAME, PASSWORD)
    app.run(debug=True, port=port)
