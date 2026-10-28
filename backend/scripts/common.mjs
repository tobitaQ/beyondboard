import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
export const SETTINGS = JSON.parse(fs.readFileSync(path.join(ROOT, "settings.json"), "utf8"));
const OUTPUTS = path.join(ROOT, ".build", "outputs.json");
const SECRETS = path.join(ROOT, ".secrets", "devices.json");

export function readOutputs() {
  if (!fs.existsSync(OUTPUTS)) {
    throw new Error("The backend is not deployed yet. Run `npm run deploy` first.");
  }
  const all = JSON.parse(fs.readFileSync(OUTPUTS, "utf8"));
  const out = all.AwsCloudBackend;
  return { apiUrl: out.ApiUrl.replace(/\/$/, ""), tableName: out.TableName };
}

export function readTokens() {
  return fs.existsSync(SECRETS) ? JSON.parse(fs.readFileSync(SECRETS, "utf8")) : {};
}

export function writeTokens(tokens) {
  fs.mkdirSync(path.dirname(SECRETS), { recursive: true });
  fs.writeFileSync(SECRETS, JSON.stringify(tokens, null, 2) + "\n", { mode: 0o600 });
}
