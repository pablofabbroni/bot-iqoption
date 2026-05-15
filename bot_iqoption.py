import asyncio
import re
import logging
import os
from datetime import datetime, timedelta
import pytz
import requests
from telethon import TelegramClient, events
from iqoptionapi.stable_api import IQ_Option
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# ==============================
# CONFIGURACION
# ==============================
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')
GROUP_LINK = os.getenv('GROUP_LINK', 'https://t.me/+W6a8NfSSR8w4YzJi')
NTFY_TOPIC = os.getenv('NTFY_TOPIC', 'senales-ptf-2026')

IQ_EMAIL = os.getenv('IQ_EMAIL', '')
IQ_PASSWORD = os.getenv('IQ_PASSWORD', '')
IQ_ACCOUNT_TYPE = os.getenv('IQ_ACCOUNT_TYPE', 'PRACTICE')  # PRACTICE = demo | REAL = real

MAX_MONTO = float(os.getenv('MAX_MONTO', '10'))        # Tope máximo por operación en demo
PORCENTAJE = float(os.getenv('PORCENTAJE', '0.05'))     # 5% del balance
MAX_MARTINGALE = int(os.getenv('MAX_MARTINGALE', '2'))    # Máximo 2 martingales
SEGUNDOS_ANTES = int(os.getenv('SEGUNDOS_ANTES', '3'))    # Entrar 3 segundos antes

ZONA_ARGENTINA = pytz.timezone('America/Argentina/Buenos_Aires')
ZONA_UTC = pytz.timezone('UTC')
# ==============================

logging.basicConfig(level=logging.INFO)

# Conexión IQ Option
iq = IQ_Option(IQ_EMAIL, IQ_PASSWORD)
iq.connect()
iq.change_balance(IQ_ACCOUNT_TYPE)

client = TelegramClient('sesion_bot_iq', API_ID, API_HASH)

def notificar(titulo, mensaje):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=mensaje.encode('utf-8', errors='replace'),
            headers={
                "Title": titulo,
                "Priority": "high",
                "Tags": "chart_with_upwards_trend",
                "Content-Type": "text/plain; charset=utf-8"
            }
        )
    except Exception as e:
        print(f"❌ Error ntfy: {e}")

def parsear_senal(texto):
    """Extrae los datos de la señal del mensaje de Telegram"""
    try:
        # Detectar tipo de mercado
        if 'OTC' in texto.upper():
            mercado = 'OTC'
        else:
            mercado = 'REAL'

        # Extraer par (ej: GBP / CHF o GBP/CHF)
        par_match = re.search(r'([A-Z]{3})\s*/\s*([A-Z]{3})', texto)
        if not par_match:
            return None
        par = par_match.group(1) + par_match.group(2)
        if mercado == 'OTC':
            par = par + '-OTC'

        # Detectar dirección
        if 'COMPRA' in texto.upper() or 'CALL' in texto.upper():
            direccion = 'call'
        elif 'VENTA' in texto.upper() or 'PUT' in texto.upper():
            direccion = 'put'
        else:
            return None

        # Extraer hora (ej: 10:15)
        hora_match = re.search(r'(\d{1,2}):(\d{2})', texto)
        if not hora_match:
            return None
        hora = int(hora_match.group(1))
        minuto = int(hora_match.group(2))

        # Extraer expiración en minutos (ej: 5M)
        exp_match = re.search(r'(\d+)M', texto.upper())
        expiracion = int(exp_match.group(1)) if exp_match else 5

        return {
            'par': par,
            'direccion': direccion,
            'hora': hora,
            'minuto': minuto,
            'expiracion': expiracion,
            'mercado': mercado
        }
    except Exception as e:
        print(f"❌ Error parseando señal: {e}")
        return None

def calcular_monto():
    """Calcula el 5% del balance con tope máximo"""
    try:
        balance = iq.get_balance()
        monto = round(balance * PORCENTAJE, 2)
        monto = min(monto, MAX_MONTO)
        monto = max(monto, 1)  # Mínimo $1
        return monto
    except:
        return 1

