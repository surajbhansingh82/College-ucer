import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from tabulate import tabulate
import os

active_sessions = {}

# ... (get_captcha_image — JESA THA WESA HI RAHEGA)

# ✅ ADD #1: cleanup_session() — bot.py logout me use hoga
async def cleanup_session(chat_id):
    """Browser + Playwright memory safely free karo"""
    if chat_id in active_sessions:
        sess = active_sessions.pop(chat_id)
        try:
            await sess["browser"].close()
        except Exception:
            pass
        try:
            await sess["p"].stop()
        except Exception:
            pass


# ✅ ADD #2: submit_login ke START me — agar purana session ho toh pehle cleanup
async def submit_login(chat_id, user_id, password, captcha_text):
    # ✅ NAYA: duplicate browser prevent karo (memory leak fix)
    if chat_id in active_sessions:
        old_page = active_sessions[chat_id].get("page")
        # Purana session free karo (agar get_captcha_image ne banaya tha)
        try:
            await active_sessions[chat_id]["browser"].close()
            await active_sessions[chat_id]["p"].stop()
        except Exception:
            pass
        del active_sessions[chat_id]

    session = active_sessions.get(chat_id)
    if not session:
        return False, "Session time out. Dobara /start karein."

    # ... (BAKI CODE JESA THA WESA HI RAHEGA)


