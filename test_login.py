from playwright.sync_api import sync_playwright
import time

def test_portal_login():
    with sync_playwright() as p:
        print("\n--- Browser Start Ho Raha Hai ---")
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context()
        page = context.new_page()

        print("--- Website Open Ho Rahi Hai ---")
        page.goto("https://student.icampuserp.in/Login.aspx")

        # Captcha Image ka link nikalna
        captcha_url = page.locator("img[id*='CaptchaImage']").get_attribute("src")
        if captcha_url and captcha_url.startswith("/"):
            captcha_url = "https://student.icampuserp.in" + captcha_url

        print("\n=======================================================")
        print("CAPTCHA URL (Ise copy karein): \n" + str(captcha_url))
        print("=======================================================\n")
        
        # User se details lena
        college = input("College Code likhein (jaise UCER): ")
        user_id = input("Student ID likhein: ")
        password = input("Password likhein: ")
        captcha_code = input("Captcha Code likhein (jo image me dikha): ")

        print("\n--- Form Fill Ho Raha Hai ---")
        page.select_option("select[name='ddl_College']", college)
        page.fill("input[name='UserId_Box']", user_id)
        page.fill("input[name='PasswordBox']", password)
        page.fill("input[name='CaptchaCodeTextBox']", captcha_code)
        
        print("--- Sign In Button Daba Rahe Hain ---")
        page.click("input[name='btnLogin']")
        
        # 5 second wait karte hain login process ke liye
        time.sleep(5)

        # Check karte hain login hua ya nahi
        if "Dashboard" in page.content() or "Home" in page.content():
            print("\n✅ LOGIN SUCCESSFUL!")
            context.storage_state(path="session.json")
            print("Session save ho gaya 'session.json' me.")
        else:
            print("\n❌ LOGIN FAILED! Captcha galat ho sakta hai.")
            page.screenshot(path="error.png")
            print("Error screenshot 'error.png' me save kar diya.")

        browser.close()

test_portal_login()
