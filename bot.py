"""
Reconnecting Minecraft offline-mode bot.

Requires: pyCraft (from ammaraskar/pyCraft) and Flask
"""

import os
import threading
from flask import Flask, jsonify
import socket
import time
import sys
import traceback

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
# pyCraft (the library this bot uses) only understands protocol packets up
# through Minecraft 1.18.1 — it doesn't know 1.21.x packet formats at all.
# Your server is 1.21.11, but since you have ViaBackwards installed
# alongside ViaVersion, the server will transparently translate pyCraft's
# 1.18.1 packets up to 1.21.11 for you. So this must stay "1.18.1" — do NOT
# change it to your server's real version, or the handshake will fail.
MC_PROTOCOL_VERSION = "1.18.1"


def is_server_online(host, port, timeout=3):
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


def wait_for_server(host, port, poll_interval=5):
    attempt = 0
    while True:
        if is_server_online(host, port):
            return
        attempt += 1
        if attempt == 1 or attempt % 6 == 0:  # log immediately, then every ~30s
            print(f"Still waiting for {host}:{port} to come online...")
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
            def handle_exception(exception, exc_info):
                # Log cleanly instead of letting pyCraft re-raise inside its
                # networking thread (which dumps a raw traceback to stderr).
                print(f"Networking error: {exception}")

            try:
                if BOT_SKIN:
                    conn = Connection(host, port, username=username, skin=BOT_SKIN,
                                       initial_version=MC_PROTOCOL_VERSION,
                                       handle_exception=handle_exception)
                else:
                    conn = Connection(host, port, username=username,
                                       initial_version=MC_PROTOCOL_VERSION,
                                       handle_exception=handle_exception)
            except TypeError:
                conn = Connection(host, port, username=username,
                                   initial_version=MC_PROTOCOL_VERSION,
                                   handle_exception=handle_exception)

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

        # Always pause before the next attempt so a fast-failing connection
        # (e.g. protocol mismatch, instant kick) can't spin in a tight loop.
        time.sleep(poll_interval)

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
    # Everything is hardcoded above (MC_HOST, MC_PORT, BOT_USERNAME,
    # REGISTER_PASSWORD, AUTO_REGISTER, AUTO_AFK, BOT_SKIN) — no CLI flags,
    # no environment variables to configure. Just edit the constants at the
    # top of this file and redeploy.
    print(f"Starting bot for {MC_HOST}:{MC_PORT} as {BOT_USERNAME}")
    run_as_web_and_bot(MC_HOST, MC_PORT, BOT_USERNAME, poll_interval=5)


if __name__ == "__main__":
    main()
