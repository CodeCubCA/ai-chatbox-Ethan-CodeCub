import streamlit as st
import os
import re
import sys
import requests
import base64
from io import StringIO, BytesIO
from functools import partial
from dotenv import load_dotenv
from PIL import Image
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import google.generativeai as genai
from audio_recorder_streamlit import audio_recorder
import speech_recognition as sr
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from huggingface_hub import InferenceClient
import random

# Set page configuration FIRST - must be before any other Streamlit commands
st.set_page_config(
    page_title="ethel-chat",
    page_icon="🧑‍💻",
    layout="centered"
)

# Initialize session state IMMEDIATELY after page config
if "theme" not in st.session_state:
    st.session_state.theme = "Rainbow"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "personality" not in st.session_state:
    st.session_state.personality = "Friendly"
if "language" not in st.session_state:
    st.session_state.language = "English"
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "signed_in" not in st.session_state:
    st.session_state.signed_in = False
if "show_help" not in st.session_state:
    st.session_state.show_help = False
if "profile_photo" not in st.session_state:
    st.session_state.profile_photo = None
if "ai_avatar" not in st.session_state:
    st.session_state.ai_avatar = None
if "page_icon" not in st.session_state:
    st.session_state.page_icon = "💬"
if "uploaded_images" not in st.session_state:
    st.session_state.uploaded_images = []
if "job" not in st.session_state:
    st.session_state.job = "Just chat"
if "auto_play_tts" not in st.session_state:
    st.session_state.auto_play_tts = False
if "selected_voice" not in st.session_state:
    st.session_state.selected_voice = "Joanna"
if "tts_audio" not in st.session_state:
    st.session_state.tts_audio = {}
if "last_audio" not in st.session_state:
    st.session_state.last_audio = None
if "image_generator_mode" not in st.session_state:
    st.session_state.image_generator_mode = False

# Web search function with caching
@st.cache_data(ttl=3600)  # Cache for 1 hour
def web_search(query, num_results=3):
    """Search the web and return results"""
    try:
        # Use DuckDuckGo's HTML search (no API key needed)
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=5)  # Reduced timeout

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []

            for result in soup.find_all('div', class_='result')[:num_results]:
                title_elem = result.find('a', class_='result__a')
                snippet_elem = result.find('a', class_='result__snippet')

                if title_elem:
                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href', '')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    results.append({
                        'title': title,
                        'link': link,
                        'snippet': snippet
                    })

            return results
        return []
    except Exception as e:
        return [{"error": str(e)}]

# Fetch webpage content with caching
@st.cache_data(ttl=1800)  # Cache for 30 minutes
def fetch_webpage(url):
    """Fetch and extract text from a webpage"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=5)  # Reduced timeout

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)

            return text[:5000]  # Limit to 5000 characters
        return "Could not fetch webpage"
    except Exception as e:
        return f"Error fetching webpage: {str(e)}"

# Convert image to base64 for vision API
def image_to_base64(image_file):
    """Convert uploaded image to base64 string"""
    try:
        # Read the image file
        image_file.seek(0)
        image_bytes = image_file.read()
        # Convert to base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        return base64_image
    except Exception as e:
        st.error(f"Error converting image: {str(e)}")
        return None

# Convert image to text representation with pixel data
def image_to_text_representation(image_file):
    """Convert image to detailed text representation with enhanced recognition"""
    try:
        # Read and open image
        image_file.seek(0)
        img = Image.open(image_file)

        # Resize for processing - using 64x64 for much better detail (4096 pixels)
        # Higher resolution = better recognition accuracy
        img_small = img.resize((64, 64), Image.Resampling.LANCZOS)

        # Convert to RGB if necessary
        if img_small.mode != 'RGB':
            img_small = img_small.convert('RGB')

        # Get image metadata
        width, height = img.size
        format_type = img.format if img.format else "Unknown"

        # Build enhanced text representation
        text_rep = f"\n[IMAGE ANALYSIS START]\n"
        text_rep += f"Original Size: {width}x{height} pixels\n"
        text_rep += f"Format: {format_type}\n"
        text_rep += f"Analyzed at: 64x64 resolution (4096 pixels)\n\n"

        # Use compact hexadecimal representation to save tokens
        text_rep += "PIXEL GRID (Hex RGB format for high accuracy):\n"
        text_rep += "Format: Each row is 64 pixels, each pixel as RRGGBB hex\n\n"

        pixels = img_small.load()
        for y in range(64):
            row_data = []
            for x in range(64):
                r, g, b = pixels[x, y]
                # Convert to compact hex format (e.g., FF00AA instead of (255,0,170))
                row_data.append(f"{r:02X}{g:02X}{b:02X}")
            text_rep += " ".join(row_data) + "\n"

        # Add color analysis
        text_rep += "\n[COLOR ANALYSIS]\n"
        # Get average color
        img_array = list(img_small.getdata())
        avg_r = sum(p[0] for p in img_array) // len(img_array)
        avg_g = sum(p[1] for p in img_array) // len(img_array)
        avg_b = sum(p[2] for p in img_array) // len(img_array)
        text_rep += f"Average Color: RGB({avg_r}, {avg_g}, {avg_b})\n"

        # Detect dominant colors
        if avg_r > avg_g and avg_r > avg_b:
            dominant = "Red tones"
        elif avg_g > avg_r and avg_g > avg_b:
            dominant = "Green tones"
        elif avg_b > avg_r and avg_b > avg_g:
            dominant = "Blue tones"
        else:
            dominant = "Neutral/Gray tones"
        text_rep += f"Dominant Color: {dominant}\n"

        # Brightness analysis
        brightness = (avg_r + avg_g + avg_b) // 3
        if brightness > 200:
            brightness_level = "Very Bright"
        elif brightness > 150:
            brightness_level = "Bright"
        elif brightness > 100:
            brightness_level = "Medium"
        elif brightness > 50:
            brightness_level = "Dark"
        else:
            brightness_level = "Very Dark"
        text_rep += f"Brightness: {brightness_level} (avg: {brightness}/255)\n"

        # Add edge detection analysis for better object recognition
        text_rep += "\n[EDGE DETECTION]\n"
        edges_detected = []
        for y in range(1, 63):  # Skip first and last row
            for x in range(1, 63):  # Skip first and last column
                # Simple edge detection: check brightness difference with neighbors
                curr = sum(pixels[x, y]) // 3
                right = sum(pixels[x + 1, y]) // 3
                down = sum(pixels[x, y + 1]) // 3

                # If significant brightness difference, mark as edge
                if abs(curr - right) > 30 or abs(curr - down) > 30:
                    edges_detected.append((x, y))

        text_rep += f"Edges Detected: {len(edges_detected)} edge points (indicates object boundaries)\n"

        # Analyze edge distribution
        if edges_detected:
            avg_edge_x = sum(e[0] for e in edges_detected) / len(edges_detected)
            avg_edge_y = sum(e[1] for e in edges_detected) / len(edges_detected)
            text_rep += f"Edge Center: ({avg_edge_x:.1f}, {avg_edge_y:.1f}) - main object location\n"

        text_rep += "\n[IMAGE ANALYSIS END]\n"
        text_rep += "\n=== CRITICAL ANALYSIS INSTRUCTIONS ===\n"
        text_rep += "You are analyzing a 64x64 pixel grid (4096 pixels total) in hexadecimal RGB format.\n"
        text_rep += "Each 6-character code is one pixel (RRGGBB hex). Example: FFFFFF=white, 000000=black.\n\n"
        text_rep += "IMPORTANT: Carefully examine the ENTIRE pixel grid pattern to identify:\n"
        text_rep += "1. ANIMALS: Look for fur textures, body shapes, faces, eyes, ears, tails\n"
        text_rep += "   - Light beige/cream (F5E5D0-FFFAF0) = light colored fur (dogs, cats)\n"
        text_rep += "   - Dark patterns around center = eyes, nose, facial features\n"
        text_rep += "2. PEOPLE: Skin tones, clothing, hair, facial features, body poses\n"
        text_rep += "3. OBJECTS: Shapes, textures, consistent color patterns\n"
        text_rep += "4. BACKGROUNDS: Green tones = grass/nature, Blue = sky/water, etc.\n"
        text_rep += "5. EDGE PATTERNS: High edge density = detailed objects with defined shapes\n\n"
        text_rep += "DO NOT guess based only on color! Analyze the SHAPE and PATTERN in the pixel grid.\n"
        text_rep += "The pixel data contains the actual visual structure - decode it carefully!\n"

        return text_rep
    except Exception as e:
        return f"\n[ERROR: Could not process image - {str(e)}]\n"

# Email validation function
def is_valid_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# Password validation function
def is_valid_password(password):
    """Validate password: at least 8 characters, 1 uppercase, 1 lowercase, 1 number"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least 1 uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least 1 lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least 1 number"
    return True, "Password is valid"

def generate_tts_audio(text, message_index):
    """Generate TTS audio for a message using AWS Polly and cache it in session state"""
    if not polly_client:
        return None

    # Check if audio already exists in cache
    if message_index in st.session_state.tts_audio:
        return st.session_state.tts_audio[message_index]

    try:
        # Limit text length to avoid very long audio files
        if len(text) > 1500:
            text = text[:1500] + "..."

        # Get selected voice from session state
        voice_id = st.session_state.get('selected_voice', 'Joanna')

        # Generate speech using AWS Polly
        response = polly_client.synthesize_speech(
            Text=text,
            Engine='standard',
            VoiceId=voice_id,
            OutputFormat='mp3',
            LanguageCode='en-US'
        )

        # Read audio stream directly
        if 'AudioStream' in response:
            audio_bytes = response['AudioStream'].read()

            # Cache the audio
            st.session_state.tts_audio[message_index] = audio_bytes

            return audio_bytes
        else:
            return None

    except (BotoCoreError, ClientError) as e:
        return None
    except Exception as e:
        return None

# Load environment variables
load_dotenv()

# Initialize Gemini client with caching
@st.cache_resource
def get_gemini_client():
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    return genai.GenerativeModel('gemini-2.5-flash')

client = get_gemini_client()

# Configure AWS Polly client for text-to-speech
@st.cache_resource
def get_polly_client():
    return boto3.client(
        'polly',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION", "us-east-1")
    )

try:
    polly_client = get_polly_client()
    # Test if credentials work
    if polly_client and os.getenv("AWS_ACCESS_KEY_ID"):
        polly_client = polly_client
    else:
        polly_client = None
except Exception as e:
    polly_client = None
    print(f"AWS Polly error: {e}")

