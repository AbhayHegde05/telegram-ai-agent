# Groq Setup Guide

## Create the API key

1. Sign in to Groq.
2. Open the API keys page.
3. Create a new key.
4. Put it into `GROQ_API_KEY`.

## Runtime model configuration

This project uses:

- Base URL: `https://api.groq.com/openai/v1`
- Model: `llama-3.3-70b-versatile`

These values are already wired into:

- `.env.example`
- [workflow-assets/ai-agent-orchestrator.js](/c:/My%20Projects/Telegram%20bot/workflow-assets/ai-agent-orchestrator.js:1)

## How the assistant uses Groq

The workflow uses Groq in two stages:

1. A planning call that decides whether to use tools such as memory retrieval or memory saving.
2. A final answer call that turns tool results into a clean Telegram reply.

Both requests use Groq's OpenAI-compatible `chat/completions` endpoint.

## Failure behavior

If Groq times out or returns an invalid response:

- the workflow does not crash the whole Telegram webhook flow
- the user receives a graceful fallback message
- the execution remains visible in n8n for inspection

## Official references

- Groq OpenAI compatibility: https://console.groq.com/docs/openai
- Groq model catalog: https://console.groq.com/docs/models
- Groq chat completions example: https://console.groq.com/docs/api-reference

