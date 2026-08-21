import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';

interface DataStackProps extends cdk.StackProps {
  stage: string;
}

/**
 * Storage layer - one private S3 bucket for generated narration audio, plus
 * (added for the "always-on agent" follow-up challenge) one DynamoDB table
 * for the unattended auto-remix. Interactive sagas stay stateless by design
 * (generated, played, forgotten); only the scheduler's own output needs to
 * persist, so it is ready before anyone asks.
 */
export class DataStack extends cdk.Stack {
  public readonly audioBucket: s3.Bucket;
  public readonly autoSagas: dynamodb.Table;

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

    // pk=LATEST_AUTO holds the current premiere; pk=AUTO/sk=timestamp is
    // history. 7-day TTL matches the audio bucket's own lifecycle, so a
    // saga's text never outlives the audio it points at.
    this.autoSagas = new dynamodb.Table(this, 'AutoSagas', {
      tableName: `dsg-autosaga-${props.stage}`,
      partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'sk', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'expires_at',
      removalPolicy: isProd ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
    });

    new cdk.CfnOutput(this, 'AudioBucketName', { value: this.audioBucket.bucketName });
  }
}