# Configure HuggingFace client for image generation
@st.cache_resource
def get_hf_client():
    token = os.getenv("HUGGINGFACE_TOKEN")
    if token:
        return InferenceClient(token=token)
    return None

hf_client = get_hf_client()
IMAGE_MODEL = "black-forest-labs/FLUX.1-schnell"

# Define gradient themes
themes = {
    "Rainbow": "linear-gradient(135deg, #667eea 0%, #764ba2 15%, #f093fb 30%, #4facfe 45%, #00f2fe 60%, #43e97b 75%, #fa709a 90%, #fee140 100%)",
    "Ocean": "linear-gradient(135deg, #667eea 0%, #764ba2 25%, #f5576c 50%, #4facfe 75%, #00f2fe 100%)",
    "Sunset": "linear-gradient(135deg, #fa709a 0%, #fee140 25%, #fa8c16 50%, #ff6b6b 75%, #ee5a6f 100%)",
    "Forest": "linear-gradient(135deg, #43e97b 0%, #38f9d7 25%, #4facfe 50%, #667eea 75%, #764ba2 100%)",
    "Purple Dream": "linear-gradient(135deg, #a8edea 0%, #fed6e3 25%, #d299c2 50%, #c471ed 75%, #764ba2 100%)",
    "Fire": "linear-gradient(135deg, #ff0844 0%, #ffb199 25%, #ff6b6b 50%, #ee5a6f 75%, #c44569 100%)",
    "Cool Blue": "linear-gradient(135deg, #30cfd0 0%, #330867 25%, #667eea 50%, #4facfe 75%, #00f2fe 100%)",
    "Neon": "linear-gradient(135deg, #fa8bff 0%, #2bd2ff 20%, #2bff88 40%, #f8ff2b 60%, #ff6b2b 80%, #fa2bff 100%)"
}

# Apply selected theme
selected_gradient = themes.get(st.session_state.theme, themes["Rainbow"])

# CSS styling with theme using .format() to avoid Pylance false positives
css_style = """
<style>
    /* Cool static gradient background */
    .stApp {{
        background: {gradient};
        background-attachment: fixed;
    }}

    /* Make cards semi-transparent with glass effect */
    .stChatMessage {{
        background-color: rgba(255, 255, 255, 0.85) !important;
        backdrop-filter: blur(15px);
        border-radius: 20px;
        padding: 20px;
        margin: 15px 0;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.3);
    }}

    /* Rainbow gradient sidebar */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg,
            rgba(255, 36, 0, 0.7) 0%,
            rgba(232, 29, 29, 0.7) 14%,
            rgba(232, 183, 29, 0.7) 28%,
            rgba(227, 232, 29, 0.7) 42%,
            rgba(29, 232, 64, 0.7) 56%,
            rgba(29, 221, 232, 0.7) 70%,
            rgba(43, 29, 232, 0.7) 84%,
            rgba(221, 0, 243, 0.7) 100%);
        backdrop-filter: blur(15px);
    }}

    /* Glowing input box */
    .stChatInputContainer {{
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.15), rgba(255, 255, 255, 0.05));
        backdrop-filter: blur(10px);
        border-radius: 30px;
        border: 2px solid rgba(255, 255, 255, 0.3);
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
    }}

    /* Make buttons glow */
    .stButton>button {{
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.2), rgba(255, 255, 255, 0.1));
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 15px;
        color: white;
        font-weight: bold;
        text-shadow: 0 0 10px rgba(0, 0, 0, 0.5);
        transition: all 0.3s ease;
    }}

    .stButton>button:hover {{
        transform: scale(1.05);
        box-shadow: 0 0 20px rgba(255, 255, 255, 0.5);
    }}
</style>
""".format(gradient=selected_gradient)

st.markdown(css_style, unsafe_allow_html=True)

# Session state already initialized at the top of the file

# Language instruction templates and UI translations
language_instructions = {
    "English": "Respond in English.",
    "中文 (Chinese)": "用中文回复。",
    "Español (Spanish)": "Responde en español.",
    "Français (French)": "Répondez en français.",
    "Deutsch (German)": "Antworte auf Deutsch.",
    "日本語 (Japanese)": "日本語で返信してください。",
    "한국어 (Korean)": "한국어로 답변해주세요.",
    "Português (Portuguese)": "Responda em português.",
    "Русский (Russian)": "Отвечайте на русском языке.",
    "العربية (Arabic)": "أجب بالعربية."
}

