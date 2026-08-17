"""
Reconnecting Minecraft offline-mode bot.

Requires: pyCraft (from ammaraskar/pyCraft) and mcstatus
"""

import argparse
import os
import threading
from flask import Flask, jsonify
import socket
import time
import sys
import traceback

from mcstatus import MinecraftServer

try:
    from minecraft.networking.connection import Connection
    from minecraft.networking.packets import clientbound
except Exception:
    Connection = None

try:
    from minecraft.networking.packets.serverbound.play import ChatPacket as ServerChatPacket
except Exception:
    try:
        from minecraft.networking.packets.serverbound.play import ChatMessagePacket as ServerChatPacket
    except Exception:
        ServerChatPacket = None

# Top-level configurable variables
MC_HOST = "aevummc.mcsh.io"
MC_PORT = 25565
BOT_USERNAME = "AevumBot"
BOT_SKIN = None  # Set to a skin identifier or None
REGISTER_PASSWORD = "password"
AUTO_REGISTER = True
AUTO_AFK = True


def is_server_online(host, port, timeout=3):
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


def wait_for_server(host, port, poll_interval=5):
    while True:
        if is_server_online(host, port):
            return
        time.sleep(poll_interval)


def run_bot(host, port, username, poll_interval=5):
    if Connection is None:
        print("pyCraft not available. Install requirements first.")
        return

    while True:
        print(f"Checking {host}:{port}...")
        wait_for_server(host, port, poll_interval=poll_interval)
        print("Server appears online — attempting to connect...")

        try:
            try:
                if BOT_SKIN:
                    conn = Connection(host, port, username=username, skin=BOT_SKIN)
                else:
                    conn = Connection(host, port, username=username)
            except TypeError:
                conn = Connection(host, port, username=username)

            def send_chat(conn, message):
                if ServerChatPacket is None:
                    print("Chat packet class not available; cannot send message.")
                    return
                try:
                    packet = ServerChatPacket(message=message)
                except Exception:
                    try:
                        packet = ServerChatPacket()
                        if hasattr(packet, 'message'):
                            packet.message = message
                        elif hasattr(packet, 'chatMessage'):
                            packet.chatMessage = message
                        else:
                            setattr(packet, 'message', message)
                    except Exception as e:
                        print("Failed to construct chat packet:", e)
                        return
                try:
                    conn.write_packet(packet)
                except Exception:
                    try:
                        conn.send_packet(packet)
                    except Exception as e:
                        print("Failed to send chat packet:", e)

            def handle_join(packet):
                print("Joined the server; sending auto-commands if enabled.")
                try:
                    if AUTO_REGISTER and REGISTER_PASSWORD:
                        pw = REGISTER_PASSWORD
                        if ' ' in pw:
                            pw_repr = f'"{pw}"'
                        else:
                            pw_repr = pw
                        send_chat(conn, f"/register {pw_repr} {pw_repr}")
                        time.sleep(0.15)
                    if AUTO_AFK:
                        send_chat(conn, "/afk")
                except Exception as e:
                    print("Error sending join commands:", e)

            conn.register_packet_listener(handle_join, clientbound.play.JoinGamePacket)

            try:
                conn.connect()
            except Exception as e:
                print("Connection error or disconnected:", e)
                traceback.print_exc()

            print("Disconnected — will poll and reconnect when server is back.")

        except Exception as e:
            print("Failed to connect:", e)
            traceback.print_exc()

        # Poll server until it becomes available again
        while not is_server_online(host, port):
            time.sleep(poll_interval)


def run_as_web_and_bot(host, port, username, poll_interval=5):
    # Start the reconnecting bot in a daemon thread and run a simple Flask app
    t = threading.Thread(target=run_bot, args=(host, port, username, poll_interval), daemon=True)
    t.start()

    app = Flask(__name__)

    @app.route('/health')
    def health():
        return jsonify(status='ok')

    port_env = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port_env)


def main():
    parser = argparse.ArgumentParser(description="Simple reconnecting Minecraft bot (offline-mode)")
    parser.add_argument("--host", default=MC_HOST)
    parser.add_argument("--port", type=int, default=MC_PORT)
    parser.add_argument("--username", default=BOT_USERNAME)
    parser.add_argument("--skin", default=BOT_SKIN, help="Optional skin identifier to send to the server")
    parser.add_argument("--register-password", dest="register_password", default=None,
                        help="Password to use for /register (overrides REGISTER_PASSWORD)")
    parser.add_argument("--no-register", dest="auto_register", action="store_false", default=AUTO_REGISTER,
                        help="Disable automatic /register on join")
    parser.add_argument("--no-afk", dest="auto_afk", action="store_false", default=AUTO_AFK,
                        help="Disable automatic /afk on join")
    parser.add_argument("--poll", type=int, default=5, help="Seconds between server checks when offline")
    parser.add_argument("--web", dest="web", action="store_true", default=False,
                        help="Run as a web service and expose /health (for platforms like Render)")
    args = parser.parse_args()

    # Apply CLI overrides to top-level config
    global REGISTER_PASSWORD, AUTO_REGISTER, AUTO_AFK, BOT_SKIN
    if args.register_password is not None:
        REGISTER_PASSWORD = args.register_password
    AUTO_REGISTER = args.auto_register
    AUTO_AFK = args.auto_afk
    BOT_SKIN = args.skin

    print(f"Starting bot for {args.host}:{args.port} as {args.username}")
    if args.web:
        run_as_web_and_bot(args.host, args.port, args.username, poll_interval=args.poll)
    else:
        run_bot(args.host, args.port, args.username, poll_interval=args.poll)


if __name__ == "__main__":
    main()
