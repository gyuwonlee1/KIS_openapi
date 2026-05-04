import assert from "node:assert/strict";
import crypto from "node:crypto";

import { commandText, verifyDiscordRequest } from "../lib/discord.js";

function test(name, fn) {
  try {
    fn();
    console.log(`ok - ${name}`);
  } catch (error) {
    console.error(`not ok - ${name}`);
    throw error;
  }
}

test("verifies Discord Ed25519 request signatures", () => {
  const { publicKey, privateKey } = crypto.generateKeyPairSync("ed25519");
  const publicKeyDer = publicKey.export({ format: "der", type: "spki" });
  const publicKeyHex = publicKeyDer.subarray(-32).toString("hex");
  const timestamp = "1700000000";
  const body = JSON.stringify({ type: 1 });
  const signature = crypto.sign(null, Buffer.from(`${timestamp}${body}`, "utf8"), privateKey).toString("hex");

  assert.equal(verifyDiscordRequest({ body, signature, timestamp, publicKey: publicKeyHex }), true);
  assert.equal(verifyDiscordRequest({ body: `${body} `, signature, timestamp, publicKey: publicKeyHex }), false);
});

test("extracts the slash command text option", () => {
  const interaction = {
    data: {
      options: [
        {
          type: 3,
          name: "내용",
          value: "삼성전자가 8만원 이상이면 알려줘",
        },
      ],
    },
  };

  assert.equal(commandText(interaction), "삼성전자가 8만원 이상이면 알려줘");
});
