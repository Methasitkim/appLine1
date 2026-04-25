from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

app = Flask(__name__)

# ใส่ค่าของคุณตรงนี้
LINE_CHANNEL_ACCESS_TOKEN = "ใส่ Channel Access Token ของคุณ"
LINE_CHANNEL_SECRET = "ใส่ Channel Secret ของคุณ"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# เชื่อม Google Sheets
def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    return client.open("FinBot").sheet1

# แยกหมวดหมู่จากข้อความ
def get_category(text):
    food = ["กาแฟ","ข้าว","อาหาร","กิน","ชา","ขนม"]
    transport = ["รถ","แท็กซี่","bts","mrt","น้ำมัน","grab"]
    for word in food:
        if word in text: return "อาหาร"
    for word in transport:
        if word in text: return "เดินทาง"
    return "อื่นๆ"

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    
    # รูปแบบ: "กาแฟ 60" หรือ "เงินเดือน +15000"
    parts = text.split()
    if len(parts) == 2:
        try:
            name = parts[0]
            amount = float(parts[1].replace("+",""))
            is_income = "+" in parts[1]
            category = "รายรับ" if is_income else get_category(name)
            date = datetime.now().strftime("%d/%m/%Y %H:%M")
            
            # บันทึกลง Google Sheets
            sheet = get_sheet()
            sheet.append_row([date, name, amount, category])
            
            emoji = "💰" if is_income else "💸"
            reply = f"{emoji} บันทึกแล้ว!\n{name} = {amount:.0f} บาท\nหมวด: {category}"
        except:
            reply = "พิมพ์ให้ถูกรูปแบบนะครับ\nเช่น: กาแฟ 60\nหรือ: เงินเดือน +15000"
    elif text == "สรุป":
        sheet = get_sheet()
        rows = sheet.get_all_values()[1:]
        total_out = sum(float(r[2]) for r in rows if r[3] != "รายรับ")
        total_in = sum(float(r[2]) for r in rows if r[3] == "รายรับ")
        reply = f"📊 สรุปของคุณ\nรายรับ: {total_in:.0f} บาท\nรายจ่าย: {total_out:.0f} บาท\nคงเหลือ: {total_in-total_out:.0f} บาท"
    else:
        reply = "วิธีใช้:\nบันทึกจ่าย → กาแฟ 60\nบันทึกรับ → เงินเดือน +15000\nดูสรุป → พิมพ์ สรุป"
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    app.run(port=5000)