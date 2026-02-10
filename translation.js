const { ComprehendClient, DetectDominantLanguageCommand } = require("@aws-sdk/client-comprehend");
const { TranslateClient, TranslateTextCommand } = require("@aws-sdk/client-translate");
const { DynamoDBClient, PutItemCommand, GetItemCommand } = require("@aws-sdk/client-dynamodb");

const comprehendClient = new ComprehendClient({});
const translateClient = new TranslateClient({});
const dynamoClient = new DynamoDBClient({});
const tableName = process.env.TABLE_NAME;

exports.handler = async (event) => {
    let participantRole = event.chatContent.participantRole;
    let content = event.chatContent.content;
    let contactId = event.chatContent.contactId;

    try {
        if (participantRole === 'CUSTOMER') {
            const detectLanguageCommand = new DetectDominantLanguageCommand({ Text: content });
            const languageResult = await comprehendClient.send(detectLanguageCommand);
            const dominantLanguage = languageResult.Languages[0];
            
            let finalContent = content;
            
            if (dominantLanguage.LanguageCode !== 'en' && dominantLanguage.Score > 0.5) {
                await dynamoClient.send(new PutItemCommand({
                    TableName: tableName,
                    Item: {
                        contactId: { S: contactId },
                        language: { S: dominantLanguage.LanguageCode }
                    }
                }));
                
                const translateCommand = new TranslateTextCommand({
                    Text: content,
                    SourceLanguageCode: dominantLanguage.LanguageCode,
                    TargetLanguageCode: 'en'
                });
                const translateResult = await translateClient.send(translateCommand);
                finalContent = `${content} (Translated to English: ${translateResult.TranslatedText})`;
            }
            
            return {
                status: "PROCESSED",
                result: {
                    processedChatContent: {
                        content: finalContent,
                        contentType: "text/plain"
                    }
                }
            };
        } else {
            const getItemCommand = new GetItemCommand({
                TableName: tableName,
                Key: { contactId: { S: contactId } }
            });
            const result = await dynamoClient.send(getItemCommand);
            
            let finalContent = content;
            
            if (result.Item && result.Item.language) {
                const customerLanguage = result.Item.language.S;
                if (customerLanguage !== 'en') {
                    const translateCommand = new TranslateTextCommand({
                        Text: content,
                        SourceLanguageCode: 'en',
                        TargetLanguageCode: customerLanguage
                    });
                    const translateResult = await translateClient.send(translateCommand);
                    finalContent = `${content} (Translated to ${customerLanguage}: ${translateResult.TranslatedText})`;
                }
            }
            
            return {
                status: "PROCESSED",
                result: {
                    processedChatContent: {
                        content: finalContent,
                        contentType: "text/plain"
                    }
                }
            };
        }
    } catch (error) {
        console.error('Error processing content:', error);
        return {
            status: "FAILED",
            result: {
                processedChatContent: {
                    content: content,
                    contentType: "text/plain"
                }
            }
        };
    }
};