# UI translations for all languages
ui_translations = {
    "English": {
        "title": "💬 {name}'s {job}",
        "title_default": "💬 {job}",
        "caption": "Your versatile AI assistant - talk about literally anything",
        "enter_name": "Enter your name:",
        "name_placeholder": "Your name",
        "enter_email": "Enter your email:",
        "email_placeholder": "your.email@example.com",
        "enter_password": "Enter your password:",
        "password_placeholder": "Password",
        "signin_title": "🔐 Sign In",
        "signin_welcome": "Welcome! Please create your account to continue",
        "signin_button": "Sign In",
        "signout_button": "Sign Out",
        "error_all_fields": "Please fill in all fields",
        "error_invalid_email": "Invalid email format",
        "error_password_length": "Password must be at least 8 characters",
        "error_password_uppercase": "Password must contain at least 1 uppercase letter",
        "error_password_lowercase": "Password must contain at least 1 lowercase letter",
        "error_password_number": "Password must contain at least 1 number",
        "password_requirements": "Password must be at least 8 characters with 1 uppercase, 1 lowercase, and 1 number",
        "welcome": "👋 Welcome! I'm your Everything AI Assistant. I can discuss any topic with you: learning, work, life, entertainment, technology, arts, and more. Whatever you want to chat about, I'm here to help!",
        "settings": "⚙️ Settings",
        "language": "🌐 Language",
        "choose_language": "Choose response language:",
        "language_changed": "Language changed to",
        "personality": "🎭 AI Personality",
        "choose_personality": "Choose AI's reply style:",
        "switched_to": "Switched to",
        "mode": "mode!",
        "clear_chat": "🗑️ Clear Chat History",
        "current_config": "📊 Current Config",
        "model": "Model",
        "messages": "Messages",
        "how_to_use": "📖 How to Use",
        "instructions": """
        1. 💬 Type your question in the input box
        2. 🌐 Select your preferred language
        3. 🎭 Select AI personality style
        4. 🤖 AI will reply in real-time
        5. 🗑️ Click "Clear Chat History" to restart
        6. ✨ Discuss any topic you want
        """,
        "input_placeholder": "Type your message here...",
        "error": "Error:",
        "check_api": "Please check if your API key is configured correctly.",
        "run_code": "▶️ Run Code",
        "code_result": "📟 Code Execution Result",
        "output": "✅ Output:",
        "error_label": "❌ Error:",
        "friendly": "Friendly",
        "professional": "Professional",
        "humorous": "Humorous"
    },
    "中文 (Chinese)": {
        "title": "💬 {name} 的万能 AI 伙伴",
        "title_default": "💬 我的万能 AI 伙伴",
        "caption": "您的多功能 AI 助手 - 无所不谈",
        "enter_name": "输入您的名字：",
        "name_placeholder": "您的名字",
        "enter_email": "输入您的邮箱：",
        "email_placeholder": "your.email@example.com",
        "enter_password": "输入您的密码：",
        "password_placeholder": "密码",
        "signin_title": "🔐 登录",
        "signin_welcome": "欢迎！请创建您的账户以继续",
        "signin_button": "登录",
        "signout_button": "退出登录",
        "error_all_fields": "请填写所有字段",
        "error_invalid_email": "邮箱格式无效",
        "error_password_length": "密码至少需要8个字符",
        "error_password_uppercase": "密码必须包含至少1个大写字母",
        "error_password_lowercase": "密码必须包含至少1个小写字母",
        "error_password_number": "密码必须包含至少1个数字",
        "password_requirements": "密码必须至少8个字符，包含1个大写字母、1个小写字母和1个数字",
        "welcome": "👋 欢迎！我是您的万能 AI 助手。我可以和您讨论任何话题：学习、工作、生活、娱乐、科技、艺术等等。无论您想聊什么，我都乐意奉陪！",
        "settings": "⚙️ 设置",
        "language": "🌐 语言",
        "choose_language": "选择回复语言：",
        "language_changed": "语言已更改为",
        "personality": "🎭 AI 人格",
        "choose_personality": "选择 AI 回复风格：",
        "switched_to": "已切换到",
        "mode": "模式！",
        "clear_chat": "🗑️ 清空聊天记录",
        "current_config": "📊 当前配置",
        "model": "模型",
        "messages": "消息数",
        "how_to_use": "📖 使用说明",
        "instructions": """
        1. 💬 在输入框输入您的问题
        2. 🌐 选择您偏好的语言
        3. 🎭 选择 AI 人格风格
        4. 🤖 AI 将实时回复
        5. 🗑️ 点击"清空聊天记录"重新开始
        6. ✨ 讨论任何您想谈的话题
        """,
        "input_placeholder": "在这里输入您的消息...",
        "error": "错误：",
        "check_api": "请检查您的 API 密钥是否正确配置。",
        "run_code": "▶️ 运行代码",
        "code_result": "📟 代码执行结果",
        "output": "✅ 输出：",
        "error_label": "❌ 错误：",
        "friendly": "友好型",
        "professional": "专业型",
        "humorous": "幽默型"
    },
    "Español (Spanish)": {
        "title": "💬 AI Amigo Todoterreno de {name}",
        "title_default": "💬 Mi AI Amigo Todoterreno",
        "caption": "Tu asistente AI versátil - habla de literalmente cualquier cosa",
        "enter_name": "Ingresa tu nombre:",
        "name_placeholder": "Tu nombre",
        "enter_email": "Ingresa tu correo electrónico:",
        "email_placeholder": "tu.correo@ejemplo.com",
        "enter_password": "Ingresa tu contraseña:",
        "password_placeholder": "Contraseña",
        "signin_title": "🔐 Iniciar Sesión",
        "signin_welcome": "¡Bienvenido! Crea tu cuenta para continuar",
        "signin_button": "Iniciar Sesión",
        "signout_button": "Cerrar Sesión",
        "welcome": "👋 ¡Bienvenido! Soy tu Asistente AI Todoterreno. Puedo discutir cualquier tema contigo: aprendizaje, trabajo, vida, entretenimiento, tecnología, artes y más. ¡Lo que quieras hablar, estoy aquí para ayudar!",
        "settings": "⚙️ Configuración",
        "language": "🌐 Idioma",
        "choose_language": "Elige el idioma de respuesta:",
        "language_changed": "Idioma cambiado a",
        "personality": "🎭 Personalidad AI",
        "choose_personality": "Elige el estilo de respuesta:",
        "switched_to": "Cambiado a",
        "mode": "modo!",
        "clear_chat": "🗑️ Borrar Historial",
        "current_config": "📊 Configuración Actual",
        "model": "Modelo",
        "messages": "Mensajes",
        "how_to_use": "📖 Cómo Usar",
        "instructions": """
        1. 💬 Escribe tu pregunta en el cuadro
        2. 🌐 Selecciona tu idioma preferido
        3. 🎭 Selecciona la personalidad AI
        4. 🤖 AI responderá en tiempo real
        5. 🗑️ Haz clic en "Borrar Historial" para reiniciar
        6. ✨ Discute cualquier tema que quieras
        """,
        "input_placeholder": "Escribe tu mensaje aquí...",
        "error": "Error:",
        "check_api": "Por favor verifica si tu clave API está configurada correctamente.",
        "run_code": "▶️ Ejecutar Código",
        "code_result": "📟 Resultado de Ejecución",
        "output": "✅ Salida:",
        "error_label": "❌ Error:",
        "friendly": "Amigable",
        "professional": "Profesional",
        "humorous": "Divertido"
    },
    "Français (French)": {
        "title": "💬 AI Compagnon Polyvalent de {name}",
        "title_default": "💬 Mon AI Compagnon Polyvalent",
        "caption": "Votre assistant AI polyvalent - parlez de n'importe quoi",
        "enter_name": "Entrez votre nom:",
        "name_placeholder": "Votre nom",
        "enter_email": "Entrez votre e-mail:",
        "email_placeholder": "votre.email@exemple.com",
        "enter_password": "Entrez votre mot de passe:",
        "password_placeholder": "Mot de passe",
        "signin_title": "🔐 Connexion",
        "signin_welcome": "Bienvenue! Créez votre compte pour continuer",
        "signin_button": "Se Connecter",
        "signout_button": "Se Déconnecter",
        "welcome": "👋 Bienvenue! Je suis votre Assistant AI Polyvalent. Je peux discuter de n'importe quel sujet avec vous: apprentissage, travail, vie, divertissement, technologie, arts et plus. Quoi que vous vouliez discuter, je suis là pour vous aider!",
        "settings": "⚙️ Paramètres",
        "language": "🌐 Langue",
        "choose_language": "Choisissez la langue de réponse:",
        "language_changed": "Langue changée en",
        "personality": "🎭 Personnalité AI",
        "choose_personality": "Choisissez le style de réponse:",
        "switched_to": "Basculé vers",
        "mode": "mode!",
        "clear_chat": "🗑️ Effacer l'Historique",
        "current_config": "📊 Configuration Actuelle",
        "model": "Modèle",
        "messages": "Messages",
        "how_to_use": "📖 Comment Utiliser",
        "instructions": """
        1. 💬 Tapez votre question dans la boîte
        2. 🌐 Sélectionnez votre langue préférée
        3. 🎭 Sélectionnez la personnalité AI
        4. 🤖 L'AI répondra en temps réel
        5. 🗑️ Cliquez sur "Effacer l'Historique" pour recommencer
        6. ✨ Discutez de n'importe quel sujet
        """,
        "input_placeholder": "Tapez votre message ici...",
        "error": "Erreur:",
        "check_api": "Veuillez vérifier si votre clé API est correctement configurée.",
        "run_code": "▶️ Exécuter le Code",
        "code_result": "📟 Résultat d'Exécution",
        "output": "✅ Sortie:",
        "error_label": "❌ Erreur:",
        "friendly": "Amical",
        "professional": "Professionnel",
        "humorous": "Humoristique"
    },
    "Deutsch (German)": {
        "title": "💬 {name}s Alleskönner AI Kumpel",
        "title_default": "💬 Mein Alleskönner AI Kumpel",
        "caption": "Ihr vielseitiger AI-Assistent - sprechen Sie über buchstäblich alles",
        "enter_name": "Geben Sie Ihren Namen ein:",
        "name_placeholder": "Ihr Name",
        "enter_email": "Geben Sie Ihre E-Mail ein:",
        "email_placeholder": "ihre.email@beispiel.com",
        "enter_password": "Geben Sie Ihr Passwort ein:",
        "password_placeholder": "Passwort",
        "signin_title": "🔐 Anmelden",
        "signin_welcome": "Willkommen! Erstellen Sie Ihr Konto, um fortzufahren",
        "signin_button": "Anmelden",
        "signout_button": "Abmelden",
        "welcome": "👋 Willkommen! Ich bin Ihr Alleskönner AI-Assistent. Ich kann mit Ihnen über jedes Thema sprechen: Lernen, Arbeit, Leben, Unterhaltung, Technologie, Kunst und mehr. Worüber Sie auch sprechen möchten, ich bin hier, um zu helfen!",
        "settings": "⚙️ Einstellungen",
        "language": "🌐 Sprache",
        "choose_language": "Wählen Sie die Antwortsprache:",
        "language_changed": "Sprache geändert zu",
        "personality": "🎭 AI-Persönlichkeit",
        "choose_personality": "Wählen Sie den Antwortstil:",
        "switched_to": "Gewechselt zu",
        "mode": "Modus!",
        "clear_chat": "🗑️ Verlauf Löschen",
        "current_config": "📊 Aktuelle Konfiguration",
        "model": "Modell",
        "messages": "Nachrichten",
        "how_to_use": "📖 Anleitung",
        "instructions": """
        1. 💬 Geben Sie Ihre Frage ein
        2. 🌐 Wählen Sie Ihre bevorzugte Sprache
        3. 🎭 Wählen Sie die AI-Persönlichkeit
        4. 🤖 AI antwortet in Echtzeit
        5. 🗑️ Klicken Sie auf "Verlauf Löschen" zum Neustart
        6. ✨ Besprechen Sie jedes gewünschte Thema
        """,
        "input_placeholder": "Geben Sie hier Ihre Nachricht ein...",
        "error": "Fehler:",
        "check_api": "Bitte überprüfen Sie, ob Ihr API-Schlüssel korrekt konfiguriert ist.",
        "run_code": "▶️ Code Ausführen",
        "code_result": "📟 Ausführungsergebnis",
        "output": "✅ Ausgabe:",
        "error_label": "❌ Fehler:",
        "friendly": "Freundlich",
        "professional": "Professionell",
        "humorous": "Humorvoll"
    },
    "日本語 (Japanese)": {
        "title": "💬 {name} の万能 AI 相棒",
        "title_default": "💬 私の万能 AI 相棒",
        "caption": "あなたの多用途AIアシスタント - 文字通り何でも話せます",
        "enter_name": "名前を入力：",
        "name_placeholder": "あなたの名前",
        "enter_email": "メールアドレスを入力：",
        "email_placeholder": "your.email@example.com",
        "enter_password": "パスワードを入力：",
        "password_placeholder": "パスワード",
        "signin_title": "🔐 サインイン",
        "signin_welcome": "ようこそ！続行するにはアカウントを作成してください",
        "signin_button": "サインイン",
        "signout_button": "サインアウト",
        "welcome": "👋 ようこそ！私はあなたの万能AIアシスタントです。学習、仕事、生活、娯楽、技術、芸術など、あらゆるトピックについて話し合うことができます。何を話したくても、お手伝いします！",
        "settings": "⚙️ 設定",
        "language": "🌐 言語",
        "choose_language": "応答言語を選択：",
        "language_changed": "言語が変更されました",
        "personality": "🎭 AIパーソナリティ",
        "choose_personality": "AI応答スタイルを選択：",
        "switched_to": "切り替えました",
        "mode": "モード！",
        "clear_chat": "🗑️ チャット履歴をクリア",
        "current_config": "📊 現在の設定",
        "model": "モデル",
        "messages": "メッセージ数",
        "how_to_use": "📖 使い方",
        "instructions": """
        1. 💬 入力ボックスに質問を入力
        2. 🌐 希望の言語を選択
        3. 🎭 AIパーソナリティを選択
        4. 🤖 AIがリアルタイムで応答
        5. 🗑️ 「チャット履歴をクリア」で再起動
        6. ✨ 好きなトピックについて話す
        """,
        "input_placeholder": "ここにメッセージを入力...",
        "error": "エラー：",
        "check_api": "APIキーが正しく設定されているか確認してください。",
        "run_code": "▶️ コードを実行",
        "code_result": "📟 コード実行結果",
        "output": "✅ 出力：",
        "error_label": "❌ エラー：",
        "friendly": "フレンドリー",
        "professional": "プロフェッショナル",
        "humorous": "ユーモラス"
    },
    "한국어 (Korean)": {
        "title": "💬 {name}의 만능 AI 친구",
        "title_default": "💬 나의 만능 AI 친구",
        "caption": "당신의 다재다능한 AI 어시스턴트 - 문자 그대로 모든 것에 대해 이야기하세요",
        "enter_name": "이름을 입력하세요:",
        "name_placeholder": "당신의 이름",
        "enter_email": "이메일을 입력하세요:",
        "email_placeholder": "your.email@example.com",
        "enter_password": "비밀번호를 입력하세요:",
        "password_placeholder": "비밀번호",
        "signin_title": "🔐 로그인",
        "signin_welcome": "환영합니다! 계속하려면 계정을 만드세요",
        "signin_button": "로그인",
        "signout_button": "로그아웃",
        "welcome": "👋 환영합니다! 저는 당신의 만능 AI 어시스턴트입니다. 학습, 업무, 생활, 엔터테인먼트, 기술, 예술 등 모든 주제에 대해 토론할 수 있습니다. 무엇을 이야기하고 싶든, 도와드리겠습니다!",
        "settings": "⚙️ 설정",
        "language": "🌐 언어",
        "choose_language": "응답 언어 선택:",
        "language_changed": "언어가 변경되었습니다",
        "personality": "🎭 AI 성격",
        "choose_personality": "AI 응답 스타일 선택:",
        "switched_to": "전환됨",
        "mode": "모드!",
        "clear_chat": "🗑️ 채팅 기록 지우기",
        "current_config": "📊 현재 설정",
        "model": "모델",
        "messages": "메시지",
        "how_to_use": "📖 사용 방법",
        "instructions": """
        1. 💬 입력 상자에 질문 입력
        2. 🌐 선호하는 언어 선택
        3. 🎭 AI 성격 스타일 선택
        4. 🤖 AI가 실시간으로 응답
        5. 🗑️ "채팅 기록 지우기" 클릭하여 재시작
        6. ✨ 원하는 주제에 대해 토론
        """,
        "input_placeholder": "여기에 메시지를 입력하세요...",
        "error": "오류:",
        "check_api": "API 키가 올바르게 구성되어 있는지 확인하세요.",
        "run_code": "▶️ 코드 실행",
        "code_result": "📟 코드 실행 결과",
        "output": "✅ 출력:",
        "error_label": "❌ 오류:",
        "friendly": "친근함",
        "professional": "전문적",
        "humorous": "유머러스"
    },
    "Português (Portuguese)": {
        "title": "💬 AI Companheiro Versátil de {name}",
        "title_default": "💬 Meu AI Companheiro Versátil",
        "caption": "Seu assistente AI versátil - fale sobre literalmente qualquer coisa",
        "enter_name": "Digite seu nome:",
        "name_placeholder": "Seu nome",
        "enter_email": "Digite seu e-mail:",
        "email_placeholder": "seu.email@exemplo.com",
        "enter_password": "Digite sua senha:",
        "password_placeholder": "Senha",
        "signin_title": "🔐 Entrar",
        "signin_welcome": "Bem-vindo! Crie sua conta para continuar",
        "signin_button": "Entrar",
        "signout_button": "Sair",
        "welcome": "👋 Bem-vindo! Sou seu Assistente AI Versátil. Posso discutir qualquer tópico com você: aprendizado, trabalho, vida, entretenimento, tecnologia, artes e muito mais. Seja qual for o assunto, estou aqui para ajudar!",
        "settings": "⚙️ Configurações",
        "language": "🌐 Idioma",
        "choose_language": "Escolha o idioma de resposta:",
        "language_changed": "Idioma alterado para",
        "personality": "🎭 Personalidade AI",
        "choose_personality": "Escolha o estilo de resposta:",
        "switched_to": "Alterado para",
        "mode": "modo!",
        "clear_chat": "🗑️ Limpar Histórico",
        "current_config": "📊 Configuração Atual",
        "model": "Modelo",
        "messages": "Mensagens",
        "how_to_use": "📖 Como Usar",
        "instructions": """
        1. 💬 Digite sua pergunta na caixa
        2. 🌐 Selecione seu idioma preferido
        3. 🎭 Selecione a personalidade AI
        4. 🤖 AI responderá em tempo real
        5. 🗑️ Clique em "Limpar Histórico" para reiniciar
        6. ✨ Discuta qualquer tópico desejado
        """,
        "input_placeholder": "Digite sua mensagem aqui...",
        "error": "Erro:",
        "check_api": "Verifique se sua chave API está configurada corretamente.",
        "run_code": "▶️ Executar Código",
        "code_result": "📟 Resultado da Execução",
        "output": "✅ Saída:",
        "error_label": "❌ Erro:",
        "friendly": "Amigável",
        "professional": "Profissional",
        "humorous": "Bem-humorado"
    },
    "Русский (Russian)": {
        "title": "💬 Универсальный AI Друг {name}",
        "title_default": "💬 Мой Универсальный AI Друг",
        "caption": "Ваш универсальный AI ассистент - говорите буквально о чем угодно",
        "enter_name": "Введите ваше имя:",
        "name_placeholder": "Ваше имя",
        "enter_email": "Введите ваш e-mail:",
        "email_placeholder": "your.email@example.com",
        "enter_password": "Введите ваш пароль:",
        "password_placeholder": "Пароль",
        "signin_title": "🔐 Вход",
        "signin_welcome": "Добро пожаловать! Создайте свой аккаунт, чтобы продолжить",
        "signin_button": "Войти",
        "signout_button": "Выйти",
        "welcome": "👋 Добро пожаловать! Я ваш Универсальный AI Ассистент. Я могу обсудить с вами любую тему: обучение, работу, жизнь, развлечения, технологии, искусство и многое другое. О чем бы вы ни хотели поговорить, я здесь, чтобы помочь!",
        "settings": "⚙️ Настройки",
        "language": "🌐 Язык",
        "choose_language": "Выберите язык ответа:",
        "language_changed": "Язык изменен на",
        "personality": "🎭 Личность AI",
        "choose_personality": "Выберите стиль ответа:",
        "switched_to": "Переключено на",
        "mode": "режим!",
        "clear_chat": "🗑️ Очистить Историю",
        "current_config": "📊 Текущая Конфигурация",
        "model": "Модель",
        "messages": "Сообщения",
        "how_to_use": "📖 Как Использовать",
        "instructions": """
        1. 💬 Введите вопрос в поле ввода
        2. 🌐 Выберите предпочитаемый язык
        3. 🎭 Выберите личность AI
        4. 🤖 AI ответит в реальном времени
        5. 🗑️ Нажмите "Очистить Историю" для перезапуска
        6. ✨ Обсудите любую желаемую тему
        """,
        "input_placeholder": "Введите ваше сообщение здесь...",
        "error": "Ошибка:",
        "check_api": "Пожалуйста, проверьте правильность настройки вашего API ключа.",
        "run_code": "▶️ Выполнить Код",
        "code_result": "📟 Результат Выполнения",
        "output": "✅ Вывод:",
        "error_label": "❌ Ошибка:",
        "friendly": "Дружелюбный",
        "professional": "Профессиональный",
        "humorous": "Юмористичный"
    },
    "العربية (Arabic)": {
        "title": "💬 رفيق الذكاء الاصطناعي الشامل لـ {name}",
        "title_default": "💬 رفيقي الذكي الشامل",
        "caption": "مساعدك الذكي المتعدد الاستخدامات - تحدث عن أي شيء حرفياً",
        "enter_name": "أدخل اسمك:",
        "name_placeholder": "اسمك",
        "enter_email": "أدخل بريدك الإلكتروني:",
        "email_placeholder": "your.email@example.com",
        "enter_password": "أدخل كلمة المرور:",
        "password_placeholder": "كلمة المرور",
        "signin_title": "🔐 تسجيل الدخول",
        "signin_welcome": "مرحباً! أنشئ حسابك للمتابعة",
        "signin_button": "تسجيل الدخول",
        "signout_button": "تسجيل الخروج",
        "welcome": "👋 مرحباً! أنا مساعدك الذكي الشامل. يمكنني مناقشة أي موضوع معك: التعلم، العمل، الحياة، الترفيه، التكنولوجيا، الفنون والمزيد. مهما كان ما تريد التحدث عنه، أنا هنا للمساعدة!",
        "settings": "⚙️ الإعدادات",
        "language": "🌐 اللغة",
        "choose_language": "اختر لغة الرد:",
        "language_changed": "تم تغيير اللغة إلى",
        "personality": "🎭 شخصية الذكاء الاصطناعي",
        "choose_personality": "اختر نمط الرد:",
        "switched_to": "تم التبديل إلى",
        "mode": "الوضع!",
        "clear_chat": "🗑️ مسح السجل",
        "current_config": "📊 الإعدادات الحالية",
        "model": "النموذج",
        "messages": "الرسائل",
        "how_to_use": "📖 كيفية الاستخدام",
        "instructions": """
        1. 💬 اكتب سؤالك في مربع الإدخال
        2. 🌐 اختر لغتك المفضلة
        3. 🎭 اختر شخصية الذكاء الاصطناعي
        4. 🤖 سيرد الذكاء الاصطناعي في الوقت الفعلي
        5. 🗑️ انقر على "مسح السجل" لإعادة البدء
        6. ✨ ناقش أي موضوع تريده
        """,
        "input_placeholder": "اكتب رسالتك هنا...",
        "error": "خطأ:",
        "check_api": "يرجى التحقق من تكوين مفتاح API الخاص بك بشكل صحيح.",
        "run_code": "▶️ تشغيل الكود",
        "code_result": "📟 نتيجة التنفيذ",
        "output": "✅ الإخراج:",
        "error_label": "❌ خطأ:",
        "friendly": "ودود",
        "professional": "محترف",
        "humorous": "فكاهي"
    }
}

