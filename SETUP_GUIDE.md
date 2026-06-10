# Setup & Deployment Guide (Serverless Webhook)

This guide walks you through setting up the Telegram Movie Bot for a **serverless webhook architecture** using Vercel and Supabase. This architecture is perfect for free hosting because it doesn't require a continuously running server.

## 1. Create the Telegram Bot

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot` and follow the instructions to choose a name and username for your bot.
3. BotFather will give you a **Bot Token** (e.g., `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`).
4. Save this token securely. You will need it later as `TELEGRAM_BOT_TOKEN`.

## 2. Obtain API Keys

### Groq API Key
1. Go to the [Groq Console](https://console.groq.com/).
2. Create an account and generate a new API Key.
3. Save this key as `GROQ_API_KEY`.

### Tavily API Key
1. Go to [Tavily](https://tavily.com/) and sign up.
2. Generate a new API Key for search.
3. Save this key as `TAVILY_API_KEY`.

## 3. Set up Supabase Database

Since serverless environments (like Vercel) reset their file system on every request, the bot uses **Supabase** (a free Postgres database) to store user sessions and preferences.

1. Go to [Supabase](https://supabase.com/) and create a new project.
2. In the Supabase dashboard, go to **SQL Editor** and create a new query.
3. Copy the entire contents of [`supabase/schema.sql`](supabase/schema.sql) from this repository and paste it into the SQL Editor.
4. Click **Run** to create the necessary tables (`user_data` and `user_history`).
5. Go to **Project Settings -> API**.
6. Copy the **Project URL** and save it as `SUPABASE_URL`.
7. Copy the **anon / public key** and save it as `SUPABASE_KEY`.

## 4. Deploy to Vercel (Free Hosting)

1. Create a free account on [Vercel](https://vercel.com/).
2. Install the Vercel CLI locally (if you prefer deploying from terminal) by running `npm i -g vercel`, OR push this repository to GitHub and connect your Vercel account to the repository.
3. If deploying via GitHub, click **Import Project** in Vercel and select your repository.
4. Expand the **Environment Variables** section and add the following keys:
   - `TELEGRAM_BOT_TOKEN`: (Your Telegram token)
   - `GROQ_API_KEY`: (Your Groq key)
   - `TAVILY_API_KEY`: (Your Tavily key)
   - `SUPABASE_URL`: (Your Supabase URL)
   - `SUPABASE_KEY`: (Your Supabase Anon Key)
5. Click **Deploy**. Vercel will build and assign you a production domain (e.g., `https://your-bot-app.vercel.app`).

## 5. Register the Webhook

Now that your bot is deployed, you need to tell Telegram to send updates to your new Vercel URL.

1. In Vercel, copy your deployment domain.
2. Go back to the Vercel **Environment Variables** settings and add one more variable:
   - `WEBHOOK_URL`: `https://your-bot-app.vercel.app` (replace with your actual domain).
3. Redeploy your app so the new environment variable takes effect.
4. Open your browser and visit: `https://your-bot-app.vercel.app/api/set_webhook`.
5. You should see a success message like: `{"status": "success", "message": "Webhook successfully set to https://your-bot-app.vercel.app/api/webhook"}`.

## 6. Testing

Open Telegram and send `/start` to your bot. Try out all three features:
1. **Movie Recommendation**: Verify that it asks for your preferences step-by-step and then returns 5 recommendations.
2. **Movie Brief**: Give it a movie name and verify you receive a structured, spoiler-safe brief.
3. **Movie Review**: Ask for a review and confirm it retrieves live data and outputs a comprehensive scored review.

## Troubleshooting

- **Bot doesn't respond:** Ensure the webhook is registered properly by visiting the `/api/set_webhook` endpoint again.
- **Bot forgets state:** Check your Supabase URL and Key in the environment variables. If they are incorrect, the bot will silently drop memory writes.
- **Search fails:** Check that your `TAVILY_API_KEY` is valid and not expired.
- **LLM errors:** Ensure `GROQ_API_KEY` is valid. You can monitor the Vercel Logs tab for specific Python traceback errors.
