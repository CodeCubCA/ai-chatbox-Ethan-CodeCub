import streamlit as st
import os
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Set page configuration
st.set_page_config(
    page_title="My Everything AI Assistant",
    page_icon="💬",
    layout="centered"
)

# Page title
st.title("💬 My Everything AI Assistant")
st.caption("Your versatile AI assistant - talk about literally anything")

# Welcome message
st.info("👋 Welcome! I'm your Everything AI Assistant. I can discuss any topic with you: learning, work, life, entertainment, technology, arts, and more. Whatever you want to chat about, I'm here to help!")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "personality" not in st.session_state:
    st.session_state.personality = "Friendly"

# Define AI personality settings
personality_prompts = {
    "Friendly": "You are a warm and friendly AI assistant who chats like a friend. Use a kind tone, appropriate emojis, and make conversations relaxed and pleasant.",
    "Professional": "You are a rigorous and professional AI assistant who provides accurate and reliable advice. Use a formal tone, focus on logic and accuracy, and give detailed explanations.",
    "Humorous": "You are a relaxed and humorous AI assistant who makes chatting fun. Use a witty tone, make appropriate jokes, but ensure information accuracy."
}

personality_icons = {
    "Friendly": "😊",
    "Professional": "🎯",
    "Humorous": "😄"
}

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
if prompt := st.chat_input("Type your message here..."):
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
            # Build message list with personality setting
            system_message = {
                "role": "system",
                "content": personality_prompts[st.session_state.personality]
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
            full_response = f"Error: {str(e)}\n\nPlease check if your API key is configured correctly."
            message_placeholder.markdown(full_response)

        # Add assistant message to chat history
        st.session_state.messages.append({"role": "assistant", "content": full_response})

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")

    # AI personality selection
    st.subheader("🎭 AI Personality")
    selected_personality = st.selectbox(
        "Choose AI's reply style:",
        options=list(personality_prompts.keys()),
        index=list(personality_prompts.keys()).index(st.session_state.personality),
        format_func=lambda x: f"{personality_icons[x]} {x}"
    )

    # Update state if personality changed
    if selected_personality != st.session_state.personality:
        st.session_state.personality = selected_personality
        st.success(f"Switched to {personality_icons[selected_personality]} {selected_personality} mode!")

    # Display current personality description
    st.caption(personality_prompts[st.session_state.personality])

    st.divider()

    # Clear chat history button
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

    st.divider()

    # Display current configuration
    st.subheader("📊 Current Config")
    st.write(f"**Model**: llama-3.3-70b-versatile")
    st.write(f"**AI Personality**: {personality_icons[st.session_state.personality]} {st.session_state.personality}")
    st.write(f"**Messages**: {len(st.session_state.messages)}")

    st.divider()

    # Usage instructions
    st.subheader("📖 How to Use")
    st.markdown("""
    1. 💬 Type your question in the input box
    2. 🎭 Select AI personality style
    3. 🤖 AI will reply in real-time
    4. 🗑️ Click "Clear Chat History" to restart
    5. ✨ Discuss any topic you want
    """)
