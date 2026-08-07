'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useTheme } from 'next-themes';
import { AnimatePresence, motion } from 'motion/react';
import { useAgent, useSessionContext } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { AgentSessionView_01 } from '@/components/agents-ui/blocks/agent-session-view-01';
import { WelcomeView } from '@/components/app/welcome-view';
import { Button } from '@/components/ui/button';

const MotionWelcomeView = motion.create(WelcomeView);
const MotionSessionView = motion.create(AgentSessionView_01);

const VIEW_MOTION_PROPS = {
  variants: {
    visible: {
      opacity: 1,
    },
    hidden: {
      opacity: 0,
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.5,
    ease: 'linear',
  },
};

interface ViewControllerProps {
  appConfig: AppConfig;
}

/**
 * Connecting view — shown while the agent session is being established.
 * Day 3 Step 2: "Connecting — the agent is joining the call; tell the user to wait"
 */
function ConnectingView() {
  return (
    <motion.div
      key="connecting"
      {...VIEW_MOTION_PROPS}
      className="flex flex-col items-center justify-center gap-4"
    >
      {/* Pulsing health cross */}
      <div className="animate-connecting-pulse flex size-16 items-center justify-center rounded-full border border-primary/30 bg-primary/10">
        <svg
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
          className="text-primary"
        >
          <path
            d="M8 2v4H4a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h4v4a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-4h4a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-4V2a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2z"
            fill="currentColor"
            fillOpacity="0.7"
          />
        </svg>
      </div>
      <div className="text-center">
        <p className="text-foreground text-sm font-semibold">Connecting to Aarogya Mitra...</p>
        <p className="text-muted-foreground mt-1 text-xs">Setting up your health consultation</p>
      </div>
      {/* Animated dots */}
      <div className="flex gap-1.5">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="size-2 rounded-full bg-primary"
            animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1, 0.8] }}
            transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
          />
        ))}
      </div>
    </motion.div>
  );
}

/**
 * Call ended view — shown after the session disconnects.
 * Day 3 Step 2: "Call ended — the conversation is over; show an option to start again"
 */
function CallEndedView({ onRestart }: { onRestart: () => void }) {
  return (
    <motion.div
      key="call-ended"
      {...VIEW_MOTION_PROPS}
      className="flex flex-col items-center justify-center gap-4 px-6"
    >
      {/* Checkmark icon */}
      <div className="flex size-16 items-center justify-center rounded-full border border-primary/20 bg-primary/10">
        <svg
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
          className="text-primary"
        >
          <path
            d="M20 6L9 17L4 12"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      <div className="text-center">
        <p className="text-foreground text-base font-semibold">Consultation Ended</p>
        <p className="text-muted-foreground mt-1 max-w-xs text-sm leading-relaxed">
          Thank you for using Aarogya Mitra. Remember — for emergencies, always call{' '}
          <span className="text-destructive font-semibold">108</span>.
        </p>
      </div>
      <Button
        size="lg"
        onClick={onRestart}
        className="mt-2 w-64 rounded-full font-mono text-xs font-bold tracking-wider uppercase shadow-lg shadow-primary/20"
      >
        Start New Conversation
      </Button>
    </motion.div>
  );
}

export function ViewController({ appConfig }: ViewControllerProps) {
  const { isConnected, start } = useSessionContext();
  const { resolvedTheme } = useTheme();

  // Track session lifecycle
  const [hasStarted, setHasStarted] = useState(false);
  const [hasEnded, setHasEnded] = useState(false);
  const wasConnectedRef = useRef(false);

  // Detect disconnection after an active session (user clicked END CALL or agent disconnected)
  useEffect(() => {
    if (isConnected) {
      wasConnectedRef.current = true;
    } else if (wasConnectedRef.current) {
      // Was connected, now disconnected → session ended
      wasConnectedRef.current = false;
      setHasEnded(true);
    }
  }, [isConnected]);

  const handleStart = useCallback(() => {
    setHasStarted(true);
    setHasEnded(false);
    start();
  }, [start]);

  const handleRestart = useCallback(() => {
    setHasEnded(false);
    setHasStarted(true);
    start();
  }, [start]);

  // Determine the current view state
  // Day 3 Step 2: Show 5 agent states clearly
  const isConnecting = hasStarted && !isConnected && !hasEnded;
  const isSessionActive = isConnected;
  const showCallEnded = hasStarted && !isConnected && hasEnded;
  const showWelcome = !hasStarted;

  return (
    <AnimatePresence mode="wait">
      {/* 1. Ready — the agent has not started yet; show one clear button to begin */}
      {showWelcome && (
        <MotionWelcomeView
          key="welcome"
          {...VIEW_MOTION_PROPS}
          startButtonText={appConfig.startButtonText}
          onStartCall={handleStart}
        />
      )}

      {/* 2. Connecting — the agent is joining the call; tell the user to wait */}
      {isConnecting && <ConnectingView />}

      {/* 3 & 4. Listening / Speaking — handled by AgentStateIndicator inside session view */}
      {isSessionActive && (
        <MotionSessionView
          key="session-view"
          {...VIEW_MOTION_PROPS}
          supportsChatInput={appConfig.supportsChatInput}
          supportsVideoInput={appConfig.supportsVideoInput}
          supportsScreenShare={appConfig.supportsScreenShare}
          isPreConnectBufferEnabled={appConfig.isPreConnectBufferEnabled}
          audioVisualizerType={appConfig.audioVisualizerType}
          audioVisualizerColor={
            resolvedTheme === 'dark'
              ? appConfig.audioVisualizerColorDark
              : appConfig.audioVisualizerColor
          }
          audioVisualizerColorShift={appConfig.audioVisualizerColorShift}
          audioVisualizerBarCount={appConfig.audioVisualizerBarCount}
          audioVisualizerGridRowCount={appConfig.audioVisualizerGridRowCount}
          audioVisualizerGridColumnCount={appConfig.audioVisualizerGridColumnCount}
          audioVisualizerRadialBarCount={appConfig.audioVisualizerRadialBarCount}
          audioVisualizerRadialRadius={appConfig.audioVisualizerRadialRadius}
          audioVisualizerWaveLineWidth={appConfig.audioVisualizerWaveLineWidth}
          className="fixed inset-0"
        />
      )}

      {/* 5. Call ended — the conversation is over; show an option to start again */}
      {showCallEnded && <CallEndedView onRestart={handleRestart} />}
    </AnimatePresence>
  );
}
