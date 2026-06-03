const inputItem = $input.first();
const update = inputItem?.json ?? {};

const ACTIONS = {
  RECOMMEND: "movie_recommendation",
  BRIEF: "movie_brief",
  REVIEW: "movie_review"
};

const SESSION_TTL_MS = 60 * 60 * 1000;

function truncateTelegram(text) {
  const safe = typeof text === "string" ? text.trim() : "";
  if (!safe) {
    return "I received your message, but I could not build a response this time.";
  }
  return safe.length <= 3900 ? safe : `${safe.slice(0, 3890)}...`;
}

function mainMenuMarkup() {
  return {
    inline_keyboard: [
      [{ text: "Movie recommendation", callback_data: ACTIONS.RECOMMEND }],
      [{ text: "Movie brief", callback_data: ACTIONS.BRIEF }],
      [{ text: "Movie review", callback_data: ACTIONS.REVIEW }]
    ]
  };
}

function clearMarkup() {
  return { inline_keyboard: [] };
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
  const known = new Set(["/start", "/help", "/recommend"]);

  if (!known.has(command)) {
    return {
      route: "unknown_command",
      command,
      commandArg,
      unknownCommand: true
    };
  }

  return {
    route: command === "/recommend" ? "recommend_command" : command.slice(1),
    command,
    commandArg,
    unknownCommand: false
  };
}

function normalizeUpdate(payload) {
  const callback = payload.callback_query ?? null;
  if (callback) {
    const data = typeof callback.data === "string" ? callback.data.trim() : "";
    return {
      isValid: true,
      isCallback: true,
      callbackQueryId: callback.id ?? null,
      updateId: payload.update_id ?? null,
      messageId: callback.message?.message_id ?? null,
      chatId: callback.message?.chat?.id ?? null,
      telegramId: callback.from?.id ?? null,
      username: callback.from?.username ?? "",
      firstName: callback.from?.first_name ?? "there",
      text: data,
      route: "callback",
      action: data,
      command: "",
      commandArg: "",
      unknownCommand: false
    };
  }

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
      isCallback: false,
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
    isCallback: false,
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

function getSessionStore() {
  const store = $getWorkflowStaticData("global");
  if (!store.movieBotSessions || typeof store.movieBotSessions !== "object") {
    store.movieBotSessions = {};
  }
  return store.movieBotSessions;
}

function sessionKey(userInput) {
  return `${userInput.chatId}:${userInput.telegramId}`;
}

function getSession(userInput) {
  const sessions = getSessionStore();
  const key = sessionKey(userInput);
  const session = sessions[key] ?? null;
  if (!session) {
    return null;
  }

  if (Date.now() - (session.updatedAt || 0) > SESSION_TTL_MS) {
    delete sessions[key];
    return null;
  }

  return session;
}

function setSession(userInput, nextSession) {
  const sessions = getSessionStore();
  sessions[sessionKey(userInput)] = {
    ...nextSession,
    updatedAt: Date.now()
  };
}

function clearSession(userInput) {
  const sessions = getSessionStore();
  delete sessions[sessionKey(userInput)];
}

function helpText() {
  return [
    "Use /start to open the movie menu.",
    "",
    "Available now:",
    "/recommend - get 5 movie recommendations from your preferences",
    "",
    "Movie brief and movie review are visible in the menu and will be wired next."
  ].join("\n");
}

function startText(firstName) {
  return [
    `Hello ${firstName || "there"}!`,
    "",
    "I can help you with movies. Choose one option:"
  ].join("\n");
}

function recommendationPromptText() {
  return [
    "Tell me what kind of movie you want.",
    "",
    "You can include genre, language, mood, age rating, release period, actors, movies you liked, things to avoid, and whether you want mainstream or hidden gems.",
    "",
    "Example: action thriller, Hindi or English, recent, smart story, no horror, liked John Wick and Drishyam."
  ].join("\n");
}

function unsupportedContentText() {
  return [
    "I can currently process text messages only.",
    "Use /start and choose one option from the movie menu."
  ].join("\n");
}

function unknownCommandText(command) {
  return [
    `I do not recognize the command ${command}.`,
    "",
    helpText()
  ].join("\n");
}

function comingSoonText(featureName) {
  return [
    `${featureName} is the next flow I will connect after recommendation is verified.`,
    "",
    "For now, choose Movie recommendation or send /recommend."
  ].join("\n");
}

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

async function fetchDuckDuckGoSnippets(query) {
  const url = `https://duckduckgo.com/html/?q=${encodeURIComponent(query)}`;
  const response = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0 TelegramMovieBot/1.0"
    }
  });

  if (!response.ok) {
    throw new Error(`Search failed with HTTP ${response.status}`);
  }

  const html = await response.text();
  const snippets = [];
  const resultRegex = /<a[^>]+class="result__a"[^>]*>([\s\S]*?)<\/a>[\s\S]*?<a[^>]+class="result__snippet"[^>]*>([\s\S]*?)<\/a>/gi;
  let match;

  while ((match = resultRegex.exec(html)) && snippets.length < 8) {
    const title = plainTextFromHtml(match[1]);
    const snippet = plainTextFromHtml(match[2]);
    if (title || snippet) {
      snippets.push(`${title}: ${snippet}`.trim());
    }
  }

  if (snippets.length > 0) {
    return snippets;
  }

  const compact = plainTextFromHtml(html);
  return compact ? [compact.slice(0, 1800)] : [];
}

