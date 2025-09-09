import os
import re
import json
import requests
from flask import Flask, request
from telebot import TeleBot, types
from difflib import get_close_matches
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8476510332:AAFiPdMnGGHUVYDxsjD8UoN5_ycfF6BjPh0"
OMDB_KEY = "8d917eec"
OMDB_URL = "https://www.omdbapi.com/"

# Initialize bot and Flask app
bot = TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Movie genres and suggestions
MOVIE_SUGGESTIONS = {
    'funny': ['Hera Pheri', 'Golmaal', 'Andaz Apna Apna', 'Chupke Chupke', 'Padosan', 'Jaane Bhi Do Yaaro', 'Welcome', 'Hungama'],
    'hindi': ['Sholay', 'Dilwale Dulhania Le Jayenge', '3 Idiots', 'Zindagi Na Milegi Dobara', 'Queen', 'Dangal', 'Taare Zameen Par'],
    'horror': ['Tumhari Sulu', 'Stree', 'Bhool Bhulaiyaa', 'Raaz', '1920', 'Pari', 'Bulbbul', 'Roohi'],
    'action': ['Baahubali', 'KGF', 'Pushpa', 'RRR', 'War', 'Tiger Zinda Hai', 'Pathaan', 'Jawan'],
    'romance': ['Dilwale Dulhania Le Jayenge', 'Kuch Kuch Hota Hai', 'Kabhi Khushi Kabhie Gham', 'Yeh Jawaani Hai Deewani', 'Aashiqui 2'],
    'thriller': ['Andhadhun', 'Pink', 'Kahaani', 'Drishyam', 'Talaash', 'Badla', 'Article 15'],
    'drama': ['Taare Zameen Par', 'Dangal', 'Pink', 'Court', 'Masaan', 'October', 'Tumhari Sulu']
}

TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_CAPTION_LIMIT = 1024

def clean_movie_name(text):
    """Clean and extract movie name from user input"""
    # Remove common words and patterns
    text = re.sub(r'\b(movie|film|cinema|picture)\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(bollywood|hollywood)\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(latest|new|old|best)\b', '', text, flags=re.IGNORECASE)
    
    # Handle year patterns (2023 movie name or movie name 2023)
    year_match = re.search(r'\b(19|20)\d{2}\b', text)
    if year_match:
        year = year_match.group()
        text = re.sub(r'\b(19|20)\d{2}\b', '', text)
        text = text.strip()
        return text, year
    
    return text.strip(), None

def search_movie(query, year=None):
    """Search for movie using OMDB API"""
    try:
        params = {
            'apikey': OMDB_KEY,
            's': query,
            'type': 'movie'
        }
        if year:
            params['y'] = year
            
        response = requests.get(OMDB_URL, params=params, timeout=10)
        data = response.json()
        
        if data.get('Response') == 'True':
            return data.get('Search', [])
        return []
    except Exception as e:
        logger.error(f"Error searching movie: {e}")
        return []

def get_movie_details(imdb_id):
    """Get detailed movie information"""
    try:
        params = {
            'apikey': OMDB_KEY,
            'i': imdb_id,
            'plot': 'short'  # Changed from 'full' to 'short' to reduce message length
        }
        
        response = requests.get(OMDB_URL, params=params, timeout=10)
        data = response.json()
        
        if data.get('Response') == 'True':
            return data
        return None
    except Exception as e:
        logger.error(f"Error getting movie details: {e}")
        return None

def format_movie_info(movie):
    """Format movie information for display with Telegram limits"""
    title = movie.get('Title', 'N/A')
    year = movie.get('Year', 'N/A')
    genre = movie.get('Genre', 'N/A')
    director = movie.get('Director', 'N/A')
    actors = movie.get('Actors', 'N/A')
    plot = movie.get('Plot', 'N/A')
    rating = movie.get('imdbRating', 'N/A')
    runtime = movie.get('Runtime', 'N/A')
    language = movie.get('Language', 'N/A')
    
    # Truncate long fields to fit within limits
    if len(actors) > 100:
        actors = actors[:97] + "..."
    if len(plot) > 300:
        plot = plot[:297] + "..."
    if len(director) > 50:
        director = director[:47] + "..."
    
    message = f"🎬 *{title}* ({year})\n\n"
    message += f"🎭 *Genre:* {genre}\n"
    message += f"🎯 *IMDB:* {rating}/10\n"
    message += f"⏱️ *Runtime:* {runtime}\n"
    message += f"🎪 *Director:* {director}\n"
    message += f"🌟 *Cast:* {actors}\n"
    message += f"🗣️ *Language:* {language}\n\n"
    message += f"📖 *Plot:*\n{plot}\n\n"
    message += "━━━━━━━━━━━━━━━━━━━━\n"
    message += "🎭 *Powered by* [Tigertheater](https://t.me/+Tbkw7GQzcB05M2U9)"
    
    # Ensure message is within Telegram limits
    if len(message) > TELEGRAM_MESSAGE_LIMIT:
        # Create shorter version
        message = f"🎬 *{title}* ({year})\n\n"
        message += f"🎭 *Genre:* {genre}\n"
        message += f"🎯 *IMDB:* {rating}/10\n"
        message += f"⏱️ *Runtime:* {runtime}\n"
        message += f"🎪 *Director:* {director}\n\n"
        message += f"📖 *Plot:*\n{plot}\n\n"
        message += "🎭 *Powered by* [Tigertheater](https://t.me/+Tbkw7GQzcB05M2U9)"
    
    return message, movie.get('Poster', None)

