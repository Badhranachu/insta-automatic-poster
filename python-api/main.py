from flask import Flask, jsonify, render_template
from instagrapi import Client
import os

app = Flask(__name__)
image_folder = r'C:\Users\User\Pictures\insta'  # Make sure this path is correct

# Caption with hashtags
caption = (
    "#home #homedecor #interiordesign #homevibes #simpleliving #lifestyle #minimalist "
    "#calmhome #homelife #dailyinspo #plantsmakepeoplehappy #indoorplants #greenthumb "
    "#plantlover #plantdecor #urbanjungle #bohohome #natureathome #eco_home #sustainableliving "
    "#aesthetic #inspirationdaily #slowliving #softaesthetic #naturalvibes #neutraltones "
)

# Login to Instagram
cl = Client()
cl.login("_test.123_7778_", "test12345678")  # Replace with secure method in production

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/post-image', methods=['POST'])
def post_image():
    files = os.listdir(image_folder)
    images_or_videos = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4'))]

    if not images_or_videos:
        return jsonify({"message": "❌ No more images or videos to post."})

    file_to_post = os.path.join(image_folder, images_or_videos[0])

    try:
        print(f"Posting: {file_to_post}")
        print(f"Caption: {caption}")

        if file_to_post.lower().endswith('.mp4'):
            cl.video_upload(file_to_post, caption=caption)
        else:
            cl.photo_upload(file_to_post, caption=caption)

        os.remove(file_to_post)
        return jsonify({"message": f"✅ Posted: {images_or_videos[0]}"})

    except Exception as e:
        print("Error:", e)
        return jsonify({"message": f"❌ Error: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
