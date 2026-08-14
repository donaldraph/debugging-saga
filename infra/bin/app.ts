#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { DataStack } from '../lib/data-stack';
import { ApiStack } from '../lib/api-stack';
import { HostingStack } from '../lib/hosting-stack';

const app = new cdk.App();

// Stage drives naming and prod-vs-dev behaviour. Override: cdk deploy --all -c stage=prod
const stage = app.node.tryGetContext('stage') || 'dev';

const env: cdk.Environment = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
};

const prefix = `dsg-${stage}`;

// Storage layer - the audio bucket. No database; a saga is stateless.
const data = new DataStack(app, `${prefix}-data`, { env, stage });

// Compute + API - saga generation (Gemini) and narration (Polly).
const api = new ApiStack(app, `${prefix}-api`, { env, stage, audioBucket: data.audioBucket });

// Static hosting - S3 + CloudFront for the frontend, fed the API base URL.
new HostingStack(app, `${prefix}-hosting`, { env, stage, apiUrl: api.api.url });

cdk.Tags.of(app).add('project', 'debugging-saga');
cdk.Tags.of(app).add('stage', stage);
