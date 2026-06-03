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
      position: [200, 60],
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
      position: [460, 160]
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
            node: "Should Send Reply?",
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
