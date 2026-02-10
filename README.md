# AWS Connect Message Processing Lambda - Grammar Check & Live Translation

Python Lambda function that uses Amazon Bedrock with Amazon Nova Lite for grammar/spelling checks and AWS Translate for live translation on Amazon Connect chat messages.

## Overview

This Lambda integrates with [Amazon Connect's message processing feature](https://docs.aws.amazon.com/connect/latest/adminguide/redaction-message-processing.html) to:
- Automatically detect customer language using AWS Comprehend
- Translate customer messages to English for agents
- Apply grammar and spelling corrections using Amazon Bedrock (Nova Lite)
- Translate agent responses back to customer's language
- Store language preferences in DynamoDB for the conversation

## Features

- **Language Detection**: Automatically detects customer's language using AWS Comprehend
- **Live Translation**: Translates customer messages to English and agent messages to customer's language
- **Grammar Correction**: Uses Amazon Nova Lite for intelligent grammar and spelling corrections
- **Language Persistence**: Stores customer language preference in DynamoDB per contact
- **Bilingual Display**: Shows both original and translated text
- **Graceful Fallback**: Returns original message on any failure
- **Low Latency**: Optimized for real-time chat conversations

## Architecture

```
Customer Message (Any Language) → Lambda → Comprehend (Detect Language) → DynamoDB (Store Preference)
                                         ↓
                                    Translate (to English) → Bedrock (Grammar Check) → Agent

Agent Message (English) → Lambda → Bedrock (Grammar Check) → DynamoDB (Get Preference)
                                         ↓
                                    Translate (to Customer Language) → Customer
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

1. **DynamoDB Table**: Create a table to store language preferences
   ```bash
   aws dynamodb create-table \
     --table-name ConnectTranslationTable \
     --attribute-definitions AttributeName=contactId,AttributeType=S \
     --key-schema AttributeName=contactId,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST \
     --region us-west-2
   ```

2. **Enable Amazon Bedrock model access**:
   - Go to AWS Console → Bedrock → Model access
   - Request access to Amazon Nova Lite (amazon.nova-lite-v1:0)
   - Wait for approval (usually instant)

3. **Create IAM execution role** with these policies:
   - `AWSLambdaBasicExecutionRole` (for CloudWatch Logs)
   - Custom policy for Bedrock, Translate, Comprehend, and DynamoDB:
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
       },
       {
         "Effect": "Allow",
         "Action": [
           "translate:TranslateText"
         ],
         "Resource": "*"
       },
       {
         "Effect": "Allow",
         "Action": [
           "comprehend:DetectDominantLanguage"
         ],
         "Resource": "*"
       },
       {
         "Effect": "Allow",
         "Action": [
           "dynamodb:PutItem",
           "dynamodb:GetItem"
         ],
         "Resource": "arn:aws:dynamodb:us-west-2:YOUR_ACCOUNT_ID:table/ConnectTranslationTable"
       }
     ]
   }
   ```

### Deploy Lambda

1. Package the Lambda function:
   ```bash
   zip lambda_function.zip lambda_function.py
   ```

2. Create Lambda function with environment variable:
   ```bash
   aws lambda create-function \
     --function-name connect-translation-grammar-checker \
     --runtime python3.11 \
     --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-translation-execution-role \
     --handler lambda_function.lambda_handler \
     --zip-file fileb://lambda_function.zip \
     --timeout 30 \
     --environment Variables={TABLE_NAME=ConnectTranslationTable} \
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

1. **Caching**: Cache corrections and translations for identical messages to reduce API calls
2. **Batch Processing**: If processing multiple messages, consider batching where possible
3. **Fallback Logic**: Implement regex-based fallback if Bedrock is unavailable
4. **Language Detection**: Add manual language override option for customers
5. **Custom Instructions**: Adjust prompts based on participant role and industry
6. **Metrics**: Add custom CloudWatch metrics for translation rate, language distribution, and quality
7. **TTL**: Add Time-To-Live to DynamoDB items to auto-cleanup old language preferences
8. **Multi-language Agents**: Support agents who speak multiple languages natively

## IAM Permissions

The Lambda execution role needs:

1. Basic Lambda execution:
   - `logs:CreateLogGroup`
   - `logs:CreateLogStream`
   - `logs:PutLogEvents`

2. Bedrock access:
   - `bedrock:InvokeModel` for Amazon Nova Lite

3. Translation services:
   - `translate:TranslateText`
   - `comprehend:DetectDominantLanguage`

4. DynamoDB access:
   - `dynamodb:PutItem`
   - `dynamodb:GetItem`

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
    },
    {
      "Effect": "Allow",
      "Action": [
        "translate:TranslateText",
        "comprehend:DetectDominantLanguage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem"
      ],
      "Resource": "arn:aws:dynamodb:us-west-2:YOUR_ACCOUNT_ID:table/ConnectTranslationTable"
    }
  ]
}
```

## Configuration

The Lambda uses:
- **Model**: Amazon Nova Lite via cross-region inference (`us.amazon.nova-lite-v1:0`)
- **Translation**: AWS Translate for language conversion
- **Language Detection**: AWS Comprehend for automatic language detection
- **Storage**: DynamoDB for language preference persistence
- **Region**: us-west-2
- **Temperature**: 0.0 (for consistent corrections)
- **Max Tokens**: 1000
- **Timeout**: 30 seconds (recommended)

## Environment Variables

- `TABLE_NAME`: DynamoDB table name for storing language preferences (default: `ConnectTranslationTable`)

## Cost Considerations

**Amazon Nova Lite** (as of 2026):
- Input: ~$0.06 per million tokens
- Output: ~$0.24 per million tokens

**AWS Translate**:
- ~$15 per million characters

**AWS Comprehend**:
- ~$0.0001 per unit (100 characters)

**DynamoDB**:
- Pay-per-request: $1.25 per million write requests, $0.25 per million read requests

For typical chat messages (50-100 tokens/characters), total cost per message is minimal (~$0.0001-0.0003 per message with translation).

## Testing

### Local Testing (Mock Mode)

Since the function requires AWS credentials and services, set up your environment:

```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_SESSION_TOKEN=your_token  # if using temporary credentials
export TABLE_NAME=ConnectTranslationTable
```

### Test Event - Customer Message (Spanish)

```json
{
  "version": "1.0",
  "instanceId": "test-instance",
  "associatedResourceArn": "arn:aws:connect:us-east-1:123456789012:instance/test",
  "chatContent": {
    "content": "Hola, necesito ayuda con mi pedido",
    "contentType": "text/plain",
    "participantRole": "CUSTOMER",
    "contactId": "contact-123"
  }
}
```

Expected output: Original Spanish text + English translation with grammar check

### Test Event - Agent Response

```json
{
  "version": "1.0",
  "instanceId": "test-instance",
  "associatedResourceArn": "arn:aws:connect:us-east-1:123456789012:instance/test",
  "chatContent": {
    "content": "I can help you with your order",
    "contentType": "text/plain",
    "participantRole": "AGENT",
    "contactId": "contact-123"
  }
}
```

Expected output: Grammar-checked English + Spanish translation (if customer language was detected)

### Lambda Console Testing

Use the AWS Lambda console test feature with the above test events to verify the function works with all services.

## Monitoring

Monitor the Lambda function:
- CloudWatch Logs for execution logs and errors
- CloudWatch Metrics for invocation count, duration, and errors
- Bedrock metrics for model invocation latency and throttling
- DynamoDB metrics for read/write capacity
- Translate/Comprehend usage in AWS Cost Explorer

## Troubleshooting

**Error: "Could not resolve the foundation model"**
- Ensure you've enabled model access in Bedrock console
- Verify the model ID is correct: `us.amazon.nova-lite-v1:0` (cross-region inference profile)
- Check that your region supports Amazon Nova Lite cross-region inference

**Error: "AccessDeniedException"**
- Check IAM role has all required permissions (Bedrock, Translate, Comprehend, DynamoDB)
- Verify the resource ARNs in the policy match your resources

**Error: "ResourceNotFoundException" (DynamoDB)**
- Ensure the DynamoDB table exists: `ConnectTranslationTable`
- Verify the TABLE_NAME environment variable is set correctly
- Check the table is in the same region as the Lambda

**Translation not working**
- Verify AWS Translate supports the detected language
- Check Comprehend confidence score (must be > 0.5)
- Review CloudWatch logs for language detection results

**High latency**
- Amazon Nova Lite is optimized for speed and cost
- Translation adds ~200-500ms per message
- Consider increasing Lambda timeout if needed
- Check CloudWatch metrics for each service invocation time
