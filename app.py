import streamlit as st
import os
import re
import sys
from io import StringIO
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Set page configuration
st.set_page_config(
    page_title="My Can Do Everything AI Assistant",
    page_icon="💬",
    layout="centered"
)

# Initialize session state FIRST
if "messages" not in st.session_state:
    st.session_state.messages = []

if "personality" not in st.session_state:
    st.session_state.personality = "Friendly"

if "language" not in st.session_state:
    st.session_state.language = "English"

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
        "title": "💬 My Can Do Everything AI Assistant",
        "caption": "Your versatile AI assistant - talk about literally anything",
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
        "title": "💬 我的万能 AI 助手",
        "caption": "您的多功能 AI 助手 - 无所不谈",
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
        "title": "💬 Mi Asistente AI Todoterreno",
        "caption": "Tu asistente AI versátil - habla de literalmente cualquier cosa",
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
        "title": "💬 Mon Assistant AI Polyvalent",
        "caption": "Votre assistant AI polyvalent - parlez de n'importe quoi",
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
        "title": "💬 Mein Alleskönner AI-Assistent",
        "caption": "Ihr vielseitiger AI-Assistent - sprechen Sie über buchstäblich alles",
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
        "title": "💬 私の万能AIアシスタント",
        "caption": "あなたの多用途AIアシスタント - 文字通り何でも話せます",
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
        "title": "💬 나의 만능 AI 어시스턴트",
        "caption": "당신의 다재다능한 AI 어시스턴트 - 문자 그대로 모든 것에 대해 이야기하세요",
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
        "title": "💬 Meu Assistente AI Versátil",
        "caption": "Seu assistente AI versátil - fale sobre literalmente qualquer coisa",
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
        "title": "💬 Мой Универсальный AI Ассистент",
        "caption": "Ваш универсальный AI ассистент - говорите буквально о чем угодно",
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
        "title": "💬 مساعدي الذكي الشامل",
        "caption": "مساعدك الذكي المتعدد الاستخدامات - تحدث عن أي شيء حرفياً",
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

# Define AI personality settings
personality_prompts = {
    "Friendly": "You are a warm and friendly AI assistant who chats like a friend. Use a kind tone, appropriate emojis, and make conversations relaxed and pleasant. Always understand the user's intent even if they make typos, spelling mistakes, or use incorrect words. Be forgiving and helpful. When showing Python code examples, always wrap them in ```python code blocks so they can be executed.",
    "Professional": "You are a rigorous and professional AI assistant who provides accurate and reliable advice. Use a formal tone, focus on logic and accuracy, and give detailed explanations. Understand user intent even with typos or unclear phrasing, and politely clarify if needed. When showing Python code examples, always wrap them in ```python code blocks so they can be executed.",
    "Humorous": "You are a relaxed and humorous AI assistant who makes chatting fun. Use a witty tone, make appropriate jokes, but ensure information accuracy. Don't worry about typos or mistakes - understand what the user means and maybe make a light joke about it! When showing Python code examples, always wrap them in ```python code blocks so they can be executed."
}

personality_icons = {
    "Friendly": "😊",
    "Professional": "🎯",
    "Humorous": "😄"
}

# Get current language translations
t = ui_translations[st.session_state.language]

# Page title
st.title(t["title"])
st.caption(t["caption"])

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
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # If assistant message contains code, show run button
        if message["role"] == "assistant" and "```python" in message["content"]:
            if st.button(t["run_code"], key=f"run_{st.session_state.messages.index(message)}"):
                code_results = extract_and_run_code(message["content"])
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

# User input
if prompt := st.chat_input(t["input_placeholder"]):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display assistant reply
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        try:
            # Build message list with personality and language settings
            system_message = {
                "role": "system",
                "content": f"{personality_prompts[st.session_state.personality]} {language_instructions[st.session_state.language]}"
            }

            messages_with_personality = [system_message] + [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ]

            # Call Groq API
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages_with_personality,
                stream=True,
                max_tokens=2048,
                temperature=0.7
            )

            # Stream output response
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    message_placeholder.markdown(full_response + "▌")

            # Display full response
            message_placeholder.markdown(full_response)

        except Exception as e:
            full_response = f"{t['error']} {str(e)}\n\n{t['check_api']}"
            message_placeholder.markdown(full_response)

        # Add assistant message to chat history
        st.session_state.messages.append({"role": "assistant", "content": full_response})

# Sidebar
with st.sidebar:
    st.header(t["settings"])

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

    # Display current personality description
    st.caption(personality_prompts[st.session_state.personality])

    st.divider()

    # Clear chat history button
    if st.button(t["clear_chat"]):
        st.session_state.messages = []
        st.rerun()

    st.divider()

    # Display current configuration
    st.subheader(t["current_config"])
    st.write(f"**{t['model']}**: llama-3.3-70b-versatile")
    st.write(f"**{t['language']}**: {st.session_state.language}")
    st.write(f"**{t['personality']}**: {personality_icons[st.session_state.personality]} {personality_names[st.session_state.personality]}")
    st.write(f"**{t['messages']}**: {len(st.session_state.messages)}")

    st.divider()

    # Usage instructions
    st.subheader(t["how_to_use"])
    st.markdown(t["instructions"])
