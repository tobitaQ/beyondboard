// npm run revoke -- <device>   stop a device's token now (for example, if aws_config.h leaked)
// npm run rotate -- <device>   stop it and make a new aws_config.h
import { SETTINGS } from "./common.mjs";
import { configPath, hasToken, registerDevices, revokeDevice } from "./devices.mjs";

const rotate = process.argv[2] === "--rotate";
const device = process.argv[rotate ? 3 : 2];
if (!device) {
  console.error(`Usage: npm run ${rotate ? "rotate" : "revoke"} -- <device>`);
  process.exit(1);
}
// rotate also works after a plain revoke, when the old token is already gone.
if (!(rotate && !(await hasToken(device)))) {
  await revokeDevice(device);
  console.log(`Stopped "${device}". It can no longer use the cloud.`);
}
if (rotate) {
  if (!SETTINGS.devices.includes(device)) {
    console.error(`"${device}" is not in settings.json, so no new aws_config.h was made.`);
    process.exit(1);
  }
  await registerDevices();
  console.log(`New ${configPath(device)} was made. Copy it into your sketch folder and upload again.`);
}