# Define AI job/role settings (for API - always in English)
job_prompts = {
    "Just chat": "You are a versatile AI assistant ready to chat about anything.",
    "Game pro": "You are a gaming expert AI assistant. You have deep knowledge about video games, gaming strategies, game mechanics, esports, gaming hardware, and the gaming industry. Help users with game recommendations, walkthroughs, tips, tricks, and gaming-related questions.",
    "Study buddy": "You are an educational AI assistant focused on helping students learn. You excel at explaining complex concepts clearly, creating study plans, answering homework questions, providing learning resources, and motivating students. You adapt explanations to different learning styles.",
    "Coder": "You are an expert programming AI assistant. You specialize in helping with code writing, debugging, code reviews, explaining programming concepts, suggesting best practices, and solving coding problems across multiple programming languages and frameworks. Always provide clean, well-commented code examples."
}

# Define AI personality settings (for API - always in English)
personality_prompts = {
    "Friendly": "You are a warm and friendly AI assistant who chats like a friend. Use a kind tone and make conversations relaxed and pleasant. Do not use emojis in your responses. Always understand the user's intent even if they make typos, spelling mistakes, or use incorrect words. Be forgiving and helpful. When showing Python code examples, always wrap them in ```python code blocks so they can be executed.",
    "Professional": "You are a rigorous and professional AI assistant who provides accurate and reliable advice. Use a formal tone, focus on logic and accuracy, and give detailed explanations. Do not use emojis in your responses. Understand user intent even with typos or unclear phrasing, and politely clarify if needed. When showing Python code examples, always wrap them in ```python code blocks so they can be executed.",
    "Humorous": "You are a relaxed and humorous AI assistant who makes chatting fun. Use a witty tone, make appropriate jokes, but ensure information accuracy. Do not use emojis in your responses. Don't worry about typos or mistakes - understand what the user means and maybe make a light joke about it! When showing Python code examples, always wrap them in ```python code blocks so they can be executed."
}