async function askGroqForRecommendations(preferences, searchSnippets) {
  const apiKey = $env.GROQ_API_KEY || "";
  if (!apiKey) {
    throw new Error("GROQ_API_KEY is not configured.");
  }

  const baseUrl = ($env.GROQ_BASE_URL || "https://api.groq.com/openai/v1").replace(/\/+$/, "");
  const model = $env.GROQ_MODEL || "llama-3.3-70b-versatile";
  const systemPrompt = [
    "You are a sharp movie recommendation assistant.",
    "Use the supplied live web search snippets as supporting evidence, but do not invent sources or links.",
    "Return exactly 5 recommendations that best match the user's preferences.",
    "Avoid spoilers.",
    "For each movie include: rank, title, year if known, languages/regions if useful, why it fits, and a confidence score out of 10.",
    "End with one short line asking which title they want to explore next."
  ].join(" ");

  const userPrompt = [
    `User preferences: ${preferences}`,
    "",
    "Web search snippets:",
    searchSnippets.length ? searchSnippets.map((snippet, index) => `${index + 1}. ${snippet}`).join("\n") : "No snippets were found.",
    "",
    "Format the answer for Telegram in plain text. Keep it concise and readable."
  ].join("\n");

  const response = await fetch(`${baseUrl}/chat/completions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model,
      temperature: 0.45,
      max_tokens: 950,
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userPrompt }
      ]
    })
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload?.error?.message || `HTTP ${response.status}`;
    throw new Error(`Groq request failed: ${detail}`);
  }

  const content = payload?.choices?.[0]?.message?.content;
  if (!content) {
    throw new Error("Groq did not return a recommendation.");
  }

  return content;
}

async function recommendMovies(preferences) {
  const searchQueries = [
    `best movies recommendations ${preferences}`,
    `top films like ${preferences}`,
    `best recent movies ${preferences}`
  ];
  const snippetGroups = [];

  for (const query of searchQueries) {
    try {
      const snippets = await fetchDuckDuckGoSnippets(query);
      snippetGroups.push(...snippets);
    } catch (error) {
      snippetGroups.push(`Search note for "${query}": ${error.message}`);
    }
  }

  const uniqueSnippets = [...new Set(snippetGroups)].slice(0, 12);
  return askGroqForRecommendations(preferences, uniqueSnippets);
}

function makeEnvelope(overrides = {}) {
  return {
    shouldSend: false,
    chatId: null,
    replyText: "",
    replyMarkup: null,
    telegramMessage: null,
    httpBody: {
      ok: true,
      status: "ignored"
    },
    ...overrides
  };
}

function makeTelegramMessage(chatId, replyText, replyMarkup = null) {
  const message = {
    chat_id: chatId,
    text: truncateTelegram(replyText),
    disable_web_page_preview: true
  };

  if (replyMarkup) {
    message.reply_markup = replyMarkup;
  }

  return message;
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

async function buildReply(normalized) {
  if (normalized.route === "unsupported_content") {
    return { replyText: unsupportedContentText() };
  }

  if (normalized.route === "start") {
    clearSession(normalized);
    return {
      replyText: startText(normalized.firstName),
      replyMarkup: mainMenuMarkup()
    };
  }

  if (normalized.route === "help") {
    return {
      replyText: helpText(),
      replyMarkup: mainMenuMarkup()
    };
  }

  if (normalized.route === "recommend_command") {
    const preferences = (normalized.commandArg || "").trim();
    if (preferences.length >= 4) {
      const recommendations = await recommendMovies(preferences);
      return {
        replyText: recommendations,
        replyMarkup: mainMenuMarkup()
      };
    }

    setSession(normalized, { mode: ACTIONS.RECOMMEND });
    return {
      replyText: recommendationPromptText(),
      replyMarkup: clearMarkup()
    };
  }

  if (normalized.route === "unknown_command") {
    return {
      replyText: unknownCommandText(normalized.command),
      replyMarkup: mainMenuMarkup()
    };
  }

  if (normalized.route === "callback") {
    if (normalized.action === ACTIONS.RECOMMEND) {
      setSession(normalized, { mode: ACTIONS.RECOMMEND });
      return {
        replyText: recommendationPromptText(),
        replyMarkup: clearMarkup()
      };
    }

    if (normalized.action === ACTIONS.BRIEF) {
      clearSession(normalized);
      return {
        replyText: comingSoonText("Movie brief"),
        replyMarkup: mainMenuMarkup()
      };
    }

    if (normalized.action === ACTIONS.REVIEW) {
      clearSession(normalized);
      return {
        replyText: comingSoonText("Movie review"),
        replyMarkup: mainMenuMarkup()
      };
    }
  }

  const session = getSession(normalized);
  if (session?.mode === ACTIONS.RECOMMEND) {
    const preferences = (normalized.text || "").trim();
    if (preferences.length < 4) {
      return {
        replyText: "Please add a little more detail, such as genre, language, mood, or movies you liked."
      };
    }

    clearSession(normalized);
    const recommendations = await recommendMovies(preferences);
    return {
      replyText: recommendations,
      replyMarkup: mainMenuMarkup()
    };
  }

  if (normalized.route === "chat") {
    const preferences = (normalized.text || "").trim();
    if (preferences.length < 4) {
      return {
        replyText: "Please add a little more detail, such as genre, language, mood, or movies you liked."
      };
    }

    clearSession(normalized);
    const recommendations = await recommendMovies(preferences);
    return {
      replyText: recommendations,
      replyMarkup: mainMenuMarkup()
    };
  }

  return {
    replyText: "Use /start to choose Movie recommendation, Movie brief, or Movie review.",
    replyMarkup: mainMenuMarkup()
  };
}

async function main() {
  const configuredSecret = $env.TELEGRAM_WEBHOOK_SECRET || "";
  const suppliedSecret = webhookHeaderSecret(update.headers);
  if (configuredSecret && suppliedSecret !== configuredSecret) {
    return [
      {
        json: makeEnvelope({
          httpBody: {
            ok: false,
            status: "rejected",
            reason: "Invalid Telegram webhook secret."
          }
        })
      }
    ];
  }

  const normalized = normalizeUpdate(update.body ?? update);
  if (!normalized.isValid) {
    return [
      {
        json: makeEnvelope({
          httpBody: {
            ok: true,
            status: "ignored",
            reason: normalized.reason
          }
        })
      }
    ];
  }

  if (!normalized.chatId || !normalized.telegramId) {
    return [
      {
        json: makeEnvelope({
          httpBody: {
            ok: false,
            status: "ignored",
            reason: "Telegram identifiers are missing from the payload."
          }
        })
      }
    ];
  }

  try {
    const reply = await buildReply(normalized);
    const replyText = truncateTelegram(reply.replyText);
    return [
      {
        json: makeEnvelope({
          shouldSend: true,
          chatId: normalized.chatId,
          replyText,
          replyMarkup: reply.replyMarkup ?? null,
          telegramMessage: makeTelegramMessage(normalized.chatId, replyText, reply.replyMarkup ?? null),
          route: normalized.route,
          telegramId: normalized.telegramId,
          httpBody: {
            ok: true,
            status: "processed",
            route: normalized.route
          }
        })
      }
    ];
  } catch (error) {
    return [
      {
        json: makeEnvelope({
          shouldSend: true,
          chatId: normalized.chatId,
          replyText: truncateTelegram([
            "I could not complete the movie recommendation request this time.",
            "",
            `Reason: ${error.message}`,
            "",
            "Please try again with /recommend, or adjust the preferences."
          ].join("\n")),
          replyMarkup: mainMenuMarkup(),
          telegramMessage: makeTelegramMessage(normalized.chatId, [
            "I could not complete the movie recommendation request this time.",
            "",
            `Reason: ${error.message}`,
            "",
            "Please try again with /recommend, or adjust the preferences."
          ].join("\n"), mainMenuMarkup()),
          route: normalized.route,
          telegramId: normalized.telegramId,
          httpBody: {
            ok: true,
            status: "processed_with_error",
            route: normalized.route
          }
        })
      }
    ];
  }
}

return main();
