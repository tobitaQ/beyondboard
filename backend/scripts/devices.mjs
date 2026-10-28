// Device tokens and aws_config.h.
// The sketch never contains secrets: Wi-Fi and the device token live in aws_config.h.
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { DeleteItemCommand, DynamoDBClient, PutItemCommand } from "@aws-sdk/client-dynamodb";
import { ROOT, SETTINGS, readOutputs, readTokens, writeTokens } from "./common.mjs";

const db = new DynamoDBClient({ region: SETTINGS.region });
const digest = (token) => crypto.createHash("sha256").update(token).digest("hex");

// A typical question: ~300 tokens in, ~200 out (an upper-side estimate).
export function askCostPerCall() {
  const p = SETTINGS.prices;
  return (300 * p.askInputPerMillionTokens + 200 * p.askOutputPerMillionTokens) / 1e6;
}
// save / load / run: one Lambda request (~100 ms) and one DynamoDB request.
const CALL_COST_USD = 0.000003;

export function configPath(device) {
  return path.join(ROOT, "out", device, "aws_config.h");
}

// Keeps the Wi-Fi name and password the user already wrote into aws_config.h.
function existingWifi(device) {
  const file = configPath(device);
  const text = fs.existsSync(file) ? fs.readFileSync(file, "utf8") : "";
  const get = (key, fallback) => text.match(new RegExp(`#define ${key} "(.*)"`))?.[1] ?? fallback;
  return { name: get("AWS_WIFI_NAME", "wifi-name"), password: get("AWS_WIFI_PASSWORD", "wifi-password") };
}

function writeConfig(device, apiUrl, token) {
  const wifi = existingWifi(device);
  fs.mkdirSync(path.dirname(configPath(device)), { recursive: true });
  fs.writeFileSync(
    configPath(device),
    `// Made by \`npm run deploy\` for "${device}". Copy this file into your sketch folder.
// Do not share this file: it lets a device use your cloud.
// If it leaks, run \`npm run revoke -- ${device}\` (stop it) or \`npm run rotate -- ${device}\` (make a new one).
#pragma once

// Write your Wi-Fi here (kept when you deploy again).
#define AWS_WIFI_NAME "${wifi.name}"
#define AWS_WIFI_PASSWORD "${wifi.password}"

#define AWS_CLOUD_URL "${apiUrl}"
#define AWS_CLOUD_TOKEN "${token}"

// Rough prices (as of ${SETTINGS.prices.asOf}), used to warn when calls are too frequent.
#define AWS_ASK_COST_USD ${askCostPerCall().toFixed(6)}
#define AWS_CALL_COST_USD ${CALL_COST_USD}
#define AWS_ASK_DAILY_LIMIT ${SETTINGS.ask.dailyLimitPerDevice}
#include <BeyondBoardAws.h>
`,
  );
}

// Gives every device in settings.json a token and writes its aws_config.h.
export async function registerDevices() {
  const { apiUrl, tableName } = readOutputs();
  const tokens = readTokens();
  for (const device of SETTINGS.devices) {
    tokens[device] ??= crypto.randomBytes(24).toString("base64url");
    await db.send(
      new PutItemCommand({
        TableName: tableName,
        Item: { pk: { S: `TOKEN#${digest(tokens[device])}` }, sk: { S: "META" }, device: { S: device } },
      }),
    );
    writeConfig(device, apiUrl, tokens[device]);
  }
  writeTokens(tokens);
}

export async function hasToken(device) {
  return Boolean(readTokens()[device]);
}

// Stops a device's token immediately. The device gets "This device is not registered."
export async function revokeDevice(device) {
  const { tableName } = readOutputs();
  const tokens = readTokens();
  if (!tokens[device]) throw new Error(`There is no device "${device}".`);
  await db.send(
    new DeleteItemCommand({
      TableName: tableName,
      Key: { pk: { S: `TOKEN#${digest(tokens[device])}` }, sk: { S: "META" } },
    }),
  );
  delete tokens[device];
  writeTokens(tokens);
}
