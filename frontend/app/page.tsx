"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);  // 세션 ID 상태 추가
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    // 빈 assistant 메시지를 추가하고 인덱스 저장
    const assistantMessageIndex = messages.length + 1;
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const requestBody: { user_query: string; session_id?: string } = {
        user_query: userMessage,
      };

      // 세션 ID가 있으면 함께 전송
      if (sessionId) {
        requestBody.session_id = sessionId;
      }

      const response = await fetch("http://34.134.58.155:8000/query/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error("서버 응답 오류");
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("스트림을 읽을 수 없습니다.");
      }

      let buffer = "";
      let currentContent = "";

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        // 디코딩된 청크를 버퍼에 추가
        buffer += decoder.decode(value, { stream: true });

        // 완전한 이벤트들을 처리
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // 마지막 불완전한 줄은 버퍼에 유지

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const jsonData = JSON.parse(line.slice(6));

              if (jsonData.type === "session_id") {
                // 세션 ID 저장
                if (jsonData.session_id && jsonData.session_id !== sessionId) {
                  setSessionId(jsonData.session_id);
                  console.log("Session ID:", jsonData.session_id);
                }
              } else if (jsonData.type === "node_update") {
                // 노드 업데이트 처리
                if (jsonData.data.final_answer) {
                  currentContent = jsonData.data.final_answer;
                  setMessages((prev) => {
                    const newMessages = [...prev];
                    newMessages[assistantMessageIndex] = {
                      role: "assistant",
                      content: currentContent,
                    };
                    return newMessages;
                  });
                } else if (jsonData.data.plan) {
                  currentContent = `**계획 수립 중...**\n\n${jsonData.data.plan}`;
                  setMessages((prev) => {
                    const newMessages = [...prev];
                    newMessages[assistantMessageIndex] = {
                      role: "assistant",
                      content: currentContent,
                    };
                    return newMessages;
                  });
                } else if (jsonData.data.answer) {
                  currentContent = jsonData.data.answer;
                  setMessages((prev) => {
                    const newMessages = [...prev];
                    newMessages[assistantMessageIndex] = {
                      role: "assistant",
                      content: currentContent,
                    };
                    return newMessages;
                  });
                }
              } else if (jsonData.type === "done") {
                console.log("스트리밍 완료");
              } else if (jsonData.type === "error") {
                throw new Error(jsonData.error);
              }
            } catch (parseError) {
              console.error("JSON 파싱 오류:", parseError);
            }
          }
        }
      }

      // 내용이 비어있으면 기본 메시지 설정
      if (!currentContent) {
        setMessages((prev) => {
          const newMessages = [...prev];
          newMessages[assistantMessageIndex] = {
            role: "assistant",
            content: "답변을 생성하지 못했습니다.",
          };
          return newMessages;
        });
      }
    } catch (err) {
      setError("응답을 받는데 실패했습니다. 다시 시도해주세요.");
      console.error("Error:", err);
      // 에러 발생 시 빈 메시지 제거
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-gradient-to-br from-indigo-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-800 dark:to-indigo-950">
      {/* Animated background elements */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 h-80 w-80 animate-pulse rounded-full bg-purple-300 opacity-20 blur-3xl dark:bg-purple-900"></div>
        <div className="absolute -bottom-40 -left-40 h-80 w-80 animate-pulse rounded-full bg-indigo-300 opacity-20 blur-3xl delay-1000 dark:bg-indigo-900"></div>
      </div>

      {/* Header with glassmorphism */}
      <header className="relative z-10 border-b border-white/20 bg-white/70 px-6 py-4 backdrop-blur-xl dark:border-gray-700/50 dark:bg-gray-900/70">
        <div className="mx-auto flex max-w-4xl items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg">
            <svg className="h-6 w-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent dark:from-indigo-400 dark:to-purple-400">
              맛집을 포(4)기할 수 없다
            </h1>
            <p className="text-xs text-gray-600 dark:text-gray-400">식당 데이터기반 맛집 정보를 찾는 AgenticRAG</p>
          </div>
        </div>
      </header>

      {/* Messages area */}
      <div className="relative z-10 flex-1 overflow-y-auto px-4 py-8 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-700">
        <div className="mx-auto max-w-4xl space-y-6">
          {messages.length === 0 && (
            <div className="flex min-h-[60vh] flex-col items-center justify-center space-y-8 text-center">
              <div className="relative">
                <div className="absolute inset-0 animate-ping rounded-full bg-indigo-400 opacity-20"></div>
                <div className="relative flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 shadow-2xl">
                  <svg className="h-12 w-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                </div>
              </div>
              <div className="space-y-3">
                <h2 className="text-3xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent dark:from-indigo-400 dark:to-purple-400">
                  어떤 맛집을 찾고 계신가요?
                </h2>
                <p className="text-gray-600 dark:text-gray-400">AI가 당신에게 완벽한 맛집을 추천해드립니다</p>
              </div>
              <div className="flex flex-wrap justify-center gap-3">
                {["인도 최고의 맛집", "강남 이탈리안 레스토랑", "혼밥하기 좋은 곳"].map((example, i) => (
                  <button
                    key={i}
                    onClick={() => setInput(example)}
                    className="group rounded-full border border-indigo-200 bg-white/60 px-5 py-2.5 text-sm font-medium text-indigo-700 backdrop-blur-sm transition-all hover:scale-105 hover:border-indigo-300 hover:bg-white hover:shadow-lg dark:border-indigo-800 dark:bg-gray-800/60 dark:text-indigo-300 dark:hover:bg-gray-800"
                  >
                    <span className="flex items-center gap-2">
                      <svg className="h-4 w-4 transition-transform group-hover:rotate-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                      </svg>
                      {example}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex animate-fade-in-up ${
                message.role === "user" ? "justify-end" : "justify-start"
              }`}
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              <div className={`flex max-w-[85%] items-start gap-3 ${message.role === "user" ? "flex-row-reverse" : ""}`}>
                {/* Avatar */}
                <div className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg shadow-md ${
                  message.role === "user"
                    ? "bg-gradient-to-br from-indigo-500 to-purple-600"
                    : "bg-gradient-to-br from-emerald-500 to-teal-600"
                }`}>
                  {message.role === "user" ? (
                    <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  ) : (
                    <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                  )}
                </div>

                {/* Message bubble */}
                <div
                  className={`group relative rounded-2xl px-5 py-3 shadow-lg transition-all hover:shadow-xl ${
                    message.role === "user"
                      ? "bg-gradient-to-br from-indigo-500 to-purple-600 text-white"
                      : "border border-gray-200 bg-white/80 text-gray-800 backdrop-blur-sm dark:border-gray-700 dark:bg-gray-800/80 dark:text-gray-100"
                  }`}
                >
                  {message.role === "user" ? (
                    <p className="whitespace-pre-wrap break-words leading-relaxed">{message.content}</p>
                  ) : (
                    <div className="prose prose-sm max-w-none dark:prose-invert prose-headings:font-bold prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg prose-p:leading-relaxed prose-a:text-indigo-600 dark:prose-a:text-indigo-400 prose-a:no-underline hover:prose-a:underline prose-strong:font-semibold prose-code:bg-gray-100 dark:prose-code:bg-gray-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-gray-100 dark:prose-pre:bg-gray-800 prose-pre:p-4 prose-pre:rounded-lg prose-ul:list-disc prose-ol:list-decimal prose-li:my-1">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {message.content}
                      </ReactMarkdown>
                    </div>
                  )}
                  {/* Decorative corner */}
                  <div className={`absolute ${message.role === "user" ? "-right-1 top-2" : "-left-1 top-2"} h-3 w-3 rotate-45 ${
                    message.role === "user"
                      ? "bg-purple-600"
                      : "border-l border-t border-gray-200 bg-white/80 dark:border-gray-700 dark:bg-gray-800/80"
                  }`}></div>
                </div>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex animate-fade-in justify-start">
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 shadow-md">
                  <svg className="h-5 w-5 animate-pulse text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
                <div className="rounded-2xl border border-gray-200 bg-white/80 px-6 py-4 shadow-lg backdrop-blur-sm dark:border-gray-700 dark:bg-gray-800/80">
                  <div className="flex items-center space-x-2">
                    <div className="h-2.5 w-2.5 animate-bounce rounded-full bg-gradient-to-r from-indigo-500 to-purple-500"></div>
                    <div className="h-2.5 w-2.5 animate-bounce rounded-full bg-gradient-to-r from-purple-500 to-pink-500" style={{ animationDelay: "0.2s" }}></div>
                    <div className="h-2.5 w-2.5 animate-bounce rounded-full bg-gradient-to-r from-pink-500 to-indigo-500" style={{ animationDelay: "0.4s" }}></div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="animate-shake rounded-2xl border border-red-200 bg-gradient-to-r from-red-50 to-pink-50 px-5 py-4 shadow-lg dark:border-red-800 dark:from-red-900/30 dark:to-pink-900/30">
              <div className="flex items-center gap-3">
                <svg className="h-5 w-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="font-medium text-red-800 dark:text-red-200">{error}</p>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input area with glassmorphism */}
      <div className="relative z-10 border-t border-white/20 bg-white/70 px-4 py-6 backdrop-blur-xl dark:border-gray-700/50 dark:bg-gray-900/70">
        <form onSubmit={sendMessage} className="mx-auto max-w-4xl">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="무엇이든 물어보세요..."
                disabled={isLoading}
                className="w-full rounded-2xl border border-gray-200 bg-white/90 px-6 py-4 pr-12 text-gray-800 shadow-lg backdrop-blur-sm transition-all placeholder:text-gray-400 focus:border-indigo-300 focus:outline-none focus:ring-4 focus:ring-indigo-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800/90 dark:text-gray-100 dark:placeholder:text-gray-500 dark:focus:border-indigo-700 dark:focus:ring-indigo-900/30"
              />
              <div className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
              </div>
            </div>
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="group relative overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-500 to-purple-600 px-8 py-4 font-semibold text-white shadow-lg transition-all hover:scale-105 hover:shadow-2xl disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-purple-600 to-indigo-500 opacity-0 transition-opacity group-hover:opacity-100"></div>
              <div className="relative flex items-center gap-2">
                {isLoading ? (
                  <svg className="h-5 w-5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                ) : (
                  <svg className="h-5 w-5 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                )}
                <span>전송</span>
              </div>
            </button>
          </div>
        </form>
      </div>

      <style jsx>{`
        @keyframes fade-in-up {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        @keyframes fade-in {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }
        @keyframes shake {
          0%, 100% {
            transform: translateX(0);
          }
          10%, 30%, 50%, 70%, 90% {
            transform: translateX(-5px);
          }
          20%, 40%, 60%, 80% {
            transform: translateX(5px);
          }
        }
        .animate-fade-in-up {
          animation: fade-in-up 0.5s ease-out forwards;
        }
        .animate-fade-in {
          animation: fade-in 0.3s ease-out;
        }
        .animate-shake {
          animation: shake 0.5s ease-in-out;
        }
      `}</style>
    </div>
  );
}
