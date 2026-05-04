import crypto from "node:crypto";

const DISCORD_PUBLIC_KEY_PREFIX = Buffer.from("302a300506032b6570032100", "hex");

export const DISCORD_RESPONSE = {
  PONG: 1,
  CHANNEL_MESSAGE_WITH_SOURCE: 4,
  DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE: 5,
  DEFERRED_UPDATE_MESSAGE: 6,
  UPDATE_MESSAGE: 7,
};

export const DISCORD_FLAGS = {
  EPHEMERAL: 1 << 6,
};

export function verifyDiscordRequest({ body, signature, timestamp, publicKey }) {
  if (!body || !signature || !timestamp || !publicKey) {
    return false;
  }
  try {
    const key = crypto.createPublicKey({
      key: Buffer.concat([DISCORD_PUBLIC_KEY_PREFIX, Buffer.from(publicKey, "hex")]),
      format: "der",
      type: "spki",
    });
    return crypto.verify(
      null,
      Buffer.from(`${timestamp}${body}`, "utf8"),
      key,
      Buffer.from(signature, "hex"),
    );
  } catch {
    return false;
  }
}

export function ephemeralMessage(content, extra = {}) {
  return {
    type: DISCORD_RESPONSE.CHANNEL_MESSAGE_WITH_SOURCE,
    data: {
      content,
      flags: DISCORD_FLAGS.EPHEMERAL,
      ...extra,
    },
  };
}

export function deferredEphemeralMessage() {
  return {
    type: DISCORD_RESPONSE.DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE,
    data: {
      flags: DISCORD_FLAGS.EPHEMERAL,
    },
  };
}

export function deferredUpdate() {
  return { type: DISCORD_RESPONSE.DEFERRED_UPDATE_MESSAGE };
}

export function updatedMessage(content, extra = {}) {
  return {
    type: DISCORD_RESPONSE.UPDATE_MESSAGE,
    data: {
      content,
      components: [],
      ...extra,
    },
  };
}

export async function editOriginalInteractionResponse(interaction, payload) {
  const appId = interaction.application_id;
  const token = interaction.token;
  const response = await fetch(
    `https://discord.com/api/v10/webhooks/${appId}/${token}/messages/@original`,
    {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Discord response edit failed: ${response.status} ${body}`);
  }
}

export function commandText(interaction) {
  const options = interaction?.data?.options || [];
  const stringOption = findStringOption(options);
  return String(stringOption?.value || "").trim();
}

function findStringOption(options) {
  for (const option of options) {
    if (option?.type === 3 && option.value) {
      return option;
    }
    if (Array.isArray(option?.options)) {
      const nested = findStringOption(option.options);
      if (nested) {
        return nested;
      }
    }
  }
  return null;
}
