// npm run stats [-- days]
// Shows how often each call ran, how many failed, how long it took, and a rough cost.
import { DynamoDBClient, QueryCommand } from "@aws-sdk/client-dynamodb";
import { SETTINGS, readOutputs } from "./common.mjs";

const days = Number(process.argv[2] ?? 7);
const { tableName } = readOutputs();
const db = new DynamoDBClient({ region: SETTINGS.region });

const rows = new Map();
let tokensIn = 0;
let tokensOut = 0;
for (let i = 0; i < days; i++) {
  const day = new Date(Date.now() - i * 86400_000).toISOString().slice(0, 10);
  let start;
  do {
    const page = await db.send(
      new QueryCommand({
        TableName: tableName,
        KeyConditionExpression: "pk = :pk",
        ExpressionAttributeValues: { ":pk": { S: `CALL#${day}` } },
        ExclusiveStartKey: start,
      }),
    );
    for (const item of page.Items ?? []) {
      const key = `${item.op.S} ${item.name?.S ?? ""}`.trim();
      const row = rows.get(key) ?? { calls: 0, errors: 0, ms: [] };
      row.calls++;
      if (Number(item.code.N) !== 0) row.errors++;
      row.ms.push(Number(item.ms.N));
      rows.set(key, row);
      tokensIn += Number(item.tokensIn?.N ?? 0);
      tokensOut += Number(item.tokensOut?.N ?? 0);
    }
    start = page.LastEvaluatedKey;
  } while (start);
}

const median = (a) => a.sort((x, y) => x - y)[Math.floor(a.length / 2)] ?? 0;
console.log(`Last ${days} days\n`);
console.log("call".padEnd(32) + "times".padStart(7) + "errors".padStart(8) + "median ms".padStart(11));
for (const [key, r] of [...rows].sort()) {
  console.log(
    key.padEnd(32) + String(r.calls).padStart(7) + String(r.errors).padStart(8) + String(median(r.ms)).padStart(11),
  );
}
const p = SETTINGS.prices;
const cost = (tokensIn * p.askInputPerMillionTokens + tokensOut * p.askOutputPerMillionTokens) / 1e6;
const perMonth = (cost / days) * 30;
console.log(`
AI tokens: ${tokensIn} in, ${tokensOut} out
Rough AI cost: ${p.currency} ${cost.toFixed(4)} (about ${p.currency} ${perMonth.toFixed(2)} per month at this pace)
Prices as of ${p.asOf}. This is an estimate, not your bill.`);
