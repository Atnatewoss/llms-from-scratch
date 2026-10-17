import {
  createUIMessageStream,
  createUIMessageStreamResponse,
  type UIMessage,
} from "ai";

import { apiUrl, client } from "@/lib/pyrpc";

export const maxDuration = 30;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const userTexts = (messages: UIMessage[]) =>
  messages
    .filter((message) => message.role === "user")
    .map((message) =>
      (message.parts ?? [])
        .filter((part) => part.type === "text")
        .map((part) => part.text)
        .join("\n")
        .trim(),
    )
    .filter(Boolean);

export async function POST(req: Request) {
  const { messages }: { messages: UIMessage[] } = await req.json();
  const texts = userTexts(messages);

  let answer: string;
  try {
    // The RPC call is typed from the Python signatures, so a field renamed in
    // api/main.py fails `tsc` here.
    const reply = await client.reply(texts.at(-1) ?? "", texts.slice(0, -1));
    answer = reply.text;
  } catch (error) {
    // Keep the setup hint on the server: the visitor sees a plain apology.
    console.error(`Rule server unreachable at ${apiUrl}`, error);
    answer =
      "I can't reach my rules right now, so I have nothing to say. Try again in a moment.";
  }

  const stream = createUIMessageStream({
    execute: async ({ writer }) => {
      writer.write({ type: "start" });
      writer.write({ type: "text-start", id: "0" });
      // Stream word by word so the reply arrives like a model would type it.
      for (const delta of answer.match(/\S+\s*/g) ?? [answer]) {
        writer.write({ type: "text-delta", id: "0", delta });
        await sleep(20);
      }
      writer.write({ type: "text-end", id: "0" });
      writer.write({ type: "finish" });
    },
  });

  return createUIMessageStreamResponse({ stream });
}
