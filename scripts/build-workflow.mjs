import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, "..");
const jsPath = path.join(root, "workflow-assets", "ai-agent-orchestrator.js");
const outDir = path.join(root, "workflows");
const outPath = path.join(outDir, "telegram-ai-assistant.json");

const jsCode = await readFile(jsPath, "utf8");

const buildGroqRecommendationRequestCode = String.raw`const source = $items("AI Agent Orchestrator")[0]?.json ?? {};
const searchResult = $input.first()?.json ?? {};

function plainTextFromHtml(html) {
  return String(html || "")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\s+/g, " ")
    .trim();
}

function extractHtml(value) {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value?.data === "string") {
    return value.data;
  }
  if (typeof value?.body === "string") {
    return value.body;
  }
  if (typeof value?.response === "string") {
    return value.response;
  }
  return JSON.stringify(value || {});
}

function parseDuckDuckGoSnippets(html) {
  const snippets = [];
  const resultRegex = /<a[^>]+class="[^"]*result__a[^"]*"[^>]*>([\s\S]*?)<\/a>[\s\S]*?<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>([\s\S]*?)<\/a>/gi;
  let match;
  while ((match = resultRegex.exec(html)) && snippets.length < 8) {
    const title = plainTextFromHtml(match[1]);
    const snippet = plainTextFromHtml(match[2]);
    if (title || snippet) {
      snippets.push((title + ": " + snippet).trim());
    }
  }
  if (snippets.length > 0) {
    return snippets;
  }
  const compact = plainTextFromHtml(html);
  return compact ? [compact.slice(0, 1800)] : [];
}

const preferences = String(source.preferences || "").trim();
const html = extractHtml(searchResult);
const snippets = parseDuckDuckGoSnippets(html).slice(0, 10);
const model = $env.GROQ_MODEL || "llama-3.3-70b-versatile";

const systemPrompt = [
  "You are a sharp movie recommendation assistant for Telegram.",
  "First understand the user's free-form request, including genre, language, runtime, mood, exclusions, and examples.",
  "Use the supplied web search snippets as supporting context. If snippets are weak, rely on your film knowledge and say that web evidence was limited.",
  "Return exactly 5 movies that best match the user's preferences.",
  "Avoid spoilers.",
  "Do not recommend series unless the user asks for series.",
  "Prefer real, released movies.",
  "Use this exact plain-text format:",
  "Top 5 movie matches",
  "",
  "1. Title (Year)",
  "Genre/language: ...",
  "Why it fits: ...",
  "Match score: x/10",
  "",
  "Keep each movie to 2-3 short lines and end with: Want a brief for any one of these?"
].join(" ");

const userPrompt = [
  "User preferences: " + preferences,
  "",
  "Web search snippets:",
  snippets.length ? snippets.map((snippet, index) => (index + 1) + ". " + snippet).join("\n") : "No snippets were found.",
  "",
  "Format the answer for Telegram in plain text. Keep it concise and readable."
].join("\n");

return [
  {
    json: {
      chatId: source.chatId,
      preferences,
      httpBody: source.httpBody,
      groqRequest: {
        model,
        temperature: 0.45,
        max_tokens: 1100,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt }
        ]
      }
    }
  }
];`;

const extractRecommendationReplyCode = String.raw`const source = $items("Build Groq Recommendation Request")[0]?.json ?? {};
const payload = $input.first()?.json ?? {};
const body = payload.body ?? payload;
const content = body?.choices?.[0]?.message?.content;

function truncateTelegram(text) {
  const safe = typeof text === "string" ? text.trim() : "";
  if (!safe) {
    return "I could not build a recommendation response this time.";
  }
  return safe.length <= 3900 ? safe : safe.slice(0, 3890) + "...";
}

function mainMenuMarkup() {
  return {
    inline_keyboard: [
      [{ text: "Movie recommendation", callback_data: "movie_recommendation" }],
      [{ text: "Movie brief", callback_data: "movie_brief" }],
      [{ text: "Movie review", callback_data: "movie_review" }]
    ]
  };
}

const replyText = truncateTelegram(content || [
  "I could not complete the movie recommendation request this time.",
  "",
  "Reason: Groq did not return recommendation text.",
  "",
  "Please try again with /recommend, or adjust the preferences."
].join("\n"));

return [
  {
    json: {
      shouldSend: true,
      chatId: source.chatId,
      replyText,
      replyMarkup: mainMenuMarkup(),
      telegramMessage: {
        chat_id: source.chatId,
        text: replyText,
        disable_web_page_preview: true,
        reply_markup: mainMenuMarkup()
      },
      httpBody: source.httpBody ?? {
        ok: true,
        status: "processed",
        route: "recommendation"
      }
    }
  }
];`;

