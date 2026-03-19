import { useState, useEffect, useRef, useCallback } from "react";
import { getStreamUrl } from "@/lib/api";
import type { ProgressUpdate } from "@/lib/types";

type SSEStatus = "idle" | "connecting" | "open" | "closed" | "error";

interface UseSSEReturn {
  messages: ProgressUpdate[];
  status: SSEStatus;
  progress: number;
  isFinished: boolean;
  close: () => void;
}

export function useSSE(jobId: string | null): UseSSEReturn {
  const [messages, setMessages] = useState<ProgressUpdate[]>([]);
  const [status, setStatus] = useState<SSEStatus>("idle");
  const [progress, setProgress] = useState(0);
  const [isFinished, setIsFinished] = useState(false);

  // useRef to hold the EventSource instance across renders.
  // We need this to close the connection in cleanup and in the
  // close() function without triggering re-renders.
  const eventSourceRef = useRef<EventSource | null>(null);

  const close = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      setStatus("closed");
    }
  }, []);

  useEffect(() => {
    if (!jobId) {
      return;
    }

    // Open the SSE connection
    const url = getStreamUrl(jobId);
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => {
      // Reset state when connection opens
      setMessages([]);
      setProgress(0);
      setIsFinished(false);
      setStatus("open");
    };

    es.onmessage = (event: MessageEvent) => {
      // EventSource automatically parses the "data: " prefix.
      // event.data contains the JSON string after "data: ".
      try {
        const update: ProgressUpdate = JSON.parse(event.data);

        setMessages((prev) => [...prev, update]);
        setProgress(Number(update.progress) || 0);

        // Check if this is the terminal event
        if (update.step === "complete" || update.step === "error") {
          setIsFinished(true);
          setStatus("closed");
          es.close();
          eventSourceRef.current = null;
        }
      } catch (err) {
        console.error("Failed to parse SSE message:", event.data, err);
      }
    };

    es.onerror = () => {
      // EventSource fires onerror for both network errors AND
      // when the server closes the connection. Check readyState
      // to distinguish:
      if (es.readyState === EventSource.CLOSED) {
        setStatus("closed");
        eventSourceRef.current = null;
      } else {
        setStatus("error");
      }
    };

    // Cleanup function: runs when the component unmounts or jobId changes.
    // This prevents leaked connections when the user navigates away
    // or submits a new filing while a stream is still open.
    return () => {
      es.close();
      eventSourceRef.current = null;
      setStatus("idle");
    };
  }, [jobId]);

  return { messages, status, progress, isFinished, close };
}
