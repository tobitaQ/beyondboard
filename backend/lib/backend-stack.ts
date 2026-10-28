import * as cdk from "aws-cdk-lib";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as iam from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as logs from "aws-cdk-lib/aws-logs";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as s3deploy from "aws-cdk-lib/aws-s3-deployment";
import { Construct } from "constructs";
import * as fs from "fs";
import * as path from "path";

export interface FunctionPermissions {
  // Let the function read what devices saved (DynamoDB). Its `context` has the table name.
  readSavedData?: boolean;
  // Bedrock models (inference profile IDs) the function may call itself.
  models?: string[];
  // Let the function use Amazon Rekognition (for example, to detect faces in a saved image).
  rekognition?: boolean;
}

export interface Settings {
  region: string;
  devices: string[];
  ask: { model: string; dailyLimitPerDevice: number; maxChars: number };
  // Extra permissions for functions that call cloud services themselves
  // (the bottom level, outside the contract).
  functions?: Record<string, FunctionPermissions>;
}

export interface BackendStackProps extends cdk.StackProps {
  settings: Settings;
}

const ROOT = path.join(__dirname, "..");
const FUNCTION_NAME = /^[A-Za-z][A-Za-z0-9_]{0,63}$/;

// Inference profile IDs look like "jp.anthropic.claude-...": the part after the
// geography prefix is the underlying foundation model ID.
function foundationModelId(profileOrModelId: string): string {
  const m = profileOrModelId.match(/^(us|eu|apac|jp|au|ca|global)\.(.+)$/);
  return m ? m[2] : profileOrModelId;
}

// Copies the user's functions/*.py next to a small shim, so that users only
// write `def run(input): return ...` and never see Lambda's handler signature.
function buildUserFunctionAsset(name: string): string {
  const out = path.join(ROOT, ".build", "functions", name);
  fs.rmSync(out, { recursive: true, force: true });
  fs.mkdirSync(out, { recursive: true });
  fs.copyFileSync(
    path.join(ROOT, "functions", `${name}.py`),
    path.join(out, "user_function.py"),
  );
  fs.copyFileSync(
    path.join(ROOT, "runtime", "shim.py"),
    path.join(out, "shim.py"),
  );
  return out;
}

export class BackendStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: BackendStackProps) {
    super(scope, id, props);
    const { settings } = props;

    // One table for records, device tokens, usage counters and the call log.
    const table = new dynamodb.Table(this, "Data", {
      partitionKey: { name: "pk", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "sk", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: "ttl",
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Files placed in backend/files/ are readable with aws.load(name).
    const bucket = new s3.Bucket(this, "Files", {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });
    new s3deploy.BucketDeployment(this, "DeployFiles", {
      sources: [s3deploy.Source.asset(path.join(ROOT, "files"))],
      destinationBucket: bucket,
      destinationKeyPrefix: "files/",
    });

    // User-defined functions for aws.run(name, input).
    const functionArns: Record<string, string> = {};
    const userFunctions: lambda.Function[] = [];
    for (const file of fs.readdirSync(path.join(ROOT, "functions"))) {
      if (!file.endsWith(".py")) continue;
      const name = file.slice(0, -3);
      if (!FUNCTION_NAME.test(name)) {
        throw new Error(
          `functions/${file}: the name must start with a letter and use only letters, digits and _`,
        );
      }
      const fn = new lambda.Function(this, `Fn_${name}`, {
        runtime: lambda.Runtime.PYTHON_3_13,
        handler: "shim.handler",
        code: lambda.Code.fromAsset(buildUserFunctionAsset(name)),
        timeout: cdk.Duration.seconds(60),
        memorySize: 128, // the smallest size; users' functions are small
        logGroup: this.logGroup(`Fn_${name}Logs`),
      });
      functionArns[name] = fn.functionArn;
      userFunctions.push(fn);
      const allow = settings.functions?.[name];
      if (allow?.readSavedData) {
        table.grantReadData(fn);
        bucket.grantRead(fn, "saved/*");
        fn.addEnvironment("TABLE", table.tableName);
        fn.addEnvironment("BUCKET", bucket.bucketName);
      }
      if (allow?.rekognition) {
        fn.addToRolePolicy(
          new iam.PolicyStatement({
            actions: ["rekognition:DetectFaces", "rekognition:DetectLabels", "rekognition:DetectText"],
            resources: ["*"], // Rekognition's image APIs do not take resource-level permissions
          }),
        );
      }
      if (allow?.models?.length) {
        fn.addToRolePolicy(
          new iam.PolicyStatement({
            actions: ["bedrock:InvokeModel"],
            resources: allow.models.flatMap((m) => this.bedrockResources(m)),
          }),
        );
      }
    }

    // The single entry point the device talks to.
    const api = new lambda.Function(this, "Api", {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(path.join(ROOT, "runtime"), {
        exclude: ["shim.py", "__pycache__", "tests"],
      }),
      timeout: cdk.Duration.seconds(90),
      memorySize: 256,
      logGroup: this.logGroup("ApiLogs"),
      environment: {
        TABLE: table.tableName,
        BUCKET: bucket.bucketName,
        FUNCTIONS: JSON.stringify(functionArns),
        ASK_MODEL: settings.ask.model,
        ASK_DAILY_LIMIT: String(settings.ask.dailyLimitPerDevice),
        ASK_MAX_CHARS: String(settings.ask.maxChars),
      },
    });
    table.grantReadWriteData(api);
    bucket.grantRead(api, "files/*");
    bucket.grantReadWrite(api, "saved/*"); // images saved with save(name, bytes) (MVP+)
    bucket.grantDelete(api, "saved/*");
    userFunctions.forEach((fn) => fn.grantInvoke(api));

    // Least privilege for Bedrock: only the configured model, through its
    // inference profile (which may route to any region of its geography).
    api.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["bedrock:InvokeModel"],
        resources: this.bedrockResources(settings.ask.model),
      }),
    );

    const url = api.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE, // device tokens are checked in the handler
    });

    new cdk.CfnOutput(this, "ApiUrl", { value: url.url });
    new cdk.CfnOutput(this, "TableName", { value: table.tableName });
  }

  private bedrockResources(profileOrModelId: string): string[] {
    const modelId = foundationModelId(profileOrModelId);
    const resources = [`arn:aws:bedrock:*::foundation-model/${modelId}`];
    if (modelId !== profileOrModelId) {
      resources.push(
        `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/${profileOrModelId}`,
      );
    }
    return resources;
  }

    private logGroup(id: string): logs.LogGroup {
    return new logs.LogGroup(this, id, {
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
  }
}