def send_safe_message(chat_id, text, parse_mode='Markdown', disable_web_page_preview=True):
    """Send message safely within Telegram limits"""
    if len(text) <= TELEGRAM_MESSAGE_LIMIT:
        bot.send_message(chat_id, text, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)
    else:
        # Split message into chunks
        chunks = []
        current_chunk = ""
        
        for line in text.split('\n'):
            if len(current_chunk + line + '\n') <= TELEGRAM_MESSAGE_LIMIT:
                current_chunk += line + '\n'
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line + '\n'
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        for chunk in chunks:
            bot.send_message(chat_id, chunk, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)

def create_inline_keyboard(movies):
    """Create inline keyboard for movie suggestions"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    for movie in movies[:10]:  # Limit to 10 suggestions
        title = movie.get('Title', 'Unknown')
        year = movie.get('Year', 'N/A')
        imdb_id = movie.get('imdbID', '')
        
        button_text = f"{title} ({year})"
        if len(button_text) > 64:
            button_text = button_text[:61] + "..."
        
        callback_data = f"movie_{imdb_id}"
        keyboard.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
    
    return keyboard

def get_genre_suggestions(genre_query):
    """Get movie suggestions based on genre"""
    genre_query = genre_query.lower()
    suggestions = []
    
    # Find matching genres
    for genre, movies in MOVIE_SUGGESTIONS.items():
        if genre in genre_query:
            suggestions.extend(movies)
    
    # If no specific genre found, check for keywords
    if not suggestions:
        if any(word in genre_query for word in ['funny', 'comedy', 'hasna', 'mazak']):
            suggestions = MOVIE_SUGGESTIONS['funny']
        elif any(word in genre_query for word in ['horror', 'scary', 'dar', 'bhoot']):
            suggestions = MOVIE_SUGGESTIONS['horror']
        elif any(word in genre_query for word in ['action', 'fight', 'jung']):
            suggestions = MOVIE_SUGGESTIONS['action']
        elif any(word in genre_query for word in ['romance', 'love', 'pyar', 'ishq']):
            suggestions = MOVIE_SUGGESTIONS['romance']
        elif any(word in genre_query for word in ['thriller', 'suspense']):
            suggestions = MOVIE_SUGGESTIONS['thriller']
        else:
            suggestions = MOVIE_SUGGESTIONS['hindi']  # Default to Hindi movies
    
    return suggestions[:8]  # Return top 8 suggestions

@bot.message_handler(commands=['start'])
def start_command(message):
    welcome_text = """
🎬 *Welcome to Movie Info Bot!* 🎭

I can help you with:
• 🔍 Get movie information - just send me a movie name
• 🎯 Movie suggestions by genre
• 📱 Smart search with spelling correction

*How to use:*
• Send movie name: `Sholay` or `2023 Animal movie`
• Ask for suggestions: `suggest funny hindi movies`
• Get genre recommendations: `horror movies`

