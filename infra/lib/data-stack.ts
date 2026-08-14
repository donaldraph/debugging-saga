import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';

interface DataStackProps extends cdk.StackProps {
  stage: string;
}

/**
 * Storage layer - one private S3 bucket for generated narration audio.
 * No database: a saga is generated, played, and forgotten. Audio objects
 * expire after 7 days so the bucket cannot quietly accumulate cost; the
 * presigned URLs handed to the frontend expire long before that anyway.
 */
export class DataStack extends cdk.Stack {
  public readonly audioBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props: DataStackProps) {
    super(scope, id, props);
    const isProd = props.stage === 'prod';

    this.audioBucket = new s3.Bucket(this, 'AudioBucket', {
      bucketName: `dsg-audio-${props.stage}-${this.account}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      lifecycleRules: [{ expiration: cdk.Duration.days(7) }],
      removalPolicy: isProd ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: !isProd,
    });

    new cdk.CfnOutput(this, 'AudioBucketName', { value: this.audioBucket.bucketName });
  }
}
