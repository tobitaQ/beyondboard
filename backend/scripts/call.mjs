// npm run call -- <save|load|run|ask> ...
// Calls the deployed cloud exactly like a device does (as the first device in settings.json).
//   npm run call -- save temp.csv 23.5
//   npm run call -- load temp.csv
//   npm run call -- run detectAnomaly 38.2
//   npm run call -- ask "Is this hot?" 38.2
//   npm run call -- ask "Which one?" 38.2 normal,warning,danger
import crypto from "node:crypto";
import { SETTINGS, readOutputs, readTokens } from "./common.mjs";

export async function call(op, body, device = SETTINGS.devices[0]) {
  const { apiUrl } = readOutputs();
  const token = readTokens()[device];
  const started = Date.now();
  const res = await fetch(`${apiUrl}/v1/${op}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-device-token": token ?? "",
      "x-request-id": crypto.randomUUID(),
    },
    body: JSON.stringify(body),
  });
  const json = await res.json();
  return { ...json, ms: Date.now() - started };
}

function bodyFor(op, args) {
  switch (op) {
    case "ping":
      return {};
    case "save":
      return { name: args[0], value: args[1] ?? "" };
    case "load":
      return { name: args[0] };
    case "run":
      return { name: args[0], input: args[1] ?? "", timeoutMs: args[2] && Number(args[2]) };
    case "ask":
      return { prompt: args[0], data: args[1] ?? "", choices: args[2] ? args[2].split(",") : [] };
    default:
      throw new Error("Usage: npm run call -- <ping|save|load|run|ask> ...");
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [op, ...args] = process.argv.slice(2);
  const r = await call(op, bodyFor(op, args));
  if (r.ok) {
    console.log(r.result);
  } else {
    console.log(`error ${r.code}: ${r.error}`);
  }
  console.log(`(${r.ms} ms)`);
}
