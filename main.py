import os, requests
import telebot
from dotenv import load_dotenv
import yt_dlp
from ytmusicapi import YTMusic
import threading
import shutil  # Додано для очищення папки
from flask import Flask, request

load_dotenv()

TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)


@app.route('/' + TOKEN, methods=['POST'])
def get_message():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200

@app.route('/')
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url='https://music-bot-i71c.onrender.com/' + TOKEN)  # Replace with your Render app name!
    return "Webhook set!", 200


ytmusic = YTMusic()
DOWNLOAD_PATH = "downloads/"  # Папка для збереження пісень

# Функція для пошуку музики
def search_youtube_music(song_name):
    results = ytmusic.search(song_name, filter="songs")
    if results:
        video_id = results[0]["videoId"]
        return f"https://www.youtube.com/watch?v={video_id}"
    return None

# Функція для завантаження музики
def download_youtube_audio(url, song_name):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{DOWNLOAD_PATH}%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }]
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info).replace(".webm", ".mp3").replace(".m4a", ".mp3")
        return filename

# Видаляє всі старі файли перед новим запитом
def clear_download_folder():
    if os.path.exists(DOWNLOAD_PATH):
        shutil.rmtree(DOWNLOAD_PATH)  # Видалити всю папку
    os.makedirs(DOWNLOAD_PATH)  # Створити заново

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "👋 Надішли список пісень (кожна з нового рядка), і я скачаю їх!")

@bot.message_handler(func=lambda message: True)
def handle_song_request(message):
    song_names = message.text.strip().split("\n")
    total_songs = len(song_names)
    
    if total_songs > 1:
        bot.send_message(message.chat.id, f"🔍 Знайдено {total_songs} пісень. Починаю завантаження...")
    else:
        bot.send_message(message.chat.id, f"🔍 Шукаю '{song_names[0]}'...")

    # Очищаємо старі файли перед новим запитом
    clear_download_folder()

    # Запускаємо завантаження в окремому потоці
    threading.Thread(target=process_song_list, args=(song_names, message.chat.id)).start()

def process_song_list(song_names, chat_id):
    total_songs = len(song_names)
    downloaded_files = []
    
    for index, song_name in enumerate(song_names, start=1):
        song_name = song_name.strip()
        if not song_name:
            continue

        video_url = search_youtube_music(song_name)
        if video_url:
            bot.send_message(chat_id, f"📥 {index}/{total_songs} Завантажую: {song_name}...")
            file_path = download_youtube_audio(video_url, song_name)

            if os.path.exists(file_path):
                downloaded_files.append(file_path)
        else:
            bot.send_message(chat_id, f"❌ Не знайдено: {song_name}")

        # Оновлення загального прогресу
        progress = int((index / total_songs) * 100)
        bot.send_message(chat_id, f"📊 Загальний прогрес: {progress}%")

    if downloaded_files:
        bot.send_message(chat_id, "✅ Усі пісні завантажено! Надсилаю файли...")
        
        for file_path in downloaded_files:
            with open(file_path, "rb") as audio:
                bot.send_audio(chat_id, audio)
    else:
        bot.send_message(chat_id, "❌ Жодна пісня не була успішно завантажена.")

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=5000)