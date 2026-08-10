import { ReactNode, useEffect } from 'react';
import { toast as sonnerToast } from 'sonner';
import { useAgent, useSessionContext } from '@livekit/components-react';
import { WarningIcon } from '@phosphor-icons/react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface ToastProps {
  title: ReactNode;
  description: ReactNode;
}

function toastAlert(toast: ToastProps) {
  const { title, description } = toast;

  return sonnerToast.custom(
    (id) => (
      <Alert onClick={() => sonnerToast.dismiss(id)} className="bg-accent w-full md:w-[364px]">
        <WarningIcon weight="bold" />
        <AlertTitle>{title}</AlertTitle>
        {description && <AlertDescription>{description}</AlertDescription>}
      </Alert>
    ),
    { duration: 10_000 }
  );
}

/**
 * Shows a user-friendly toast when microphone permission is denied.
 * This is critical for a voice-based health assistant.
 */
function showMicrophonePermissionError() {
  toastAlert({
    title: 'Microphone Access Required',
    description: (
      <>
        <p className="w-full">
          Aarogya Mitra needs microphone access for your voice health consultation.
        </p>
        <p className="mt-2 w-full text-xs">
          <strong>How to enable:</strong> Click the lock/camera icon in your browser&apos;s address
          bar → Allow Microphone → Reload this page.
        </p>
      </>
    ),
  });
}

export function useAgentErrors() {
  const agent = useAgent();
  const { isConnected, end } = useSessionContext();

  // Listen for microphone permission errors
  useEffect(() => {
    const handleDeviceError = (event: Event) => {
      const detail = (event as CustomEvent)?.detail;
      if (
        detail?.error?.name === 'NotAllowedError' ||
        detail?.error?.name === 'PermissionDeniedError'
      ) {
        showMicrophonePermissionError();
      }
    };

    // Also check for permission on connect
    if (isConnected) {
      navigator.mediaDevices?.getUserMedia({ audio: true }).catch((err) => {
        if (err.name === 'NotAllowedError' || err.name === 'NotFoundError') {
          showMicrophonePermissionError();
        }
      });
    }

    window.addEventListener('deviceerror', handleDeviceError);
    return () => window.removeEventListener('deviceerror', handleDeviceError);
  }, [isConnected]);

  useEffect(() => {
    if (isConnected && agent.state === 'failed') {
      const reasons = agent.failureReasons;

      toastAlert({
        title: 'Session ended',
        description: (
          <>
            {reasons.length > 1 && (
              <ul className="list-inside list-disc">
                {reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            )}
            {reasons.length === 1 && <p className="w-full">{reasons[0]}</p>}
            <p className="w-full">
              Please try again or{' '}
              <a
                target="_blank"
                rel="noopener noreferrer"
                href="https://docs.livekit.io/agents/start/voice-ai/"
                className="whitespace-nowrap underline"
              >
                see the quickstart guide
              </a>
              .
            </p>
          </>
        ),
      });

      end();
    }
  }, [agent, isConnected, end]);
}
