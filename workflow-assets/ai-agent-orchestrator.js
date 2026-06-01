const inputItem = $input.first();
const update = inputItem?.json ?? {};
const env = process.env;

const MODEL = env.GROQ_MODEL || "llama-3.3-70b-versatile";
const GROQ_BASE_URL = (env.GROQ_BASE_URL || "https://api.groq.com/openai/v1").replace(/\/+$/, "");
const SUPABASE_URL = (env.SUPABASE_URL || "").replace(/\/+$/, "");
const SUPABASE_KEY = env.SUPABASE_ANON_KEY || "";
const TELEGRAM_WEBHOOK_SECRET = env.TELEGRAM_WEBHOOK_SECRET || "";
const MESSAGE_LIMIT = Number.parseInt(env.SUPABASE_CONTEXT_MESSAGE_LIMIT || "12", 10);
const MEMORY_LIMIT = Number.parseInt(env.SUPABASE_CONTEXT_MEMORY_LIMIT || "10", 10);
const HAS_SUPABASE = Boolean(SUPABASE_URL && SUPABASE_KEY);
const HAS_GROQ = Boolean(env.GROQ_API_KEY);

function truncateTelegram(text) {
  const safe = typeof text === "string" ? text.trim() : "";
  if (!safe) {
    return "I received your message, but I could not build a response this time.";
  }
  return safe.length <= 3900 ? safe : `${safe.slice(0, 3890)}...`;
}