# Personality descriptions (for UI display - multilingual)
personality_descriptions = {
    "English": {
        "Friendly": "You are a warm and friendly AI assistant who chats like a friend. Use a kind tone and make conversations relaxed and pleasant. Do not use emojis in your responses. Always understand the user's intent even if they make typos, spelling mistakes, or use incorrect words. Be forgiving and helpful. When showing Python code examples, always wrap them in ```python code blocks so they can be executed.",
        "Professional": "You are a rigorous and professional AI assistant who provides accurate and reliable advice. Use a formal tone, focus on logic and accuracy, and give detailed explanations. Do not use emojis in your responses. Understand user intent even with typos or unclear phrasing, and politely clarify if needed. When showing Python code examples, always wrap them in ```python code blocks so they can be executed.",
        "Humorous": "You are a relaxed and humorous AI assistant who makes chatting fun. Use a witty tone, make appropriate jokes, but ensure information accuracy. Do not use emojis in your responses. Don't worry about typos or mistakes - understand what the user means and maybe make a light joke about it! When showing Python code examples, always wrap them in ```python code blocks so they can be executed."
    },
    "中文 (Chinese)": {
        "Friendly": "你是一个温暖友好的 AI 助手，像朋友一样聊天。使用亲切的语气和适当的表情符号，让对话轻松愉快。即使用户打错字、拼写错误或使用不正确的词语，也要理解用户的意图。宽容且乐于助人。显示 Python 代码示例时，请用 ```python 代码块包装，以便执行。",
        "Professional": "你是一个严谨专业的 AI 助手，提供准确可靠的建议。使用正式的语气，注重逻辑性和准确性，给出详细的解释。即使有拼写错误或表达不清，也要理解用户意图，并礼貌地澄清。显示 Python 代码示例时，请用 ```python 代码块包装，以便执行。",
        "Humorous": "你是一个轻松幽默的 AI 助手，让聊天变得有趣。使用诙谐的语气，适当开玩笑，但要确保信息的准确性。不要担心拼写错误或错误 - 理解用户的意思，也许可以开个小玩笑！显示 Python 代码示例时，请用 ```python 代码块包装，以便执行。"
    },
    "Español (Spanish)": {
        "Friendly": "Eres un asistente AI cálido y amigable que charla como un amigo. Usa un tono amable, emojis apropiados y haz que las conversaciones sean relajadas y agradables. Comprende siempre la intención del usuario incluso si comete errores tipográficos o usa palabras incorrectas. Sé comprensivo y servicial. Al mostrar ejemplos de código Python, envuélvelos en bloques ```python para que puedan ejecutarse.",
        "Professional": "Eres un asistente AI riguroso y profesional que brinda consejos precisos y confiables. Usa un tono formal, enfócate en la lógica y precisión, y da explicaciones detalladas. Comprende la intención del usuario incluso con errores, y aclara cortésmente si es necesario. Al mostrar ejemplos de código Python, envuélvelos en bloques ```python para que puedan ejecutarse.",
        "Humorous": "Eres un asistente AI relajado y humorístico que hace que chatear sea divertido. Usa un tono ingenioso, haz bromas apropiadas, pero asegura la precisión de la información. ¡No te preocupes por los errores tipográficos - comprende lo que el usuario quiere decir y tal vez haz una broma ligera! Al mostrar ejemplos de código Python, envuélvelos en bloques ```python para que puedan ejecutarse."
    },
    "Français (French)": {
        "Friendly": "Vous êtes un assistant IA chaleureux et amical qui discute comme un ami. Utilisez un ton aimable, des emojis appropriés et rendez les conversations détendues et agréables. Comprenez toujours l'intention de l'utilisateur même s'il fait des fautes de frappe ou utilise des mots incorrects. Soyez indulgent et serviable. Lorsque vous montrez des exemples de code Python, enveloppez-les dans des blocs ```python pour qu'ils puissent être exécutés.",
        "Professional": "Vous êtes un assistant IA rigoureux et professionnel qui fournit des conseils précis et fiables. Utilisez un ton formel, concentrez-vous sur la logique et la précision, et donnez des explications détaillées. Comprenez l'intention même avec des erreurs, et clarifiez poliment si nécessaire. Lorsque vous montrez des exemples de code Python, enveloppez-les dans des blocs ```python pour qu'ils puissent être exécutés.",
        "Humorous": "Vous êtes un assistant IA détendu et humoristique qui rend le chat amusant. Utilisez un ton spirituel, faites des blagues appropriées, mais assurez l'exactitude des informations. Ne vous inquiétez pas des erreurs - comprenez ce que l'utilisateur veut dire et faites peut-être une blague légère! Lorsque vous montrez des exemples de code Python, enveloppez-les dans des blocs ```python pour qu'ils puissent être exécutés."
    },
    "Deutsch (German)": {
        "Friendly": "Sie sind ein warmherziger und freundlicher KI-Assistent, der wie ein Freund chattet. Verwenden Sie einen freundlichen Ton, passende Emojis und machen Sie Gespräche entspannt und angenehm. Verstehen Sie immer die Absicht des Benutzers, auch wenn Tippfehler oder falsche Wörter verwendet werden. Seien Sie nachsichtig und hilfsbereit. Wenn Sie Python-Codebeispiele zeigen, verpacken Sie sie in ```python-Blöcken, damit sie ausgeführt werden können.",
        "Professional": "Sie sind ein strenger und professioneller KI-Assistent, der präzise und zuverlässige Ratschläge gibt. Verwenden Sie einen formellen Ton, konzentrieren Sie sich auf Logik und Genauigkeit und geben Sie detaillierte Erklärungen. Verstehen Sie die Absicht auch bei Fehlern und klären Sie höflich bei Bedarf. Wenn Sie Python-Codebeispiele zeigen, verpacken Sie sie in ```python-Blöcken, damit sie ausgeführt werden können.",
        "Humorous": "Sie sind ein entspannter und humorvoller KI-Assistent, der das Chatten unterhaltsam macht. Verwenden Sie einen witzigen Ton, machen Sie angemessene Witze, aber stellen Sie die Genauigkeit der Informationen sicher. Machen Sie sich keine Sorgen über Tippfehler - verstehen Sie, was der Benutzer meint, und machen Sie vielleicht einen leichten Scherz! Wenn Sie Python-Codebeispiele zeigen, verpacken Sie sie in ```python-Blöcken, damit sie ausgeführt werden können."
    },
    "日本語 (Japanese)": {
        "Friendly": "あなたは友人のように話す温かくフレンドリーなAIアシスタントです。親切な口調、適切な絵文字を使い、会話をリラックスして楽しくしてください。タイプミスやスペルミス、間違った言葉を使っても、常にユーザーの意図を理解してください。寛容で役立つようにしてください。Pythonコード例を示すときは、実行できるように```pythonブロックで囲んでください。",
        "Professional": "あなたは厳格で専門的なAIアシスタントで、正確で信頼できるアドバイスを提供します。正式な口調を使い、論理性と正確性に焦点を当て、詳細な説明をしてください。エラーがあっても意図を理解し、必要に応じて丁寧に明確にしてください。Pythonコード例を示すときは、実行できるように```pythonブロックで囲んでください。",
        "Humorous": "あなたはリラックスしたユーモラスなAIアシスタントで、チャットを楽しくします。機知に富んだ口調を使い、適切な冗談を言いますが、情報の正確性を確保してください。タイプミスや間違いを心配しないでください - ユーザーの意味を理解し、軽い冗談を言うかもしれません！Pythonコード例を示すときは、実行できるように```pythonブロックで囲んでください。"
    },
    "한국어 (Korean)": {
        "Friendly": "당신은 친구처럼 대화하는 따뜻하고 친근한 AI 어시스턴트입니다. 친절한 어조, 적절한 이모티콘을 사용하고 대화를 편안하고 즐겁게 만드세요. 오타, 철자 오류 또는 잘못된 단어를 사용하더라도 항상 사용자의 의도를 이해하세요. 관대하고 도움이 되도록 하세요. Python 코드 예제를 표시할 때는 실행할 수 있도록 ```python 블록으로 감싸세요.",
        "Professional": "당신은 정확하고 신뢰할 수 있는 조언을 제공하는 엄격하고 전문적인 AI 어시스턴트입니다. 공식적인 어조를 사용하고 논리와 정확성에 집중하며 자세한 설명을 제공하세요. 오류가 있어도 의도를 이해하고 필요시 정중하게 명확히 하세요. Python 코드 예제를 표시할 때는 실행할 수 있도록 ```python 블록으로 감싸세요.",
        "Humorous": "당신은 채팅을 재미있게 만드는 편안하고 유머러스한 AI 어시스턴트입니다. 재치있는 어조를 사용하고 적절한 농담을 하되 정보의 정확성을 보장하세요. 오타나 실수를 걱정하지 마세요 - 사용자의 의미를 이해하고 가벼운 농담을 할 수도 있습니다! Python 코드 예제를 표시할 때는 실행할 수 있도록 ```python 블록으로 감싸세요."
    },
    "Português (Portuguese)": {
        "Friendly": "Você é um assistente de IA caloroso e amigável que conversa como um amigo. Use um tom gentil, emojis apropriados e torne as conversas relaxadas e agradáveis. Sempre entenda a intenção do usuário, mesmo que cometa erros de digitação ou use palavras incorretas. Seja tolerante e prestativo. Ao mostrar exemplos de código Python, envolva-os em blocos ```python para que possam ser executados.",
        "Professional": "Você é um assistente de IA rigoroso e profissional que fornece conselhos precisos e confiáveis. Use um tom formal, concentre-se em lógica e precisão e dê explicações detalhadas. Entenda a intenção mesmo com erros e esclareça educadamente se necessário. Ao mostrar exemplos de código Python, envolva-os em bloques ```python para que possam ser executados.",
        "Humorous": "Você é um assistente de IA descontraído e bem-humorado que torna o bate-papo divertido. Use um tom espirituoso, faça piadas apropriadas, mas garanta a precisão das informações. Não se preocupe com erros de digitação - entenda o que o usuário quer dizer e talvez faça uma piada leve! Ao mostrar exemplos de código Python, envolva-os em blocos ```python para que possam ser executados."
    },
    "Русский (Russian)": {
        "Friendly": "Вы - теплый и дружелюбный ИИ-ассистент, который общается как друг. Используйте добрый тон, подходящие эмодзи и делайте разговоры расслабленными и приятными. Всегда понимайте намерение пользователя, даже если он делает опечатки или использует неправильные слова. Будьте снисходительны и полезны. При показе примеров кода Python оборачивайте их в блоки ```python, чтобы их можно было выполнить.",
        "Professional": "Вы - строгий и профессиональный ИИ-ассистент, который дает точные и надежные советы. Используйте формальный тон, сосредоточьтесь на логике и точности и давайте подробные объяснения. Понимайте намерение даже при ошибках и вежливо уточняйте при необходимости. При показе примеров кода Python оборачивайте их в блоки ```python, чтобы их можно было выполнить.",
        "Humorous": "Вы - расслабленный и юмористичный ИИ-ассистент, который делает общение веселым. Используйте остроумный тон, шутите уместно, но обеспечивайте точность информации. Не беспокойтесь об опечатках - поймите, что имеет в виду пользователь, и, возможно, пошутите легко! При показе примеров кода Python оборачивайте их в блоки ```python, чтобы их можно было выполнить."
    },
    "العربية (Arabic)": {
        "Friendly": "أنت مساعد ذكاء اصطناعي دافئ وودود يتحدث كصديق. استخدم نبرة لطيفة، رموز تعبيرية مناسبة، واجعل المحادثات مريحة وممتعة. افهم دائمًا نية المستخدم حتى لو ارتكب أخطاء إملائية أو استخدم كلمات غير صحيحة. كن متسامحًا ومفيدًا. عند عرض أمثلة كود Python، قم بتغليفها في كتل ```python حتى يمكن تنفيذها.",
        "Professional": "أنت مساعد ذكاء اصطناعي صارم ومحترف يقدم نصائح دقيقة وموثوقة. استخدم نبرة رسمية، ركز على المنطق والدقة، وقدم تفسيرات مفصلة. افهم النية حتى مع الأخطاء ووضح بأدب إذا لزم الأمر. عند عرض أمثلة كود Python، قم بتغليفها في كتل ```python حتى يمكن تنفيذها.",
        "Humorous": "أنت مساعد ذكاء اصطناعي مريح وفكاهي يجعل الدردشة ممتعة. استخدم نبرة ذكية، اصنع نكاتًا مناسبة، لكن تأكد من دقة المعلومات. لا تقلق بشأن الأخطاء الإملائية - افهم ما يعنيه المستخدم وربما تمزح قليلاً! عند عرض أمثلة كود Python، قم بتغليفها في كتل ```python حتى يمكن تنفيذها."
    }
}

