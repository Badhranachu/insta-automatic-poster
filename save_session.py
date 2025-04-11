from instagrapi import Client

client = Client()

username = "devang8836"   # 🔁 Replace this
password = "m6cA7kG!CX$xkG,"   # 🔁 Replace this

client.login(username, password)
client.dump_settings("settings.json")

print("✅ Login successful and session saved to settings.json")
