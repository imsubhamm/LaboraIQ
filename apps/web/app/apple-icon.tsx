import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(145deg, #effbf7 0%, #bceadd 100%)",
          borderRadius: 40,
          color: "#102d2a",
          fontSize: 72,
          fontWeight: 700,
          letterSpacing: -2,
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
        }}
      >
        LQ
      </div>
    ),
    { ...size }
  );
}