async def get_captcha_image(chat_id, college):
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context(viewport={'width': 1280, 'height': 800}) 
    page = await context.new_page()
    try:
        await page.goto("https://student.icampuserp.in/Login.aspx", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        await page.select_option("select[name='ddl_College']", value=college)
        await page.wait_for_timeout(4000) 
        captcha_image = page.locator("img[id*='CaptchaImage']").first
        img_path = f"captcha_{chat_id}.png"
        await captcha_image.screenshot(path=img_path)
        
        # Memory mein save kar rahe hain
        active_sessions[chat_id] = {"p": p, "browser": browser, "context": context, "page": page}
        return img_path
    except Exception as e:
        print(f"Error: {e}")
        await browser.close()
        await p.stop()
        return None

async def submit_login(chat_id, user_id, password, captcha_text):
    session = active_sessions.get(chat_id)
    if not session: return False, "Session time out. Dobara /start karein."
    page, context, browser, p = session["page"], session["context"], session["browser"], session["p"]
    try:
        await page.fill("input[name='UserId_Box']", user_id)
        await page.locator("input[name='PasswordBox']").press_sequentially(password, delay=50)
        await page.fill("input[name='CaptchaCodeTextBox']", captcha_text)
        await page.locator("input[name='btnLogin']").click(force=True)
        
        await page.wait_for_timeout(10000) 
        
        content = await page.content()
        if "Sign out" in content or "MAIN NAVIGATION" in content:
            # SUCCESS! Browser ko band NAHI kar rahe, memory mein save kar rahe hain
            result = True, "✅ LOGIN SUCCESSFUL! Ab aap direct data check kar sakte hain."
        else:
            await browser.close()
            await p.stop()
            del active_sessions[chat_id]
            result = False, "❌ LOGIN FAILED! Captcha ya password galat tha."
    except Exception as e:
        await browser.close()
        await p.stop()
        if chat_id in active_sessions: del active_sessions[chat_id]
        result = False, f"Error: {e}"
    return result

async def check_session(chat_id):
    if chat_id not in active_sessions:
        return False, "❌ Aap logged in nahi hain. Kripya Login karein."
    page = active_sessions[chat_id]["page"]
    try:
        content = await page.content()
        if "Sign out" in content or "MAIN NAVIGATION" in content:
            return True, "✅ Aap successfully logged in hain! Portal live chal raha hai."
        else:
            return False, "❌ Aapka session expire ho gaya hai. Kripya dobara Login karein."
    except:
        return False, "❌ Error checking session."

def parse_html_table(html):
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table')
    if not tables: return None
    main_table = max(tables, key=lambda t: len(t.get_text()))
    rows = main_table.find_all('tr')
    data = []
    for row in rows:
        cols = [col.get_text(strip=True) for col in row.find_all(['td', 'th'])]
        if cols: data.append(cols)
    if not data: return None
    return tabulate(data, headers="firstrow", tablefmt="grid")

async def fetch_data(chat_id, action, sub_action=None):
    if chat_id not in active_sessions: return "SESSION_EXPIRED"
    
    # Wahi live page use kar rahe hain jo login ke waqt tha
    page = active_sessions[chat_id]["page"]
    
    try:
        content = await page.content()
        if "Sign out" not in content and "MAIN NAVIGATION" not in content:
            return "SESSION_EXPIRED"
            
        link_text = ""
        if action == 'attendance':
            if sub_action == 'history': link_text = "Attendance History"
            elif sub_action == 'day_wise': link_text = "Day Wise"
            elif sub_action == 'summary': link_text = "Summary - Till Date"
            else: link_text = "Attendance"
        elif action == 'marks': link_text = "Sessional Marks"
        elif action == 'fees': link_text = "Fee Information" 
        elif action == 'library': link_text = "Library"

        # Javascript se link click kar rahe hain (100% working)
        js_click = f"""
        () => {{
            const links = Array.from(document.querySelectorAll('a'));
            const link = links.find(l => l.textContent.trim() === '{link_text}' || l.textContent.trim().includes('{link_text}'));
            if (link) {{
                link.click();
                return true;
            }}
            return false;
        }}
        """
        clicked = await page.evaluate(js_click)
        if not clicked:
            return f"ERROR_SCREENSHOT|Link '{link_text}' nahi mila dashboard par."
            
        await page.wait_for_timeout(6000) 

        if action == 'marks':
            try:
                dropdown = page.locator("select").first
                if await dropdown.count() > 0:
                    await dropdown.select_option(index=1) 
                    await page.wait_for_timeout(1500)
                    btn = page.locator("input[type='submit'], input[value*='View'], button:has-text('View')").first
                    if await btn.count() > 0:
                        await btn.click(force=True)
                        await page.wait_for_timeout(5000)
            except Exception as e:
                print(f"Marks error: {e}")

        html = await page.content()
        table_text = parse_html_table(html)
        
        if table_text:
            result = f"✅ **{action.capitalize()} Data:**\n\n<pre>{table_text}</pre>"
        else:
            soup = BeautifulSoup(html, 'html.parser')
            for script in soup(["script", "style"]): script.extract()
            text = soup.get_text(separator='\n', strip=True)
            
            # Sidebar text ko hata rahe hain taaki sirf data dikhe
            lines = text.split('\n')
            filtered = [l for l in lines if l.strip() and not any(x in l for x in ["MAIN NAVIGATION", "Dashboard", "Attendance", "Fee Information", "Sessional Marks", "Library", "SMS Inbox", "Placement", "Student Info", "Change Password", "Log Out"])]
            clean_text = "\n".join(filtered) if filtered else text
            
            if "Welcome to United Group" in text:
                result = "ERROR_SCREENSHOT|Landing Page load ho gaya."
            else:
                result = f"✅ **{action.capitalize()} Data:**\n\n{clean_text[:3500]}"
                
        # Data nikalne ke baad wapas Dashboard par aa rahe hain
        try:
            js_back = """
            () => {
                const links = Array.from(document.querySelectorAll('a'));
                const link = links.find(l => l.textContent.trim() === 'Dashboard');
                if (link) link.click();
            }
            """
            await page.evaluate(js_back)
            await page.wait_for_timeout(3000)
        except:
            pass
            
        return result
            
    except Exception as e:
        try:
            await page.screenshot(path=f"error_{chat_id}.png", full_page=True)
        except:
            pass
        return f"ERROR_SCREENSHOT|{str(e)}"