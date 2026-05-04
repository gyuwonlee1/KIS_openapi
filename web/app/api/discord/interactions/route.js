import { NextResponse, after } from "next/server";
import {
  DISCORD_RESPONSE,
  commandText,
  deferredEphemeralMessage,
  deferredUpdate,
  editOriginalInteractionResponse,
  ephemeralMessage,
  updatedMessage,
  verifyDiscordRequest,
} from "@/lib/discord";
import { parseNaturalAlert } from "@/lib/gemini";
import {
  applyConditionToPortfolio,
  confirmationComponents,
  confirmationMessage,
  decodeConfirmId,
  decodeSymbolSelectId,
  formatConditionSummary,
  isCancelId,
  isSymbolSelectId,
  resolveParsedAlert,
  symbolSelectionComponents,
  symbolSelectionMessage,
} from "@/lib/natural-alert";
import { fetchPortfolio, savePortfolio } from "@/lib/github";

export const runtime = "nodejs";

export async function POST(request) {
  const body = await request.text();
  const signature = request.headers.get("x-signature-ed25519");
  const timestamp = request.headers.get("x-signature-timestamp");

  if (
    !verifyDiscordRequest({
      body,
      signature,
      timestamp,
      publicKey: process.env.DISCORD_PUBLIC_KEY,
    })
  ) {
    return new NextResponse("invalid request signature", { status: 401 });
  }

  const interaction = JSON.parse(body);
  if (interaction.type === 1) {
    return NextResponse.json({ type: DISCORD_RESPONSE.PONG });
  }

  if (interaction.type === 2) {
    const text = commandText(interaction);
    if (!text) {
      return NextResponse.json(ephemeralMessage("알림 조건을 문장으로 입력해 주세요."));
    }
    after(async () => handleNaturalAlertCommand(interaction, text));
    return NextResponse.json(deferredEphemeralMessage());
  }

  if (interaction.type === 3) {
    const customId = interaction?.data?.custom_id || "";
    if (isCancelId(customId)) {
      return NextResponse.json(updatedMessage("조건 저장을 취소했습니다."));
    }
    if (isSymbolSelectId(customId)) {
      after(async () => handleSymbolSelection(interaction, customId));
      return NextResponse.json(deferredUpdate());
    }
    after(async () => handleConfirmation(interaction, customId));
    return NextResponse.json(deferredUpdate());
  }

  return NextResponse.json(ephemeralMessage("지원하지 않는 Discord 상호작용입니다."));
}

async function handleNaturalAlertCommand(interaction, text) {
  try {
    const parsed = await parseNaturalAlert(text);
    const resolved = resolveParsedAlert(parsed);
    if (!resolved.ok) {
      if (resolved.needsSymbolSelection) {
        await editOriginalInteractionResponse(interaction, {
          content: symbolSelectionMessage(resolved.candidates),
          components: symbolSelectionComponents(resolved.candidates, resolved.condition),
        });
        return;
      }
      await editOriginalInteractionResponse(interaction, {
        content: resolved.message,
        components: [],
      });
      return;
    }

    await editOriginalInteractionResponse(interaction, {
      content: confirmationMessage(resolved.symbol, resolved.condition),
      components: confirmationComponents(resolved.symbol, resolved.condition),
    });
  } catch (error) {
    await safeEdit(interaction, `조건을 해석하지 못했습니다.\n\n${error.message}`);
  }
}

async function handleSymbolSelection(interaction, customId) {
  try {
    const decoded = decodeSymbolSelectId(customId);
    if (!decoded) {
      await editOriginalInteractionResponse(interaction, {
        content: "종목 선택 정보를 읽지 못했습니다. 다시 시도해 주세요.",
        components: [],
      });
      return;
    }
    await editOriginalInteractionResponse(interaction, {
      content: confirmationMessage(decoded.symbol, decoded.condition),
      components: confirmationComponents(decoded.symbol, decoded.condition),
    });
  } catch (error) {
    await safeEdit(interaction, `종목 선택 처리에 실패했습니다.\n\n${error.message}`);
  }
}

async function handleConfirmation(interaction, customId) {
  try {
    const decoded = decodeConfirmId(customId);
    if (!decoded) {
      await editOriginalInteractionResponse(interaction, {
        content: "확인 정보를 읽지 못했습니다. 다시 시도해 주세요.",
        components: [],
      });
      return;
    }

    const result = await saveConditionWithRetry(decoded.symbol, decoded.condition);
    await editOriginalInteractionResponse(interaction, {
      content: `조건을 저장했습니다.\n\n${formatConditionSummary(decoded.symbol, decoded.condition)}\n\ncommit ${result.commitSha || ""}`,
      components: [],
    });
  } catch (error) {
    await safeEdit(interaction, `조건 저장에 실패했습니다.\n\n${error.message}`);
  }
}

async function saveConditionWithRetry(symbol, condition) {
  let lastError;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const current = await fetchPortfolio();
      const nextPortfolio = applyConditionToPortfolio(current.portfolio, symbol, condition);
      return await savePortfolio(
        nextPortfolio,
        current.sha,
        `Add ${symbol.name} alert condition from Discord`,
      );
    } catch (error) {
      lastError = error;
      if (!String(error.message || "").includes("409")) {
        break;
      }
    }
  }
  throw lastError;
}

async function safeEdit(interaction, content) {
  try {
    await editOriginalInteractionResponse(interaction, {
      content,
      components: [],
    });
  } catch (error) {
    console.error(error);
  }
}