const workflow = {
  id: "7f0f3df4-b71a-4f1a-ae6a-65b6f4e2a9a4",
  name: "Telegram AI Assistant - Groq + Supabase",
  nodes: [
    {
      parameters: {
        httpMethod: "POST",
        path: "telegram-assistant",
        responseMode: "responseNode",
        options: {}
      },
      id: "8cc6c6c4-e85f-48b4-b7ca-73c12fc4db54",
      name: "Telegram Webhook",
      type: "n8n-nodes-base.webhook",
      typeVersion: 2,
      position: [-620, 160],
      webhookId: "telegram-ai-assistant"
    },
    {
      parameters: {
        jsCode
      },
      id: "2eea4c7f-4c0b-4ce6-b379-b1f0ef548d1e",
      name: "AI Agent Orchestrator",
      type: "n8n-nodes-base.code",
      typeVersion: 2,
      position: [-320, 160]
    },
    {
      parameters: {
        conditions: {
          boolean: [
            {
              value1: "={{$json.shouldSend}}",
              value2: true
            }
          ]
        }
      },
      id: "851870d7-9af7-4aea-8ccf-5626cca7cb4c",
      name: "Should Send Reply?",
      type: "n8n-nodes-base.if",
      typeVersion: 2,
      position: [-60, 160]
    },
    {
      parameters: {
        conditions: {
          boolean: [
            {
              value1: "={{$json.shouldRecommend}}",
              value2: true
            }
          ]
        }
      },
      id: "a4d6c50d-055c-4f4c-964f-84ac1f45e4c2",
      name: "Should Recommend?",
      type: "n8n-nodes-base.if",
      typeVersion: 2,
      position: [-80, 160]
    },
    {
      parameters: {
        method: "POST",
        url: "=https://api.telegram.org/bot{{$env.TELEGRAM_BOT_TOKEN}}/sendMessage",
        sendHeaders: true,
        headerParameters: {
          parameters: [
            {
              name: "Content-Type",
              value: "application/json"
            }
          ]
        },
        sendBody: true,
        specifyBody: "json",
        jsonBody: '={{ {"chat_id": $json.chatId, "text": $json.statusMessage, "disable_web_page_preview": true} }}',
        options: {
          timeout: 30000
        }
      },
      id: "82a45979-bd5b-473a-af1f-75baf5cf0d20",
      name: "Telegram Recommendation Status",
      type: "n8n-nodes-base.httpRequest",
      typeVersion: 4.2,
      position: [180, -120],
      onError: "continueRegularOutput"
    },
    {
      parameters: {
        method: "GET",
        url: '={{"https://html.duckduckgo.com/html/?q=" + encodeURIComponent($items("AI Agent Orchestrator")[0].json.searchQuery)}}',
        sendHeaders: true,
        headerParameters: {
          parameters: [
            {
              name: "User-Agent",
              value: "Mozilla/5.0 TelegramMovieBot/1.0"
            }
          ]
        },
        options: {
          timeout: 10000,
          response: {
            response: {
              responseFormat: "text",
              outputPropertyName: "data"
            }
          }
        }
      },
      id: "e37b5582-9015-4426-adc1-58f6a66976aa",
      name: "Web Search Movies",
      type: "n8n-nodes-base.httpRequest",
      typeVersion: 4.2,
      position: [440, -120],
      onError: "continueRegularOutput"
    },
    {
      parameters: {
        jsCode: buildGroqRecommendationRequestCode
      },
      id: "3e8d8d4e-5f74-4b13-bff4-4223e6291023",
      name: "Build Groq Recommendation Request",
      type: "n8n-nodes-base.code",
      typeVersion: 2,
      position: [700, -120]
    },
    {
      parameters: {
        method: "POST",
        url: '={{($env.GROQ_BASE_URL || "https://api.groq.com/openai/v1").replace(/\\/+$/, "") + "/chat/completions"}}',
        sendHeaders: true,
        headerParameters: {
          parameters: [
            {
              name: "Authorization",
              value: "={{'Bearer ' + $env.GROQ_API_KEY}}"
            },
            {
              name: "Content-Type",
              value: "application/json"
            }
          ]
        },
        sendBody: true,
        specifyBody: "json",
        jsonBody: "={{$json.groqRequest}}",
        options: {
          timeout: 45000
        }
      },
      id: "eb907ae8-136a-4841-980f-4cf7f22be8fa",
      name: "Groq Recommendation Request",
      type: "n8n-nodes-base.httpRequest",
      typeVersion: 4.2,
      position: [960, -120],
      onError: "continueRegularOutput"
    },
    {
      parameters: {
        jsCode: extractRecommendationReplyCode
      },
      id: "fa1907e0-c582-4688-a9c5-4ef23270b35f",
      name: "Extract Recommendation Reply",
      type: "n8n-nodes-base.code",
      typeVersion: 2,
      position: [1220, -120]
    },
    {
      parameters: {
        method: "POST",
        url: "=https://api.telegram.org/bot{{$env.TELEGRAM_BOT_TOKEN}}/sendMessage",
        sendHeaders: true,
        headerParameters: {
          parameters: [
            {
              name: "Content-Type",
              value: "application/json"
            }
          ]
        },
        sendBody: true,
        specifyBody: "json",
        jsonBody: "={{$json.telegramMessage}}",
        options: {
          timeout: 30000
        }
      },
      id: "991e135f-5ba5-43d2-a52c-91fae7b76144",
      name: "Telegram Send Message",
      type: "n8n-nodes-base.httpRequest",
      typeVersion: 4.2,
      position: [1480, 60],
      onError: "continueRegularOutput"
    },
    {
      parameters: {
        respondWith: "json",
        responseBody: '={{$json.httpBody ?? $json}}',
        options: {
          responseCode: 200
        }
      },
      id: "72dc93a4-36d2-48fa-a38b-861b73c95da2",
      name: "Respond 200",
      type: "n8n-nodes-base.respondToWebhook",
      typeVersion: 1.3,
      position: [1740, 160]
    }
  ],
  connections: {
    "Telegram Webhook": {
      main: [
        [
          {
            node: "AI Agent Orchestrator",
            type: "main",
            index: 0
          }
        ]
      ]
    },
    "AI Agent Orchestrator": {
      main: [
        [
          {
            node: "Should Recommend?",
            type: "main",
            index: 0
          }
        ]
      ]
    },
    "Should Recommend?": {
      main: [
        [
          {
            node: "Telegram Recommendation Status",
            type: "main",
            index: 0
          }
        ],
        [
          {
            node: "Should Send Reply?",
            type: "main",
            index: 0
          }
        ]
      ]
    },
    "Telegram Recommendation Status": {
      main: [
        [
          {
            node: "Web Search Movies",
            type: "main",
            index: 0
          }
        ]
      ]
    },
    "Web Search Movies": {
      main: [
        [
          {
            node: "Build Groq Recommendation Request",
            type: "main",
            index: 0
          }
        ]
      ]
    },
    "Build Groq Recommendation Request": {
      main: [
        [
          {
            node: "Groq Recommendation Request",
            type: "main",
            index: 0
          }
        ]
      ]
    },
    "Groq Recommendation Request": {
      main: [
        [
          {
            node: "Extract Recommendation Reply",
            type: "main",
            index: 0
          }
        ]
      ]
    },
    "Extract Recommendation Reply": {
      main: [
        [
          {
            node: "Telegram Send Message",
            type: "main",
            index: 0
          }
        ]
      ]
    },
    "Should Send Reply?": {
      main: [
        [
          {
            node: "Telegram Send Message",
            type: "main",
            index: 0
          }
        ],
        [
          {
            node: "Respond 200",
            type: "main",
            index: 0
          }
        ]
      ]
    },
    "Telegram Send Message": {
      main: [
        [
          {
            node: "Respond 200",
            type: "main",
            index: 0
          }
        ]
      ]
    }
  },
  pinData: {},
  settings: {
    executionOrder: "v1",
    saveDataErrorExecution: "all",
    saveDataSuccessExecution: "all",
    saveManualExecutions: true,
    callerPolicy: "workflowsFromSameOwner"
  },
  staticData: null,
  meta: {
    templateCredsSetupCompleted: true
  },
  tags: [],
  active: false,
  versionId: "f8f3b70b-8313-46fd-9d35-a9bdcb3e5be6"
};

await mkdir(outDir, { recursive: true });
await writeFile(outPath, `${JSON.stringify(workflow, null, 2)}\n`, "utf8");
console.log(`Generated ${outPath}`);
