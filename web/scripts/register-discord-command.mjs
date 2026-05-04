const token = process.env.DISCORD_BOT_TOKEN;
const applicationId = process.env.DISCORD_APPLICATION_ID;
const guildId = process.env.DISCORD_GUILD_ID;

if (!token) {
  throw new Error("DISCORD_BOT_TOKEN is not configured");
}
if (!applicationId) {
  throw new Error("DISCORD_APPLICATION_ID is not configured");
}

const command = {
  name: "알림",
  description: "자연어로 주식 알림 조건을 설정합니다.",
  type: 1,
  options: [
    {
      name: "내용",
      description: "예: 삼성전자가 8만원 이상이면 알려줘",
      type: 3,
      required: true,
    },
  ],
};

const base = `https://discord.com/api/v10/applications/${applicationId}`;
const url = guildId ? `${base}/guilds/${guildId}/commands` : `${base}/commands`;

const response = await fetch(url, {
  method: "POST",
  headers: {
    authorization: `Bot ${token}`,
    "content-type": "application/json",
  },
  body: JSON.stringify(command),
});

if (!response.ok) {
  const body = await response.text();
  throw new Error(`Discord command registration failed: ${response.status} ${body}`);
}

const payload = await response.json();
console.log(`Registered /${payload.name} command: ${payload.id}`);
