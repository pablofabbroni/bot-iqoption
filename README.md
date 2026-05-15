# Bot IQ Option

Bot automatizado para IQ Option que opera basado en señales recibidas desde un grupo de Telegram.

## Características
- Conexión con la API de IQ Option.
- Escucha señales en tiempo real desde Telegram.
- Soporte para mercado REAL y OTC.
- Gestión de riesgo (Martingale configurable).
- Notificaciones vía ntfy.sh.
- Dockerizado para fácil despliegue.

## Requisitos
- Python 3.9+
- Una cuenta de IQ Option.
- API ID y Hash de Telegram (puedes obtenerlos en [my.telegram.org](https://my.telegram.org)).

## Instalación

1. Clona el repositorio:
   ```bash
   git clone https://github.com/pablofabbroni/bot-iqoption.git
   cd bot-iqoption
   ```

2. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

3. Configura tus credenciales en `bot_iqoption.py` (o usa variables de entorno).

4. Ejecuta el bot:
   ```bash
   python bot_iqoption.py
   ```

## Docker
Para ejecutar con Docker:
```bash
docker build -t bot-iqoption .
docker run bot-iqoption
```

## Aviso Legal
El trading de opciones binarias conlleva un alto nivel de riesgo. Este bot es para fines educativos y no garantiza ganancias. Úsalo bajo tu propio riesgo.
