import { useEffect, useState, useRef } from "react";
import { mutate } from "swr";

const API_URL = "https://hassan5858-pulseboard-backend.hf.space";
const WS_URL = API_URL.replace(/^http/, "ws") + "/ws";

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelayRef = useRef(1000); // Start reconnect delay at 1s
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    let active = true;

    function connect() {
      if (wsRef.current) {
        wsRef.current.close();
      }

      console.log(`Connecting to WebSocket: ${WS_URL}`);
      const socket = new WebSocket(WS_URL);
      wsRef.current = socket;

      socket.onopen = () => {
        if (!active) return;
        console.log("WebSocket connected.");
        setIsConnected(true);
        reconnectDelayRef.current = 1000; // Reset delay on successful connection

        // Setup ping interval every 30s to keep connection alive through proxies
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send("ping");
          }
        }, 30000);
      };

      socket.onmessage = (event) => {
        if (!active) return;
        if (event.data === "pong") return;

        try {
          const data = JSON.parse(event.data);
          console.log("WebSocket message received:", data);

          if (data.type === "trends_updated") {
            setIsSyncing(true);
            // Revalidate all SWR queries starting with API_URL
            mutate(
              (key) => typeof key === "string" && key.startsWith(API_URL),
              undefined,
              { revalidate: true }
            ).finally(() => {
              // Show syncing state briefly to let user know UI refreshed
              setTimeout(() => {
                if (active) setIsSyncing(false);
              }, 1200);
            });
          } else if (data.type === "user_count") {
            setUserCount(data.count);
          }
        } catch (err) {
          console.error("Failed to parse WebSocket message:", err);
        }
      };

      socket.onclose = (e) => {
        if (!active) return;
        console.log(`WebSocket closed: ${e.reason} (code: ${e.code}). Attempting reconnect...`);
        setIsConnected(false);
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }
        
        // Reconnect with exponential backoff, max 30s
        const delay = reconnectDelayRef.current;
        reconnectDelayRef.current = Math.min(delay * 2, 30000);
        setTimeout(() => {
          if (active) connect();
        }, delay);
      };

      socket.onerror = (err) => {
        console.error("WebSocket error:", err);
        socket.close();
      };
    }

    connect();

    return () => {
      active = false;
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
    };
  }, []);

  return { isConnected, isSyncing, userCount };
}
