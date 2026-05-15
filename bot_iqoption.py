import asyncio
import re
import logging
from datetime import datetime, timedelta
import pytz
import requests
from telethon import TelegramClient, events
from iqoptionapi.stable_api import IQ_Option

# ==============================
# CONFIGURACION
# ==============================
API_ID = 33556386
API_HASH = '1cb5333facf7aa801a7eea1eaf27ff29'
PHONE = '+543584845466'
GROUP_LINK = 'https://t.me/+W6a8NfSSR8w4YzJi'
NTFY_TOPIC = 'senales-ptf-2026'

IQ_EMAIL = 'pablofabbroni@gmail.com'
IQ_PASSWORD = 'Cabrera1798'
IQ_ACCOUNT_TYPE = 'PRACTICE'  # PRACTICE = demo | REAL = real

MAX_MONTO = 10        # Tope máximo por operación en demo
PORCENTAJE = 0.05     # 5% del balance
MAX_MARTINGALE = 2    # Máximo 2 martingales
SEGUNDOS_ANTES = 3    # Entrar 3 segundos antes

ZONA_ARGENTINA = pytz.timezone('America/Argentina/Buenos_Aires')
# ==============================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

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
            },
            timeout=10
        )
        log.info(f"Notificacion enviada: {titulo}")
    except Exception as e:
        log.error(f"Error ntfy: {e}")

def conectar_iq():
    log.info("Conectando a IQ Option...")
    iq = IQ_Option(IQ_EMAIL, IQ_PASSWORD)
    check, reason = iq.connect()
    if check:
        log.info("Conectado a IQ Option exitosamente")
        iq.change_balance(IQ_ACCOUNT_TYPE)
        balance = iq.get_balance()
        log.info(f"Balance: ${balance}")
        notificar("Bot IQ conectado", f"Balance demo: ${balance}")
        return iq
    else:
        log.error(f"Error IQ Option: {reason}")
        notificar("Error IQ Option", str(reason))
        return None

def parsear_senal(texto):
    try:
        if 'OTC' in texto.upper():
            mercado = 'OTC'
        else:
            mercado = 'REAL'

        par_match = re.search(r'([A-Z]{3})\s*/\s*([A-Z]{3})', texto)
        if not par_match:
            return None
        par = par_match.group(1) + par_match.group(2)
        if mercado == 'OTC':
            par = par + '-OTC'

        if 'COMPRA' in texto.upper() or 'CALL' in texto.upper():
            direccion = 'call'
        elif 'VENTA' in texto.upper() or 'PUT' in texto.upper():
            direccion = 'put'
        else:
            return None

        hora_match = re.search(r'(\d{1,2}):(\d{2})', texto)
        if not hora_match:
            return None
        hora = int(hora_match.group(1))
        minuto = int(hora_match.group(2))

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
        log.error(f"Error parseando senal: {e}")
        return None

def calcular_monto(iq):
    try:
        balance = iq.get_balance()
        monto = round(balance * PORCENTAJE, 2)
        monto = min(monto, MAX_MONTO)
        monto = max(monto, 1)
        return monto
    except:
        return 1

async def esperar_hasta(hora, minuto):
    ahora = datetime.now(ZONA_ARGENTINA)
    entrada = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if entrada <= ahora:
        entrada += timedelta(days=1)
    entrada_real = entrada - timedelta(seconds=SEGUNDOS_ANTES)
    espera = (entrada_real - ahora).total_seconds()
    if espera > 0:
        log.info(f"Esperando {espera:.0f} segundos para operar a las {hora:02d}:{minuto:02d}...")
        await asyncio.sleep(espera)

async def operar(iq, senal, monto, intento=1):
    par = senal['par']
    direccion = senal['direccion']
    expiracion = senal['expiracion']

    log.info(f"Operando: {par} {direccion.upper()} ${monto} exp:{expiracion}min intento:{intento}")
    notificar(
        f"Operando {'CALL' if direccion == 'call' else 'PUT'}",
        f"{par} | ${monto} | Exp: {expiracion}min | Intento {intento}"
    )

    try:
        check, id_operacion = iq.buy(monto, par, direccion, expiracion)
        if not check:
            log.error(f"Error al colocar operacion en {par}")
            notificar("Error", f"No se pudo operar {par}")
            return

        log.info(f"Operacion colocada ID: {id_operacion}, esperando resultado...")
        await asyncio.sleep(expiracion * 60 + 5)

        resultado = iq.check_win_v3(id_operacion)

        if resultado > 0:
            log.info(f"GANO ${resultado}")
            notificar("GANO!", f"{par} | Ganancia: ${resultado:.2f} | Intento {intento}")
        else:
            log.info(f"PERDIO en intento {intento}")
            if intento <= MAX_MARTINGALE:
                nuevo_monto = round(monto * 2, 2)
                nuevo_monto = min(nuevo_monto, MAX_MONTO * 3)
                notificar(
                    f"Perdio - Martingale {intento}",
                    f"{par} | Proxima entrada: ${nuevo_monto}"
                )
                await asyncio.sleep(5)
                await operar(iq, senal, nuevo_monto, intento + 1)
            else:
                notificar(
                    "Perdio - Fin de martingales",
                    f"{par} | Se agotaron los {MAX_MARTINGALE} intentos"
                )

    except Exception as e:
        log.error(f"Error en operacion: {e}")
        notificar("Error operacion", str(e))

async def main():
    log.info("Iniciando bot...")

    iq = conectar_iq()
    if not iq:
        log.error("No se pudo conectar a IQ Option, saliendo...")
        return

    client = TelegramClient('sesion_bot_iq', API_ID, API_HASH)
    await client.start(phone=PHONE)
    log.info("Bot Telegram conectado y escuchando senales...")
    notificar("Bot listo", "Escuchando senales de Telegram...")

    group = await client.get_entity(GROUP_LINK)

    @client.on(events.NewMessage(chats=group))
    async def handler(event):
        texto = event.message.message
        if not texto:
            return

        log.info(f"Mensaje recibido: {texto[:100]}")

        if 'COMPRA' not in texto.upper() and 'VENTA' not in texto.upper() and 'CALL' not in texto.upper() and 'PUT' not in texto.upper():
            return

        senal = parsear_senal(texto)
        if not senal:
            log.warning("No se pudo parsear la senal")
            return

        log.info(f"Senal parseada: {senal}")
        notificar(
            "Nueva senal",
            f"{senal['par']} | {'CALL' if senal['direccion'] == 'call' else 'PUT'} | {senal['hora']:02d}:{senal['minuto']:02d} | {senal['mercado']}"
        )

        await esperar_hasta(senal['hora'], senal['minuto'])
        monto = calcular_monto(iq)
        await operar(iq, senal, monto)

    await client.run_until_disconnected()

asyncio.run(main())
