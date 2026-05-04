import "./globals.css";

export const metadata = {
  title: "KIS 알림 설정",
  description: "KIS 주식 알림 봇 관심 종목과 조건 설정",
};

export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