function stripCodeFence(value) {
  if (typeof value !== "string") {
    return value;
  }
  return value
    .replace(/^```json\s*/i, "")
    .replace(/^```\s*/i, "")
    .replace(/\s*```$/i, "")
    .trim();
}

function tryParseJson(text) {
  if (typeof text !== "string") {
    return null;
  }
  const cleaned = stripCodeFence(text);
  try {
    return JSON.parse(cleaned);
  } catch {
    const start = cleaned.indexOf("{");
    const end = cleaned.lastIndexOf("}");
    if (start >= 0 && end > start) {
      try {
        return JSON.parse(cleaned.slice(start, end + 1));
      } catch {
        return null;
      }
    }
    return null;
  }
}

function detectRoute(messageText) {
  const text = (messageText || "").trim();
  if (!text.startsWith("/")) {
    return {
      route: "chat",
      command: "",
      commandArg: "",
      unknownCommand: false
    };
  }

  const commandWithBot = text.split(/\s+/)[0].toLowerCase();
  const command = commandWithBot.split("@")[0];
  const commandArg = text.slice(commandWithBot.length).trim();
  const known = new Set(["/start", "/help", "/remember", "/history"]);

  if (!known.has(command)) {
    return {
      route: "unknown_command",
      command,
      commandArg,
      unknownCommand: true
    };
  }

  return {
    route: command.slice(1),
    command,
    commandArg,
    unknownCommand: false
  };
}

function normalizeUpdate(payload) {
  const message = payload.message ?? payload.edited_message ?? null;
  if (!message) {
    return {
      isValid: false,
      reason: "No Telegram message payload found."
    };
  }

  const text = typeof message.text === "string" ? message.text.trim() : "";
  if (!text) {
    return {
      isValid: true,
      shouldSend: true,
      chatId: message.chat?.id ?? null,
      telegramId: message.from?.id ?? null,
      username: message.from?.username ?? "",
      firstName: message.from?.first_name ?? "there",
      route: "unsupported_content",
      command: "",
      commandArg: "",
      text: "",
      updateId: payload.update_id ?? null,
      messageId: message.message_id ?? null
    };
  }

  const routing = detectRoute(text);
  return {
    isValid: true,
    shouldSend: true,
    updateId: payload.update_id ?? null,
    messageId: message.message_id ?? null,
    chatId: message.chat?.id ?? null,
    telegramId: message.from?.id ?? null,
    username: message.from?.username ?? "",
    firstName: message.from?.first_name ?? "there",
    text,
    ...routing
  };
}

async function fetchJson(url, options = {}, timeoutMs = 20000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });

    const rawText = await response.text();
    let parsed;
    try {
      parsed = rawText ? JSON.parse(rawText) : null;
    } catch {
      parsed = rawText;
    }

    if (!response.ok) {
      const message =
        typeof parsed === "object" && parsed !== null
          ? JSON.stringify(parsed)
          : String(parsed);
      throw new Error(`HTTP ${response.status} ${response.statusText}: ${message}`);
    }

    return parsed;
  } finally {
    clearTimeout(timeout);
  }
}

function supabaseHeaders() {
  return {
    apikey: SUPABASE_KEY,
    Authorization: `Bearer ${SUPABASE_KEY}`,
    "Content-Type": "application/json"
  };
}

async function callRpc(rpcName, payload, timeoutMs = 15000) {
  if (!HAS_SUPABASE) {
    throw new Error("Supabase is not configured yet.");
  }
  return fetchJson(`${SUPABASE_URL}/rest/v1/rpc/${rpcName}`, {
    method: "POST",
    headers: supabaseHeaders(),
    body: JSON.stringify(payload)
  }, timeoutMs);
}

async function upsertTelegramUser(user) {
  return callRpc("upsert_telegram_user", {
    p_telegram_id: user.telegramId,
    p_username: user.username || null,
    p_first_name: user.firstName || "there"
  });
}

async function getUserContext(telegramId) {
  try {
    const response = await callRpc("get_user_context", {
      p_telegram_id: telegramId,
      p_message_limit: MESSAGE_LIMIT,
      p_memory_limit: MEMORY_LIMIT
    });

    return {
      memories: Array.isArray(response?.memories) ? response.memories : [],
      history: Array.isArray(response?.history) ? response.history : [],
      user: response?.user ?? null
    };
  } catch {
    return {
      memories: [],
      history: [],
      user: null
    };
  }
}

async function rememberFact(telegramId, memory) {
  return callRpc("remember_fact", {
    p_telegram_id: telegramId,
    p_memory: memory
  });
}

async function saveConversation(telegramId, userMessage, aiResponse) {
  return callRpc("save_conversation", {
    p_telegram_id: telegramId,
    p_user_message: userMessage,
    p_ai_response: aiResponse
  });
}

function helpText() {
  return [
    "Here is what I can do:",
    "/start - introduce the assistant",
    "/help - show this guide",
    "/remember <fact> - save something permanently",
    "/history - show your recent conversation history",
    "",
    "You can also send any normal message and I will reply using Groq with your personal memory and recent history."
  ].join("\n");
}

function startText(firstName) {
  return [
    `Hello ${firstName || "there"}!`,
    "",
    "I am your AI Telegram assistant powered by n8n, Groq, and Supabase.",
    "I keep separate memory for every Telegram user, remember facts across restarts, and can continue conversations using saved history.",
    "",
    "Type /help to see commands, or just send a message to start chatting."
  ].join("\n");
}

function unsupportedContentText() {
  return [
    "I can currently process text messages only.",
    "Try sending plain text, or use /help to see the available commands."
  ].join("\n");
}

function unknownCommandText(command) {
  return [
    `I do not recognize the command ${command}.`,
    "",
    helpText()
  ].join("\n");
}

function formatHistory(context) {
  if (!Array.isArray(context.history) || context.history.length === 0) {
    return "No conversation history is stored for you yet.";
  }

  const lines = ["Your recent conversation history:"];
  for (const entry of context.history.slice(0, 10)) {
    lines.push("");
    lines.push(`You: ${entry.user_message}`);
    lines.push(`Assistant: ${entry.ai_response}`);
  }
  return lines.join("\n");
}

function summarizeContextForPrompt(context) {
  const memories = (context.memories || [])
    .slice(0, MEMORY_LIMIT)
    .map((entry, index) => `${index + 1}. ${entry.memory}`);

  const history = (context.history || [])
    .slice(0, MESSAGE_LIMIT)
    .map((entry, index) => {
      return `${index + 1}. User: ${entry.user_message}\nAssistant: ${entry.ai_response}`;
    });

  return {
    memoryText: memories.length > 0 ? memories.join("\n") : "No saved memories.",
    historyText: history.length > 0 ? history.join("\n\n") : "No recent conversation history."
  };
}

async function groqChat(messages, temperature = 0.3) {
  if (!HAS_GROQ) {
    throw new Error("Groq is not configured yet.");
  }
  const response = await fetchJson(`${GROQ_BASE_URL}/chat/completions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GROQ_API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model: MODEL,
      temperature,
      response_format: { type: "json_object" },
      messages
    })
  }, 30000);

  return response?.choices?.[0]?.message?.content || "";
}

