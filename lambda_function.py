import json
import boto3
import os
from typing import Dict, Any

# Initialize AWS clients
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-west-2')
comprehend_client = boto3.client('comprehend')
translate_client = boto3.client('translate')
dynamodb_client = boto3.client('dynamodb')

# Get DynamoDB table name from environment variable
TABLE_NAME = os.environ.get('TABLE_NAME', 'ConnectTranslationTable')

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
        participant_role = chat_content.get('participantRole', '')
        contact_id = chat_content.get('contactId', '')
        
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
        
        # Process based on participant role
        if participant_role == 'CUSTOMER':
            processed_content = process_customer_message(original_content, contact_id)
        elif participant_role == 'AGENT':
            processed_content = process_agent_message(original_content, contact_id)
        else:
            # Unknown role, just apply grammar check
            processed_content = check_grammar_with_bedrock(original_content)
        
        # Return processed message
        return {
            "status": "PROCESSED",
            "result": {
                "processedChatContent": {
                    "content": processed_content,
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


def process_customer_message(content: str, contact_id: str) -> str:
    """
    Process customer message: detect language, translate to English if needed, apply grammar check.
    
    Args:
        content: The customer's message
        contact_id: The contact ID for storing language preference
        
    Returns:
        Processed message content
    """
    try:
        # Detect the dominant language
        detect_response = comprehend_client.detect_dominant_language(Text=content)
        languages = detect_response.get('Languages', [])
        
        if not languages:
            # No language detected, just apply grammar check
            return check_grammar_with_bedrock(content)
        
        dominant_language = languages[0]
        language_code = dominant_language.get('LanguageCode', 'en')
        confidence_score = dominant_language.get('Score', 0.0)
        
        # If not English and confidence is high, translate
        if language_code != 'en' and confidence_score > 0.5:
            # Store customer's language preference in DynamoDB
            try:
                dynamodb_client.put_item(
                    TableName=TABLE_NAME,
                    Item={
                        'contactId': {'S': contact_id},
                        'language': {'S': language_code}
                    }
                )
            except Exception as e:
                print(f"Error storing language preference: {str(e)}")
            
            # Translate to English
            translate_response = translate_client.translate_text(
                Text=content,
                SourceLanguageCode=language_code,
                TargetLanguageCode='en'
            )
            translated_text = translate_response.get('TranslatedText', content)
            
            # Apply grammar check to translated text
            corrected_text = check_grammar_with_bedrock(translated_text)
            
            # Return original with translation
            return f"{content} (Translated to English: {corrected_text})"
        else:
            # English message, just apply grammar check
            return check_grammar_with_bedrock(content)
            
    except Exception as e:
        print(f"Error processing customer message: {str(e)}")
        # Fallback to grammar check only
        return check_grammar_with_bedrock(content)


def process_agent_message(content: str, contact_id: str) -> str:
    """
    Process agent message: apply grammar check, translate to customer's language if needed.
    
    Args:
        content: The agent's message
        contact_id: The contact ID for retrieving language preference
        
    Returns:
        Processed message content
    """
    try:
        # Apply grammar check first
        corrected_content = check_grammar_with_bedrock(content)
        
        # Check if customer has a language preference
        try:
            get_response = dynamodb_client.get_item(
                TableName=TABLE_NAME,
                Key={'contactId': {'S': contact_id}}
            )
            
            item = get_response.get('Item')
            if item and 'language' in item:
                customer_language = item['language']['S']
                
                # If customer's language is not English, translate
                if customer_language != 'en':
                    translate_response = translate_client.translate_text(
                        Text=corrected_content,
                        SourceLanguageCode='en',
                        TargetLanguageCode=customer_language
                    )
                    translated_text = translate_response.get('TranslatedText', corrected_content)
                    
                    # Return original with translation
                    return f"{corrected_content} (Translated to {customer_language}: {translated_text})"
        
        except Exception as e:
            print(f"Error retrieving language preference: {str(e)}")
        
        # No translation needed or error occurred
        return corrected_content
        
    except Exception as e:
        print(f"Error processing agent message: {str(e)}")
        return content


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
