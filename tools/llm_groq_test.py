from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(model="llama-3.3-70b-versatile")
print(llm.invoke("你好，請用繁體中文介紹你自己"))