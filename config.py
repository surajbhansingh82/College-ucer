import os
from dotenv import load_dotenv

# .env file load karega (agar local me use kar rahe hain to)
load_dotenv()

# Yahan aapko apna Bot Token daalna hoga
BOT_TOKEN = os.getenv("BOT_TOKEN", "YAHAN_APNA_BOTFATHER_WALA_TOKEN_DALEIN")

# Portal URL
BASE_URL = "https://student.icampuserp.in/Login.aspx"