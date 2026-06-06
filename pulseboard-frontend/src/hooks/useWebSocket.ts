import { useEffect, useState, useRef } from "react";
import { mutate } from "swr";

const API_URL = "https://hassan5858-pulseboard-backend.hf.space";
const WS_URL = API_URL.replace(/^https/, "wss") + "/ws";

// Close codes that mean we should NOT attempt to reconnect
const FATAL_CODES = new Set([1002, 1003, 1007, 1008, 1009, 1010, 1011, 4000, 4001, 4002, 4003, 4004]);

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [userCount, setUserCount] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelayRef = useRef(2000);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const failCountRef = useRef(0);
  // If WS fails 3 times in a row, back off to polling-only mode
  const MAX_FAILS = 3;

  useEffect(() => {
    let active = true;

    function cleanup() {
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = null;
      }
    }

    function connect() {
      if (!active) return;
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent triggering reconnect from old socket
        wsRef.current.close();
      }

      const socket = new WebSocket(WS_URL);
      wsRef.current = socket;

      const openTimeout = setTimeout(() => {
        // If socket hasn't opened within 8s, abort — HF Space proxy likely blocking
        if (socket.readyState !== WebSocket.OPEN) {
          socket.onclose = null;
          socket.close();
          handleFail("timeout");
        }
      }, 8000);

      socket.onopen = () => {
        clearTimeout(openTimeout);
        if (!active) return;
        setIsConnected(true);
        failCountRef.current = 0;
        reconnectDelayRef.current = 2000;

        // Ping every 25s to keep connection alive
        cleanup();
        pingIntervalRef.current = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send("ping");
          }
        }, 25000);
      };

      socket.onmessage = (event) => {
        if (!active) return;
        if (event.data === "pong") return;
        try {
          const data = JSON.parse(event.data);
          if (data.type === "trends_updated") {
            setIsSyncing(true);
            mutate(
              (key) => typeof key === "string" && key.startsWith(API_URL),
              undefined,
              { revalidate: true }
            ).finally(() => {
              setTimeout(() => { if (active) setIsSyncing(false); }, 1200);
            });
          } else if (data.type === "user_count") {
            setUserCount(data.count);
          }
        } catch {
          // ignore malformed messages
        }
      };

      socket.onclose = (e) => {
        clearTimeout(openTimeout);
        cleanup();
        if (!active) return;
        setIsConnected(false);

        // 403 comes through as close code 1006 (abnormal closure) from WS perspective
        // Stop retrying if we hit too many failures or fatal codes
        if (FATAL_CODES.has(e.code)) {
          console.warn(`WebSocket closed with fatal code ${e.code}. Falling back to polling.`);
          return;
        }

        handleFail(`code ${e.code}`);
      };

      socket.onerror = () => {
        clearTimeout(openTimeout);
        // onerror is always followed by onclose — let onclose handle reconnect
      };
    }

    function handleFail(reason: string) {
      failCountRef.current += 1;
      if (failCountRef.current >= MAX_FAILS) {
        console.warn(`WebSocket unavailable (${reason}). Running in polling-only mode.`);
        return; // Give up — SWR polling will keep data fresh
      }
      const delay = reconnectDelayRef.current;
      reconnectDelayRef.current = Math.min(delay * 2, 30000);
      setTimeout(() => { if (active) connect(); }, delay);
    }

    connect();

    return () => {
      active = false;
      cleanup();
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, []);

  return { isConnected, isSyncing, userCount };
}
