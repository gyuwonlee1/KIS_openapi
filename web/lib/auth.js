import crypto from "node:crypto";

export const COOKIE_NAME = "kis_admin";

export function validatePassword(password) {
  const adminPassword = process.env.ADMIN_PASSWORD;
  if (!adminPassword) {
    throw new Error("ADMIN_PASSWORD is not configured");
  }
  return timingSafeEqual(String(password || ""), adminPassword);
}

export function sessionToken() {
  const adminPassword = process.env.ADMIN_PASSWORD;
  if (!adminPassword) {
    throw new Error("ADMIN_PASSWORD is not configured");
  }
  return crypto.createHash("sha256").update(`kis-alert:${adminPassword}`).digest("hex");
}

export function isAuthorized(request) {
  const cookie = request.cookies.get(COOKIE_NAME)?.value || "";
  return Boolean(cookie && timingSafeEqual(cookie, sessionToken()));
}

function timingSafeEqual(left, right) {
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right);
  if (leftBuffer.length !== rightBuffer.length) {
    return false;
  }
  return crypto.timingSafeEqual(leftBuffer, rightBuffer);
}
