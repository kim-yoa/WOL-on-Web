import threading
import asyncio
import yaml
from flask import Flask, request, abort
from wakeonlan import send_magic_packet
import discord

# config.yml 파일 로딩
with open("config.yml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

app = Flask(__name__)

# Discord client 생성 (discord.py 기본 문법 사용)
intents = discord.Intents.default()
discord_client = discord.Client(intents=intents)

@discord_client.event
async def on_ready():
    print(f"Discord Bot logged in as {discord_client.user}")

async def send_log(message: str):
    """디스코드 로그 채널로 메시지를 전송하는 비동기 함수."""
    channel = discord_client.get_channel(config['discord']['log_channel_id'])
    if channel is None:
        print("로그 채널을 찾을 수 없습니다.")
        return
    await channel.send(message)

def send_discord_log(message: str):
    """
    동기 코드(Flask 라우트)에서 비동기 send_log 함수를 호출합니다.
    """
    try:
        future = asyncio.run_coroutine_threadsafe(send_log(message), discord_client.loop)
        future.result()  # 작업 완료 대기
    except Exception as e:
        print(f"디스코드 로그 전송 실패: {e}")

@app.route('/<pc_id>', methods=['GET'])
def wake_pc(pc_id):
    """
    URL 예: http://wol.kimyoa.com/메인컴
    - config.yml에 등록된 pc_id에 해당하는 컴퓨터의 MAC 주소로 WOL 패킷 전송
    - Cloudflare 프록시가 사용될 경우 'CF-Connecting-IP' 헤더에서 원본 IP 추출
    - 성공 시 디스코드 로그 채널로 요청 정보를 전송
    """
    # config에서 해당 pc_id의 MAC 주소 확인
    pc_config = config.get('pcs', {}).get(pc_id)
    if pc_config is None:
        abort(404, description="존재하지 않는 PC ID입니다.")
    mac_address = pc_config.get('mac')
    if mac_address is None:
        abort(500, description="MAC 주소가 설정되어 있지 않습니다.")

    # Cloudflare 프록시를 사용할 경우, 원본 IP는 'CF-Connecting-IP' 헤더에 있음
    original_ip = request.headers.get("CF-Connecting-IP", request.remote_addr)

    try:
        send_magic_packet(mac_address)
    except Exception as e:
        abort(500, description=f"WOL 패킷 전송 실패: {e}")

    # 디스코드 로그 메시지 작성 (원본 IP 포함)
    log_message = f"[WOL 요청] PC: {pc_id} MAC: {mac_address} / 요청자 IP: {original_ip}"
    send_discord_log(log_message)

    return f"{pc_id}에 대한 WOL 요청을 실행했습니다.", 200

def run_discord_bot():
    """별도 스레드에서 디스코드 봇 실행"""
    discord_client.run(config['discord']['token'])

if __name__ == "__main__":
    # 디스코드 봇을 별도 스레드로 실행
    discord_thread = threading.Thread(target=run_discord_bot)
    discord_thread.start()

    # Flask 웹 서버 실행 (필요에 따라 host 및 port 설정)
    app.run(host="0.0.0.0", port=80)
