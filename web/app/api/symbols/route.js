import { NextResponse } from "next/server";
import { isAuthorized } from "@/lib/auth";
import { searchSymbols } from "@/lib/symbols";

export async function GET(request) {
  if (!isAuthorized(request)) {
    return NextResponse.json({ error: "인증이 필요합니다." }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const q = searchParams.get("q") || "";
  const market = searchParams.get("market") || "";
  const symbols = searchSymbols(q, market);

  return NextResponse.json({ symbols });
}
