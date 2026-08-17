"use strict";

/**
 * Reconnecting Minecraft bot (mineflayer) + a tiny health-check web server
 * for Render.
 *
 * Everything is hardcoded below — no CLI flags, no environment variables to
 * configure. Just edit the constants and redeploy.
 */

const mineflayer = require("mineflayer");
const express = require("express");

// ---- Hardcoded configuration ----
const MC_HOST = "aevummc.mcsh.io";
const MC_PORT = 25565;
const BOT_USERNAME = "aevumbot";
const REGISTER_PASSWORD = "password";
const AUTO_REGISTER = true;
const AUTO_LOGIN = true;
const AUTO_AFK = true;
const RECONNECT_DELAY_MS = 5000;
const COMMAND_DELAY_MS = 3000; // gap between join/register/login/afk to avoid anti-spam kicks

let bot = null;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function createBot() {
  console.log(`Connecting to ${MC_HOST}:${MC_PORT} as ${BOT_USERNAME}...`);

  bot = mineflayer.createBot({
    host: MC_HOST,
    port: MC_PORT,
    username: BOT_USERNAME,
    auth: "offline",
    version: false, // auto-detect the server's real protocol version (1.21.x) — no ViaBackwards needed
  });

  bot.on("login", () => {
    console.log("Connected — logging in to the server...");
  });

  bot.on("spawn", () => {
    console.log("Spawned in the world; sending auto-commands if enabled.");
    runAutoCommands().catch((e) => console.log("Error sending join commands:", e));
  });

  // Prints anything the server/plugins say back (login errors, kick
  // warnings, etc.) so failures are never silent.
  bot.on("message", (jsonMsg) => {
    console.log("Server message:", jsonMsg.toString());
  });

  bot.on("kicked", (reason) => {
    console.log("Kicked:", reason);
  });

  bot.on("end", (reason) => {
    console.log(
      `Disconnected (${reason || "unknown reason"}) — reconnecting in ${RECONNECT_DELAY_MS / 1000}s...`
    );
    scheduleReconnect();
  });

  bot.on("error", (err) => {
    console.log("Connection error:", err && err.message ? err.message : err);
  });
}

function scheduleReconnect() {
  setTimeout(createBot, RECONNECT_DELAY_MS);
}

async function runAutoCommands() {
  // Space commands out — sending them back-to-back on join has triggered
  // "you used a command too fast" kicks from anti-spam/login plugins.
  await sleep(COMMAND_DELAY_MS);

  if (AUTO_REGISTER && REGISTER_PASSWORD) {
    bot.chat(`/register ${REGISTER_PASSWORD} ${REGISTER_PASSWORD}`);
    await sleep(COMMAND_DELAY_MS);
  }

  if (AUTO_LOGIN && REGISTER_PASSWORD) {
    bot.chat(`/login ${REGISTER_PASSWORD}`);
    await sleep(COMMAND_DELAY_MS);
  }

  if (AUTO_AFK) {
    bot.chat("/afk");
  }
}

// ---- Minimal health-check web server (Render requires something bound
// to $PORT for a Web Service) ----
const app = express();
app.get("/health", (req, res) => res.json({ status: "ok" }));

const port = process.env.PORT || 5000;
app.listen(port, "0.0.0.0", () => {
  console.log(`Health server listening on port ${port}`);
});

createBot();
