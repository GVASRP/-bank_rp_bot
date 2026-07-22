import asyncio
import logging
import os
import threading

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("app")


def run_bot():
    from main import main as bot_main
    asyncio.run(bot_main(skip_web=True))


thread = threading.Thread(target=run_bot, daemon=True)
thread.start()
logger.info("Bot started in background thread")

import gradio as gr

with gr.Blocks(title="Bank RP Bot", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Bank RP Bot")
    gr.Markdown("Telegram bot is running in background")

demo.launch(server_name="0.0.0.0", server_port=7860)
