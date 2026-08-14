import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as s3 from 'aws-cdk-lib/aws-s3';
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

    this.api = new apigw.RestApi(this, 'Api', {
      restApiName: `dsg-${props.stage}`,
      deployOptions: { stageName: props.stage, tracingEnabled: true },
      defaultCorsPreflightOptions: {
        allowOrigins: apigw.Cors.ALL_ORIGINS,
        allowMethods: apigw.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type'],
      },
    });

    this.api.root.addResource('health').addMethod('GET', new apigw.LambdaIntegration(healthFn));

    new cdk.CfnOutput(this, 'ApiUrl', { value: this.api.url });
  }
}
