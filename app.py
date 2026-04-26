import os
import json
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds_json = json.loads(os.environ.get("GOOGLE_CREDENTIALS"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    return client.open("appLine1").sheet1

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

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text.strip()
    parts = text.split()
    print(f"DEBUG: text='{text}' parts={parts} len={len(parts)}")
    if len(parts) >= 2:
        parts = [parts[0], parts[-1]]
        try:
            name = parts[0]
            amount_str = parts[1].replace("+","").strip()
            print(f"DEBUG: name='{name}' amount_str='{amount_str}'")
            amount = float(amount_str)
            is_income = "+" in parts[1]
            category = "รายรับ" if is_income else get_category(name)
            date = datetime.now().strftime("%d/%m/%Y %H:%M")
            sheet = get_sheet()
            sheet.append_row([date, name, amount, category])
            emoji = "💰" if is_income else "💸"
            reply_text = f"{emoji} บันทึกแล้ว!\n{name} = {amount:.0f} บาท\nหมวด: {category}"
        except Exception as e:
            print(f"DEBUG error: {e}")
            reply_text = "พิมพ์ให้ถูกรูปแบบนะครับ\nเช่น: กาแฟ 60\nหรือ: เงินเดือน +15000"
    elif text == "ลบ":
        try:
            sheet = get_sheet()
            rows = sheet.get_all_values()
            if len(rows) <= 1:
                reply_text = "ไม่มีรายการให้ลบครับ"
            else:
                last_row = rows[-1]
                sheet.delete_rows(len(rows))
                reply_text = f"🗑️ ลบรายการล่าสุดแล้ว!\n{last_row[1]} = {last_row[2]} บาท\nหมวด: {last_row[3]}"
        except Exception as e:
            print(f"DEBUG error: {e}")
        reply_text = "เกิดข้อผิดพลาด ลองใหม่นะครับ"
    elif text == "สรุป":
        sheet = get_sheet()
        rows = sheet.get_all_values()[1:]
        total_out = sum(float(r[2]) for r in rows if r[3] != "รายรับ")
        total_in = sum(float(r[2]) for r in rows if r[3] == "รายรับ")
        reply_text = f"📊 สรุปของคุณ\nรายรับ: {total_in:.0f} บาท\nรายจ่าย: {total_out:.0f} บาท\nคงเหลือ: {total_in-total_out:.0f} บาท"
    else:
        reply_text = "วิธีใช้:\nบันทึกจ่าย → กาแฟ 60\nบันทึกรับ → เงินเดือน +15000\nดูสรุป → พิมพ์ สรุป"

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))