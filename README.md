require("dotenv").config();
const { Configuration, OpenAIApi } = require("openai");

const configuration = new Configuration({
    apiKey: process.env.OPENAI_API_KEY,
});
const openai = new OpenAIApi(configuration);

async function getAIResponse() {
    const response = await openai.createChatCompletion({
        model: "gpt-4",
        messages: [{ role: "user", content: "write a haiku about AI" }],
    });
    console.log(response.data.choices[0].message.content);
}

getAIResponse();
