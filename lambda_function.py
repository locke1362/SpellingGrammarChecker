import json
import boto3
from typing import Dict, Any

# Initialize Bedrock client
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-west-2')

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda function for grammar/spelling check on Amazon Connect chat messages.
    
    Input format from AWS Connect:
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
    
    Output format:
    {
      "status": "PROCESSED"|"APPROVED"|"FAILED"|"REJECTED",
      "result": {
        "processedChatContent": {
          "content": "string",
          "contentType": "string"
        }
      }
    }
    """
    
    try:
        # Extract chat content
        chat_content = event.get('chatContent', {})
        original_content = chat_content.get('content', '')
        content_type = chat_content.get('contentType', 'text/plain')
        
        # Skip processing if content is empty
        if not original_content or not original_content.strip():
            return {
                "status": "PROCESSED",
                "result": {
                    "processedChatContent": {
                        "content": original_content,
                        "contentType": content_type
                    }
                }
            }
        
        # Perform grammar and spelling check using Bedrock
        corrected_content = check_grammar_with_bedrock(original_content)
        
        # Return processed message
        return {
            "status": "PROCESSED",
            "result": {
                "processedChatContent": {
                    "content": corrected_content,
                    "contentType": content_type
                }
            }
        }
        
    except Exception as e:
        print(f"Error processing message: {str(e)}")
        return {
            "status": "FAILED",
            "result": {
                "processedChatContent": {
                    "content": event.get('chatContent', {}).get('content', ''),
                    "contentType": event.get('chatContent', {}).get('contentType', 'text/plain')
                }
            }
        }


def check_grammar_with_bedrock(text: str) -> str:
    """
    Use Amazon Bedrock with Amazon Nova Lite to perform grammar and spelling corrections.
    
    Args:
        text: The original text to check and correct
        
    Returns:
        The corrected text
    """
    
    try:
        # Prepare the prompt for Nova Lite
        prompt = f"""You are a grammar and spelling checker. Your task is to correct any spelling or grammar errors in the provided text while preserving the original meaning and tone.

Rules:
- Only fix spelling and grammar mistakes
- Do not change the meaning or add new content
- Preserve the original tone and style
- Return ONLY the corrected text, nothing else
- If the text is already correct, return it unchanged

Text to check:
{text}

Corrected text:"""

        # Prepare request body for Amazon Nova Lite
        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "inferenceConfig": {
                "max_new_tokens": 1000,
                "temperature": 0.0,
                "top_p": 1.0
            }
        }
        
        # Call Bedrock with Nova Lite using cross-region inference profile
        response = bedrock_runtime.invoke_model(
            modelId='us.amazon.nova-lite-v1:0',
            contentType='application/json',
            accept='application/json',
            body=json.dumps(request_body)
        )
        
        # Parse response
        response_body = json.loads(response['body'].read())
        corrected_text = response_body['output']['message']['content'][0]['text'].strip()
        
        return corrected_text
        
    except Exception as e:
        print(f"Error calling Bedrock: {str(e)}")
        # Return original text if Bedrock call fails
        return text
