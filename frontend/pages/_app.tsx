import type { AppProps } from "next/app";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <style>{`
        @keyframes blink-cursor { 0%, 50% { opacity: 1 } 50.01%, 100% { opacity: 0 } }
        @keyframes blink { 0%, 100% { opacity: 1 } 50% { opacity: 0.4 } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(6px) } to { opacity: 1; transform: translateY(0) } }
      `}</style>
      <Component {...pageProps} />
    </>
  );
}
