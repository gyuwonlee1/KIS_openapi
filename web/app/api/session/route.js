import { NextResponse } from "next/server";
import { COOKIE_NAME, validatePassword, sessionToken } from "@/lib/auth";

export async function GET(request) {
  const authorized = request.cookies.get(COOKIE_NAME)?.value === sessionToken();
  return NextResponse.json({ authorized });
}

export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  if (!validatePassword(body.password)) {
    return NextResponse.json({ error: "비밀번호가 올바르지 않습니다." }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set({
    name: COOKIE_NAME,
    value: sessionToken(),
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  return response;
}

export async function DELETE() {
  const response = NextResponse.json({ ok: true });
  response.cookies.set({
    name: COOKIE_NAME,
    value: "",
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 0,
  });
  return response;
}
