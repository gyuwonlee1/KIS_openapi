import { NextResponse } from "next/server";
import { isAuthorized } from "@/lib/auth";
import { fetchPortfolio, savePortfolio } from "@/lib/github";
import { validatePortfolio } from "@/lib/portfolio";

export async function GET(request) {
  if (!isAuthorized(request)) {
    return NextResponse.json({ error: "인증이 필요합니다." }, { status: 401 });
  }

  try {
    const payload = await fetchPortfolio();
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

export async function PUT(request) {
  if (!isAuthorized(request)) {
    return NextResponse.json({ error: "인증이 필요합니다." }, { status: 401 });
  }

  const body = await request.json().catch(() => ({}));
  const errors = validatePortfolio(body.portfolio);
  if (errors.length > 0) {
    return NextResponse.json({ errors }, { status: 400 });
  }

  try {
    const result = await savePortfolio(body.portfolio, body.sha, body.message);
    return NextResponse.json({ ok: true, ...result });
  } catch (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
