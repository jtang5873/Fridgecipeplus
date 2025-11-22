# app.py

import os
import base64
import json

import streamlit as st
from openai import OpenAI

# ----------------- 基本页面设置 -----------------
st.set_page_config(
    page_title="Fridgecipe+",
    page_icon="🥗",
    layout="centered",
)

# 从 Streamlit Secrets 中读取 API key
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", None)

client = None
if OPENAI_API_KEY is None:
    st.warning("⚠️ 请在 Streamlit secrets 中设置 OPENAI_API_KEY 才能调用 GPT-4o。")
else:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    client = OpenAI()

# DEBUG：在左侧栏显示 key 是否加载成功
st.sidebar.write("DEBUG: API key loaded? ", OPENAI_API_KEY is not None)

# ----------------- 一点 CSS 美化 -----------------
st.markdown(
    """
    <style>
        .main {
            background: linear-gradient(135deg, #e0f2fe, #fef9c3);
        }
        .card {
            background-color: #ffffff;
            padding: 1.5rem;
            border-radius: 1rem;
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.15);
            margin-bottom: 1rem;
        }
        .ingredients-badge {
            display: inline-block;
            padding: 0.25rem 0.6rem;
            margin: 0.15rem;
            border-radius: 999px;
            background-color: #eff6ff;
            color: #1e3a8a;
            font-size: 0.85rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------- 工具函数 -----------------


def image_file_to_base64(uploaded_file) -> str:
    """
    把 Streamlit 上传的文件 / camera_input 输出转成 base64 字符串。
    注意用 getvalue()，避免 read() 读到空。
    """
    bytes_data = uploaded_file.getvalue()
    return base64.b64encode(bytes_data).decode("utf-8")


def detect_ingredients_with_gpt(image_file):
    """
    使用 GPT-4o-mini 的视觉能力，从冰箱照片中识别食材。
    返回食材列表 list[str]，并在页面上显示模型原始输出以便 debug。
    """
    if client is None:
        st.error("❌ OpenAI client 未初始化，请检查 OPENAI_API_KEY。")
        return []

    base64_img = image_file_to_base64(image_file)
    image_data_url = f"data:image/png;base64,{base64_img}"

    system_prompt = (
        "You are an AI that inspects a photo of the inside of a refrigerator "
        "and lists visible food ingredients. "
        "Return ONLY a JSON array of short, lowercase ingredient names in English, "
        "for example: [\"milk\", \"eggs\", \"lettuce\"]."
    )

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Identify the ingredients you can see in this fridge photo.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data_url},
                        },
                    ],
                },
            ],
            temperature=0.2,
        )
    except Exception as e:
        st.error(f"调用 OpenAI 识别食材时出错：{e}")
        return []

    # 对于 vision 输出，message.content 可能是一个内容块列表
    msg_content = completion.choices[0].message.content

    if isinstance(msg_content, list):
        raw_parts = []
        for part in msg_content:
            # 新版 SDK 中 text 内容通常在 part.text 或 str(part)
            text = getattr(part, "text", None)
            if text is None:
                text = str(part)
            raw_parts.append(text)
        raw = "\n".join(raw_parts)
    else:
        raw = msg_content or ""

    # 在页面显示原始输出以便调试
    st.write("🛠️ DEBUG 模型原始输出：", raw)

    # 先尝试从中抽取 JSON 数组
    ingredients = []
    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        json_str = raw[start:end]
        ingredients = json.loads(json_str)
        ingredients = [
            str(i).strip().lower() for i in ingredients if str(i).strip()
        ]
    except Exception:
        # JSON 解析失败时，退回到简单切分
        parts = raw.replace("\n", ",").split(",")
        ingredients = [
            p.strip(" -•").lower()
            for p in parts
            if p.strip()
        ]

    # 去掉空字符串
    ingredients = [i for i in ingredients if i]

    return ingredients


def generate_recipes_with_gpt(ingredients, servings=2):
    """
    使用文本大模型，根据食材生成几道简单菜谱。
    返回 Markdown 字符串。
    """
    if client is None:
        return "⚠️ OpenAI client 未初始化，请检查 OPENAI_API_KEY。"

    ing_str = ", ".join(ingredients)

    prompt = f"""
You are an AI cooking assistant. A user has the following ingredients in their fridge:

{ing_str}

Please create 3–4 simple recipes using mostly these ingredients.

For EACH recipe, provide:
1. Recipe name (English)
2. Short description (1–2 sentences)
3. Ingredients list with approximate amounts
4. Step-by-step instructions (4–8 short steps)
5. A short note about how this recipe helps reduce food waste.

Write everything in clear English, beginner-friendly, formatted in Markdown.
Assume about {servings} servings per recipe.
"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful cooking assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
        )
    except Exception as e:
        return f"调用 OpenAI 生成菜谱时出错：{e}"

    msg_content = completion.choices[0].message.content

    if isinstance(msg_content, list):
        # 纯文本输出一般只会有一个 text 块，这里做个保险
        texts = []
        for part in msg_content:
            text = getattr(part, "text", None)
            if text is None:
                text = str(part)
            texts.append(text)
        text = "\n".join(texts)
    else:
        text = msg_content or ""

    return text


# ----------------- Streamlit 页面布局 -----------------

st.markdown('<div class="card">', unsafe_allow_html=True)
st.title("Fridgecipe+ 🥗")
st.write(
    "Upload or take a photo of your fridge, and let AI detect ingredients and suggest recipes.\n"
    "上传或拍下你的冰箱照片，让 AI 帮你认出食材并生成菜谱（顺便减少食物浪费 🌍）。"
)
st.markdown("</div>", unsafe_allow_html=True)

tab_upload, tab_camera = st.tabs(["📁 Upload Image", "📷 Take Photo"])

uploaded_image = None

with tab_upload:
    file = st.file_uploader(
        "Upload a photo of the inside of your fridge (JPG/PNG)",
        type=["jpg", "jpeg", "png"],
    )
    if file is not None:
        uploaded_image = file
        st.image(file, caption="Uploaded image", use_column_width=True)

with tab_camera:
    cam = st.camera_input("Take a photo with your camera")
    if cam is not None:
        uploaded_image = cam
        st.image(cam, caption="Captured image", use_column_width=True)

servings = st.slider("Number of servings (每份人数)", 1, 6, 2)

if uploaded_image is None:
    st.info("👆 请先上传或拍一张冰箱照片。")
else:
    if st.button("✨ Analyze fridge & generate recipes"):
        with st.spinner("Analyzing image and detecting ingredients..."):
            ingredients = detect_ingredients_with_gpt(uploaded_image)

        if not ingredients:
            st.error("😢 没有成功识别出食材，可以换一张更清晰的照片试试。")
        else:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("Detected ingredients / 检测到的食材")
            for ing in ingredients:
                st.markdown(
                    f'<span class="ingredients-badge">{ing}</span>',
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

            with st.spinner("Cooking up recipe ideas with AI..."):
                recipes_md = generate_recipes_with_gpt(
                    ingredients, servings=servings
                )

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("Recipe suggestions 🍽️")
            st.markdown(recipes_md)
            st.markdown("</div>", unsafe_allow_html=True)

