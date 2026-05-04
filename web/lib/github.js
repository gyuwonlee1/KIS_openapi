import { normalizePortfolio } from "./portfolio.js";

export function githubConfig() {
  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_REPO || "gyuwonlee1/KIS_openapi";
  const branch = process.env.GITHUB_BRANCH || "main";
  if (!token) {
    throw new Error("GITHUB_TOKEN is not configured");
  }
  return { token, repo, branch };
}

export async function fetchPortfolio() {
  const { token, repo, branch } = githubConfig();
  const url = `https://api.github.com/repos/${repo}/contents/portfolio.json?ref=${encodeURIComponent(branch)}`;
  const response = await fetch(url, {
    headers: githubHeaders(token),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`GitHub portfolio fetch failed: ${response.status}`);
  }
  const payload = await response.json();
  const content = Buffer.from(payload.content || "", "base64").toString("utf8");
  return {
    portfolio: JSON.parse(content),
    sha: payload.sha,
    repo,
    branch,
  };
}

export async function savePortfolio(portfolio, sha, message) {
  const { token, repo, branch } = githubConfig();
  const normalized = normalizePortfolio(portfolio);
  const content = `${JSON.stringify(normalized, null, 2)}\n`;
  const url = `https://api.github.com/repos/${repo}/contents/portfolio.json`;
  const response = await fetch(url, {
    method: "PUT",
    headers: githubHeaders(token),
    body: JSON.stringify({
      message: message || "Update portfolio from web editor",
      content: Buffer.from(content, "utf8").toString("base64"),
      sha,
      branch,
    }),
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`GitHub portfolio save failed: ${response.status} ${body}`);
  }
  const payload = await response.json();
  return {
    commitSha: payload.commit?.sha,
    contentSha: payload.content?.sha,
  };
}

function githubHeaders(token) {
  return {
    Accept: "application/vnd.github+json",
    Authorization: `Bearer ${token}`,
    "X-GitHub-Api-Version": "2022-11-28",
  };
}
