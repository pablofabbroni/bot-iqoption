from telethon.sync import TelegramClient

API_ID = 33556386
API_HASH = '1cb5333facf7aa801a7eea1eaf27ff29'
PHONE = '+543584845466'

client = TelegramClient('sesion_bot_iq', API_ID, API_HASH)
client.start(phone=PHONE)
print("Sesion creada correctamente!")
client.disconnect()