personality_icons = {
    "Friendly": "😊",
    "Professional": "🎯",
    "Humorous": "😄"
}

# Get current language translations
t = ui_translations[st.session_state.language]

# Check if user is signed in
if not st.session_state.signed_in:
    # Sign-in page
    st.title(t["signin_title"])
    st.info(t["signin_welcome"])

    # Center the sign-in form
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        signin_name = st.text_input(
            t["enter_name"],
            placeholder=t["name_placeholder"],
            key="signin_name_input"
        )

        signin_email = st.text_input(
            t["enter_email"],
            placeholder=t["email_placeholder"],
            key="signin_email_input"
        )

        signin_password = st.text_input(
            t["enter_password"],
            placeholder=t["password_placeholder"],
            type="password",
            key="signin_password_input",
            help=t["password_requirements"]
        )

        if st.button(t["signin_button"], type="primary", use_container_width=True):
            # Check if all fields are filled
            if not signin_name.strip() or not signin_email.strip() or not signin_password.strip():
                st.error(t["error_all_fields"])
            # Validate email format
            elif not is_valid_email(signin_email.strip()):
                st.error(t["error_invalid_email"])
            # Validate password
            else:
                is_valid, error_msg = is_valid_password(signin_password)
                if not is_valid:
                    # Show specific password error
                    if "8 characters" in error_msg:
                        st.error(t["error_password_length"])
                    elif "uppercase" in error_msg:
                        st.error(t["error_password_uppercase"])
                    elif "lowercase" in error_msg:
                        st.error(t["error_password_lowercase"])
                    elif "number" in error_msg:
                        st.error(t["error_password_number"])
                else:
                    # All validations passed
                    st.session_state.user_name = signin_name.strip()
                    st.session_state.user_email = signin_email.strip()
                    st.session_state.signed_in = True
                    st.rerun()

    st.stop()

# User is signed in - show main app

# IMAGE GENERATOR MODE
if st.session_state.image_generator_mode:
    st.title("🎨 AI Image Generator")
    st.markdown("Generate stunning images from text descriptions using AI")
    st.markdown("---")

    # Check if HuggingFace is configured
    if not hf_client:
        st.error("⚠️ HuggingFace API token not found!")
        st.info("""
        **Setup Instructions:**
        1. Go to https://huggingface.co/settings/tokens
        2. Create a new token
        3. Add HUGGINGFACE_TOKEN=your_token to your .env file
        4. Restart the application
        """)
    else:
        # Image generation prompt
        img_prompt = st.text_area(
            "Enter your image description:",
            placeholder="e.g., A serene landscape with mountains at sunset, digital art style",
            height=100,
            key="image_prompt"
        )

        # Rainbow gradient CSS for generate button
        st.markdown("""
            <style>
            div.stButton > button[kind="primary"] {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 15%, #f093fb 30%, #4facfe 45%, #00f2fe 60%, #43e97b 75%, #fa709a 90%, #fee140 100%);
                color: white;
                font-weight: bold;
                border: none;
                padding: 0.5rem 2rem;
                font-size: 18px;
            }
            div.stButton > button[kind="primary"]:hover {
                opacity: 0.9;
                transform: scale(1.02);
            }
            </style>
        """, unsafe_allow_html=True)

        # Generate button
        if st.button("🚀 Generate Image", type="primary", use_container_width=True):
            if not img_prompt.strip():
                st.warning("⚠️ Please enter a description for your image!")
            else:
                try:
                    with st.spinner("🎨 Generating your image... This may take 10-30 seconds..."):
                        # Generate image
                        image = hf_client.text_to_image(
                            prompt=img_prompt,
                            model=IMAGE_MODEL,
                            width=1024,
                            height=1024
                        )

                        # Display the generated image
                        st.success("✅ Image generated successfully!")
                        st.image(image, caption=f"Generated: {img_prompt}", use_container_width=True)

                        # Convert PIL Image to bytes for download
                        buf = BytesIO()
                        image.save(buf, format="PNG")
                        byte_im = buf.getvalue()

                        # Download button
                        st.download_button(
                            label="📥 Download Image",
                            data=byte_im,
                            file_name="generated_image.png",
                            mime="image/png"
                        )

                except Exception as e:
                    st.error(f"❌ Error generating image: {str(e)}")
                    st.info("Please try again or modify your prompt.")

