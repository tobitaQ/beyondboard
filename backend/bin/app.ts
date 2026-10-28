#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import * as fs from "fs";
import * as path from "path";
import { BackendStack } from "../lib/backend-stack";

const settings = JSON.parse(
  fs.readFileSync(path.join(__dirname, "..", "settings.json"), "utf8"),
);

const app = new cdk.App();
new BackendStack(app, "AwsCloudBackend", {
  settings,
  env: { region: settings.region },
});