🎭 *Powered by* [Tigertheater](https://t.me/+Tbkw7GQzcB05M2U9)
    """
    send_safe_message(message.chat.id, welcome_text)

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """
🎬 *Movie Bot Help* 🎭

*Commands:*
• Just send a movie name to get info
• `suggest [genre] movies` - Get movie suggestions
• `/start` - Welcome message
• `/help` - This help message

*Examples:*
• `Sholay`
• `Animal 2023 movie`
• `suggest funny hindi movies`
• `horror movie suggestions`
• `best action movies`

🎭 *Powered by* [Tigertheater](https://t.me/+Tbkw7GQzcB05M2U9)
    """
    send_safe_message(message.chat.id, help_text)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_input = message.text.strip()
    
    # Check if user is asking for suggestions
    if any(word in user_input.lower() for word in ['suggest', 'recommendation', 'recommend', 'batao', 'bolo']):
        suggestions = get_genre_suggestions(user_input)
        
        if suggestions:
            suggestion_text = "🎬 *Movie Suggestions:*\n\n"
            for i, movie in enumerate(suggestions, 1):
                suggestion_text += f"{i}. {movie}\n"
            
            suggestion_text += "\n━━━━━━━━━━━━━━━━━━━━\n"
            suggestion_text += "💡 *Tip:* Send any movie name to get detailed info!\n"
            suggestion_text += "🎭 *Powered by* [Tigertheater](https://t.me/+Tbkw7GQzcB05M2U9)"
            
            send_safe_message(message.chat.id, suggestion_text)
        else:
            bot.reply_to(message, "🤔 Sorry, I couldn't understand the genre. Try: 'suggest funny hindi movies'")
        return
    
    # Clean the movie name and search
    cleaned_name, year = clean_movie_name(user_input)
    
    if len(cleaned_name) < 2:
        bot.reply_to(message, "🤔 Please send a valid movie name!")
        return
    
    # Search for movies
    bot.send_chat_action(message.chat.id, 'typing')
    movies = search_movie(cleaned_name, year)
    
    if not movies:
        # Try with spelling correction
        all_movie_names = []
        for genre_movies in MOVIE_SUGGESTIONS.values():
            all_movie_names.extend(genre_movies)
        
        close_matches = get_close_matches(cleaned_name, all_movie_names, n=3, cutoff=0.6)
        
        if close_matches:
            suggestion_text = f"🤔 No exact match found for '*{cleaned_name}*'\n\n"
            suggestion_text += "Did you mean:\n"
            for match in close_matches:
                suggestion_text += f"• {match}\n"
            suggestion_text += "\n🎭 *Powered by* [Tigertheater](https://t.me/+Tbkw7GQzcB05M2U9)"
            send_safe_message(message.chat.id, suggestion_text)
        else:
            bot.reply_to(message, f"😔 Sorry, couldn't find any movie matching '*{cleaned_name}*'\n\n🎭 *Powered by* [Tigertheater](https://t.me/+Tbkw7GQzcB05M2U9)", parse_mode='Markdown', disable_web_page_preview=True)
        return
    
    # If exact match found, show details directly
    if len(movies) == 1 or movies[0]['Title'].lower() == cleaned_name.lower():
        movie_details = get_movie_details(movies[0]['imdbID'])
        if movie_details:
            formatted_info, poster = format_movie_info(movie_details)
            
            if poster and poster != "N/A":
                # Create short caption for photo
                short_caption = f"🎬 {movie_details.get('Title', 'N/A')} ({movie_details.get('Year', 'N/A')})\n⭐ IMDB: {movie_details.get('imdbRating', 'N/A')}/10"
                if len(short_caption) > TELEGRAM_CAPTION_LIMIT:
                    short_caption = short_caption[:TELEGRAM_CAPTION_LIMIT-3] + "..."
                
                bot.send_photo(message.chat.id, poster, caption=short_caption, parse_mode='Markdown')
                # Send full info as separate message
                send_safe_message(message.chat.id, formatted_info)
            else:
                send_safe_message(message.chat.id, formatted_info)
        else:
            bot.reply_to(message, "😔 Sorry, couldn't fetch movie details right now.")
    else:
        # Show multiple options
        keyboard = create_inline_keyboard(movies)
        bot.reply_to(message, f"🎬 Found multiple movies for '*{cleaned_name}*'. Please select:", 
                    reply_markup=keyboard, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('movie_'))
def handle_movie_selection(call):
    imdb_id = call.data.replace('movie_', '')
    bot.send_chat_action(call.message.chat.id, 'typing')
    movie_details = get_movie_details(imdb_id)

    if movie_details:
        formatted_info, poster = format_movie_info(movie_details)

        # Short caption for poster
        short_caption = f"🎬 {movie_details.get('Title', 'N/A')} ({movie_details.get('Year', 'N/A')})\n⭐ IMDB: {movie_details.get('imdbRating', 'N/A')}/10"
        if len(short_caption) > TELEGRAM_CAPTION_LIMIT:
            short_caption = short_caption[:TELEGRAM_CAPTION_LIMIT-3] + "..."

        # Send poster with short caption
        if poster and poster != "N/A":
            bot.send_photo(call.message.chat.id, poster, caption=short_caption, parse_mode='Markdown')
        else:
            bot.send_message(call.message.chat.id, short_caption, parse_mode='Markdown')

        # Send full info safely
        send_safe_message(call.message.chat.id, formatted_info)
    else:
        bot.answer_callback_query(call.id, "😔 Sorry, couldn't fetch movie details.")

# Flask webhook setup
@app.route('/', methods=['GET'])
def index():
    return "🎬 Telegram Movie Bot is running! 🎭"

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'Bad Request', 400

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    webhook_url = request.args.get('url')
    if webhook_url:
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url + '/webhook')
        return f"Webhook set to {webhook_url}/webhook"
    return "Please provide webhook URL as ?url=your_webhook_url"

if __name__ == '__main__':
    # Check if running in production (web service mode)
    if os.getenv('FLASK_ENV') == 'production' or os.getenv('PORT'):
        # Production mode - run Flask app for web service
        print("🎬 Starting Telegram Movie Bot in web service mode...")
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port)
    else:
        # Development mode - use polling
        bot.remove_webhook()
        print("🎬 Starting Telegram Movie Bot in development mode...")
        print("Bot is running in polling mode...")
        bot.polling(none_stop=True)