# CHAT MODE
else:
    # Page title with help button in top right corner
    col_title, col_help = st.columns([6, 1])
    with col_title:
        # Page title - personalize with user name and job if provided
        job_display = "ethel-chat" if st.session_state.job == "Just chat" else st.session_state.job
        if st.session_state.user_name:
            st.title(t["title"].format(name=st.session_state.user_name, job=job_display))
        else:
            st.title(t["title_default"].format(job=job_display))
        st.caption(t["caption"])
    with col_help:
        st.write("")  # Add spacing
        if st.button("❓", key="help_button_top", help=t["how_to_use"]):
            st.session_state.show_help = True

    # Welcome message
    st.info(t["welcome"])

    # Function to extract and run Python code
    def extract_and_run_code(text):
        """Extract Python code blocks from text and execute them"""
        # Find code blocks in markdown format
        code_pattern = r'```python\n(.*?)```'
        matches = re.findall(code_pattern, text, re.DOTALL)

        results = []
        for code in matches:
            # Create a string buffer to capture output
            output_buffer = StringIO()
            error_buffer = StringIO()

            try:
                # Redirect stdout to capture print statements
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                sys.stdout = output_buffer
                sys.stderr = error_buffer

                # Execute the code
                exec(code, {"__builtins__": __builtins__})

                # Restore stdout
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                output = output_buffer.getvalue()
                error = error_buffer.getvalue()

                if output or error:
                    results.append({
                        'code': code,
                        'output': output if output else None,
                        'error': error if error else None,
                        'success': not error
                    })
            except Exception as e:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                results.append({
                    'code': code,
                    'output': None,
                    'error': str(e),
                    'success': False
                })

        return results

    # Display chat history
    for idx, message in enumerate(st.session_state.messages):
        avatar = None
        if message["role"] == "assistant" and st.session_state.ai_avatar is not None:
            avatar = st.session_state.ai_avatar
        elif message["role"] == "user" and st.session_state.profile_photo is not None:
            avatar = st.session_state.profile_photo

        with st.chat_message(message["role"], avatar=avatar):
            # Handle both string and dict content (for messages with images)
            if isinstance(message["content"], dict):
                # Message with images
                st.markdown(message["content"]["text"])
                if message["content"].get("images"):
                    for img in message["content"]["images"]:
                        st.image(img, width=300)
            else:
                # Regular text message
                st.markdown(message["content"])

            # If assistant message contains code, show run button
            content_text = message["content"] if isinstance(message["content"], str) else message["content"].get("text", "")
            if message["role"] == "assistant" and "```python" in content_text:
                if st.button(t["run_code"], key=f"run_{idx}"):
                    code_results = extract_and_run_code(content_text)
                    for result in code_results:
                        with st.expander(t["code_result"], expanded=True):
                            st.code(result['code'], language='python')
                            if result['success']:
                                if result['output']:
                                    st.success(t["output"])
                                    st.code(result['output'])
                            else:
                                st.error(t["error_label"])
                                st.code(result['error'])

        # Add TTS audio player for assistant messages (outside chat_message container)
        if message["role"] == "assistant" and st.session_state.auto_play_tts and polly_client:
            content_for_tts = content_text if isinstance(message["content"], str) else message["content"].get("text", "")

            audio_bytes = generate_tts_audio(content_for_tts, idx)

            if audio_bytes:
                # Only autoplay the most recent message
                is_latest = idx == len(st.session_state.messages) - 1

                if is_latest:
                    # Convert audio bytes to base64 for HTML embedding
                    audio_base64 = base64.b64encode(audio_bytes).decode()

                    # Create HTML audio element with autoplay
                    audio_html = f"""
                        <audio autoplay controls style="width: 100%;">
                            <source src="data:audio/mpeg;base64,{audio_base64}" type="audio/mpeg">
                        </audio>
                    """

                    # Display HTML audio (autoplay)
                    st.markdown(audio_html, unsafe_allow_html=True)
                else:
                    # Show regular player for older messages
                    st.audio(audio_bytes, format='audio/mpeg')

    # Voice input section
    st.markdown("---")
    col_voice, col_text = st.columns([1, 4])
    with col_voice:
        st.write("🎤 Voice:")
        audio_bytes = audio_recorder(
            text="",
            recording_color="#e74c3c",
            neutral_color="#3498db",
            icon_name="microphone",
            icon_size="1x"
        )

    voice_prompt = None
    if audio_bytes:
        # Check if this is a new recording
        if st.session_state.last_audio != audio_bytes:
            st.session_state.last_audio = audio_bytes

            with st.spinner("Converting speech to text..."):
                try:
                    # Initialize recognizer
                    recognizer = sr.Recognizer()

                    # Convert bytes to audio file
                    audio_data = sr.AudioFile(BytesIO(audio_bytes))

                    with audio_data as source:
                        # Adjust for ambient noise
                        recognizer.adjust_for_ambient_noise(source, duration=0.5)
                        audio = recognizer.record(source)

                    # Recognize speech using Google Speech Recognition
                    voice_prompt = recognizer.recognize_google(audio, language="en-US")
                    st.success(f"Recognized: {voice_prompt}")

                except sr.UnknownValueError:
                    st.error("Could not understand audio. Please try again.")
                except sr.RequestError as e:
                    st.error(f"Speech recognition error: {str(e)}")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    with col_text:
        st.write("⌨️ Text:")

    # User input (no separate image upload section here - moved to sidebar)
    prompt = st.chat_input(t["input_placeholder"])

    # Use voice prompt if available, otherwise use typed input
    if voice_prompt:
        prompt = voice_prompt

    # Handle user input
    if prompt:
        # Prepare message content with images converted to bytes (so they persist across reruns)
        saved_images = []
        if st.session_state.uploaded_images:
            for img_file in st.session_state.uploaded_images:
                # Convert to bytes so it persists
                img_file.seek(0)
                img_bytes = BytesIO(img_file.read())
                img_bytes.name = img_file.name  # Preserve filename
                saved_images.append(img_bytes)

        message_content = {"text": prompt, "images": saved_images if saved_images else []}

        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": message_content})

        # Clear uploaded images after adding to message
        st.session_state.uploaded_images = []

        # Display user message
        user_avatar = st.session_state.profile_photo if st.session_state.profile_photo is not None else None
        with st.chat_message("user", avatar=user_avatar):
            st.markdown(prompt)
            # Display uploaded images if any
            if message_content["images"]:
                for img in message_content["images"]:
                    st.image(img, width=300)

        # Check if we need to search the web
        web_context = ""
        search_keywords = ["search", "find", "look up", "what is", "what's", "who is", "current", "latest",
                           "news", "today", "now", "recent", "weather", "forecast", "temperature",
                           "tomorrow", "how to", "when is", "where is"]
        url_pattern = r'https?://[^\s]+'

        # Check for URLs in the prompt
        urls_found = re.findall(url_pattern, prompt)
        if urls_found:
            with st.spinner("🌐 Fetching webpage content..."):
                for url in urls_found:
                    webpage_content = fetch_webpage(url)
                    web_context += f"\n\n[Content from {url}]:\n{webpage_content}\n"

        # Check if user wants to search
        elif any(keyword in prompt.lower() for keyword in search_keywords):
            with st.spinner("🔍 Searching the web..."):
                search_results = web_search(prompt, num_results=5)
                if search_results and len(search_results) > 0:
                    web_context = "\n\n[Web Search Results]:\n"
                    for i, result in enumerate(search_results):
                        if "error" not in result:
                            web_context += f"{i+1}. {result['title']}\n"
                            web_context += f"   {result['snippet']}\n"
                            web_context += f"   URL: {result['link']}\n\n"

                    if not web_context.strip().endswith("URL:"):
                        st.info(f"🔍 Found {len(search_results)} search results")
                else:
                    web_context = "\n\n[Web search was attempted but no results were found]"

        # Display assistant reply
        avatar = st.session_state.ai_avatar if st.session_state.ai_avatar is not None else None
        with st.chat_message("assistant", avatar=avatar):
            message_placeholder = st.empty()
            full_response = ""

            try:
                # Build message list with personality and language settings
                internet_note = "You have access to the internet. When users ask about current events, recent information, or provide URLs, use the web search results or webpage content provided in the context."
                image_analysis_note = "\n\nENHANCED IMAGE ANALYSIS: When you receive [IMAGE ANALYSIS START]...[IMAGE ANALYSIS END] sections, you're getting a 32x32 pixel grid (1024 pixels total) in hexadecimal RGB format. Each pixel is 6 hex characters (RRGGBB). The data includes: 1) Full pixel grid in hex format, 2) Color analysis (average color, dominant tones, brightness), 3) Edge detection data showing object boundaries and locations. Use ALL this data together to accurately identify objects, people, animals, text, scenes, and content. The 32x32 resolution with hex encoding provides good detail while staying token-efficient. Edge detection helps you locate and identify distinct objects in the image."
                system_message = {
                    "role": "system",
                    "content": f"{job_prompts[st.session_state.job]} {personality_prompts[st.session_state.personality]} {language_instructions[st.session_state.language]} {internet_note}{image_analysis_note}"
                }

                # Convert messages to API format with vision support
                # OPTIMIZATION: Only send last 10 messages to save tokens
                recent_messages = st.session_state.messages[-10:] if len(st.session_state.messages) > 10 else st.session_state.messages

                api_messages = [system_message]
                has_images = False
                image_files = []  # Store actual image files for Gemini

                for i, m in enumerate(recent_messages):
                    content = m["content"]
                    if isinstance(content, dict):
                        # Check if this message has images - handle both list and empty list cases
                        images_list = content.get("images", [])
                        # Filter out None or empty objects
                        valid_images = [img for img in images_list if img is not None]

                        if valid_images and len(valid_images) > 0:
                            # Convert images to compact text representation for Groq
                            text = content.get("text", "")

                            # Add each image as text data (now much smaller with 20x20)
                            for idx, img_file in enumerate(valid_images):
                                image_text = image_to_text_representation(img_file)
                                text += f"\n\n--- IMAGE {idx + 1} ---\n{image_text}\n"

                            # Add web context to the last user message
                            if i == len(recent_messages) - 1 and m["role"] == "user" and web_context:
                                text += web_context

                            api_messages.append({"role": m["role"], "content": text})
                        else:
                            # Text only
                            text = content.get("text", "")
                            if i == len(recent_messages) - 1 and m["role"] == "user" and web_context:
                                text += web_context
                            api_messages.append({"role": m["role"], "content": text})
                    else:
                        message_text = content
                        # Add web context to the last user message
                        if i == len(recent_messages) - 1 and m["role"] == "user" and web_context:
                            message_text += web_context
                        api_messages.append({"role": m["role"], "content": message_text})

                messages_with_personality = api_messages

                # Use Gemini API for all requests (images are converted to 32x32 pixel text with edge detection)
                # Build conversation prompt for Gemini
                conversation_text = ""
                for msg in messages_with_personality:
                    if msg["role"] == "system":
                        conversation_text += msg["content"] + "\n\n"
                    elif msg["role"] == "user":
                        conversation_text += "User: " + msg["content"] + "\n\n"
                    elif msg["role"] == "assistant":
                        conversation_text += "Assistant: " + msg["content"] + "\n\n"

                # Call Gemini API with streaming
                response = client.generate_content(
                    conversation_text,
                    stream=True,
                    generation_config={
                        'max_output_tokens': 2048,
                        'temperature': 0.7
                    }
                )

                # Stream output response
                try:
                    for chunk in response:
                        if hasattr(chunk, 'text') and chunk.text:
                            full_response += chunk.text
                            message_placeholder.markdown(full_response + "▌")
                except Exception as stream_error:
                    # Check if it's a safety block or other error
                    if "block" in str(stream_error).lower():
                        full_response += "\n\n[Response was blocked by safety filters]"
                    else:
                        full_response += f"\n\n[Streaming error: {str(stream_error)}]"

                # Display full response
                message_placeholder.markdown(full_response)

            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"ERROR: {error_details}")  # Print to terminal for debugging
                full_response = f"{t['error']}\n\n**Error Details:** {str(e)}\n\n{t['check_api']}"
                message_placeholder.markdown(full_response)

            # Add assistant message to chat history
            st.session_state.messages.append({"role": "assistant", "content": full_response})

            # Clear uploaded images after sending to prevent accidental reuse
            st.session_state.uploaded_images = []

    # Sidebar
    with st.sidebar:
        st.header(t["settings"])

        # Display profile photo with upload option
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.session_state.profile_photo is not None:
                if isinstance(st.session_state.profile_photo, str):
                    # It's an emoji character
                    st.markdown(f"<div style='background-color: #f0f2f6; border-radius: 50%; width: 80px; height: 80px; display: flex; align-items: center; justify-content: center; font-size: 48px;'>{st.session_state.profile_photo}</div>", unsafe_allow_html=True)
                else:
                    # It's an uploaded image
                    st.image(st.session_state.profile_photo, width=80)
            else:
                st.markdown("<div style='background-color: #f0f2f6; border-radius: 50%; width: 80px; height: 80px; display: flex; align-items: center; justify-content: center; font-size: 48px;'>👤</div>", unsafe_allow_html=True)

        with col2:
            st.write(f"**{st.session_state.user_name}**")
            st.write(f"{st.session_state.user_email}")

        # Profile avatar characters
        profile_characters = {
            "👤 Default": "👤",
            "😊 Happy": "😊",
            "😎 Cool": "😎",
            "🤓 Nerd": "🤓",
            "🥳 Party": "🥳",
            "🤠 Cowboy": "🤠",
            "🧑‍💻 Developer": "🧑‍💻",
            "🧑‍🎨 Artist": "🧑‍🎨",
            "🧑‍🚀 Astronaut": "🧑‍🚀",
            "🧙 Wizard": "🧙",
            "🦸 Superhero": "🦸",
            "🧛 Vampire": "🧛",
            "🧚 Fairy": "🧚",
            "👨‍🎓 Graduate": "👨‍🎓",
            "👑 Royalty": "👑"
        }

        # Profile photo selection method
        profile_method = st.radio(
            "Choose profile photo method:",
            ["Cartoon Characters", "Upload Custom Image"],
            horizontal=True,
            key="profile_method_radio"
        )

        if profile_method == "Cartoon Characters":
            # Display character selection
            selected_profile_char = st.selectbox(
                "Select your character:",
                options=list(profile_characters.keys()),
                format_func=lambda x: x,
                key="profile_character_select"
            )

            if st.button("Apply Profile Character", use_container_width=True, key="apply_profile_char"):
                st.session_state.profile_photo = profile_characters[selected_profile_char]
                st.rerun()

        else:
            # Upload custom image
            uploaded_file = st.file_uploader("Upload your profile photo", type=["png", "jpg", "jpeg"], key="profile_upload")
            if uploaded_file is not None:
                # Optimize image: resize and compress
                img = Image.open(uploaded_file)
                img.thumbnail((200, 200), Image.Resampling.LANCZOS)
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=85, optimize=True)
                buffer.seek(0)
                st.session_state.profile_photo = buffer
                st.rerun()
        if st.button(t["signout_button"], use_container_width=True, key="signout_btn"):
            # Clear all session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            # Reinitialize essential states
            st.session_state.signed_in = False
            st.session_state.user_name = ""
            st.session_state.user_email = ""
            st.session_state.messages = []
            st.session_state.personality = "Friendly"
            st.session_state.language = "English"
            st.rerun()

        st.divider()

        # Image upload section in sidebar
        st.subheader("📷 Upload Images")
        uploaded_image = st.file_uploader(
            "Add images to your next message",
            type=["png", "jpg", "jpeg"],
            key="chat_image_upload",
            accept_multiple_files=False,
            label_visibility="collapsed"
        )
        if uploaded_image is not None:
            # Check if this file is already in the list by comparing name and size
            is_duplicate = any(
                img.name == uploaded_image.name and img.size == uploaded_image.size
                for img in st.session_state.uploaded_images
            )
            if not is_duplicate:
                st.session_state.uploaded_images.append(uploaded_image)
                st.rerun()

        # Display preview of uploaded images
        if st.session_state.uploaded_images:
            st.write(f"**📎 Ready to send ({len(st.session_state.uploaded_images)} image{'s' if len(st.session_state.uploaded_images) > 1 else ''}):**")

            def clear_all_images():
                st.session_state.uploaded_images = []

            st.button("🗑️ Clear All Images", key="clear_all_images", use_container_width=True, on_click=clear_all_images)

            # Display images with delete buttons
            for i in range(len(st.session_state.uploaded_images)):
                if i >= len(st.session_state.uploaded_images):
                    break
                img = st.session_state.uploaded_images[i]
                col_prev, col_del = st.columns([4, 1])
                with col_prev:
                    st.image(img, use_column_width=True)
                with col_del:
                    # Use unique key based on filename and index
                    img_key = f"del_{img.name}_{i}" if hasattr(img, 'name') else f"del_img_{i}"

                    # Use partial to properly bind the index value
                    def delete_image_at_index(index):
                        if index < len(st.session_state.uploaded_images):
                            st.session_state.uploaded_images.pop(index)

                    st.button("❌", key=img_key, help="Remove", on_click=partial(delete_image_at_index, i))

        st.divider()

        # AI Avatar customization
        st.subheader("🤖 AI Assistant Avatar")

        # Cartoon character options
        avatar_characters = {
            "🤖 Robot": "🤖",
            "🐱 Cat": "🐱",
            "🐶 Dog": "🐶",
            "🦊 Fox": "🦊",
            "🐼 Panda": "🐼",
            "🐨 Koala": "🐨",
            "🦁 Lion": "🦁",
            "🐯 Tiger": "🐯",
            "🐸 Frog": "🐸",
            "🐵 Monkey": "🐵",
            "🦉 Owl": "🦉",
            "🦄 Unicorn": "🦄",
            "🐲 Dragon": "🐲",
            "👽 Alien": "👽",
            "🎃 Pumpkin": "🎃",
            "⭐ Star": "⭐"
        }

        # Avatar selection method
        avatar_method = st.radio(
            "Choose avatar method:",
            ["Cartoon Characters", "Upload Custom Image"],
            horizontal=True,
            label_visibility="collapsed"
        )

        if avatar_method == "Cartoon Characters":
            # Display character selection
            selected_ai_char = st.selectbox(
                "Select AI character:",
                options=list(avatar_characters.keys()),
                format_func=lambda x: x,
                key="ai_character_select"
            )

            if st.button("Apply AI Character", use_container_width=True, key="apply_ai_char"):
                st.session_state.ai_avatar = avatar_characters[selected_ai_char]
                st.rerun()

        else:
            # Upload custom image
            ai_avatar_upload = st.file_uploader("Upload your AI avatar", type=["png", "jpg", "jpeg"], key="ai_avatar_upload")
            if ai_avatar_upload is not None:
                # Optimize image: resize and compress
                img = Image.open(ai_avatar_upload)
                img.thumbnail((200, 200), Image.Resampling.LANCZOS)
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=85, optimize=True)
                buffer.seek(0)
                st.session_state.ai_avatar = buffer
                st.rerun()

        # Preview AI avatar in a nice display
        if st.session_state.ai_avatar is not None:
            col_av1, col_av2 = st.columns([1, 2])
            with col_av1:
                if isinstance(st.session_state.ai_avatar, str):
                    # It's an emoji character - display large
                    st.markdown(f"<div style='background-color: #f0f2f6; border-radius: 50%; width: 80px; height: 80px; display: flex; align-items: center; justify-content: center; font-size: 48px;'>{st.session_state.ai_avatar}</div>", unsafe_allow_html=True)
                else:
                    # It's an uploaded image
                    st.image(st.session_state.ai_avatar, width=80)
            with col_av2:
                st.write("**Current Avatar**")
                if isinstance(st.session_state.ai_avatar, str):
                    st.caption("Emoji character")
                else:
                    st.caption("Custom image")

        st.divider()

        # Language selection
        st.subheader(t["language"])
        selected_language = st.selectbox(
            t["choose_language"],
            options=list(language_instructions.keys()),
            index=list(language_instructions.keys()).index(st.session_state.language)
        )

        # Update state if language changed
        if selected_language != st.session_state.language:
            st.session_state.language = selected_language
            t = ui_translations[st.session_state.language]  # Update translations
            st.success(f"{t['language_changed']} {selected_language}!")
            st.rerun()

        st.divider()

        # Image Generator Mode Toggle
        st.subheader("🎨 Mode Selection")

        image_mode = st.toggle(
            "Image Generator Mode",
            value=st.session_state.image_generator_mode,
            help="Switch between chat mode and image generation mode"
        )

        if image_mode != st.session_state.image_generator_mode:
            st.session_state.image_generator_mode = image_mode
            if image_mode:
                st.success("Switched to Image Generator Mode!")
            else:
                st.success("Switched to Chat Mode!")
            st.rerun()

        st.divider()

        # AI Job/Role selection (only show in chat mode)
        if not st.session_state.image_generator_mode:
            st.subheader("AI Job")

            selected_job = st.selectbox(
                "Choose AI's role:",
                options=list(job_prompts.keys()),
                index=list(job_prompts.keys()).index(st.session_state.job),
                key="job_selector"
            )

            # Update state if job changed
            if selected_job != st.session_state.job:
                st.session_state.job = selected_job
                st.success(f"Switched to {selected_job} mode")

            st.caption(job_prompts[st.session_state.job])

            st.divider()

            # AI personality selection
            st.subheader(t["personality"])

        # Get personality names in current language
        personality_names = {
            "Friendly": t["friendly"],
            "Professional": t["professional"],
            "Humorous": t["humorous"]
        }

        selected_personality = st.selectbox(
            t["choose_personality"],
            options=list(personality_prompts.keys()),
            index=list(personality_prompts.keys()).index(st.session_state.personality),
            format_func=lambda x: f"{personality_icons[x]} {personality_names[x]}"
        )

        # Update state if personality changed
        if selected_personality != st.session_state.personality:
            st.session_state.personality = selected_personality
            st.success(f"{t['switched_to']} {personality_icons[selected_personality]} {personality_names[selected_personality]} {t['mode']}")

        # Display current personality description in selected language
        st.caption(personality_descriptions[st.session_state.language][st.session_state.personality])

        st.divider()

        # Audio Settings
        st.subheader("🔊 Audio Settings")

        # Auto-play TTS toggle
        auto_play_tts = st.toggle(
            "Auto-play AI responses",
            value=st.session_state.auto_play_tts,
            help="Automatically play audio for AI responses"
        )

        if auto_play_tts != st.session_state.auto_play_tts:
            st.session_state.auto_play_tts = auto_play_tts
            if auto_play_tts:
                if polly_client:
                    st.success("Audio enabled!")
                else:
                    st.warning("Audio enabled but AWS Polly not configured. Add AWS credentials to enable audio.")
            else:
                st.info("Audio disabled")

        # Voice selector for AWS Polly
        if polly_client:
            POLLY_VOICES = {
                "Joanna (Female, US)": "Joanna",
                "Matthew (Male, US)": "Matthew",
                "Ivy (Female, US Child)": "Ivy",
                "Joey (Male, US)": "Joey",
                "Kendra (Female, US)": "Kendra",
                "Amy (Female, British)": "Amy",
                "Brian (Male, British)": "Brian"
            }

            selected_voice = st.selectbox(
                "Voice Selection:",
                options=list(POLLY_VOICES.keys()),
                index=list(POLLY_VOICES.values()).index(st.session_state.selected_voice) if st.session_state.selected_voice in POLLY_VOICES.values() else 0,
                help="Select the voice for AI responses"
            )

            # Update session state if voice changed
            if POLLY_VOICES[selected_voice] != st.session_state.selected_voice:
                st.session_state.selected_voice = POLLY_VOICES[selected_voice]
                # Clear TTS cache when voice changes
                st.session_state.tts_audio = {}
                st.success(f"Voice changed to {selected_voice}")

        st.divider()

        # Theme selection
        st.subheader("🎨 Background Theme")

        theme_icons = {
            "Rainbow": "🌈",
            "Ocean": "🌊",
            "Sunset": "🌅",
            "Forest": "🌲",
            "Purple Dream": "💜",
            "Fire": "🔥",
            "Cool Blue": "❄️",
            "Neon": "⚡"
        }

        selected_theme = st.selectbox(
            "Choose your background theme:",
            options=list(themes.keys()),
            index=list(themes.keys()).index(st.session_state.theme),
            format_func=lambda x: f"{theme_icons[x]} {x}"
        )

        # Update state if theme changed
        if selected_theme != st.session_state.theme:
            st.session_state.theme = selected_theme
            st.success(f"Theme changed to {theme_icons[selected_theme]} {selected_theme}!")
            st.rerun()

        st.divider()

        # Clear chat history button
        if st.button(t["clear_chat"]):
            st.session_state.messages = []
            st.rerun()

        st.divider()

        # Display current configuration
        st.subheader(t["current_config"])
        st.write(f"**{t['model']}**: Google Gemini 2.5 Flash")
        st.write(f"**{t['language']}**: {st.session_state.language}")
        st.write(f"**{t['personality']}**: {personality_icons[st.session_state.personality]} {personality_names[st.session_state.personality]}")
        st.write(f"**{t['messages']}**: {len(st.session_state.messages)}")


    # Help dialog - must be defined outside sidebar
    if st.session_state.show_help:
        @st.dialog(t["how_to_use"])
        def show_help_dialog():
            st.markdown(t["instructions"])
            if st.button("Close", use_container_width=True):
                st.session_state.show_help = False
                st.rerun()

        show_help_dialog()
