// npm run deploy
// 1. Builds the backend in your AWS account (CDK).
// 2. Registers each device in settings.json and writes out/<device>/aws_config.h.
// 3. Shows a rough monthly cost and the daily limit for aws.ask().
import { execSync } from "node:child_process";
import { ROOT, SETTINGS } from "./common.mjs";
import { askCostPerCall, registerDevices } from "./devices.mjs";

execSync("npx cdk deploy --require-approval never --outputs-file .build/outputs.json", {
  cwd: ROOT,
  stdio: "inherit",
});

await registerDevices();

// Rough cost of aws.ask(). Typical question: ~300 tokens in, ~200 out.
const p = SETTINGS.prices;
const perAsk = askCostPerCall();
const perMonthEveryMinute = perAsk * 60 * 24 * 30;
const cap = perAsk * SETTINGS.ask.dailyLimitPerDevice * 30;
console.log(`
Done.
  Write your Wi-Fi name and password in out/<device>/aws_config.h,
  then copy it into your sketch folder:
${SETTINGS.devices.map((d) => `    out/${d}/aws_config.h`).join("\n")}

  Rough cost of aws.ask() (prices as of ${p.asOf}):
    about ${p.currency} ${perAsk.toFixed(4)} per question
    one question every minute would be about ${p.currency} ${perMonthEveryMinute.toFixed(0)} per month,
    but each device is limited to ${SETTINGS.ask.dailyLimitPerDevice} questions a day
    (at most about ${p.currency} ${cap.toFixed(2)} per device per month).
  save / load / run cost almost nothing at this scale.
  See actual use with: npm run stats
`);
