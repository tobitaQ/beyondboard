// npm run try -- <function> [input]
// Runs backend/functions/<function>.py on this computer, without deploying.
//   npm run try -- detectAnomaly 38.2
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { ROOT } from "./common.mjs";

const [name, input = ""] = process.argv.slice(2);
if (!name) {
  console.error("Usage: npm run try -- <function> [input]");
  process.exit(1);
}
const file = path.join(ROOT, "functions", `${name}.py`);
if (!fs.existsSync(file)) {
  console.error(`There is no function "${name}". Put ${name}.py in backend/functions/.`);
  process.exit(1);
}

const code = `
import importlib.util, inspect, sys, time
spec = importlib.util.spec_from_file_location("user_function", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
start = time.time()
if len(inspect.signature(mod.run).parameters) >= 2:
    result = mod.run(sys.argv[2], {"device": "try", "destination": "local"})
else:
    result = mod.run(sys.argv[2])
print("result :", "" if result is None else str(result))
print("time   : %d ms" % ((time.time() - start) * 1000))
`;
const r = spawnSync("python3", ["-c", code, file, input], { stdio: "inherit" });
process.exit(r.status ?? 1);
