const inputItem = $input.first();
const update = inputItem?.json ?? {};

function truncateTelegram(text) {
  const safe = typeof text === "string" ? text.trim() : "";
  if (!safe) {
    return "I received your message, but I could not build a response this time.";
  }
  return safe.length <= 3900 ? safe : `${safe.slice(0, 3890)}...`;
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

function helpText() {
  return [
    "Here is what I can do right now:",
    "/start - introduce the assistant",
    "/help - show this guide",
    "/remember <fact> - temporary placeholder reply",
    "/history - temporary placeholder reply",
    "",
    "For now I am configured to reply reliably on Telegram first. After that, we can reconnect Groq and Supabase cleanly."
  ].join("\n");
}

function startText(firstName) {
  return [
    `Hello ${firstName || "there"}!`,
    "",
    "I am now connected to Telegram through n8n.",
    "This first version is focused on making sure replies work reliably.",
    "",
    "Send /help to see commands, or send any text message and I will reply."
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

function rememberPlaceholder(commandArg) {
  if (!commandArg) {
    return "Usage: /remember <fact you want me to store>";
  }

  return [
    `I received the memory request: ${commandArg}`,
    "",
    "The Telegram reply path is working. Persistent memory will be connected after the core bot flow is stable."
  ].join("\n");
}

function historyPlaceholder() {
  return [
    "History is not connected yet in this fallback version.",
    "",
    "The important part is that your Telegram bot is now reachable and replying."
  ].join("\n");
}

function chatReply(userInput) {
  const text = (userInput.text || "").trim();
  return [
    "Telegram connection is working.",
    "",
    `You said: ${text}`,
    "",
    "Next we can reconnect AI and memory once the base flow is stable."
  ].join("\n");
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
  const configuredSecret = $env.TELEGRAM_WEBHOOK_SECRET || "";
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
  if (configuredSecret && suppliedSecret !== configuredSecret) {
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

  if (normalized.route === "unsupported_content") {
    replyText = unsupportedContentText();
  } else if (normalized.route === "start") {
    replyText = startText(normalized.firstName);
  } else if (normalized.route === "help") {
    replyText = helpText();
  } else if (normalized.route === "remember") {
    replyText = rememberPlaceholder(normalized.commandArg);
  } else if (normalized.route === "history") {
    replyText = historyPlaceholder();
  } else if (normalized.route === "unknown_command") {
    replyText = unknownCommandText(normalized.command);
  } else {
    replyText = chatReply(normalized);
  }

  return [
    {
      json: {
        shouldSend: true,
        chatId: normalized.chatId,
        replyText: truncateTelegram(replyText),
        route: normalized.route,
        telegramId: normalized.telegramId,
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
