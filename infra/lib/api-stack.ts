import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as path from 'path';

// Secret name fixed here so every phase wires the same one. Created out of
// band (never in CloudFormation, so a stack delete cannot take a credential
// with it):
//   debugging-saga/gemini  { "api_key": ... }
export const GEMINI_SECRET_NAME = 'debugging-saga/gemini';

interface ApiStackProps extends cdk.StackProps {
  stage: string;
  audioBucket: s3.Bucket;
}

/**
 * Compute + API. Scaffold ships exactly one real route, GET /health, so the
 * deployed URL proves the whole chain (API GW -> Lambda -> bucket access)
 * works. Saga generation (Gemini) and narration (Polly) land with the phases
 * that implement them.
 */
export class ApiStack extends cdk.Stack {
  public readonly api: apigw.RestApi;

  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);
    const { audioBucket } = props;

    const lambdasPath = path.join(__dirname, '..', 'lambdas');
    const commonEnv = {
      AUDIO_BUCKET: audioBucket.bucketName,
    };

    const makeFn = (
      name: string,
      handler: string,
      extraEnv: Record<string, string> = {},
      timeoutSeconds = 10,
      memoryMb = 256,
    ) =>
      new lambda.Function(this, name, {
        runtime: lambda.Runtime.PYTHON_3_12,
        code: lambda.Code.fromAsset(lambdasPath),
        handler,
        timeout: cdk.Duration.seconds(timeoutSeconds),
        memorySize: memoryMb,
        environment: { ...commonEnv, ...extraEnv },
        tracing: lambda.Tracing.ACTIVE,
      });

    const healthFn = makeFn('HealthFn', 'health.handler');
    audioBucket.grantRead(healthFn);

    // Saga generation - the load-bearing AI. Synchronous: measured chain
    // latency (flash-latest 5-13s, lite ~3s) fits the 29s API Gateway cap.
    // 28s Lambda timeout so the model budget (18s + 8s), not Lambda, is what
    // gives out first. Public route; the stage throttle guards the quota.
    const geminiSecret = secretsmanager.Secret.fromSecretNameV2(
      this, 'GeminiSecret', GEMINI_SECRET_NAME);
    const generateFn = makeFn(
      'GenerateFn',
      'generate.handler',
      {
        GEMINI_SECRET_NAME,
        MODEL_ID: this.node.tryGetContext('model') || 'gemini-flash-latest',
        MODEL_FALLBACKS: this.node.tryGetContext('modelFallbacks') || 'gemini-3.5-flash-lite',
      },
      28,
      512,
    );
    geminiSecret.grantRead(generateFn);

    const showcaseFn = makeFn('ShowcaseFn', 'get_showcase.handler');

    this.api = new apigw.RestApi(this, 'Api', {
      restApiName: `dsg-${props.stage}`,
      deployOptions: {
        stageName: props.stage,
        tracingEnabled: true,
        // Public generate endpoint spends model quota; keep the tap narrow.
        throttlingRateLimit: 5,
        throttlingBurstLimit: 10,
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigw.Cors.ALL_ORIGINS,
        allowMethods: apigw.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type'],
      },
    });

    this.api.root.addResource('health').addMethod('GET', new apigw.LambdaIntegration(healthFn));
    this.api.root.addResource('generate').addMethod('POST', new apigw.LambdaIntegration(generateFn));
    this.api.root.addResource('showcase').addMethod('GET', new apigw.LambdaIntegration(showcaseFn));

    new cdk.CfnOutput(this, 'ApiUrl', { value: this.api.url });
  }
}