function basicChatFallback(userInput) {
  const text = (userInput.text || "").trim();
  if (!text) {
    return "I am online and ready. Send me a text message and I will reply.";
  }

  return [
    "I am online and reachable from Telegram now.",
    "",
    `You said: ${text}`,
    "",
    "My advanced AI or memory settings may still be finishing setup, but the bot itself is responding correctly."
  ].join("\n");
}

function sanitizeToolCalls(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item) => item && typeof item === "object" && typeof item.tool === "string")
    .slice(0, 3);
}

async function runAgent(userInput, context) {
  const promptContext = summarizeContextForPrompt(context);

  const planningMessages = [
    {
      role: "system",
      content: [
        "You are an AI Telegram assistant.",
        "Return strict JSON only.",
        "Schema:",
        "{",
        '  "assistant_reply": "string",',
        '  "tool_calls": [',
        '    { "tool": "remember_fact", "arguments": { "memory": "string" } },',
        '    { "tool": "get_history", "arguments": { "limit": 6 } },',
        '    { "tool": "get_memories", "arguments": { "limit": 6 } }',
        "  ]",
        "}",
        "Rules:",
        "- Use remember_fact when the user explicitly asks you to remember something.",
        "- Use get_history when you need the latest chat history.",
        "- Use get_memories when you need stored facts.",
        "- Keep tool_calls empty when no tool is required.",
        "- assistant_reply must still contain a helpful natural-language draft reply."
      ].join("\n")
    },
    {
      role: "user",
      content: [
        `User message: ${userInput.text}`,
        "",
        "Saved memories:",
        promptContext.memoryText,
        "",
        "Recent history:",
        promptContext.historyText
      ].join("\n")
    }
  ];

  let firstPass;
  try {
    firstPass = tryParseJson(await groqChat(planningMessages, 0.2));
  } catch {
    return {
      replyText:
        "I hit a temporary AI service issue while thinking through that. Please try again in a moment.",
      toolResults: [],
      memoryStored: false
    };
  }

  if (!firstPass || typeof firstPass !== "object") {
    return {
      replyText:
        "I could not safely parse the model response this time. Please send that again.",
      toolResults: [],
      memoryStored: false
    };
  }

  const toolResults = [];
  let memoryStored = false;
  const toolCalls = sanitizeToolCalls(firstPass.tool_calls);

  for (const toolCall of toolCalls) {
    const tool = toolCall.tool;
    const args = toolCall.arguments || {};

    if (tool === "remember_fact" && typeof args.memory === "string" && args.memory.trim()) {
      try {
        await rememberFact(userInput.telegramId, args.memory.trim());
        toolResults.push({
          tool,
          success: true,
          memory: args.memory.trim()
        });
        memoryStored = true;
      } catch (error) {
        toolResults.push({
          tool,
          success: false,
          error: error.message
        });
      }
      continue;
    }

    if (tool === "get_history") {
      const limit = Math.max(1, Math.min(Number(args.limit) || 6, 10));
      toolResults.push({
        tool,
        success: true,
        history: (context.history || []).slice(0, limit)
      });
      continue;
    }

    if (tool === "get_memories") {
      const limit = Math.max(1, Math.min(Number(args.limit) || 6, 10));
      toolResults.push({
        tool,
        success: true,
        memories: (context.memories || []).slice(0, limit)
      });
      continue;
    }
  }

  if (toolResults.length === 0) {
    return {
      replyText: firstPass.assistant_reply || "I am here and ready to help.",
      toolResults,
      memoryStored
    };
  }

  const finalMessages = [
    {
      role: "system",
      content: [
        "You are an AI Telegram assistant.",
        "Return strict JSON only.",
        'Schema: { "assistant_reply": "string" }',
        "Use the tool results to produce the final user-facing answer.",
        "Do not mention JSON, tools, or internal planning unless the user directly asks."
      ].join("\n")
    },
    {
      role: "user",
      content: [
        `Original user message: ${userInput.text}`,
        "",
        "Draft reply:",
        String(firstPass.assistant_reply || ""),
        "",
        "Tool results:",
        JSON.stringify(toolResults, null, 2)
      ].join("\n")
    }
  ];

  try {
    const finalPass = tryParseJson(await groqChat(finalMessages, 0.3));
    return {
      replyText:
        finalPass?.assistant_reply ||
        firstPass.assistant_reply ||
        "I am here and ready to help.",
      toolResults,
      memoryStored
    };
  } catch {
    return {
      replyText:
        firstPass.assistant_reply ||
        "I am here and ready to help.",
      toolResults,
      memoryStored
    };
  }
}