async def esperar_hasta(hora, minuto):
    """Espera hasta 3 segundos antes de la hora de entrada"""
    ahora = datetime.now(ZONA_ARGENTINA)
    entrada = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)

    # Si la hora ya pasó hoy, programar para mañana
    if entrada <= ahora:
        entrada += timedelta(days=1)

    # Restar 3 segundos
    entrada_real = entrada - timedelta(seconds=SEGUNDOS_ANTES)

    espera = (entrada_real - ahora).total_seconds()
    if espera > 0:
        print(f"⏳ Esperando {espera:.0f} segundos para operar a las {hora:02d}:{minuto:02d}...")
        await asyncio.sleep(espera)

async def operar(senal, monto, intento=1):
    """Ejecuta la operación en IQ Option"""
    par = senal['par']
    direccion = senal['direccion']
    expiracion = senal['expiracion']

    print(f"🎯 Operando: {par} {direccion.upper()} ${monto} exp:{expiracion}min (intento {intento})")
    notificar(
        f"🎯 Operando {'CALL 📈' if direccion == 'call' else 'PUT 📉'}",
        f"{par} | ${monto} | Exp: {expiracion}min | Intento {intento}"
    )

    try:
        check, id_operacion = iq.buy(monto, par, direccion, expiracion)
        if not check:
            print(f"❌ Error al colocar operación")
            notificar("❌ Error", f"No se pudo operar {par}")
            return

        # Esperar resultado
        print(f"⏳ Esperando resultado de operación {id_operacion}...")
        await asyncio.sleep(expiracion * 60 + 5)

        resultado = iq.check_win_v3(id_operacion)
        ganancia = resultado

        if ganancia > 0:
            print(f"✅ GANÓ ${ganancia}")
            notificar("✅ GANÓ!", f"{par} | Ganancia: ${ganancia:.2f}")
        else:
            print(f"❌ PERDIÓ en intento {intento}")
            if intento < MAX_MARTINGALE + 1:
                nuevo_monto = round(monto * 2, 2)
                nuevo_monto = min(nuevo_monto, MAX_MONTO * 2)
                notificar(f"❌ Perdió - Martingale {intento}", f"{par} | Próxima entrada: ${nuevo_monto}")
                await operar(senal, nuevo_monto, intento + 1)
            else:
                notificar("❌ Perdió Martingale final", f"{par} | Se agotaron los intentos")

    except Exception as e:
        print(f"❌ Error en operación: {e}")
        notificar("❌ Error", str(e))

async def main():
    await client.start(phone=PHONE)
    print("✅ Bot IQ Option conectado y escuchando señales...")
    notificar("🤖 Bot iniciado", "Escuchando señales de Telegram...")

    group = await client.get_entity(GROUP_LINK)

    @client.on(events.NewMessage(chats=group))
    async def handler(event):
        texto = event.message.message
        if not texto:
            return

        print(f"\n📨 Mensaje recibido:\n{texto}\n")

        # Verificar si es una señal válida
        if 'SEÑAL' not in texto.upper() and 'COMPRA' not in texto.upper() and 'VENTA' not in texto.upper():
            return

        senal = parsear_senal(texto)
        if not senal:
            print("⚠️ No se pudo parsear la señal")
            return

        print(f"✅ Señal parseada: {senal}")
        notificar(
            "📊 Nueva señal detectada",
            f"{senal['par']} | {'CALL 📈' if senal['direccion'] == 'call' else 'PUT 📉'} | {senal['hora']:02d}:{senal['minuto']:02d} | {senal['mercado']}"
        )

        # Esperar hasta 3 segundos antes de la entrada
        await esperar_hasta(senal['hora'], senal['minuto'])

        # Calcular monto
        monto = calcular_monto()

        # Operar
        await operar(senal, monto)

    await client.run_until_disconnected()

with client:
    client.loop.run_until_complete(main())
