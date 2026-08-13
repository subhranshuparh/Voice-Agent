import { Button } from '@/components/ui/button';

function HealthIcon() {
  return (
    <div className="relative mb-6">
      {/* Outer glow ring */}
      <div className="animate-pulse-glow bg-primary/5 absolute inset-0 rounded-full" />
      {/* Icon container */}
      <div className="border-primary/20 bg-primary/10 relative flex size-20 items-center justify-center rounded-full border">
        {/* Stethoscope + heart icon */}
        <svg
          width="40"
          height="40"
          viewBox="0 0 48 48"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="text-primary"
        >
          {/* Stethoscope body */}
          <path
            d="M14 8C14 6.89543 14.8954 6 16 6H18C19.1046 6 20 6.89543 20 8V18C20 22.4183 16.4183 26 12 26H11C8.23858 26 6 28.2386 6 31V33"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
          <path
            d="M28 8C28 6.89543 28.8954 6 30 6H32C33.1046 6 34 6.89543 34 8V18C34 22.4183 30.4183 26 26 26H25C22.2386 26 20 28.2386 20 31V33"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
          {/* Heart at bottom */}
          <path
            d="M13 34C10.5 31.5 6 33 6 37C6 41 13 44 13 44C13 44 20 41 20 37C20 33 15.5 31.5 13 34Z"
            fill="currentColor"
            fillOpacity="0.2"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinejoin="round"
          />
          {/* Pulse line */}
          <path
            d="M28 34H32L34 30L37 38L40 32H44"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    </div>
  );
}

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  ref,
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  return (
    <div ref={ref}>
      <section className="bg-background flex flex-col items-center justify-center px-6 text-center">
        <HealthIcon />

        {/* Title */}
        <h1 className="text-foreground text-2xl font-bold tracking-tight md:text-3xl">
          Aarogya Mitra
        </h1>
        <p className="text-primary mt-1 text-sm font-medium md:text-base">
          Voice Health Access Assistant
        </p>

        {/* Description */}
        <p className="text-muted-foreground mt-4 max-w-md text-sm leading-relaxed md:text-base">
          Navigate healthcare services, understand public health schemes like Ayushman Bharat, and
          prepare for your doctor visits — all through voice.
        </p>

        {/* Language support badge */}
        <div className="border-primary/20 bg-primary/5 mt-4 flex items-center gap-2 rounded-full border px-4 py-1.5">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="text-primary">
            <path
              d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z"
              stroke="currentColor"
              strokeWidth="1.5"
            />
            <path d="M2 12H22" stroke="currentColor" strokeWidth="1.5" />
            <path
              d="M12 2C14.5 4.5 16 8 16 12C16 16 14.5 19.5 12 22C9.5 19.5 8 16 8 12C8 8 9.5 4.5 12 2Z"
              stroke="currentColor"
              strokeWidth="1.5"
            />
          </svg>
          <span className="text-primary text-xs font-medium">Speaks English, Hindi & Hinglish</span>
        </div>

        {/* CTA Buttons */}
        <div className="mt-8 flex flex-col flex-wrap items-center justify-center gap-3 sm:flex-row">
          <Button
            size="lg"
            onClick={onStartCall}
            className="shadow-primary/20 hover:shadow-primary/30 w-72 rounded-full font-mono text-xs font-bold tracking-wider uppercase shadow-lg transition-shadow"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="mr-2">
              <path
                d="M12 1C12 1 12 1 12 1C5.92487 1 1 5.92487 1 12C1 18.0751 5.92487 23 12 23C18.0751 23 23 18.0751 23 12"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
              <path
                d="M12 8V16M12 8L9 11M12 8L15 11"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            {startButtonText}
          </Button>

          <a
            href="/escalations"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex h-10 items-center justify-center rounded-full border border-neutral-700 bg-neutral-900/80 px-5 font-mono text-xs font-semibold tracking-wider text-neutral-300 uppercase transition hover:bg-neutral-800 hover:text-white"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="mr-2 text-teal-400"
            >
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="M12 8v4" />
              <path d="M12 16h.01" />
            </svg>
            Escalations
          </a>

          <a
            href="/dashboard"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex h-10 items-center justify-center rounded-full border border-teal-500/40 bg-teal-950/40 px-5 font-mono text-xs font-semibold tracking-wider text-teal-300 uppercase shadow-md shadow-teal-950/50 transition hover:bg-teal-900/60 hover:text-white"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="mr-2 text-teal-300"
            >
              <line x1="18" y1="20" x2="18" y2="10" />
              <line x1="12" y1="20" x2="12" y2="4" />
              <line x1="6" y1="20" x2="6" y2="14" />
            </svg>
            Call Analytics
          </a>
        </div>

        {/* Microphone hint */}
        <p className="text-muted-foreground mt-4 flex items-center gap-1.5 text-xs">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="opacity-60">
            <path
              d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v4M8 23h8"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Microphone access required for voice consultation
        </p>
      </section>

      {/* Health disclaimer */}
      <div className="fixed bottom-5 left-0 flex w-full items-center justify-center px-4">
        <p className="text-muted-foreground max-w-prose text-center text-[10px] leading-4 font-normal text-pretty md:text-xs">
          Aarogya Mitra is an AI assistant, not a medical professional. For emergencies, call{' '}
          <span className="text-destructive font-semibold">108</span>. This service does not
          diagnose or prescribe medication.
        </p>
      </div>
    </div>
  );
};
