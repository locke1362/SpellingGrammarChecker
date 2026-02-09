# AWS Connect Message Processing Lambda - Grammar/Spelling Check with Bedrock

Python Lambda function that uses Amazon Bedrock with Amazon Nova Lite to perform grammar and spelling checks on Amazon Connect chat messages before they reach participants.

## Overview

This Lambda integrates with [Amazon Connect's message processing feature](https://docs.aws.amazon.com/connect/latest/adminguide/redaction-message-processing.html) to automatically correct spelling and grammar mistakes in real-time chat conversations using Amazon Nova Lite via Amazon Bedrock.

## Features

- Uses Amazon Nova Lite for intelligent grammar and spelling corrections
- Preserves original meaning and tone
- Handles AWS Connect's input/output format
- Graceful error handling (returns original message on failure)
- Low latency and cost-effective
- Deployed in us-west-2 region

## Architecture

```
Amazon Connect Chat → Lambda Function → Amazon Bedrock (Nova Lite) → Corrected Message → Chat Participant
```

## Input Format

```json
{
  "version": "1.0",
  "instanceId": "string",
  "associatedResourceArn": "string",
  "chatContent": {
    "absoluteTime": "string",
    "content": "string",
    "contentType": "string",
    "id": "string",
    "participantId": "string",
    "displayName": "string",
    "participantRole": "string",
    "initialContactId": "string",
    "contactId": "string"
  }
}
```

## Output Format

```json
{
  "status": "PROCESSED",
  "result": {
    "processedChatContent": {
      "content": "corrected message text",
      "contentType": "text/plain"
    }
  }
}
```

## Deployment

### Prerequisites

1. Enable Amazon Bedrock model access:
   - Go to AWS Console → Bedrock → Model access
   - Request access to Amazon Nova Lite (amazon.nova-lite-v1:0)
   - Wait for approval (usually instant)

2. Create IAM execution role with these policies:
   - `AWSLambdaBasicExecutionRole` (for CloudWatch Logs)
   - Custom policy for Bedrock:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "bedrock:InvokeModel"
         ],
         "Resource": "arn:aws:bedrock:us-west-2::foundation-model/amazon.nova-lite-v1:0"
       }
     ]
   }
   ```

### Deploy Lambda

1. Package the Lambda function:
   ```bash
   zip lambda_function.zip lambda_function.py
   ```

2. Create Lambda function (must be in us-west-2 or region with Bedrock access):
   ```bash
   aws lambda create-function \
     --function-name connect-grammar-checker-bedrock \
     --runtime python3.11 \
     --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-bedrock-execution-role \
     --handler lambda_function.lambda_handler \
     --zip-file fileb://lambda_function.zip \
     --timeout 30 \
     --region us-west-2
   ```

3. Configure in Amazon Connect:
   - Go to your Contact Flow
   - Add "Set recording and analytics behavior" block
   - Specify this Lambda function for custom message processing
   - Ensure Amazon Connect has permission to invoke the Lambda

**Note**: Amazon Nova Lite requires using cross-region inference profile. The model ID is `us.amazon.nova-lite-v1:0`.

## Production Enhancements

Consider these improvements for production:

1. **Caching**: Cache corrections for identical messages to reduce Bedrock calls
2. **Batch Processing**: If processing multiple messages, consider batching
3. **Fallback Logic**: Implement regex-based fallback if Bedrock is unavailable
4. **Language Detection**: Add language detection and pass to Claude for better results
5. **Custom Instructions**: Adjust the prompt based on participant role (agent vs customer)
6. **Metrics**: Add custom CloudWatch metrics for correction rate and quality

## IAM Permissions

The Lambda execution role needs:

1. Basic Lambda execution:
   - `logs:CreateLogGroup`
   - `logs:CreateLogStream`
   - `logs:PutLogEvents`

2. Bedrock access:
   - `bedrock:InvokeModel` for Amazon Nova Lite

Example IAM policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:us-west-2::foundation-model/amazon.nova-lite-v1:0"
    }
  ]
}
```

## Configuration

The Lambda uses:
- **Model**: Amazon Nova Lite via cross-region inference (`us.amazon.nova-lite-v1:0`)
- **Region**: us-west-2
- **Temperature**: 0.0 (for consistent corrections)
- **Max Tokens**: 1000
- **Timeout**: 30 seconds (recommended)

## Cost Considerations

Amazon Nova Lite pricing (as of 2026):
- Input: ~$0.06 per million tokens
- Output: ~$0.24 per million tokens

For typical chat messages (50-100 tokens), cost per correction is minimal (~$0.00002-0.00004 per message).

## Testing

### Local Testing (Mock Mode)

Since Bedrock requires AWS credentials, create a mock test:

```python
# Set AWS credentials first
# export AWS_ACCESS_KEY_ID=your_key
# export AWS_SECRET_ACCESS_KEY=your_secret
# export AWS_SESSION_TOKEN=your_token (if using temporary credentials)

python test_lambda.py
```

### Test Event

```json
{
  "version": "1.0",
  "instanceId": "test-instance",
  "associatedResourceArn": "arn:aws:connect:us-east-1:123456789012:instance/test",
  "chatContent": {
    "content": "teh quick brown fox recieve your message",
    "contentType": "text/plain",
    "participantRole": "CUSTOMER"
  }
}
```

Expected output: "The quick brown fox receive your message"

### Lambda Console Testing

Use the AWS Lambda console test feature with the above test event to verify the function works with Bedrock.

## Monitoring

Monitor the Lambda function:
- CloudWatch Logs for execution logs and errors
- CloudWatch Metrics for invocation count, duration, and errors
- Bedrock metrics for model invocation latency and throttling

## Troubleshooting

**Error: "Could not resolve the foundation model"**
- Ensure you've enabled model access in Bedrock console
- Verify the model ID is correct: `us.amazon.nova-lite-v1:0` (cross-region inference profile)
- Check that your region supports Amazon Nova Lite cross-region inference

**Error: "AccessDeniedException"**
- Check IAM role has `bedrock:InvokeModel` permission
- Verify the resource ARN in the policy matches the model

**High latency**
- Amazon Nova Lite is optimized for speed and cost
- Consider increasing Lambda timeout if needed
- Check CloudWatch metrics for Bedrock invocation time
