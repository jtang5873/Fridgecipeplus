import streamlit as st
import openai
import base64
import json
from io import BytesIO

# ------------ 基本设置 ------------
st.set_page_config(
    page_title="Fridgecipe+",
    page_icon="🥗",
    layout="centered"
)

# 推荐：在 Streamlit Cloud 用 st.secrets 管理 API Key
# 在本地调试你也可以用环境变量：export OPENAI_API_KEY="xxx"
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", None)

if OPENAI_API_KEY is None:
    st.warning("⚠️ 请在 Streamlit secrets 或环境变量中设置 OPENAI_API_KEY 才能调用 GPT-4o。")
else:
    openai.api_key = OPENAI_API_KEY

# ------------ 一点点 CSS 美化 ------------
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

# ------------ 工具函数：图片 → base64 ------------
def image_file_to_base64(image_file) -> str:
    """把上传的文件或 camera_input 输出转成 base64 字符串"""
    if hasattr(image_file, "read"):
        bytes_data = image_file.read()
    else:
        bytes_data = image_file.getvalue()
    return base64.b64encode(bytes_data).decode("utf-8")


# ------------ 调用 GPT-4o：识别食材 ------------
def detect_ingredients_with_gpt(image_file):
    """
    使用 GPT-4o 的视觉能力，从冰箱照片中识别食材。
    返回食材列表 list[str]。
    """
    if OPENAI_API_KEY is None:
        return []

    base64_img = image_file_to_base64(image_file)

    system_prompt = (
        "You are a helpful AI that inspects a photo of the inside of a refrigerator "
        "or kitchen and lists visible food ingredients. "
        "Return ONLY a JSON array of short, lowercase ingredient names in English, "
        "for example: [\"milk\", \"eggs\", \"lettuce\"]. No explanations."
    )

    user_text = "Here is the photo. Identify the ingredients you can see."

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_img}"
                        },
                    },
                ],
            },
        ],
        temperature=0.2,
    )

    raw = response.choices[0].message["content"]
    # 模型已经被要求只输出 JSON，如果不放心可以多一层 try/except
    try:
        ingredients = json.loads(raw)
        # 确保是字符串列表
        ingredients = [str(x).strip() for x in ingredients if str(x).strip()]
    except Exception:
        # fallback：简单按逗号切一下
        ingredients = [x.strip() for x in raw.split(",") if x.strip()]

    return ingredients


# ------------ 调用 GPT：根据食材生成菜谱 ------------
def generate_recipes_with_gpt(ingredients, servings=2):
    """
    使用文本大模型，根据食材生成几道简单菜谱。
    返回一个 Markdown 字符串。
    """
    if OPENAI_API_KEY is None:
        return "⚠️ 没有检测到 OPENAI_API_KEY。"

    ing_str = ", ".join(ingredients)

    prompt = f"""
You are an AI cooking assistant. A user has the following ingredients in their fridge:

{ing_str}

Please create 3–4 simple recipes using mostly these ingredients.

For EACH recipe, provide:
1. Recipe name (in English)
2. Short description (1–2 sentences)
3. Ingredients list with approximate amounts
4. Step-by-step instructions (4–8 short steps)
5. A short note about how this recipe helps reduce food waste.

Write everything in clear English, beginner-friendly, formatted in Markdown.
Assume about {servings} servings per recipe.
"""

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful cooking assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
    )

    text = response.choices[0].message["content"]
    return text


# ------------ 页面布局开始 ------------
st.markdown('<div class="card">', unsafe_allow_html=True)
st.title("Fridgecipe+ 🥗")
st.write(
    "Upload or take a photo of your fridge, and let AI detect ingredients and suggest recipes.\n"
    "上传或拍下你的冰箱照片，让 AI 帮你认出食材并生成菜谱（顺便减少食物浪费 🌍）。"
)
st.markdown('</div>', unsafe_allow_html=True)

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
            st.markdown('</div>', unsafe_allow_html=True)

            with st.spinner("Cooking up recipe ideas with AI..."):
                recipes_md = generate_recipes_with_gpt(ingredients, servings=servings)

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("Recipe suggestions 🍽️")
            st.markdown(recipes_md)
            st.markdown('</div>', unsafe_allow_html=True)