function webhookHeaderSecret(payloadHeaders) {
  const headers = payloadHeaders || {};
  return (
    headers["x-telegram-bot-api-secret-token"] ||
    headers["X-Telegram-Bot-Api-Secret-Token"] ||
    headers["x-telegram-bot_api-secret-token"] ||
    ""
  );
}

async function main() {
  const replyEnvelope = {
    shouldSend: false,
    chatId: null,
    replyText: "",
    httpBody: {
      ok: true,
      status: "ignored"
    }
  };

  const suppliedSecret = webhookHeaderSecret(update.headers);
  if (TELEGRAM_WEBHOOK_SECRET && suppliedSecret !== TELEGRAM_WEBHOOK_SECRET) {
    return [
      {
        json: {
          ...replyEnvelope,
          httpBody: {
            ok: false,
            status: "rejected",
            reason: "Invalid Telegram webhook secret."
          }
        }
      }
    ];
  }

  const normalized = normalizeUpdate(update.body ?? update);
  if (!normalized.isValid) {
    return [
      {
        json: {
          ...replyEnvelope,
          httpBody: {
            ok: true,
            status: "ignored",
            reason: normalized.reason
          }
        }
      }
    ];
  }

  if (!normalized.chatId || !normalized.telegramId) {
    return [
      {
        json: {
          ...replyEnvelope,
          httpBody: {
            ok: false,
            status: "ignored",
            reason: "Telegram identifiers are missing from the payload."
          }
        }
      }
    ];
  }

  let replyText = "";
  let diagnostics = {
    route: normalized.route,
    model: MODEL,
    hasSupabase: HAS_SUPABASE,
    hasGroq: HAS_GROQ,
    memoryStored: false,
    toolResults: []
  };

  try {
    if (HAS_SUPABASE) {
      await upsertTelegramUser(normalized);
    }
    const context = HAS_SUPABASE
      ? await getUserContext(normalized.telegramId)
      : { memories: [], history: [], user: null };

    if (normalized.route === "unsupported_content") {
      replyText = unsupportedContentText();
    } else if (normalized.route === "start") {
      replyText = startText(normalized.firstName);
    } else if (normalized.route === "help") {
      replyText = helpText();
    } else if (normalized.route === "remember") {
      if (!normalized.commandArg) {
        replyText = "Usage: /remember <fact you want me to store>";
      } else if (!HAS_SUPABASE) {
        replyText =
          "The bot is reachable, but persistent memory is not configured yet. Finish Supabase setup and then /remember will work.";
      } else {
        try {
          await rememberFact(normalized.telegramId, normalized.commandArg);
          diagnostics.memoryStored = true;
          replyText = `Saved to memory: ${normalized.commandArg}`;
        } catch {
          replyText =
            "I understood what you wanted me to remember, but I could not save it to Supabase right now. Please try again.";
        }
      }
    } else if (normalized.route === "history") {
      replyText = HAS_SUPABASE
        ? formatHistory(context)
        : "The bot is reachable, but conversation history is not configured yet. Finish Supabase setup to enable /history.";
    } else if (normalized.route === "unknown_command") {
      replyText = unknownCommandText(normalized.command);
    } else {
      if (!HAS_GROQ) {
        replyText = basicChatFallback(normalized);
      } else {
        const agentResult = await runAgent(normalized, context);
        diagnostics.memoryStored = agentResult.memoryStored;
        diagnostics.toolResults = agentResult.toolResults;
        replyText = agentResult.replyText;
      }
    }

    replyText = truncateTelegram(replyText);

    if (HAS_SUPABASE) {
      try {
        await saveConversation(normalized.telegramId, normalized.text || "[non-text-message]", replyText);
      } catch {
        diagnostics.historyPersisted = false;
      }
    }
  } catch (error) {
    replyText =
      "The assistant is temporarily unavailable because one of the backend services did not respond correctly. Please try again shortly.";
    diagnostics = {
      ...diagnostics,
      fatalError: error.message
    };
  }

  return [
    {
      json: {
        shouldSend: true,
        chatId: normalized.chatId,
        replyText,
        route: normalized.route,
        telegramId: normalized.telegramId,
        diagnostics,
        httpBody: {
          ok: true,
          status: "processed",
          route: normalized.route
        }
      }
    }
  ];
}

return main();
